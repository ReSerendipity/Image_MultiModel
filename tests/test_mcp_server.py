"""test_mcp_server.py — MCP 服务器测试。

覆盖 MCPResponse / MCPRequest / 解析 / initialize / tools/list / tools/call
以及 txt2img / status / cancel 三个业务工具（mock 引擎，不加载真实模型）。

对应 roadmap 落地项 1 验证。
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from integrated_app.mcp_server import (
    MCP_PROTOCOL_VERSION,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    MCPRequest,
    MCPResponse,
    MCPServer,
    MCPTool,
)

# ── 工具函数 ─────────────────────────────────────────────────


def make_request(method: str, params: dict[str, Any] | None = None, rid: int | str | None = 1) -> MCPRequest:
    return MCPRequest(id=rid, method=method, params=params or {})


def call_params(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "arguments": arguments or {}}


def _mock_vram_preflight(monkeypatch) -> None:
    """MCP txt2img 会调用 preflight_vram 做显存预检，该预检依赖真实 GPU 显存

    （全集顺序跑时前置测试会改变显存/全局 reserved 状态，导致 can_run 在
    隔离跑通过、全集跑失败而 flaky）。本测试只验证 txt2img 装配逻辑，用
    确定性结果屏蔽真实显存依赖。
    """
    import integrated_app.gpu_utils as _gpu
    from integrated_app.gpu_utils import VRAMEstimate

    monkeypatch.setattr(
        _gpu,
        "preflight_vram",
        lambda **kw: VRAMEstimate(
            can_run=True,
            needed_vram_gb=0.0,
            available_vram_gb=99.0,
            recommended_precision="fp8",
            recommended_chunk_size=1,
            warning="",
        ),
    )


# ── Fake 引擎 / 注册表 ───────────────────────────────────────


class FakeEngine:
    """最小 ImageEngine Protocol 实现（测试用）。"""

    def __init__(self, name: str = "z_image_turbo_native", ready: bool = True) -> None:
        self._name = name
        self._ready = ready
        self.loaded = False
        self.cancelled = False
        self.last_config: Any = None
        self.output_paths = ["outputs/fake_00001_.png"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return "Z-Image Turbo"

    def is_ready(self) -> bool:
        return self._ready

    async def load(self, on_progress=None) -> None:
        self._ready = True
        self.loaded = True

    async def unload(self) -> None:
        self._ready = False

    async def infer_txt2img(self, config: Any, on_progress=None) -> list[str]:
        self.last_config = config
        return list(self.output_paths)

    async def cancel(self) -> None:
        self.cancelled = True


class FakeRegistry:
    def __init__(self, engine: FakeEngine | None = None) -> None:
        self._active: FakeEngine | None = engine
        self.registered: list[str] = []

    @property
    def active_engine_name(self) -> str | None:
        return self._active.name if self._active else None

    def get_active(self) -> FakeEngine | None:
        return self._active

    def register(self, name: str, factory: Any, config: dict | None = None) -> None:
        self.registered.append(name)

    def set_active(self, name: str) -> None:
        self._active = None


class FakeManager:
    def __init__(self) -> None:
        self.loaded_engines: list[str] = []
        self.states: dict[str, str] = {"z_image_turbo_native": "unloaded"}

    async def load_engine(self, engine_name: str, engine: Any) -> None:
        self.loaded_engines.append(engine_name)
        self.states[engine_name] = "loaded"
        await engine.load()

    def get_state(self, engine_name: str):
        state_value = self.states.get(engine_name, "unloaded")
        return SimpleNamespace(value=state_value)


class FakeEngineCfg:
    def __init__(self, name: str = "z_image_turbo_native") -> None:
        self.name = name
        self.display_name = "Z-Image Turbo"
        self.display_name_en = "Z-Image Turbo"
        self.backend = "native"

    def model_dump(self) -> dict:
        return {}


class FakeConfig:
    def __init__(self) -> None:
        self.version = "1.4.0"
        self.default_engine = "z_image_turbo_native"
        engine_cfg = FakeEngineCfg()
        self.engines: dict[str, FakeEngineCfg] = {engine_cfg.name: engine_cfg}
        # mcp_server 与 HTTP 通道对齐，需读取安全配置（内容过滤 fail-closed 开关）
        self.security = SimpleNamespace(
            content_filter=SimpleNamespace(fail_closed_on_clip_missing=False),
        )
        # mcp_server 预检显存时读取推理配置项
        self.inference = SimpleNamespace(
            vram_multisample_rule=1.5,
            vram_headroom_gb=2.0,
            vram_tight_continue=False,
        )

    @property
    def models(self):
        return SimpleNamespace(
            default_engine=self.default_engine,
            engines=self.engines,
        )


@pytest.fixture
def fake_env(monkeypatch):
    """构造 fake config / registry / manager 环境，供业务工具测试使用。"""
    import integrated_app.config as config_mod
    import integrated_app.engine_interface as ei_mod
    import integrated_app.model_manager as mm_mod
    import integrated_app.model_registry as mr_mod

    engine = FakeEngine()
    registry = FakeRegistry(engine)
    manager = FakeManager()

    monkeypatch.setattr(config_mod, "get_config", lambda: FakeConfig())
    monkeypatch.setattr(ei_mod, "get_registry", lambda: registry)
    monkeypatch.setattr(mm_mod, "get_model_manager", lambda: manager)
    monkeypatch.setattr(mr_mod, "get_model_registry", lambda: SimpleNamespace(
        create_engine_instance=lambda **kw: engine,
    ))
    _mock_vram_preflight(monkeypatch)
    return SimpleNamespace(engine=engine, registry=registry, manager=manager)


# ── MCPResponse ──────────────────────────────────────────────


class TestMCPResponse:
    def test_to_json_result(self):
        resp = MCPResponse(id=1, result={"ok": True})
        data = json.loads(resp.to_json())
        assert data == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}

    def test_to_json_error(self):
        resp = MCPResponse(id="abc", error={"code": -32601, "message": "nope"})
        data = json.loads(resp.to_json())
        assert data == {"jsonrpc": "2.0", "id": "abc", "error": {"code": -32601, "message": "nope"}}

    def test_to_json_none_id(self):
        resp = MCPResponse(id=None, result={})
        data = json.loads(resp.to_json())
        assert data["id"] is None
        assert data["result"] == {}


# ── MCPRequest / 解析 ────────────────────────────────────────


class TestParseMessage:
    def test_valid_message(self):
        req = MCPServer._parse_message(
            json.dumps({"jsonrpc": "2.0", "id": 5, "method": "ping", "params": {}})
        )
        assert req is not None
        assert req.id == 5
        assert req.method == "ping"
        assert req.params == {}

    def test_missing_params_defaults_to_empty(self):
        req = MCPServer._parse_message('{"id": 1, "method": "ping"}')
        assert req is not None
        assert req.params == {}

    def test_invalid_json_returns_none(self):
        assert MCPServer._parse_message("{not json") is None

    def test_empty_line_returns_none(self):
        assert MCPServer._parse_message("") is None
        assert MCPServer._parse_message("   \n") is None


# ── 协议方法 ─────────────────────────────────────────────────


class TestProtocolMethods:
    @pytest.mark.asyncio
    async def test_initialize(self):
        server = MCPServer()
        resp = await server._handle_request(make_request("initialize"))
        assert resp.error is None
        assert resp.result["protocolVersion"] == MCP_PROTOCOL_VERSION
        assert resp.result["serverInfo"]["name"] == MCP_SERVER_NAME
        assert resp.result["serverInfo"]["version"] == MCP_SERVER_VERSION
        assert "tools" in resp.result["capabilities"]

    @pytest.mark.asyncio
    async def test_ping(self):
        server = MCPServer()
        resp = await server._handle_request(make_request("ping"))
        assert resp.error is None
        assert resp.result == {}

    @pytest.mark.asyncio
    async def test_unknown_method(self):
        server = MCPServer()
        resp = await server._handle_request(make_request("no/such/method"))
        assert resp.error is not None
        assert resp.error["code"] == -32601

    @pytest.mark.asyncio
    async def test_tools_list_contains_four_tools(self):
        server = MCPServer()
        resp = await server._handle_request(make_request("tools/list"))
        names = [t["name"] for t in resp.result["tools"]]
        assert sorted(names) == ["cancel", "list_tools", "status", "txt2img"]
        for tool in resp.result["tools"]:
            assert "description" in tool
            assert "inputSchema" in tool

    @pytest.mark.asyncio
    async def test_register_tool_override(self):
        server = MCPServer()
        server.register_tool(MCPTool(
            name="custom", description="d", input_schema={"type": "object"},
            handler=lambda **kw: {"ok": 1},
        ))
        resp = await server._handle_request(
            make_request("tools/call", call_params("custom"))
        )
        assert resp.error is None
        assert json.loads(resp.result["content"][0]["text"]) == {"ok": 1}


# ── tools/call 调度 ──────────────────────────────────────────


class TestToolsCall:
    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        server = MCPServer()
        resp = await server._handle_request(make_request("tools/call", call_params("nope")))
        assert resp.error is not None
        assert resp.error["code"] == -32602

    @pytest.mark.asyncio
    async def test_missing_arguments_key(self, fake_env):
        server = MCPServer()
        resp = await server._handle_request(make_request("tools/call", {"name": "status"}))
        assert resp.error is None
        text = json.loads(resp.result["content"][0]["text"])
        assert "engines" in text

    @pytest.mark.asyncio
    async def test_type_error_becomes_invalid_params(self):
        server = MCPServer()
        server.register_tool(MCPTool(
            name="need_arg", description="d", input_schema={"type": "object"},
            handler=lambda required_param, **kw: {},
        ))
        resp = await server._handle_request(make_request("tools/call", call_params("need_arg")))
        assert resp.error is not None
        assert resp.error["code"] == -32602

    @pytest.mark.asyncio
    async def test_handler_exception_becomes_internal_error(self):
        async def boom(**kwargs):
            raise RuntimeError("kaboom")

        server = MCPServer()
        server.register_tool(MCPTool(name="boom", description="d", input_schema={}, handler=boom))
        resp = await server._handle_request(make_request("tools/call", call_params("boom")))
        assert resp.error is not None
        assert resp.error["code"] == -32603
        assert "kaboom" in resp.error["message"]


# ── 业务工具：list_tools / status / cancel ───────────────────


class TestListToolsTool:
    @pytest.mark.asyncio
    async def test_list_tools(self):
        server = MCPServer()
        resp = await server._handle_request(make_request("tools/call", call_params("list_tools")))
        text = json.loads(resp.result["content"][0]["text"])
        assert text["count"] == 4
        assert {t["name"] for t in text["tools"]} == {"list_tools", "txt2img", "status", "cancel"}


class TestStatusTool:
    @pytest.mark.asyncio
    async def test_status(self, fake_env):
        server = MCPServer()
        resp = await server._handle_request(make_request("tools/call", call_params("status")))
        assert resp.error is None
        text = json.loads(resp.result["content"][0]["text"])
        assert text["default_engine"] == "z_image_turbo_native"
        assert text["active_engine"] == "z_image_turbo_native"
        assert text["engines"][0]["name"] == "z_image_turbo_native"
        assert text["engines"][0]["state"] == "unloaded"
        assert text["version"] == "1.4.0"


class TestCancelTool:
    @pytest.mark.asyncio
    async def test_cancel_calls_engine_cancel(self, fake_env):
        server = MCPServer()
        resp = await server._handle_request(
            make_request("tools/call", call_params("cancel", {"task_id": "t1"}))
        )
        assert resp.error is None
        text = json.loads(resp.result["content"][0]["text"])
        assert text["success"] is True
        assert fake_env.engine.cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_without_active_engine(self, monkeypatch):
        import sys
        import types

        import integrated_app.engine_interface as ei_mod

        fake_app = types.SimpleNamespace(state=SimpleNamespace(task_queue=None))
        monkeypatch.setitem(sys.modules, "integrated_app.app_server", SimpleNamespace(app=fake_app))
        monkeypatch.setattr(ei_mod, "get_registry", lambda: FakeRegistry(None))

        server = MCPServer()
        resp = await server._handle_request(
            make_request("tools/call", call_params("cancel", {"task_id": "t1"}))
        )
        text = json.loads(resp.result["content"][0]["text"])
        assert text["success"] is False


# ── 业务工具：txt2img ────────────────────────────────────────


class TestTxt2ImgTool:
    @pytest.mark.asyncio
    async def test_txt2img_success(self, fake_env):
        server = MCPServer()
        resp = await server._handle_request(make_request("tools/call", call_params("txt2img", {
            "prompt": "a cat",
            "width": 1024,
            "height": 1024,
        })))
        assert resp.error is None
        text = json.loads(resp.result["content"][0]["text"])
        assert text["success"] is True
        assert text["count"] == 1
        assert text["output_paths"] == ["outputs/fake_00001_.png"]
        assert text["engine"] == "z_image_turbo_native"
        # GenerationConfig 已传参
        cfg = fake_env.engine.last_config
        assert cfg.positive_prompt == "a cat"
        assert cfg.width == 1024
        assert cfg.height == 1024

    @pytest.mark.asyncio
    async def test_txt2img_sanitizes_size(self, fake_env):
        server = MCPServer()
        resp = await server._handle_request(make_request("tools/call", call_params("txt2img", {
            "prompt": "a cat",
            "width": 1000,
            "height": 99999,
        })))
        text = json.loads(resp.result["content"][0]["text"])
        assert text["width"] % 16 == 0
        assert text["height"] == 4096

    @pytest.mark.asyncio
    async def test_txt2img_unknown_engine(self, fake_env):
        server = MCPServer()
        resp = await server._handle_request(make_request("tools/call", call_params("txt2img", {
            "prompt": "a cat",
            "engine": "flux3",
        })))
        text = json.loads(resp.result["content"][0]["text"])
        assert text["success"] is False
        assert "flux3" in text["message"]

    @pytest.mark.asyncio
    async def test_txt2img_engine_not_ready_loads_first(self, monkeypatch):
        import integrated_app.config as config_mod
        import integrated_app.engine_interface as ei_mod
        import integrated_app.model_manager as mm_mod
        import integrated_app.model_registry as mr_mod

        engine = FakeEngine(ready=False)
        registry = FakeRegistry(engine)
        manager = FakeManager()

        monkeypatch.setattr(config_mod, "get_config", lambda: FakeConfig())
        monkeypatch.setattr(ei_mod, "get_registry", lambda: registry)
        monkeypatch.setattr(mm_mod, "get_model_manager", lambda: manager)
        monkeypatch.setattr(mr_mod, "get_model_registry", lambda: SimpleNamespace(
            create_engine_instance=lambda **kw: engine,
        ))
        _mock_vram_preflight(monkeypatch)

        server = MCPServer()
        resp = await server._handle_request(make_request("tools/call", call_params("txt2img", {
            "prompt": "a cat",
        })))
        text = json.loads(resp.result["content"][0]["text"])
        assert text["success"] is True
        assert engine.loaded is True
        assert manager.loaded_engines == ["z_image_turbo_native"]
