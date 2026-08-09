#!/usr/bin/env python3
"""
scripts/migrate_outputs.py — 一次性脚本：迁移旧平铺输出文件到 engine/date 结构

对应 REMAINING_TASKS_REPORT A4: 输出目录迁移兼容

用法:
    python scripts/migrate_outputs.py [--dry-run] [--delete-orphans]

功能:
    1. 扫描 outputs/*.png 平铺文件
    2. 按命名规则解析引擎名（Flux.2_Klein-9B-Distilled_* → flux2_klein_9b_distilled）
    3. 移入 outputs/{engine}/{date}/ 结构
    4. 更新 data/history.db 的 outputs.path 指向新路径
    5. --dry-run: 只打印不执行
    6. --delete-orphans: 删除无法匹配引擎的孤儿文件
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DB_PATH = PROJECT_ROOT / "data" / "history.db"

# 引擎名映射（文件名前缀 → 引擎 ID）
ENGINE_NAME_MAP = {
    "Flux.2_Klein-9B-Distilled": "flux2_klein_9b_distilled",
    "Z-Image_Turbo": "z_image_turbo",
    "test_engine": "test_engine",
}


def parse_engine_from_filename(filename: str) -> str | None:
    """从文件名解析引擎 ID"""
    for prefix, engine_id in ENGINE_NAME_MAP.items():
        if filename.startswith(prefix):
            return engine_id
    # 通用匹配：xxx_engine_yyy → engine
    m = re.match(r"([a-zA-Z0-9_]+)_\d{3,}", filename)
    if m:
        return m.group(1).lower()
    return None


def get_file_date(filepath: Path) -> str:
    """获取文件的日期（YYYYMMDD）"""
    import time

    mtime = filepath.stat().st_mtime
    return time.strftime("%Y%m%d", time.localtime(mtime))


def update_db_path(db_path: Path, old_path: str, new_path: str) -> bool:
    """更新 DB 中的 outputs.path"""
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        # 标准化路径比较（Windows 路径分隔符）
        old_normalized = old_path.replace("\\", "/")
        cur = conn.execute(
            "UPDATE outputs SET path=? WHERE path LIKE ?",
            (new_path.replace("\\", "/"), f"%{old_normalized}%"),
        )
        conn.commit()
        updated = cur.rowcount > 0
        conn.close()
        return updated
    except Exception as e:
        print(f"  [DB ERROR] {e}")
        return False


def migrate(dry_run: bool = False, delete_orphans: bool = False) -> None:
    """执行迁移"""
    if not OUTPUTS_DIR.exists():
        print(f"Outputs dir not found: {OUTPUTS_DIR}")
        return

    # 扫描平铺 PNG 文件（根目录下的 .png 文件）
    flat_files = [f for f in OUTPUTS_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".png"]
    if not flat_files:
        print("No flat PNG files found in outputs root.")
        return

    print(f"Found {len(flat_files)} flat PNG files in outputs root.")
    migrated = 0
    orphaned = 0

    for f in flat_files:
        engine_id = parse_engine_from_filename(f.name)
        if not engine_id:
            print(f"  [ORPHAN] Cannot parse engine from: {f.name}")
            orphaned += 1
            if delete_orphans and not dry_run:
                f.unlink()
                print(f"    → Deleted orphan: {f.name}")
            continue

        date_str = get_file_date(f)
        target_dir = OUTPUTS_DIR / engine_id / date_str
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f.name

        if dry_run:
            print(f"  [DRY-RUN] {f.name} → {target_path.relative_to(PROJECT_ROOT)}")
        else:
            # 移动文件
            shutil.move(str(f), str(target_path))
            print(f"  [MOVED] {f.name} → {target_path.relative_to(PROJECT_ROOT)}")

            # 更新 DB
            old_path_str = str(f).replace("\\", "/")
            new_path_str = str(target_path).replace("\\", "/")
            db_updated = update_db_path(DB_PATH, old_path_str, new_path_str)
            if db_updated:
                print(f"    → DB path updated")
            else:
                print(f"    → DB path not found (may be new file)")

        migrated += 1

    print(f"\nSummary: migrated={migrated}, orphaned={orphaned}")
    if dry_run:
        print("(dry-run mode, no changes made)")


def main():
    parser = argparse.ArgumentParser(description="Migrate flat output files to engine/date structure")
    parser.add_argument("--dry-run", action="store_true", help="Only print, don't execute")
    parser.add_argument("--delete-orphans", action="store_true", help="Delete orphan files that can't be matched")
    args = parser.parse_args()

    migrate(dry_run=args.dry_run, delete_orphans=args.delete_orphans)


if __name__ == "__main__":
    main()
