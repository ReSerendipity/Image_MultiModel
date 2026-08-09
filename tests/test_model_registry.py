"""
tests/test_model_registry.py — 引擎注册表桥接测试

对应 TEST_AUDIT_REPORT P1-3: ModelRegistry 零测试
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from integrated_app.engine_interface import InMemoryEngineRegistry
from integrated_app.model_registry import ModelRegistry, get_model_registry


class TestInMemoryEngineRegistry:
    """InMemoryEngineRegistry 直接测试"""

    def test_register_and_get(self):
        registry = InMemoryEngineRegistry()

        class FakeEngine:
            def __init__(self, **kw):
                self.name = kw.get("name", "test")
                self.display_name = self.name

            def is_ready(self):
                return False

        registry.register("test", FakeEngine, {"name": "test"})
        engine = registry.get("test")
        assert engine.name == "test"

    def test_get_nonexistent_raises(self):
        registry = InMemoryEngineRegistry()
        with pytest.raises(KeyError, match="Engine not registered"):
            registry.get("nonexistent")

    def test_list_engines(self):
        registry = InMemoryEngineRegistry()

        class FakeEngine:
            def __init__(self, **kw):
                self.name = kw.get("name", "test")
                self.display_name = "Test"

            def is_ready(self):
                return False

        registry.register("test", FakeEngine, {"name": "test"})
        # 需要先实例化才能在 list 中显示 display_name
        registry.get("test")
        engines = registry.list_engines()
        assert len(engines) == 1
        assert engines[0]["name"] == "test"

    def test_set_active(self):
        registry = InMemoryEngineRegistry()

        class FakeEngine:
            name = "test"
            display_name = "Test"

            def is_ready(self):
                return False

        registry.register("test", FakeEngine, {"name": "test"})
        registry.set_active("test")
        assert registry.active_engine_name == "test"

    def test_set_active_nonexistent_raises(self):
        registry = InMemoryEngineRegistry()
        with pytest.raises(KeyError):
            registry.set_active("nonexistent")


class TestModelRegistryBridge:
    """ModelRegistry 桥接测试"""

    def test_init_from_config(self):
        """从配置初始化引擎注册"""
        registry = ModelRegistry()
        mock_config = MagicMock()
        mock_config.models.engines = {
            "flux2_klein_9b_distilled": MagicMock(
                display_name="FLUX",
                display_name_en="FLUX",
                model_dump=MagicMock(return_value={}),
            ),
            "z_image_turbo": MagicMock(
                display_name="Z-Image",
                display_name_en="Z-Image",
                model_dump=MagicMock(return_value={}),
            ),
        }
        mock_config.models.default_engine = "flux2_klein_9b_distilled"

        registry.init_from_config(mock_config)

        assert registry._initialized is True
        assert registry.get_active_engine_name() == "flux2_klein_9b_distilled"

    def test_init_idempotent(self):
        """重复初始化 → 跳过"""
        registry = ModelRegistry()
        registry._initialized = True
        # 不应报错
        registry.init_from_config(MagicMock())

    def test_get_engine_config(self):
        """获取引擎配置"""
        registry = ModelRegistry()
        registry._registry._configs["test_engine"] = {"name": "test_engine"}
        cfg = registry.get_engine_config("test_engine")
        assert cfg["name"] == "test_engine"

    def test_get_engine_config_nonexistent(self):
        """获取不存在的引擎配置 → None"""
        registry = ModelRegistry()
        cfg = registry.get_engine_config("nonexistent")
        assert cfg is None


class TestModelRegistryGlobal:
    """全局 ModelRegistry 单例"""

    def test_get_model_registry_singleton(self):
        r1 = get_model_registry()
        r2 = get_model_registry()
        assert r1 is r2
