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

import pytest

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


def _real_layout_root() -> Path:
    """构造真实布局：<root>/data/history.db + <root>/outputs/ + <root>/data/cache/thumbs/。"""
    root = _tmp()
    (root / "data" / "cache" / "thumbs").mkdir(parents=True, exist_ok=True)
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    return root


def test_delete_tasks_with_files_removes_outputs_and_thumbs() -> None:
    """数据治理报告 P0-2 / P1-1：DELETE 路由同步删主图 + 缩略图，消灭磁盘孤儿。"""
    root = _real_layout_root()
    db = HistoryDB(root / "data" / "history.db")
    db.create_task(task_id="del1", engine="z_image_turbo_native")
    out_file = root / "outputs" / "del1_out.png"
    out_file.write_bytes(b"PNGDATA")
    db.add_output(task_id="del1", path="del1_out.png", format="png", file_size=7)
    thumb = root / "data" / "cache" / "thumbs" / "del1_0000_0_thumb.png"
    thumb.write_bytes(b"THUMB")
    deleted = db.delete_tasks_with_files(["del1"])
    assert deleted == 1
    assert not out_file.exists(), "主输出图应被删除"
    assert not thumb.exists(), "缩略图应被删除"
    assert db.conn.execute("SELECT COUNT(*) FROM tasks WHERE task_id=?", ["del1"]).fetchone()[0] == 0
    db.close()


def test_delete_tasks_with_files_idempotent_on_missing_files() -> None:
    """文件已缺失时仍应成功删除 DB 记录（容错，不抛异常）。"""
    root = _real_layout_root()
    db = HistoryDB(root / "data" / "history.db")
    db.create_task(task_id="del2", engine="z_image_turbo_native")
    # 不写任何磁盘文件
    deleted = db.delete_tasks_with_files(["del2"])
    assert deleted == 1
    assert db.conn.execute("SELECT COUNT(*) FROM tasks WHERE task_id=?", ["del2"]).fetchone()[0] == 0
    db.close()


# ── 数据治理报告 P2-4：PRAGMA user_version 版本化迁移 ──────────────
import sqlite3

from integrated_app.history_db import HistoryDB as _HDB


def _make_old_db(path: Path) -> None:
    """构造 v0 旧库：血缘列/outputs.sha256 均不存在的真实旧 schema。"""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE tasks (
            task_id          TEXT PRIMARY KEY,
            engine           TEXT NOT NULL,
            mode             TEXT NOT NULL DEFAULT 'txt2img',
            status           TEXT NOT NULL DEFAULT 'pending',
            prompt           TEXT DEFAULT '',
            negative_prompt  TEXT DEFAULT '',
            generation_config TEXT DEFAULT '{}',
            thumbnail        TEXT DEFAULT '',
            output_count     INTEGER DEFAULT 0,
            processing_time_s REAL DEFAULT 0,
            error            TEXT DEFAULT '',
            favorite         INTEGER DEFAULT 0,
            tags             TEXT DEFAULT '[]',
            created_at       TEXT DEFAULT (datetime('now')),
            updated_at       TEXT DEFAULT (datetime('now')),
            interrupted_at_reboot INTEGER DEFAULT 0
        );
        CREATE TABLE outputs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id    TEXT NOT NULL,
            path       TEXT NOT NULL,
            format     TEXT DEFAULT 'png',
            file_size  INTEGER DEFAULT 0,
            width      INTEGER DEFAULT 0,
            height     INTEGER DEFAULT 0,
            seed       TEXT DEFAULT '',
            output_type TEXT DEFAULT 'original',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        );
        CREATE TABLE presets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            engine_name TEXT NOT NULL,
            name        TEXT NOT NULL,
            thumbnail   TEXT DEFAULT '',
            config      TEXT DEFAULT '{}',
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(engine_name, name)
        );
        """
    )
    conn.execute("INSERT INTO tasks (task_id, engine, prompt) VALUES ('old1', 'e1', 'legacy row')")
    conn.commit()
    conn.close()


def test_old_db_migrated_and_versioned() -> None:
    """旧库（user_version=0）打开后：血缘列 + outputs.sha256 补齐、版本推进、旧数据保留。"""
    d = _tmp()
    db_path = d / "history.db"
    _make_old_db(db_path)
    v0 = sqlite3.connect(str(db_path)).execute("PRAGMA user_version").fetchone()[0]
    assert v0 == 0, "前置：构造的旧库版本号应为 0"

    db = HistoryDB(db_path)
    task_cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(tasks)")}
    out_cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(outputs)")}
    assert {"workflow_version", "lora_checksums", "error_code"} <= task_cols
    assert "sha256" in out_cols
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == _HDB.SCHEMA_VERSION
    # 旧数据保留且新列取默认值
    row = db.get_task("old1")
    assert row["prompt"] == "legacy row"
    assert row["workflow_version"] == ""
    db.close()


def test_fresh_db_reaches_schema_version() -> None:
    d = _tmp()
    db = HistoryDB(d / "history.db")
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == _HDB.SCHEMA_VERSION
    # 幂等：二次打开不再推进也不报错
    db.close()
    db2 = HistoryDB(d / "history.db")
    assert db2.conn.execute("PRAGMA user_version").fetchone()[0] == _HDB.SCHEMA_VERSION
    db2.close()


def test_migration_fail_closed(monkeypatch) -> None:
    """迁移单步失败必须终止启动（fail-closed），而非 warning 后继续跑。"""
    d = _tmp()
    db_path = d / "history.db"
    _make_old_db(db_path)

    def _boom(self):  # noqa: ANN001
        return (
            (2, self._migrate_v2_lineage_columns),
            (3, self._migrate_v3_outputs_sha256),
            (4, _raise_step),
        )

    def _raise_step(_conn: sqlite3.Connection) -> None:
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(_HDB, "_migrations", _boom)
    with pytest.raises(RuntimeError, match="simulated migration failure"):
        HistoryDB(db_path)
    # 版本号不得推进到失败步骤之后
    conn = sqlite3.connect(str(db_path))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 3


def test_add_output_sha256_persisted() -> None:
    """Q1-①：outputs.sha256 写入点落地。"""
    d = _tmp()
    db = HistoryDB(d / "history.db")
    db.create_task(task_id="t_sha", engine="z_image_turbo_native")
    db.add_output(task_id="t_sha", path="a.png", sha256="ab" * 32)
    row = db.conn.execute("SELECT sha256 FROM outputs WHERE task_id=?", ["t_sha"]).fetchone()
    assert row["sha256"] == "ab" * 32
    db.close()
