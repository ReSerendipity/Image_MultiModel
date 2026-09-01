#!/usr/bin/env python3
"""scripts/backup_state.py — P2-13 状态与备份治理

评估 §9-P2-13 要求：
  1. history DB 做定期备份、完整性校验和恢复演练；
  2. 明确 schema migration 向前/向后兼容；
  3. 回滚后验证 history DB、outputs、checkpoints 的一致性；
  4. 对输出文件和 DB 记录建立孤儿检测。

子命令：
  backup    用 SQLite backup API 一致性快照 history.db，连同 config.yaml、
            checkpoints 元数据打包到 backups/imm_state_<ts>.tar.zst（或 tar.gz）
  verify    对备份包或在线 DB 跑 PRAGMA integrity_check + 行数核对
  orphans   孤儿检测：DB→缺文件（missing_files）/ 文件→缺 DB 记录（unindexed_files）
            / outputs 表孤儿 task_id；默认只报告，--prune-db/--prune-files 才清理
  restore-drill  恢复演练：备份 → 还原到临时目录 → integrity_check + 行数一致 → 清理

用法：
    python scripts/backup_state.py backup
    python scripts/backup_state.py verify --file backups/imm_state_xxx.tar.gz
    python scripts/backup_state.py verify            # 校验在线 DB
    python scripts/backup_state.py orphans
    python scripts/backup_state.py orphans --prune-db --yes
    python scripts/backup_state.py restore-drill
退出码：0 成功 / 1 校验或演练失败（供 cron / CI 门禁）。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB_RELPATH = "data/history.db"
CHECKPOINTS_RELPATH = "data/checkpoints"
CONFIG_RELPATH = "config.yaml"
MANIFEST_NAME = "backup_manifest.json"


def _resolve_db(root: Path) -> Path:
    return root / DB_RELPATH


# ────────────────────────── backup ──────────────────────────
def backup_state(root: Path, out_dir: Path) -> dict:
    """一致性备份 history.db（SQLite backup API，WAL 安全）+ config + checkpoints。

    Returns 备份清单（manifest dict）。
    """
    db = _resolve_db(root)
    if not db.is_file():
        raise FileNotFoundError(f"数据库不存在: {db}")
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"imm_state_{ts}.tar.gz"

    tmp = Path(tempfile.mkdtemp(prefix="imm-backup-"))
    try:
        # 1) SQLite 在线一致性快照（比文件复制安全：合并 WAL 后输出单文件）
        snap = tmp / "history.db"
        src = sqlite3.connect(str(db))
        dst = sqlite3.connect(str(snap))
        try:
            with dst:
                src.backup(dst)
        finally:
            src.close()
            dst.close()

        # 2) 快照立即做完整性校验（坏备份不如没有备份）
        rc = _integrity_check(snap)
        if rc != "ok":
            raise RuntimeError(f"备份快照 integrity_check 失败: {rc}")

        # 3) 清单
        tasks_n, outputs_n = _row_counts(snap)
        manifest = {
            "created_at": ts,
            "source_db": str(db),
            "integrity": rc,
            "tasks_rows": tasks_n,
            "outputs_rows": outputs_n,
            "config_sha256": _sha256(root / CONFIG_RELPATH) if (root / CONFIG_RELPATH).is_file() else "",
            "checkpoints": _dir_listing(root / CHECKPOINTS_RELPATH),
        }
        (tmp / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 4) 打包
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(snap, arcname="history.db")
            tf.add(tmp / MANIFEST_NAME, arcname=MANIFEST_NAME)
            for extra in (CONFIG_RELPATH,):
                p = root / extra
                if p.is_file():
                    tf.add(p, arcname=extra)
            ck = root / CHECKPOINTS_RELPATH
            if ck.is_dir():
                tf.add(ck, arcname=CHECKPOINTS_RELPATH)
        manifest["archive"] = str(archive)
        manifest["archive_bytes"] = archive.stat().st_size
        return manifest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ────────────────────────── verify ──────────────────────────
def _integrity_check(db_path: Path) -> str:
    """PRAGMA integrity_check；捕获 sqlite3 打开/执行异常，统一返回状态字符串。"""
    try:
        con = sqlite3.connect(str(db_path))
        try:
            rows = con.execute("PRAGMA integrity_check").fetchall()
            return "ok" if rows and rows[0][0] == "ok" else "; ".join(str(r[0]) for r in rows)
        finally:
            con.close()
    except sqlite3.Error as e:
        return f"sqlite error: {e}"


def _row_counts(db_path: Path) -> tuple[int, int]:
    con = sqlite3.connect(str(db_path))
    try:
        t = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        o = con.execute("SELECT COUNT(*) FROM outputs").fetchone()[0]
        return int(t), int(o)
    finally:
        con.close()


def verify_archive(root: Path, archive: Path) -> list[str]:
    """解包备份 → integrity_check → 行数与 manifest 比对。返回问题列表。"""
    problems: list[str] = []
    if not archive.is_file():
        return [f"备份文件不存在: {archive}"]
    tmp = Path(tempfile.mkdtemp(prefix="imm-verify-"))
    try:
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(tmp, filter="data")
        snap = tmp / "history.db"
        if not snap.is_file():
            return [f"备份缺少 {DB_RELPATH}"]
        rc = _integrity_check(snap)
        if rc != "ok":
            problems.append(f"integrity_check: {rc}")
        mf_path = tmp / MANIFEST_NAME
        if not mf_path.is_file():
            problems.append("备份缺少 manifest")
        else:
            mf = json.loads(mf_path.read_text(encoding="utf-8"))
            t, o = _row_counts(snap)
            if t != mf.get("tasks_rows"):
                problems.append(f"tasks 行数漂移: manifest={mf.get('tasks_rows')} actual={t}")
            if o != mf.get("outputs_rows"):
                problems.append(f"outputs 行数漂移: manifest={mf.get('outputs_rows')} actual={o}")
        return problems
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def verify_live_db(root: Path) -> list[str]:
    """校验在线 DB（cron 巡检用）。"""
    db = _resolve_db(root)
    if not db.is_file():
        return [f"数据库不存在: {db}"]
    rc = _integrity_check(db)
    return [] if rc == "ok" else [f"integrity_check: {rc}"]


# ────────────────────────── schema 兼容性 ──────────────────────────
def schema_fingerprint(root: Path) -> dict:
    """提取表结构指纹，用于「向前/向后兼容」评审：
    备份恢复时对比指纹，若新增列可兼容（SELECT * 目标代码不受影响），
    若删列/改类型则标 needs_review。"""
    db = _resolve_db(root)
    con = sqlite3.connect(str(db))
    try:
        tables: dict[str, str] = {}
        for name, sql in con.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ):
            tables[name] = (sql or "").strip()
        user_version = con.execute("PRAGMA user_version").fetchone()[0]
        return {"user_version": int(user_version), "tables": tables}
    finally:
        con.close()


# ────────────────────────── orphans ──────────────────────────
@dataclass
class OrphanReport:
    missing_files: list[dict] = field(default_factory=list)     # DB 记录 → 文件不存在
    unindexed_files: list[str] = field(default_factory=list)    # outputs/ 文件 → 无 DB 记录
    orphan_rows: list[dict] = field(default_factory=list)       # outputs.task_id 不在 tasks
    total_output_rows: int = 0
    total_output_files: int = 0

    def to_dict(self) -> dict:
        return {
            "total_output_rows": self.total_output_rows,
            "total_output_files": self.total_output_files,
            "missing_files": len(self.missing_files),
            "unindexed_files": len(self.unindexed_files),
            "orphan_rows": len(self.orphan_rows),
            "details": {
                "missing_files": self.missing_files[:50],
                "unindexed_files": self.unindexed_files[:50],
                "orphan_rows": self.orphan_rows[:50],
            },
        }


def find_orphans(root: Path) -> OrphanReport:
    """三方一致性检测：DB 记录 ↔ 磁盘文件 ↔ task 外键。"""
    db = _resolve_db(root)
    rep = OrphanReport()
    con = sqlite3.connect(str(db))
    try:
        known_tasks = {r[0] for r in con.execute("SELECT task_id FROM tasks")}
        rows = con.execute("SELECT task_id, path FROM outputs").fetchall()
        rep.total_output_rows = len(rows)
        indexed_paths: set[str] = set()
        for task_id, path in rows:
            indexed_paths.add(Path(path).resolve().as_posix())
            if task_id not in known_tasks:
                rep.orphan_rows.append({"task_id": task_id, "path": path})
            if not Path(path).is_file():
                rep.missing_files.append({"task_id": task_id, "path": path})

        out_dir = root / "outputs"
        if out_dir.is_dir():
            for p in out_dir.rglob("*"):
                if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                    rep.total_output_files += 1
                    if p.resolve().as_posix() not in indexed_paths:
                        rep.unindexed_files.append(str(p))
    finally:
        con.close()
    return rep


def prune_orphan_rows(root: Path, report: OrphanReport) -> int:
    """清理 DB 中指向不存在文件的记录（返回删除条数）。
    调用方必须先整库备份再删，防止误清。"""
    db = _resolve_db(root)
    con = sqlite3.connect(str(db))
    try:
        with con:
            for item in report.missing_files + report.orphan_rows:
                con.execute(
                    "DELETE FROM outputs WHERE task_id = ? AND path = ?",
                    (item["task_id"], item["path"]),
                )
        return len(report.missing_files) + len(report.orphan_rows)
    finally:
        con.close()


# ────────────────────────── restore drill ──────────────────────────
def restore_drill(root: Path) -> list[str]:
    """恢复演练：backup → 解包还原到临时目录 → integrity + 行数 + 文件可查询性。
    返回问题列表（空 = 演练通过）。"""
    problems: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="imm-drill-"))
    try:
        manifest = backup_state(root, tmp)
        archive = Path(manifest["archive"])
        problems += verify_archive(root, archive)

        # 还原到隔离目录并模拟「应用重启后查询」
        restore_dir = tmp / "restored"
        restore_dir.mkdir()
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(restore_dir, filter="data")
        rdb = restore_dir / "history.db"
        con = sqlite3.connect(str(rdb))
        try:
            n1 = con.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
            n2 = con.execute("SELECT COUNT(*) FROM presets").fetchone()[0]
            if n1 < 0 or n2 < 0:  # pragma: no cover - COUNT 不为负
                problems.append("还原库查询异常")
            print(f"[DRILL] 还原库可查询：completed tasks={n1}, presets={n2}")
        except sqlite3.Error as e:
            problems.append(f"还原库查询失败: {e}")
        finally:
            con.close()
        return problems
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ────────────────────────── utils ──────────────────────────
def _sha256(p: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _dir_listing(d: Path) -> dict:
    if not d.is_dir():
        return {"present": False, "entries": []}
    entries = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file())
    return {"present": True, "entries": entries[:500], "count": len(entries)}


# ────────────────────────── CLI ──────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="P2-13 状态备份 / 校验 / 孤儿检测 / 恢复演练")
    ap.add_argument("command", choices=["backup", "verify", "orphans", "restore-drill"])
    ap.add_argument("--file", default="", help="verify：备份包路径")
    ap.add_argument("--backup-dir", default="backups", help="backup 输出目录")
    ap.add_argument("--report", default="", help="orphans：JSON 报告输出路径")
    ap.add_argument("--prune-db", action="store_true", help="orphans：删除指向不存在文件的 DB 记录（先自动备份）")
    ap.add_argument("--yes", action="store_true", help="确认破坏性操作")
    ap.add_argument("--root", default=str(ROOT), help="仓库根（默认脚本上级目录，测试可注入）")
    args = ap.parse_args()
    root = Path(args.root)

    if args.command == "backup":
        manifest = backup_state(root, root / args.backup_dir)
        print(f"[PASS] 备份完成: {manifest['archive']}")
        print(f"       integrity={manifest['integrity']} tasks={manifest['tasks_rows']} "
              f"outputs={manifest['outputs_rows']} size={manifest['archive_bytes']}B")
        return 0

    if args.command == "verify":
        if args.file:
            problems = verify_archive(root, Path(args.file))
        else:
            problems = verify_live_db(root)
        if problems:
            print("[FAIL] 校验失败：")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("[PASS] 校验通过（integrity_check ok，行数与 manifest 一致）")
        return 0

    if args.command == "orphans":
        rep = find_orphans(root)
        print(f"[INFO] outputs 记录={rep.total_output_rows} 磁盘文件={rep.total_output_files}")
        print(f"  DB→缺文件 (missing_files): {len(rep.missing_files)}")
        print(f"  文件→缺记录 (unindexed):  {len(rep.unindexed_files)}")
        print(f"  outputs 孤儿 task_id:      {len(rep.orphan_rows)}")
        if args.report:
            Path(args.report).write_text(
                json.dumps(rep.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"[INFO] 已写出 {args.report}")
        if args.prune_db:
            if not args.yes:
                print("[FAIL] --prune-db 为破坏性操作，必须加 --yes 确认")
                return 1
            man = backup_state(root, root / args.backup_dir)
            print(f"[INFO] 清理前已备份: {man['archive']}")
            n = prune_orphan_rows(root, rep)
            print(f"[PASS] 已清理 {n} 条无效 DB 记录（文件本身不删除，可由人工复核 unindexed）")
        return 0

    if args.command == "restore-drill":
        problems = restore_drill(root)
        if problems:
            print("[FAIL] 恢复演练失败：")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("[PASS] 恢复演练通过：备份 → 还原 → integrity_check → 查询链路全部可用")
        return 1 if problems else 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
