"""
model_manager.py — 模型生命周期管理

对应 MASTER_PLAN §4 / 附录 A2: model_manager.py
对应 PRD §4.2: ModelManager 生命周期 → SSE
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ModelState(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    UNLOADING = "unloading"
    ERROR = "error"


class ModelManager:
    """
    模型生命周期管理器（观察者模式 → SSE 推送）。

    职责：
    - 管理引擎的 load / unload 生命周期
    - 推送 model_status 事件到 SSE
    - 防止重复加载
    """

    def __init__(self) -> None:
        self._states: dict[str, ModelState] = {}
        self._observers: list[Callable[[str, ModelState, dict], None]] = []

    def register_observer(self, cb: Callable[[str, ModelState, dict], None]) -> None:
        """注册状态变更观察者（→ SSE）"""
        self._observers.append(cb)

    def _notify(self, engine_name: str, state: ModelState, extra: dict | None = None) -> None:
        data = extra or {}
        for cb in self._observers:
            try:
                cb(engine_name, state, data)
            except Exception as e:
                logger.warning(f"ModelManager observer error: {e}")

    def get_state(self, engine_name: str) -> ModelState:
        return self._states.get(engine_name, ModelState.UNLOADED)

    async def load_engine(self, engine_name: str, engine: Any) -> None:
        """
        加载引擎模型。

        Args:
            engine_name: 引擎名称
            engine: 实现 ImageEngine Protocol 的实例
        """
        current = self.get_state(engine_name)
        if current == ModelState.LOADED:
            logger.info(f"Engine {engine_name} already loaded")
            return
        if current == ModelState.LOADING:
            logger.warning(f"Engine {engine_name} is already loading")
            return

        self._states[engine_name] = ModelState.LOADING
        self._notify(engine_name, ModelState.LOADING)

        try:
            await engine.load(on_progress=lambda pct, phase, extra: self._notify(
                engine_name, ModelState.LOADING,
                {"progress": pct, "phase": phase, **(extra or {})},
            ))
            self._states[engine_name] = ModelState.LOADED
            self._notify(engine_name, ModelState.LOADED)
        except Exception as e:
            self._states[engine_name] = ModelState.ERROR
            self._notify(engine_name, ModelState.ERROR, {"error": str(e)})
            raise

    async def unload_engine(self, engine_name: str, engine: Any) -> None:
        """卸载引擎模型"""
        current = self.get_state(engine_name)
        if current == ModelState.UNLOADED:
            return

        self._states[engine_name] = ModelState.UNLOADING
        self._notify(engine_name, ModelState.UNLOADING)

        try:
            await engine.unload()
            self._states[engine_name] = ModelState.UNLOADED
            self._notify(engine_name, ModelState.UNLOADED)
        except Exception as e:
            self._states[engine_name] = ModelState.ERROR
            self._notify(engine_name, ModelState.ERROR, {"error": str(e)})
            raise

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """获取所有引擎状态摘要"""
        return {
            name: {"state": state.value}
            for name, state in self._states.items()
        }


# ── 全局单例 ──────────────────────────────────────────────────
_global_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = ModelManager()
    return _global_manager
