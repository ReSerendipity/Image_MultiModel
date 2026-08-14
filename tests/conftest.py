"""
conftest.py — pytest 共享 fixture 与路径注入

对应 TEST_AUDIT_REPORT P0-3: 消除 9 个测试文件的 sys.path.insert 重复
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── 统一路径注入 ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"

# 避免重复插入
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ── 共享 fixture ────────────────────────────────────────────
@pytest.fixture
def project_root():
    """项目根目录"""
    return PROJECT_ROOT


@pytest.fixture
def tmp_db(tmp_path):
    """临时 HistoryDB 实例（自动关闭）"""
    from integrated_app.history_db import HistoryDB

    db = HistoryDB(tmp_path / "test_history.db")
    yield db
    db.close()


@pytest.fixture
def path_guard(project_root):
    """PathGuard 实例（4 个白名单目录）"""
    from integrated_app.security.path_guard import PathGuard

    return PathGuard(
        allowed_base_dirs=["outputs/", "data/", "workflows/", "pretrained_models/"],
        project_root=str(project_root),
    )
