"""
tests/test_model_manager.py — 模型生命周期管理器测试

对应 TEST_AUDIT_REPORT P1-2: ModelManager 零测试
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from integrated_app.model_manager import ModelManager, ModelState


@pytest.fixture
def manager():
    return ModelManager()


class TestModelState:
    """ModelState 枚举"""

    def test_states(self):
        assert ModelState.UNLOADED.value == "unloaded"
        assert ModelState.LOADING.value == "loading"
        assert ModelState.LOADED.value == "loaded"
        assert ModelState.UNLOADING.value == "unloading"
        assert ModelState.ERROR.value == "error"


class TestModelManagerStates:
    """ModelManager 状态查询"""

    def test_default_state_unloaded(self, manager):
        assert manager.get_state("test_engine") == ModelState.UNLOADED

    def test_get_all_states_empty(self, manager):
        assert manager.get_all_states() == {}

    def test_get_all_states_after_load(self, manager):
        manager._states["engine1"] = ModelState.LOADED
        manager._states["engine2"] = ModelState.UNLOADED
        states = manager.get_all_states()
        assert states["engine1"]["state"] == "loaded"
        assert states["engine2"]["state"] == "unloaded"


class TestModelManagerLoad:
    """ModelManager.load_engine()"""

    @pytest.mark.asyncio
    async def test_load_success(self, manager):
        """成功加载 → LOADED"""
        mock_engine = AsyncMock()
        mock_engine.load = AsyncMock()

        await manager.load_engine("test_engine", mock_engine)

        assert manager.get_state("test_engine") == ModelState.LOADED
        mock_engine.load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_already_loaded_skips(self, manager):
        """已加载 → 跳过"""
        mock_engine = AsyncMock()
        manager._states["test_engine"] = ModelState.LOADED

        await manager.load_engine("test_engine", mock_engine)

        mock_engine.load.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_already_loading_skips(self, manager):
        """正在加载 → 跳过"""
        mock_engine = AsyncMock()
        manager._states["test_engine"] = ModelState.LOADING

        await manager.load_engine("test_engine", mock_engine)

        mock_engine.load.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_failure_sets_error(self, manager):
        """加载失败 → ERROR"""
        mock_engine = AsyncMock()
        mock_engine.load = AsyncMock(side_effect=RuntimeError("load failed"))

        with pytest.raises(RuntimeError, match="load failed"):
            await manager.load_engine("test_engine", mock_engine)

        assert manager.get_state("test_engine") == ModelState.ERROR

    @pytest.mark.asyncio
    async def test_load_notifies_observer(self, manager):
        """加载过程通知观察者"""
        notifications = []

        def observer(name, state, extra):
            notifications.append((name, state))

        manager.register_observer(observer)
        mock_engine = AsyncMock()
        mock_engine.load = AsyncMock()

        await manager.load_engine("test_engine", mock_engine)

        # 应至少收到 LOADING + LOADED
        states = [s for _, s in notifications]
        assert ModelState.LOADING in states
        assert ModelState.LOADED in states


class TestModelManagerUnload:
    """ModelManager.unload_engine()"""

    @pytest.mark.asyncio
    async def test_unload_success(self, manager):
        """成功卸载 → UNLOADED"""
        mock_engine = AsyncMock()
        mock_engine.unload = AsyncMock()
        manager._states["test_engine"] = ModelState.LOADED

        await manager.unload_engine("test_engine", mock_engine)

        assert manager.get_state("test_engine") == ModelState.UNLOADED
        mock_engine.unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_unload_not_loaded_skips(self, manager):
        """未加载 → 跳过"""
        mock_engine = AsyncMock()
        await manager.unload_engine("test_engine", mock_engine)
        mock_engine.unload.assert_not_called()

    @pytest.mark.asyncio
    async def test_unload_failure_sets_error(self, manager):
        """卸载失败 → ERROR"""
        mock_engine = AsyncMock()
        mock_engine.unload = AsyncMock(side_effect=RuntimeError("unload failed"))
        manager._states["test_engine"] = ModelState.LOADED

        with pytest.raises(RuntimeError, match="unload failed"):
            await manager.unload_engine("test_engine", mock_engine)

        assert manager.get_state("test_engine") == ModelState.ERROR
