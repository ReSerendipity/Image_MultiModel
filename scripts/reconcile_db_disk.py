#!/usr/bin/env python
"""scripts/reconcile_db_disk.py — 数据库 ↔ 磁盘一致性对账（一次性治理工具）

对应《数据治理评估报告（2026-09-04）》P0-1：
    outputs 表 10980 行中 10873 行指向的文件不存在；
    data/cache/thumbs 下 317 个缩略图与 DB 引用零交集（全部为孤儿）。
历史页/图库因此出现大量死链，留存承诺不可预期。

本脚本做两件事：
  1. **死记录对账**：删除 outputs 表中指向不存在文件的行（DB 备份后可回滚）。
  2. **孤儿缩略图对账**：把无任何任务引用的缩略图移入隔离目录（默认**移动**而非
     硬删除，可还原），避免 104MB 缓存无执行者地无限增长。

路径解析约定（与 history_db._delete_task_files 保持一致）：
    - ``outputs.path`` 为绝对路径时按原样判定；
    - 相对路径则相对 ``<project_root>/outputs`` 解析。

安全设计：
    - 默认 **dry-run**，只报告不改动；需显式 ``--apply`` 才落盘。
    - ``--apply`` 前自动备份 history.db（``data/history.db.reconcile-<ts>.bak``）。
    - 缩略图移入 ``data/cache/thumbs_quarantine-<ts>/``，可随时还原。

用法::

    python scripts/reconcile_db_disk.py                      # dry-run
    python scripts/reconcile_db_disk.py --apply              # 实际执行
    python scripts/reconcile_db_disk.py --apply --no-backup  # 跳过备份（不推荐）
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DB = "data/history.db"
DEFAULT_THUMBS_DIR = "data/cache/thumbs"


@dataclass
class ReconcileReport:
    """对账结果统计。"""

    outputs_total: int = 0
    outputs_dead: int = 0
    dead_ids: list[int] = field(default_factory=list)
    thumbs_total: int = 0
    thumbs_orphan: int = 0
    orphan_thumbs: list[Path] = field(default_factory=list)
    backup_path: Path | None = None
    quarantine_dir: Path | None = None

    def render(self) -> str:
        lines = [
            "── 对账结果 ────────────────────────────────",
            f"outputs 总行数      : {self.outputs_total}",
            f"  指向缺失文件的死记录: {self.outputs_dead}",
            f"缩略图总文件数      : {self.thumbs_total}",
            f"  无引用孤儿缩略图   : {self.thumbs_orphan}",
        ]
        if self.backup_path:
            lines.append(f"数据库备份          : {self.backup_path}")
        if self.quarantine_dir:
            lines.append(f"缩略图隔离目录      : {self.quarantine_dir}")
        lines.append("────────────────────────────────────────────")
        return "\n".join(lines)


def resolve_output_path(raw: str, outputs_dir: Path) -> Path:
    """把 outputs.path 解析为绝对路径（绝对按原样，相对拼 outputs_dir）。"""
    p = Path(raw)
    return p if p.is_absolute() else (outputs_dir / p)


def collect(db_path: Path, outputs_dir: Path, thumbs_dir: Path) -> ReconcileReport:
    """扫描数据库与磁盘，产出对账报告（只读，不改动任何数据）。"""
    report = ReconcileReport()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, path FROM outputs").fetchall()
        report.outputs_total = len(rows)
        for r in rows:
            if not resolve_output_path(r["path"], outputs_dir).exists():
                report.outputs_dead += 1
                report.dead_ids.append(int(r["id"]))

        # 缩略图引用集：任务 ID 前 16 位前缀（缩略图命名约定）+ tasks.thumbnail 列
        prefixes = {r[0][:16] for r in conn.execute("SELECT task_id FROM tasks").fetchall() if r[0]}
        referenced_names: set[str] = set()
        try:
            for r in conn.execute(
                "SELECT thumbnail FROM tasks WHERE thumbnail IS NOT NULL AND thumbnail != ''"
            ).fetchall():
                referenced_names.add(Path(r[0]).name)
        except sqlite3.OperationalError:
            referenced_names = set()
    finally:
        conn.close()

    if thumbs_dir.is_dir():
        for f in thumbs_dir.iterdir():
            if not f.is_file():
                continue
            report.thumbs_total += 1
            if f.name in referenced_names:
                continue
            if any(f.name.startswith(pre) for pre in prefixes):
                continue
            report.thumbs_orphan += 1
            report.orphan_thumbs.append(f)

    return report


def backup_db(db_path: Path) -> Path:
    """复制一份数据库备份（时间戳后缀）。"""
    dest = db_path.with_suffix(db_path.suffix + f".reconcile-{time.strftime('%Y%m%d-%H%M%S')}.bak")
    shutil.copy2(db_path, dest)
    return dest


def apply_changes(
    db_path: Path,
    report: ReconcileReport,
    thumbs_dir: Path,
    ts: str,
    do_backup: bool = True,
) -> ReconcileReport:
    """落盘执行：删死记录 + 隔离孤儿缩略图。"""
    if do_backup:
        report.backup_path = backup_db(db_path)

    if report.dead_ids:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            # 分批删除，避免超长 IN 子句
            for i in range(0, len(report.dead_ids), 900):
                chunk = report.dead_ids[i : i + 900]
                ph = ",".join("?" * len(chunk))
                conn.execute(f"DELETE FROM outputs WHERE id IN ({ph})", chunk)
            # 回算 tasks.output_count，避免删除后计数与真实文件数不一致
            conn.execute(
                "UPDATE tasks SET output_count = ("
                "  SELECT COUNT(*) FROM outputs WHERE outputs.task_id = tasks.task_id"
                ")"
            )
            conn.commit()
        finally:
            conn.close()

    if report.orphan_thumbs:
        quarantine = thumbs_dir.parent / f"thumbs_quarantine-{ts}"
        quarantine.mkdir(parents=True, exist_ok=True)
        for f in report.orphan_thumbs:
            try:
                shutil.move(str(f), str(quarantine / f.name))
            except OSError as e:  # noqa: BLE001
                print(f"[warn] 缩略图隔离失败 {f}: {e}", file=sys.stderr)
        report.quarantine_dir = quarantine

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="数据库 ↔ 磁盘一致性对账（P0-1）")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"history.db 路径（默认 {DEFAULT_DB}）")
    parser.add_argument("--project-root", default=".", help="项目根目录（用于解析相对 outputs 路径，默认当前目录）")
    parser.add_argument("--thumbs-dir", default=DEFAULT_THUMBS_DIR, help=f"缩略图目录（默认 {DEFAULT_THUMBS_DIR}）")
    parser.add_argument("--apply", action="store_true", help="实际执行（默认仅 dry-run 报告）")
    parser.add_argument("--no-backup", action="store_true", help="跳过数据库备份（不推荐）")
    parser.add_argument("--limit-print", type=int, default=5, help="样例打印条数")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    root = Path(args.project_root).resolve()
    outputs_dir = root / "outputs"
    thumbs_dir = Path(args.thumbs_dir)
    if not thumbs_dir.is_absolute():
        thumbs_dir = root / thumbs_dir

    if not db_path.exists():
        print(f"[error] 数据库不存在: {db_path}", file=sys.stderr)
        return 2

    print(f"数据库 : {db_path}")
    print(f"输出目录: {outputs_dir}")
    print(f"缩略图目录: {thumbs_dir}")

    report = collect(db_path, outputs_dir, thumbs_dir)

    if not args.apply:
        print("\n[dry-run] 未做任何改动；加 --apply 执行。")
        print(report.render())
        for f in report.orphan_thumbs[: args.limit_print]:
            print(f"  样例孤儿缩略图: {f}")
        return 0

    ts = time.strftime("%Y%m%d-%H%M%S")
    report = apply_changes(db_path, report, thumbs_dir, ts, do_backup=not args.no_backup)
    print("\n[apply] 已执行对账清理。")
    print(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
