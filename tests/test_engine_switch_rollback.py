"""
tests/test_engine_switch_rollback.py — 引擎切换失败自动回滚（P1·韧性）单测

对应 MLOps 反模式 #6：切换无失败回滚 → 无引擎可用空窗。
通过注入 fake manager/registry 验证 switch_engine_with_rollback 行为，无需 GPU。
"""

from __future__ import annotations

from types import SimpleNamespace

from integrated_app.routes.engine_routes import switch_engine_with_rollback


class FakeRegistry:
    def __init__(self, active: str | None = None) -> None:
        self._active = active
        self.calls: list[tuple[str, str]] = []

    @property
    def active_engine_name(self) -> str | None:
        return self._active

    def set_active(self, name: str) -> None:
        self._active = name
        self.calls.append(("set_active", name))

    def get(self, name: str):
        self.calls.append(("get", name))
        return f"engine_instance:{name}"


class FakeManager:
    def __init__(self, *, load_fail_target: str | None = None, rollback_fail_target: str | None = None) -> None:
        self.load_fail_target = load_fail_target
        self.rollback_fail_target = rollback_fail_target
        self.loaded: list[str] = []
        self.unloaded: list[str] = []

    async def load_engine(self, name: str, engine) -> None:
        self.loaded.append(name)
        if self.load_fail_target and name == self.load_fail_target:
            raise RuntimeError(f"load failed: {name}")
        if self.rollback_fail_target and name == self.rollback_fail_target:
            raise RuntimeError(f"rollback failed: {name}")

    async def unload_engine(self, name: str, engine) -> None:
        self.unloaded.append(name)


def _eng_cfg(name: str) -> SimpleNamespace:
    return SimpleNamespace(display_name=name)


async def test_load_success_no_prev_sets_active() -> None:
    reg = FakeRegistry(active=None)
    mgr = FakeManager()
    res = await switch_engine_with_rollback(mgr, reg, "new", _eng_cfg("NewEngine"),
                                            load_engine=mgr.load_engine,
                                            unload_engine=mgr.unload_engine,
                                            get_engine=reg.get)
    assert res["status"] == "loaded"
    assert res["rolled_back"] is False
    assert reg.active_engine_name == "new"
    assert "new" in mgr.loaded


async def test_switch_unloads_prev_before_load() -> None:
    reg = FakeRegistry(active="prev")
    mgr = FakeManager()
    await switch_engine_with_rollback(mgr, reg, "new", _eng_cfg("NewEngine"),
                                      load_engine=mgr.load_engine,
                                      unload_engine=mgr.unload_engine,
                                      get_engine=reg.get)
    assert "prev" in mgr.unloaded
    assert reg.active_engine_name == "new"


async def test_load_fail_rolls_back_to_prev() -> None:
    reg = FakeRegistry(active="prev")
    mgr = FakeManager(load_fail_target="new")
    res = await switch_engine_with_rollback(mgr, reg, "new", _eng_cfg("NewEngine"),
                                            load_engine=mgr.load_engine,
                                            unload_engine=mgr.unload_engine,
                                            get_engine=reg.get)
    assert res["status"] == "error"
    assert res["rolled_back"] is True
    assert reg.active_engine_name == "prev"
    # 先尝试加载 new，失败后回滚加载 prev
    assert mgr.loaded == ["new", "prev"]


async def test_load_fail_no_prev_no_rollback() -> None:
    reg = FakeRegistry(active=None)
    mgr = FakeManager(load_fail_target="new")
    res = await switch_engine_with_rollback(mgr, reg, "new", _eng_cfg("NewEngine"),
                                            load_engine=mgr.load_engine,
                                            unload_engine=mgr.unload_engine,
                                            get_engine=reg.get)
    assert res["status"] == "error"
    assert res["rolled_back"] is False
    assert reg.active_engine_name is None


async def test_load_fail_rollback_also_fails() -> None:
    reg = FakeRegistry(active="prev")
    mgr = FakeManager(load_fail_target="new", rollback_fail_target="prev")
    res = await switch_engine_with_rollback(mgr, reg, "new", _eng_cfg("NewEngine"),
                                            load_engine=mgr.load_engine,
                                            unload_engine=mgr.unload_engine,
                                            get_engine=reg.get)
    assert res["status"] == "error"
    assert res["rolled_back"] is False
    # active 仍指向 prev（从未被改），不会悬空到破损引擎
    assert reg.active_engine_name == "prev"
    assert mgr.loaded == ["new", "prev"]
