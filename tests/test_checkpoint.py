"""
tests/test_checkpoint.py — 断点续跑 save/load/续跑不重复 seed 校验

对应 REMAINING_TASKS_REPORT A2: checkpoint save() 接入
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from integrated_app.checkpoint import TaskCheckpoint


class TestTaskCheckpoint:
    """断点续跑管理器测试"""

    def setup_method(self):
        """每个测试方法使用临时目录"""
        self.tmpdir = tempfile.mkdtemp()
        self.cp = TaskCheckpoint(checkpoint_dir=self.tmpdir)

    def test_save_and_load(self):
        """save → load 数据一致"""
        self.cp.save(
            task_id="test_task_001",
            engine="z_image_turbo_native",
            total=32,
            completed_items=[{"prompt": "cat", "seed": 42}],
            remaining=[{"prompt": "dog", "seed": 99}],
            config={"positive_prompt": "test", "batch_size": 32},
        )
        data = self.cp.load("test_task_001")
        assert data is not None
        assert data["task_id"] == "test_task_001"
        assert data["engine"] == "z_image_turbo_native"
        assert data["total"] == 32
        assert data["completed"] == 1
        assert len(data["completed_items"]) == 1
        assert len(data["remaining"]) == 1

    def test_load_nonexistent(self):
        """load 不存在的 task 返回 None"""
        assert self.cp.load("nonexistent_task") is None

    def test_delete(self):
        """delete 后 load 返回 None"""
        self.cp.save(
            task_id="test_task_002",
            engine="test_engine",
            total=10,
            completed_items=[],
            remaining=[],
            config={},
        )
        assert self.cp.delete("test_task_002") is True
        assert self.cp.load("test_task_002") is None
        # 二次删除返回 False
        assert self.cp.delete("test_task_002") is False

    def test_list_checkpoints(self):
        """list_checkpoints 只返回未完成的"""
        # 未完成
        self.cp.save(
            task_id="task_incomplete",
            engine="eng",
            total=100,
            completed_items=[{"seed": 1}],
            remaining=[{"seed": 2}],
            config={},
        )
        # 已完成（completed >= total）
        self.cp.save(
            task_id="task_complete",
            engine="eng",
            total=5,
            completed_items=[{"seed": 1}, {"seed": 2}, {"seed": 3}, {"seed": 4}, {"seed": 5}],
            remaining=[],
            config={},
        )
        pending = self.cp.list_checkpoints()
        assert len(pending) == 1
        assert pending[0]["task_id"] == "task_incomplete"

    def test_should_checkpoint(self):
        """should_checkpoint 每 N 张触发"""
        assert self.cp.should_checkpoint(0) is False
        assert self.cp.should_checkpoint(50) is False
        assert self.cp.should_checkpoint(100) is True
        assert self.cp.should_checkpoint(200) is True
        assert self.cp.should_checkpoint(99) is False

    def test_should_checkpoint_custom_interval(self):
        """自定义间隔"""
        assert self.cp.should_checkpoint(50, checkpoint_every=50) is True
        assert self.cp.should_checkpoint(49, checkpoint_every=50) is False

    def test_resume_no_duplicate_seeds(self):
        """续跑场景：save → load → 剩余 seed 不包含已完成 seed"""
        total = 200
        all_seeds = list(range(200, 200 + total))
        completed_count = 100
        completed_items = [{"seed": s} for s in all_seeds[:completed_count]]
        remaining_items = [{"seed": s} for s in all_seeds[completed_count:]]

        self.cp.save(
            task_id="batch_task_001",
            engine="z_image_turbo_native",
            total=total,
            completed_items=completed_items,
            remaining=remaining_items,
            config={"batch_size": total, "seed": 200},
        )

        # 模拟重启：load → 提取剩余 seed
        data = self.cp.load("batch_task_001")
        assert data is not None
        completed_seeds = {item["seed"] for item in data["completed_items"]}
        remaining_seeds = {item["seed"] for item in data["remaining"]}

        # 已完成 seed 和剩余 seed 无交集
        assert completed_seeds.isdisjoint(remaining_seeds)
        # 剩余 seed 数量正确
        assert len(remaining_seeds) == total - completed_count
        # 全量 seed = 已完成 + 剩余
        assert completed_seeds | remaining_seeds == set(all_seeds)

    def test_checkpoint_file_format(self):
        """checkpoint 文件格式正确"""
        self.cp.save(
            task_id="format_test",
            engine="eng",
            total=10,
            completed_items=[{"seed": 1}],
            remaining=[{"seed": 2}],
            config={"key": "value"},
        )
        path = Path(self.tmpdir) / "format_test.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "task_id" in data
        assert "engine" in data
        assert "total" in data
        assert "completed" in data
        assert "completed_items" in data
        assert "remaining" in data
        assert "config" in data
        assert "updated_at" in data

    def test_on_chunk_done_callback_integration(self):
        """模拟 engine chunk 循环 → on_chunk_done → checkpoint save"""
        checkpoint_every = 5
        total = 20
        chunk = 5
        completed_items: list[dict] = []
        saved_count = 0

        def on_chunk_done(completed: int, total_n: int):
            nonlocal saved_count
            completed_items.append({"completed": completed})
            if self.cp.should_checkpoint(completed, checkpoint_every):
                self.cp.save(
                    task_id="chunk_test",
                    engine="eng",
                    total=total_n,
                    completed_items=list(completed_items),
                    remaining=[{"index": i} for i in range(completed, total_n)],
                    config={"batch_size": total_n},
                )
                saved_count += 1

        # 模拟 chunk 循环
        submitted = 0
        while submitted < total:
            cur = min(chunk, total - submitted)
            submitted += cur
            on_chunk_done(submitted, total)

        # 每 5 张保存一次 → 4 次（5, 10, 15, 20）
        assert saved_count == 4
        # 最终 checkpoint 应有全部 20 项
        data = self.cp.load("chunk_test")
        assert data is not None
        assert data["completed"] == 4  # 4 个 checkpoint 记录
        assert data["total"] == 20
