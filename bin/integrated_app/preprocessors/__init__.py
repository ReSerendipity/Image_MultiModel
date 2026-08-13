"""
preprocessors — ControlNet 预处理器系统

对应全功能实施指南任务 3: ControlNet 预处理器系统

包含：
- canny.py: Canny 边缘检测
- midas.py: MiDaS 深度估计
- openpose.py: OpenPose 人体姿态检测

所有预处理器实现 PreprocessorProtocol，支持懒加载和优雅降级。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class PreprocessorProtocol(Protocol):
    """预处理器协议"""

    @property
    def name(self) -> str:
        """预处理器名称"""
        ...

    def is_available(self) -> bool:
        """预处理器是否可用（依赖已安装）"""
        ...

    def process(self, image: np.ndarray) -> np.ndarray:
        """处理图片，返回处理后的 numpy 数组。

        Args:
            image: 输入图片 (H, W, 3) RGB uint8。

        Returns:
            处理后的图片 (H, W, 1 或 3) uint8。
        """
        ...


# ── 预处理器注册表 ──────────────────────────────────────────────
_registry: dict[str, Any] = {}


def register_preprocessor(name: str, factory: Any) -> None:
    """注册预处理器工厂。

    Args:
        name: 预处理器名称。
        factory: 创建预处理器实例的可调用对象。
    """
    _registry[name] = factory


def get_preprocessor(name: str) -> Any | None:
    """获取预处理器实例（懒加载）。

    Args:
        name: 预处理器名称。

    Returns:
        预处理器实例，未注册时返回 None。
    """
    factory = _registry.get(name)
    if factory is None:
        return None
    return factory()


def list_preprocessors() -> list[str]:
    """列出所有已注册的预处理器名称。

    Returns:
        预处理器名称列表。
    """
    return list(_registry.keys())


# ── 自动注册内置预处理器 ────────────────────────────────────────
def _register_builtin() -> None:
    """注册所有内置预处理器工厂。"""
    from .canny import _create_canny
    from .midas import _create_midas
    from .openpose import _create_openpose

    register_preprocessor("canny", _create_canny)
    register_preprocessor("midas", _create_midas)
    register_preprocessor("openpose", _create_openpose)


_register_builtin()
