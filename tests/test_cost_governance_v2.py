"""
tests/test_cost_governance_v2.py — 成本资源治理评估报告（2026-09-04）整改验收测试

对应报告缺陷清单：
- P1-② 失败任务入账：HistoryDB 支持失败状态存储 processing_time_s
- P1-③ max_gb 口径：cleanup_old_tasks 度量 outputs 目录体积（非磁盘卷）
- P2-⑤ MetricsStore 名实一致（内存环形缓冲）+ 按自然日 VRAM 峰值
- P2-⑥ 启动时把遗留 pending 僵尸任务标记为 interrupted（支持 checkpoint 排除）
- P2-⑦ 权重扫描 roots 全缺失时显式告警 + roots_existing 字段
- §5-⑤ 容量日快照：capacity_snapshots 表 + build_capacity_snapshot
- 缩略图联动删除（thumbs 前缀关联 task_id[:16]）
"""

from __future__ import annotations

import logging
import time

import pytest

from integrated_app.cost_governance import (
    MetricsStore,
    build_capacity_snapshot,
    scan_orphan_weights,
)
from integrated_app.history_db import HistoryDB


@pytest.fixture
def db(tmp_path):
    # db 落在 tmp_path/data/ 下，与生产布局一致（thumbs 相对 db_path 推导）
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    d = HistoryDB(data_dir / "history.db")
    yield d
    d.close()


# ──────────────────────────────────────────────────────────────
#  P1-② 失败任务入账
# ──────────────────────────────────────────────────────────────
def test_failed_task_records_processing_time(db):
    """失败状态同样可存储非零 processing_time_s（FinOps 失败入账的数据通路）"""
    db.create_task(task_id="fail-001", engine="test")
    db.update_task_status("fail-001", "failed", error="boom", error_code="inference_error",
                          processing_time_s=12.5)
    task = db.get_task("fail-001")
    assert task["status"] == "failed"
    assert task["processing_time_s"] == pytest.approx(12.5)


# ──────────────────────────────────────────────────────────────
#  P1-③ max_gb 口径：度量 outputs 目录而非磁盘卷
# ──────────────────────────────────────────────────────────────
def test_cleanup_max_gb_uses_outputs_dir_size(db, tmp_path, monkeypatch):
    """超限时按超额比例删除最旧非收藏任务；收藏任务保留"""
    import integrated_app.history_db as hd_mod

    (tmp_path / "outputs").mkdir(exist_ok=True)  # 目录不存在时 max_gb 分支跳过
    for i in range(10):
        tid = f"vol-task-{i:02d}-aaaaaaaaaaaa"
        db.create_task(task_id=tid, engine="test")
        db.update_task_status(tid, "completed", processing_time_s=1.0)
    db.set_favorite("vol-task-09-aaaaaaaaaaaa", True)
    for i in range(10):
        db.conn.execute(
            "UPDATE tasks SET created_at=datetime('now', ?) WHERE task_id=?",
            (f'-{100 - i} days', f"vol-task-{i:02d}-aaaaaaaaaaaa"),
        )
    db.conn.commit()

    # 模拟 outputs 目录体积超限（卷级 disk_usage 与此无关）
    monkeypatch.setattr(hd_mod, "_dir_size_bytes", lambda p: 20 * (1024**3))  # 20GB
    deleted = db.cleanup_old_tasks(keep_days=0, max_gb=10.0)
    # over_ratio = (20-10)/20 = 0.5；非收藏任务共 9 个 → 删最旧 4 个（int(9*0.5)=4）
    assert deleted == 4
    assert db.get_task("vol-task-09-aaaaaaaaaaaa")["status"] == "completed"  # 收藏保留
    assert db.get_task("vol-task-00-aaaaaaaaaaaa") is None  # 最旧被删
    assert db.get_task("vol-task-03-aaaaaaaaaaaa") is None
    assert db.get_task("vol-task-04-aaaaaaaaaaaa")["status"] == "completed"  # 边界保留


def test_cleanup_no_delete_when_dir_within_budget(db, tmp_path, monkeypatch):
    import integrated_app.history_db as hd_mod

    (tmp_path / "outputs").mkdir(exist_ok=True)
    db.create_task(task_id="small-001", engine="test")
    db.update_task_status("small-001", "completed", processing_time_s=1.0)
    monkeypatch.setattr(hd_mod, "_dir_size_bytes", lambda p: 1 * (1024**3))  # 1GB
    assert db.cleanup_old_tasks(keep_days=0, max_gb=10.0) == 0
    assert db.get_task("small-001") is not None


