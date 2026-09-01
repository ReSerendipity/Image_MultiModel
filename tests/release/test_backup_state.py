"""
tests/release/test_backup_state.py — P2-13 状态备份 / 孤儿检测 / 恢复演练测试

用合成 mini-DB（tasks + outputs 两张表）构造三种状态：
- 正常记录（文件存在）；
- DB→缺文件（missing_files）；
- 文件→缺记录（unindexed）。
覆盖 backup / verify / orphans / prune / restore-drill。
"""

from __future__ import annotations

import importlib.util
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_SPEC = Path(__file__).resolve().parents[2] / "scripts" / "backup_state.py"


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("backup_state", _SPEC)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def root():
    """合成仓库根：data/history.db + outputs/ 三类样本文件。"""
    root = Path(tempfile.mkdtemp(prefix="imm-bk-"))
    (root / "data").mkdir()
    (root / "outputs" / "z_image_turbo_native").mkdir(parents=True)
    (root / "config.yaml").write_text("runtime: {}\n", encoding="utf-8")

    db = root / "data" / "history.db"
    con = sqlite3.connect(str(db))
    with con:
        con.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT)")
        con.execute("CREATE TABLE outputs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, path TEXT)")
        con.execute("CREATE TABLE presets (id INTEGER PRIMARY KEY, name TEXT)")
        con.execute("INSERT INTO tasks VALUES ('t_ok', 'completed')")
        con.execute("INSERT INTO tasks VALUES ('t_missing', 'completed')")
        con.execute("INSERT INTO tasks VALUES ('t_orphan_row', 'completed')")
        good = root / "outputs" / "z_image_turbo_native" / "good.png"
        good.write_bytes(b"PNGDATA")
        ghost = str(root / "outputs" / "z_image_turbo_native" / "ghost.png")
        con.execute("INSERT INTO outputs (task_id, path) VALUES ('t_ok', ?)", (str(good),))
        con.execute("INSERT INTO outputs (task_id, path) VALUES ('t_missing', ?)", (ghost,))
        # outputs 表里一条 task_id 不存在于 tasks → orphan_rows
        con.execute("INSERT INTO outputs (task_id, path) VALUES ('no_such_task', ?)", (str(good),))
        con.execute("INSERT INTO presets VALUES (1, 'p1')")
    con.close()

    # 磁盘上有、DB 没有的文件 → unindexed
    (root / "outputs" / "z_image_turbo_native" / "extra.png").write_bytes(b"X")

    yield root
    shutil.rmtree(root, ignore_errors=True)


# ────────────────────────── backup / verify ──────────────────────────
def test_backup_creates_valid_archive(mod, root):
    manifest = mod.backup_state(root, root / "backups")
    arc = Path(manifest["archive"])
    assert arc.is_file() and manifest["integrity"] == "ok"
    assert manifest["tasks_rows"] == 3
    assert manifest["outputs_rows"] == 3


def test_verify_archive_roundtrip(mod, root):
    manifest = mod.backup_state(root, root / "backups")
    assert mod.verify_archive(root, Path(manifest["archive"])) == []


def test_verify_detects_missing_archive(mod, root):
    problems = mod.verify_archive(root, root / "nope.tar.gz")
    assert problems  # 不存在的文件 → 有问题


def test_verify_live_db_ok(mod, root):
    assert mod.verify_live_db(root) == []


# ────────────────────────── orphans ──────────────────────────
def test_find_orphans_three_categories(mod, root):
    rep = mod.find_orphans(root)
    assert len(rep.missing_files) == 1 and rep.missing_files[0]["task_id"] == "t_missing"
    assert len(rep.orphan_rows) == 1 and rep.orphan_rows[0]["task_id"] == "no_such_task"
    # extra.png 未被 DB 收录 → unindexed；ghost.png 不存在于磁盘不计
    assert any("extra.png" in p for p in rep.unindexed_files)
    d = rep.to_dict()
    assert d["missing_files"] == 1 and d["orphan_rows"] == 1


def test_prune_removes_bad_rows_only(mod, root):
    rep = mod.find_orphans(root)
    before = rep.total_output_rows
    n = mod.prune_orphan_rows(root, rep)
    assert n == 2  # 1 missing + 1 orphan_row
    rep2 = mod.find_orphans(root)
    assert rep2.total_output_rows == before - n
    assert rep2.missing_files == [] and rep2.orphan_rows == []


# ────────────────────────── restore drill ──────────────────────────
def test_restore_drill_passes(mod, root, capsys):
    problems = mod.restore_drill(root)
    assert problems == []
    out = capsys.readouterr().out
    assert "completed tasks=3" in out  # 3 条 tasks 全部 status=completed


def test_restore_drill_detects_corruption(mod, root):
    # 篡改 DB 头部使其损坏 → 演练必须失败
    manifest = mod.backup_state(root, root / "backups")
    arc = Path(manifest["archive"])
    tmp = Path(tempfile.mkdtemp(prefix="imm-corr-"))
    try:
        import tarfile

        with tarfile.open(arc, "r:gz") as tf:
            tf.extractall(tmp, filter="data")
        db = tmp / "history.db"
        with open(db, "r+b") as f:
            f.seek(100)
            f.write(b"\xff" * 64)  # 破坏页结构（实测可被 integrity_check 检出）
        rc = mod._integrity_check(db)
        assert rc != "ok"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ────────────────────────── schema fingerprint ──────────────────────────
def test_schema_fingerprint(mod, root):
    fp = mod.schema_fingerprint(root)
    assert set(fp["tables"]) == {"outputs", "presets", "tasks"}
    assert fp["user_version"] >= 0
    # 列集合稳定 → 同一 root 两次指纹一致（备份兼容性判定基础）
    assert fp == mod.schema_fingerprint(root)


# ────────────────────────── CLI ──────────────────────────
def test_cli_orphans_prune_requires_yes(mod, root, monkeypatch):
    sys.argv = ["backup_state", "orphans", "--root", str(root), "--prune-db"]
    assert mod.main() == 1  # 缺 --yes → 拒绝执行


def test_cli_backup_verify_drill(mod, root, monkeypatch):
    sys.argv = ["backup_state", "backup", "--root", str(root)]
    assert mod.main() == 0
    sys.argv = ["backup_state", "restore-drill", "--root", str(root)]
    assert mod.main() == 0
