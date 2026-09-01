"""
tests/observability/test_auto_unload.py — P1-7 自动卸载回归测试

MLOps P1-7：验证 ``unload_all_engines`` 为协程函数（不再在运行中的事件循环内调用
``run_until_complete``），且可在不触发 RuntimeError 的情况下被 await。
"""

from __future__ import annotations

import asyncio
import inspect

from app.integrated_app import app_server


def test_unload_all_engines_is_coroutine_function():
    assert inspect.iscoroutinefunction(app_server.unload_all_engines), (
        "unload_all_engines 必须是 async，否则会在事件循环内调用 run_until_complete"
    )


def test_unload_all_engines_has_no_run_until_complete():
    src = inspect.getsource(app_server.unload_all_engines)
    assert "run_until_complete" not in src, (
        "禁止在事件循环内调用 run_until_complete（会触发 RuntimeError: already running）"
    )


def test_unload_all_engines_awaits_without_runtime_error():
    """用假 model_manager / registry 注入，验证可安全 await 且跳过 active 引擎。"""

    class _FakeInst:
        pass

    class _FakeMM:
        def get_state(self, name):
            class _S:
                value = "loaded"
            return _S()

        async def unload_engine(self, name, inst):
            _FakeInst()  # 确认被调用
            return True

    class _FakeRegistry:
        active_engine_name = "z_image_turbo_native"

        def create_engine_instance(self, **kwargs):
            return _FakeInst()

    class _FakeEngineCfg:
        display_name = "Fake"
        display_name_en = "Fake"
        backend = "native"

        def model_dump(self):
            return {}

    class _FakeEngines(dict):
        pass

    class _FakeModels:
        engines = _FakeEngines({"z_image_turbo_native": _FakeEngineCfg()})

    class _FakeConfig:
        models = _FakeModels()

    # 注入假依赖
    orig_mm = app_server.get_model_manager if hasattr(app_server, "get_model_manager") else None
    import app.integrated_app.model_manager as mm_mod  # noqa: F401
    import app.integrated_app.model_registry as reg_mod

    real_mm = reg_mod.get_model_manager if hasattr(reg_mod, "get_model_manager") else None
    saved_mm = mm_mod.get_model_manager
    saved_reg = reg_mod.get_model_registry

    mm_mod.get_model_manager = lambda: _FakeMM()
    reg_mod.get_model_registry = lambda: _FakeRegistry()
    try:
        # 不应抛出 RuntimeError: This event loop is already running
        asyncio.run(app_server.unload_all_engines(_FakeConfig()))
    finally:
        mm_mod.get_model_manager = saved_mm
        reg_mod.get_model_registry = saved_reg