def test_dir_size_bytes_measures_directory(tmp_path):
    """_dir_size_bytes 只统计目录内文件（与磁盘卷无关）"""
    from integrated_app.history_db import _dir_size_bytes

    target = tmp_path / "dir"
    (target / "sub").mkdir(parents=True)
    (target / "a.bin").write_bytes(b"x" * 1000)
    (target / "sub" / "b.bin").write_bytes(b"x" * 500)
    assert _dir_size_bytes(target) == 1500
    assert _dir_size_bytes(tmp_path / "missing") == 0


# ──────────────────────────────────────────────────────────────
#  P2-⑤ MetricsStore：内存缓冲 + 日峰值
# ──────────────────────────────────────────────────────────────
def test_metrics_store_daily_peak():
    store = MetricsStore(history_points=5)
    today = time.strftime("%Y-%m-%d", time.localtime())
    store.record_gpu({"total_vram_gb": 16, "used_vram_gb": 6.0, "free_vram_gb": 10.0})
    store.record_gpu({"total_vram_gb": 16, "used_vram_gb": 11.5, "free_vram_gb": 4.5})
    store.record_gpu({"total_vram_gb": 16, "used_vram_gb": 8.0, "free_vram_gb": 8.0})
    assert store.peak_used_gb_for_date(today) == pytest.approx(11.5)
    assert store.peak_used_gb_for_date("1999-01-01") == 0.0


# ──────────────────────────────────────────────────────────────
#  P2-⑥ 启动 pending 僵尸回写
# ──────────────────────────────────────────────────────────────
def test_mark_stale_pending_interrupted(db):
    for i in range(3):
        db.create_task(task_id=f"zombie-{i}", engine="test")
    marked = db.mark_stale_pending_interrupted()
    assert marked == 3
    for i in range(3):
        task = db.get_task(f"zombie-{i}")
        assert task["status"] == "interrupted"
        assert task["interrupted_at_reboot"] == 1


def test_mark_stale_pending_excludes_checkpoint_resume(db):
    """待续跑的 checkpoint 任务保持 pending，其余僵尸被标记"""
    db.create_task(task_id="resume-me-aaaaaaaaaa", engine="test")
    db.create_task(task_id="zombie-000000000001", engine="test")
    marked = db.mark_stale_pending_interrupted(exclude_task_ids=["resume-me-aaaaaaaaaa"])
    assert marked == 1
    assert db.get_task("resume-me-aaaaaaaaaa")["status"] == "pending"
    assert db.get_task("zombie-000000000001")["status"] == "interrupted"


def test_mark_stale_pending_keeps_terminal_states(db):
    """completed/failed/cancelled 不被误标记"""
    db.create_task(task_id="done-001", engine="test")
    db.update_task_status("done-001", "completed", processing_time_s=1.0)
    assert db.mark_stale_pending_interrupted() == 0
    assert db.get_task("done-001")["status"] == "completed"


# ──────────────────────────────────────────────────────────────
#  P2-⑦ 权重扫描 roots 缺失告警
# ──────────────────────────────────────────────────────────────
def test_scan_orphan_weights_warns_when_roots_missing(tmp_path, caplog):
    """pretrained_models 不存在时：结果不可信须告警，且返回 roots 统计字段"""
    from integrated_app.config_models import AppConfig

    cfg = AppConfig()
    cfg.models.model_source_mode = "portable"
    cfg.models.portable.internal_models_dir = "nonexistent_models_dir"

    with caplog.at_level(logging.WARNING, logger="integrated_app.cost_governance"):
        result = scan_orphan_weights(cfg, tmp_path)
    assert result["roots_total"] > 0
    assert result["roots_existing"] == 0
    assert any("roots 均不存在" in r.message for r in caplog.records)


