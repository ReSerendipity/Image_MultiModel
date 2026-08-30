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
APP_DIR = PROJECT_ROOT / "app"

# 避免重复插入
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
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
        allowed_base_dirs=["outputs/", "data/", "workflows/", "model/"],
        project_root=str(project_root),
    )


# ── 环境感知：原生引擎栈不可用时跳过相关测试 ──────────────────
def _torch_is_functional() -> bool:
    """检测当前环境是否具备可用的 PyTorch（部分环境仅有占位/损坏的 torch）。"""
    try:
        import torch

        return bool(hasattr(torch, "tensor") and hasattr(torch, "__version__"))
    except Exception:  # pragma: no cover - 导入异常即视为不可用
        return False


def _comfy_available() -> bool:
    """检测原生引擎运行所需的 comfy 扩展是否可用。"""
    try:
        import comfy_aimdo  # noqa: F401

        return True
    except Exception:  # pragma: no cover - 依赖缺失
        return False


_TORCH_OK = _torch_is_functional()
_COMFY_OK = _comfy_available()
_ENGINE_OK = _TORCH_OK and _COMFY_OK

# 依赖原生引擎栈（torch + comfy）的测试文件：环境不可用时整体跳过
_NATIVE_TEST_FILES = {
    "test_preprocessors.py",
    "test_generate_routes.py",
    "test_forward_batch_and_cancel.py",
    "test_forward_path_api.py",
}


def pytest_collection_modifyitems(config, items):
    """原生引擎栈（torch / comfy_aimdo）不可用时，跳过依赖它的测试。

    仅作用于缺失可用 PyTorch 或 comfy 扩展的环境；在完整环境上
    ``_ENGINE_OK`` 为 True，本钩子不生效，全部测试照常执行。
    """
    if _ENGINE_OK:
        return
    skip_marker = pytest.mark.skip(
        reason="原生引擎栈不可用（缺 PyTorch 或 comfy_aimdo），跳过引擎相关测试"
    )
    for item in items:
        name = Path(item.path).name
        if name.startswith("test_native_") or name in _NATIVE_TEST_FILES:
            item.add_marker(skip_marker)
