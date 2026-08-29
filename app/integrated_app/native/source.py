"""
native/source.py — Comfy 源码复用装载

把项目内 `comfy_kernel`（独立推理内核，包含 `comfy/`、`comfy_extras/`、
`comfy_execution/`、`nodes.py` 等顶层包）整体加入 ``sys.path``，确保 ``import comfy``
命中本仓库内核源码，而不是其它环境中安装的 ComfyUI 包。

幂等：多次调用 ``ensure_loaded()`` 只装载一次。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录：native/ -> integrated_app/ -> app/ -> 项目根
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_COMFY_ROOT = _PROJECT_ROOT / "comfy_kernel"

_loaded = False
_comfy_root: Path | None = None


def _default_comfy_root() -> Path:
    """默认 Comfy 内核源码目录（项目内 comfy_kernel/）。"""
    return _DEFAULT_COMFY_ROOT


def _insert_path(path: Path) -> None:
    """将目录插入 sys.path[0]（若未出现），保证顶层包命中复用源码。"""
    s = str(path)
    if s not in sys.path:
        sys.path.insert(0, s)


def ensure_loaded(
    comfy_root: str | Path | None = None,
    custom_nodes_dir: str | Path | None = None,
) -> Path:
    """装载 Comfy 源码到 sys.path（幂等）。

    Args:
        comfy_root: Comfy 核心源码所在目录（含 ``comfy/`` 包）。为 None 时
            默认使用项目内 ``comfy_kernel``。
        custom_nodes_dir: 自定义节点源码目录（Phase 1 可传 None，仅装载核心）。

    Returns:
        解析后的 Comfy 源码根目录绝对路径。

    Raises:
        RuntimeError: ``comfy_root`` 下不存在 ``comfy/`` 包，或 import comfy 失败。
    """
    global _loaded, _comfy_root
    if _loaded and _comfy_root is not None:
        return _comfy_root

    root = Path(comfy_root).resolve() if comfy_root else _default_comfy_root().resolve()
    if not (root / "comfy").is_dir():
        raise RuntimeError(
            f"Comfy source dir invalid: '{root}' (missing 'comfy/' package). "
            "Expected the directory containing the comfy/ package (comfy_kernel)."
        )

    # 整个 comfy_kernel 加入 sys.path[0]，命中 comfy/comfy_extras/comfy_execution/nodes.py
    _insert_path(root)

    # 自定义节点目录（可选，Phase 3 再全量扫描）
    if custom_nodes_dir:
        cnd = Path(custom_nodes_dir).resolve()
        if cnd.is_dir() and str(cnd) not in sys.path:
            _insert_path(cnd)

    try:
        import comfy  # noqa: F401  # 仅为触发顶层包导入，验证可 import
    except Exception as e:  # pragma: no cover - 依赖环境相关
        raise RuntimeError(f"Failed to import comfy from '{root}': {e}") from e

    _loaded = True
    _comfy_root = root
    logger.info("Native comfy source loaded from: %s", root)
    return root


def is_loaded() -> bool:
    """Comfy 源码是否已装载。"""
    return _loaded


def get_comfy_root() -> Path | None:
    """已装载的 Comfy 源码根目录；未装载时返回 None。"""
    return _comfy_root