def test_scan_orphan_weights_no_warning_when_roots_exist(tmp_path, caplog):
    from integrated_app.config_models import AppConfig

    cfg = AppConfig()
    cfg.models.model_source_mode = "portable"
    cfg.models.portable.internal_models_dir = "weights"
    base = tmp_path / "weights" / "unet"
    base.mkdir(parents=True)

    with caplog.at_level(logging.WARNING, logger="integrated_app.cost_governance"):
        result = scan_orphan_weights(cfg, tmp_path)
    assert result["roots_existing"] > 0
    assert not any("roots 均不存在" in r.message for r in caplog.records)


# ──────────────────────────────────────────────────────────────
#  §5-⑤ 容量日快照
# ──────────────────────────────────────────────────────────────
def test_capacity_snapshot_roundtrip(db):
    import datetime as _dt

    d = _dt.date.fromtimestamp(time.time() - 86400).isoformat()
    db.record_capacity_snapshot(d, peak_used_gb=11.5, disk_used_gb=900.1, gpu_hours_24h=1.2345)
    # 同日重写 → 幂等覆盖（UNIQUE(snapshot_date)）
    db.record_capacity_snapshot(d, peak_used_gb=12.0, disk_used_gb=901.0, gpu_hours_24h=2.0)
    rows = db.list_capacity_snapshots(limit=7)
    assert len(rows) == 1
    assert rows[0]["snapshot_date"] == d
    assert rows[0]["peak_used_gb"] == pytest.approx(12.0)
    assert rows[0]["gpu_hours_24h"] == pytest.approx(2.0)


def test_build_capacity_snapshot_fields(db, tmp_path):
    import datetime as _dt

    store = MetricsStore()
    today = time.strftime("%Y-%m-%d", time.localtime())
    store.record_gpu({"total_vram_gb": 16, "used_vram_gb": 9.0, "free_vram_gb": 7.0})

    # 近 24h 的任务耗时进入 gpu_hours_24h
    db.create_task(task_id="snap-task-00000001", engine="test")
    db.update_task_status("snap-task-00000001", "completed", processing_time_s=3600.0)

    snap = build_capacity_snapshot(db, store, tmp_path)
    yesterday = _dt.date.fromtimestamp(time.time() - 86400).isoformat()
    assert snap["snapshot_date"] == yesterday  # 归属日 = 昨天
    assert snap["peak_used_gb"] == 0.0  # 峰值按归属日取（今天采样不计入昨天）
    assert snap["disk_used_gb"] > 0
    assert snap["gpu_hours_24h"] == pytest.approx(1.0, abs=0.01)
    assert today  # today 采样只影响今天的峰值表


def test_build_capacity_snapshot_picks_up_yesterday_peak():
    """日峰值按归属日（昨天）取：跨日快照能回答「昨天峰值多少」"""

    class _FakeStore:
        def __init__(self) -> None:
            self._peaks = {"2026-09-03": 13.7}

        def peak_used_gb_for_date(self, date_str: str) -> float:
            return self._peaks.get(date_str, 0.0)

    class _FakeDB:
        def sum_processing_since(self, cutoff: float) -> float:
            return 7200.0

    snap = build_capacity_snapshot(_FakeDB(), _FakeStore(), ".", now=time.mktime(
        time.strptime("2026-09-04", "%Y-%m-%d")))
    assert snap["snapshot_date"] == "2026-09-03"
    assert snap["peak_used_gb"] == pytest.approx(13.7)
    assert snap["gpu_hours_24h"] == pytest.approx(2.0)


# ──────────────────────────────────────────────────────────────
#  缩略图联动删除
# ──────────────────────────────────────────────────────────────
def test_delete_tasks_with_files_removes_linked_thumbnails(db, tmp_path):
    """删除任务时按 task_id[:16] 前缀联动清理 data/cache/thumbs"""
    tid = "abcdef0123456789aaaaaaaaaaaaaaaa"
    db.create_task(task_id=tid, engine="test")
    db.update_task_status(tid, "completed", processing_time_s=1.0)
    thumbs_dir = tmp_path / "data" / "cache" / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    linked = thumbs_dir / f"{tid[:16]}_0_thumb.png"
    other = thumbs_dir / "ffff000011112222_0_thumb.png"
    linked.write_bytes(b"png")
    other.write_bytes(b"png")

    deleted = db.delete_tasks_with_files([tid])
    assert deleted == 1
    assert not linked.exists()
    assert other.exists()  # 无关任务缩略图不受影响
