"""
test_data_governance.py — 数据治理评估报告落地验证（P1 血缘 + 生命周期/DR）

覆盖：
- history_db 血缘增强列迁移（workflow_version / lora_checksums / error_code）
- create_task / update_task_status 落地血缘字段
- HistoryDB.backup() VACUUM INTO 备份可恢复
- lineage.compute_workflow_version / compute_lora_checksums / classify_error

注：本机 Windows 下 pytest tmp_path fixture 的 sessionfinish 清理会触发
PermissionError 崩溃，故改用 tempfile 自建临时目录，避免依赖 tmp_path。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from integrated_app.history_db import HistoryDB
from integrated_app.lineage import (
    classify_error,
    compute_lora_checksums,
    compute_workflow_version,
)


class _FakeEngineCfg:
    def __init__(self, workflow_file: str) -> None:
        self.workflow_file = workflow_file


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="dg_test_"))


def test_lineage_columns_migrated() -> None:
    d = _tmp()
    db = HistoryDB(d / "history.db")
    cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(tasks)")}
    assert {"workflow_version", "lora_checksums", "error_code"} <= cols
    db.close()


def test_create_task_stores_lineage() -> None:
    d = _tmp()
    db = HistoryDB(d / "history.db")
    db.create_task(
        task_id="t1",
        engine="z_image_turbo_native",
        prompt="a cat",
        generation_config={"seed": 1},
        workflow_version="abc123",
        lora_checksums=[{"name": "lora_a", "strength": 0.7, "sha256": "deadbeef"}],
    )
    row = db.get_task("t1")
    assert row["workflow_version"] == "abc123"
    assert row["lora_checksums"] == [{"name": "lora_a", "strength": 0.7, "sha256": "deadbeef"}]
    db.close()


def test_update_task_status_error_code() -> None:
    d = _tmp()
    db = HistoryDB(d / "history.db")
    db.create_task(task_id="t2", engine="z_image_turbo_native")
    db.update_task_status("t2", "failed", error="CUDA out of memory", error_code="OOM_VRAM")
    row = db.get_task("t2")
    assert row["status"] == "failed"
    assert row["error_code"] == "OOM_VRAM"
    db.close()


def test_backup_creates_restorable_file() -> None:
    d = _tmp()
    db = HistoryDB(d / "history.db")
    db.create_task(task_id="t3", engine="z_image_turbo_native", prompt="hello")
    backup_path = db.backup()
    assert backup_path.exists()
    db2 = HistoryDB(backup_path)
    assert db2.get_task("t3")["prompt"] == "hello"
    db2.close()
    db.close()


def test_compute_workflow_version() -> None:
    d = _tmp()
    wf = d / "Z_image_turbo.json"
    wf.write_text('{"nodes": []}', encoding="utf-8")
    digest = compute_workflow_version(_FakeEngineCfg("Z_image_turbo.json"), d)
    assert len(digest) == 64  # sha256 hex
    assert compute_workflow_version(_FakeEngineCfg("Z_image_turbo.json"), d) == digest


def test_compute_workflow_version_missing_file_fallback() -> None:
    d = _tmp()
    assert compute_workflow_version(_FakeEngineCfg("nope.json"), d) == "nope.json"


def test_compute_lora_checksums_empty_stack() -> None:
    class _Cfg:
        models = None
        project_root = ""

    assert compute_lora_checksums([], _Cfg()) == []


def test_compute_lora_checksums_unknown_name() -> None:
    class _Models:
        portable = type("P", (), {"internal_models_dir": "model", "sub_dirs": {"lora": "loras"}})()

    class _Cfg:
        models = _Models()
        project_root = "/nonexistent-root"

    stack = [{"name": "ghost_lora", "strength": 0.5}]
    res = compute_lora_checksums(stack, _Cfg())
    assert res == [{"name": "ghost_lora", "strength": 0.5, "sha256": None}]


def test_classify_error() -> None:
    assert classify_error(RuntimeError("CUDA out of memory")) == "OOM_VRAM"
    assert classify_error(TimeoutError("task timeout")) == "TASK_TIMEOUT"
    assert classify_error(ValueError("lora apply failed")) == "LORA_APPLY"
    assert classify_error(Exception("something odd")) == "UNKNOWN"
