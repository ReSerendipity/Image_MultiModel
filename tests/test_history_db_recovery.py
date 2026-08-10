"""
test_history_db_recovery.py — 崩溃恢复两阶段（cleanup → recover）

对应 AUDIT_REPORT_2.0 Y2: test_history_db_recovery.py
"""

import pytest

from integrated_app.history_db import HistoryDB


@pytest.fixture
def db(tmp_path):
    d = HistoryDB(tmp_path / "test_recovery.db")
    yield d
    d.close()


class TestHistoryDBRecovery:
    """崩溃恢复两阶段"""

    def test_recover_stuck_processing_task(self, db):
        """Phase 1: 清理卡死的 processing 任务"""
        db.create_task(task_id="stuck-001", engine="test", prompt="test")
        db.update_task_status("stuck-001", "processing")

        # 修改 created_at 为 2 小时前
        db.conn.execute(
            "UPDATE tasks SET created_at=datetime('now', '-2 hours') WHERE task_id=?",
            ("stuck-001",),
        )
        db.conn.commit()

        recovered = db.recover_stuck_tasks(max_processing_hours=1.0)
        assert recovered == 1

        task = db.get_task("stuck-001")
        assert task["status"] == "interrupted"
        assert task["interrupted_at_reboot"] == 1

    def test_recover_multiple_stuck_tasks(self, db):
        """Phase 1: 批量清理多个卡死任务"""
        for i in range(5):
            db.create_task(task_id=f"stuck-{i:03d}", engine="test")
            db.update_task_status(f"stuck-{i:03d}", "processing")

        # 全部设为 2 小时前
        db.conn.execute(
            "UPDATE tasks SET created_at=datetime('now', '-2 hours') "
            "WHERE status='processing'"
        )
        db.conn.commit()

        recovered = db.recover_stuck_tasks(max_processing_hours=1.0)
        assert recovered == 5

    def test_no_recovery_for_recent_tasks(self, db):
        """Phase 2: 近期 processing 任务不被清理"""
        db.create_task(task_id="recent-001", engine="test")
        db.update_task_status("recent-001", "processing")

        recovered = db.recover_stuck_tasks(max_processing_hours=1.0)
        assert recovered == 0

        task = db.get_task("recent-001")
        assert task["status"] == "processing"

    def test_no_recovery_for_completed_tasks(self, db):
        """已完成的任务不受影响"""
        db.create_task(task_id="done-001", engine="test")
        db.update_task_status("done-001", "completed")

        # 设为很久以前
        db.conn.execute(
            "UPDATE tasks SET created_at=datetime('now', '-100 hours') "
            "WHERE task_id='done-001'"
        )
        db.conn.commit()

        recovered = db.recover_stuck_tasks()
        assert recovered == 0

    def test_wal_mode_enabled(self, db):
        """WAL 模式已启用（崩溃恢复基础）"""
        mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_fts5_search_after_recovery(self, db):
        """崩溃恢复后 FTS5 全文检索仍可用"""
        db.create_task(task_id="fts-test", engine="test", prompt="hello world keyword")
        db.update_task_status("fts-test", "processing")

        # 模拟崩溃
        db.conn.execute(
            "UPDATE tasks SET created_at=datetime('now', '-2 hours') WHERE task_id='fts-test'"
        )
        db.conn.commit()
        db.recover_stuck_tasks(max_processing_hours=1.0)

        # FTS 搜索仍可用
        tasks, total = db.list_tasks(q="keyword")
        assert total == 1
        assert tasks[0]["task_id"] == "fts-test"
