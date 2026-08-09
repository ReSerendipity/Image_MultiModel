"""
model_registry.py — 引擎注册表桥接

对应 MASTER_PLAN §4 / 附录 A3: model_registry.py
对应 PRD §4.2: Registry → SSE 桥接
"""

from __future__ import annotations

import logging
from typing import Any

from .engine_interface import get_registry
from .model_manager import get_model_manager

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    引擎注册表 + ModelManager 桥接：
    - 注册引擎到 InMemoryEngineRegistry
    - 注册 ModelManager 观察者 → SSE
    - 提供 list / get / activate / deactivate 接口
    """

    def __init__(self) -> None:
        self._registry = get_registry()
        self._manager = get_model_manager()
        self._initialized = False

    def init_from_config(self, config: Any) -> None:
        """
        从 AppConfig 初始化引擎注册。

        Args:
            config: AppConfig 实例
        """
        if self._initialized:
            return

        for engine_name, engine_cfg in config.models.engines.items():
            # 懒注册：工厂函数在 get() 时才实例化
            # 这里注册工厂 + 配置
            logger.info(f"Registering engine: {engine_name}")

            # 注册为可延迟实例化的引擎
            self._registry._factories[engine_name] = None  # type: ignore
            self._registry._configs[engine_name] = {
                "name": engine_name,
                "display_name": engine_cfg.display_name,
                "display_name_en": engine_cfg.display_name_en,
                "config": engine_cfg.model_dump(),
            }

        # 设置默认引擎
        default_engine = config.models.default_engine
        if default_engine in config.models.engines:
            self._registry.set_active(default_engine)

        self._initialized = True
        logger.info(f"ModelRegistry initialized with {len(config.models.engines)} engines")

    def list_engines(self) -> list[dict[str, Any]]:
        """列出所有引擎（含状态）"""
        engines = self._registry.list_engines()
        # 补充 ModelManager 状态
        for eng in engines:
            state = self._manager.get_state(eng["name"])
            eng["model_state"] = state.value
        return engines

    def get_active_engine_name(self) -> str | None:
        return self._registry.active_engine_name

    def set_active(self, name: str) -> None:
        self._registry.set_active(name)

    def get_engine_config(self, name: str) -> dict[str, Any] | None:
        return self._registry._configs.get(name)


# ── 全局单例 ──────────────────────────────────────────────────
_global_registry_bridge: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    global _global_registry_bridge
    if _global_registry_bridge is None:
        _global_registry_bridge = ModelRegistry()
    return _global_registry_bridge
