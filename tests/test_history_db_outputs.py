"""
tests/test_history_db_outputs.py — HistoryDB outputs 表 CRUD 测试

对应 TEST_AUDIT_REPORT P1-5: outputs 表测试缺失
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

from integrated_app.history_db import HistoryDB


@pytest.fixture
def db(tmp_path):
    """临时数据库"""
    d = HistoryDB(tmp_path / "test_outputs.db")
    yield d
    d.close()


class TestOutputsCRUD:
    """outputs 表 CRUD"""

    def test_add_output(self, db):
        """添加输出记录"""
        db.create_task(task_id="task-001", engine="test", prompt="test prompt")
        db.add_output(
            task_id="task-001",
            path="outputs/test.png",
            format="png",
            file_size=1024,
            width=1024,
            height=1024,
            seed="12345",
            output_type="original",
        )

        task = db.get_task("task-001")
        assert len(task["outputs"]) == 1
        assert task["outputs"][0]["path"] == "outputs/test.png"
        assert task["outputs"][0]["width"] == 1024

    def test_add_multiple_outputs(self, db):
        """一个任务多个输出（original + upscaled + compare）"""
        db.create_task(task_id="task-002", engine="test")
        for otype in ("original", "upscaled", "compare"):
            db.add_output(
                task_id="task-002",
                path=f"outputs/task-002_{otype}.png",
                output_type=otype,
            )

        task = db.get_task("task-002")
        assert len(task["outputs"]) == 3
        types = [o["output_type"] for o in task["outputs"]]
        assert "original" in types
        assert "upscaled" in types
        assert "compare" in types

    def test_list_outputs(self, db):
        """分页查询输出列表"""
        db.create_task(task_id="task-list", engine="test")
        for i in range(5):
            db.add_output(task_id="task-list", path=f"outputs/img_{i}.png")

        outputs, total = db.list_outputs(page=1, page_size=10)
        assert total == 5
        assert len(outputs) == 5

    def test_list_outputs_pagination(self, db):
        """输出分页"""
        db.create_task(task_id="task-page", engine="test")
        for i in range(10):
            db.add_output(task_id="task-page", path=f"outputs/page_{i}.png")

        page1, total = db.list_outputs(page=1, page_size=3)
        assert total == 10
        assert len(page1) == 3

        page2, _ = db.list_outputs(page=2, page_size=3)
        assert len(page2) == 3

    def test_list_outputs_filter_by_type(self, db):
        """按 output_type 筛选"""
        db.create_task(task_id="task-filter", engine="test")
        db.add_output(task_id="task-filter", path="outputs/orig.png", output_type="original")
        db.add_output(task_id="task-filter", path="outputs/up.png", output_type="upscaled")

        outputs, total = db.list_outputs(output_type="upscaled")
        assert total == 1
        assert outputs[0]["output_type"] == "upscaled"

    def test_set_output_favorite(self, db):
        """标记输出收藏"""
        db.create_task(task_id="task-fav", engine="test", prompt="fav test")
        db.add_output(task_id="task-fav", path="outputs/fav.png")

        db.set_output_favorite("outputs/fav.png", True)

        # 验证 task favorite 被设置
        task = db.get_task("task-fav")
        assert task["favorite"] == 1

    def test_outputs_cascade_delete(self, db):
        """删除任务时 outputs 级联删除"""
        db.create_task(task_id="task-cascade", engine="test")
        db.add_output(task_id="task-cascade", path="outputs/cascade.png")

        # 确认输出存在
        task = db.get_task("task-cascade")
        assert len(task["outputs"]) == 1

        # 删除任务
        db.delete_tasks(["task-cascade"])

        # outputs 表中的记录应被级联删除
        outputs, total = db.list_outputs()
        assert total == 0

    def test_list_outputs_empty(self, db):
        """空数据库查询"""
        outputs, total = db.list_outputs()
        assert total == 0
        assert outputs == []
