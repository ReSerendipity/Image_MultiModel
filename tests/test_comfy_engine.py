"""
tests/test_comfy_engine.py — ComfyEngine 推理流程 Mock 测试

对应 TEST_AUDIT_REPORT P0-12: ComfyEngine 零测试
使用注入的 Mock ComfyClient 验证完整推理流程
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrated_app.comfy.engine import ComfyEngine
from integrated_app.engine_interface import GenerationConfig


@pytest.fixture
def mock_client():
    """Mock ComfyClient"""
    client = AsyncMock()
    client.is_connected = True
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.connect_ws = AsyncMock()
    client.queue_prompt = AsyncMock(return_value="test-prompt-id")
    client.interrupt = AsyncMock()
    client.ws_recv = AsyncMock(return_value=None)
    client.get_history = AsyncMock(return_value={})
    client.get_image = AsyncMock(return_value=b"fake-image-data")
    return client


@pytest.fixture
def engine(mock_client):
    """带 Mock client 的 ComfyEngine"""
    return ComfyEngine(
        name="test_engine",
        display_name="Test Engine",
        config={
            "workflow_file": "workflows/Flux.2_Klein-9B-Distilled.json",
            "parameter_schema": "schemas/flux2_klein_9b_distilled.yaml",
            "comfy_backend_preference": "local",
        },
        client=mock_client,
    )


class TestComfyEngineInit:
    """ComfyEngine 初始化"""

    def test_name_and_display_name(self):
        e = ComfyEngine(name="flux", display_name="FLUX", display_name_en="FLUX EN")
        assert e.name == "flux"
        assert e.display_name == "FLUX"

    def test_default_display_name_falls_back_to_name(self):
        e = ComfyEngine(name="test")
        assert e.display_name == "test"

    def test_not_ready_before_load(self):
        e = ComfyEngine(name="test")
        assert e.is_ready() is False

    def test_client_injection(self, mock_client):
        e = ComfyEngine(name="test", client=mock_client)
        assert e._client is mock_client


class TestComfyEngineLoad:
    """ComfyEngine.load()"""

    @pytest.mark.asyncio
    async def test_load_success(self, engine, mock_client):
        """成功加载 → is_ready=True"""
        with patch("integrated_app.comfy.engine.get_config") as mock_get_config:
            mock_cfg = MagicMock()
            mock_cfg.comfy.backends.get.return_value = MagicMock(
                base_url="http://127.0.0.1:8188",
                ws_url="ws://127.0.0.1:8188/ws",
                auth_token="",
                client_id_prefix="test_",
            )
            mock_cfg.project_root = "."
            mock_get_config.return_value = mock_cfg

            await engine.load()

        assert engine.is_ready() is True
        mock_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_with_progress_callback(self, engine, mock_client):
        """加载时调用进度回调"""
        progress_calls = []

        def on_progress(pct, phase, extra):
            progress_calls.append((pct, phase))

        with patch("integrated_app.comfy.engine.get_config") as mock_get_config:
            mock_cfg = MagicMock()
            mock_cfg.comfy.backends.get.return_value = MagicMock(
                base_url="http://127.0.0.1:8188",
                ws_url="ws://127.0.0.1:8188/ws",
                auth_token="",
                client_id_prefix="test_",
            )
            mock_cfg.project_root = "."
            mock_get_config.return_value = mock_cfg

            await engine.load(on_progress=on_progress)

        assert len(progress_calls) >= 2
        assert progress_calls[0][0] == 10  # 首次 10%
        assert progress_calls[-1][0] == 100  # 最后 100%


class TestComfyEngineInferTxt2img:
    """ComfyEngine.infer_txt2img() 推理流程"""

    @pytest.mark.asyncio
    async def test_infer_not_ready_raises(self, engine):
        """未加载 → RuntimeError"""
        config = GenerationConfig()
        with pytest.raises(RuntimeError, match="Engine not ready"):
            await engine.infer_txt2img(config)

    @pytest.mark.asyncio
    async def test_infer_success_flow(self, engine, mock_client):
        """完整推理流程：patch → queue → WS → fetch outputs"""
        engine._ready = True

        # Mock WorkflowManager
        mock_wf_mgr = MagicMock()
        mock_wf_mgr.patch.return_value = {"nodes": []}
        engine._workflow_mgr = mock_wf_mgr

        # Mock WS 消息序列：progress → executing → execution_success
        ws_messages = [
            {"type": "progress", "data": {"value": 5, "max": 10}},
            {"type": "executing", "data": {"node_id": "node-1"}},
            {"type": "executed", "data": {"images": [{"filename": "test.png"}]}},
            {"type": "execution_success", "data": {}},
            None,  # WS closed
        ]
        mock_client.ws_recv = AsyncMock(side_effect=ws_messages)

        # Mock history → outputs
        mock_client.get_history = AsyncMock(return_value={
            "test-prompt-id": {
                "outputs": {
                    "node-9": {
                        "images": [{"filename": "output.png", "subfolder": ""}],
                    },
                },
            },
        })

        config = GenerationConfig(positive_prompt="test", seed=42)

        with patch("integrated_app.comfy.engine.get_config") as mock_get_config:
            mock_cfg = MagicMock()
            mock_cfg.project_root = "."
            mock_cfg.output.base_dir = "outputs"
            mock_get_config.return_value = mock_cfg

            outputs = await engine.infer_txt2img(config)

        # 验证调用链
        mock_wf_mgr.patch.assert_called_once_with(config)
        mock_client.queue_prompt.assert_called_once()
        mock_client.connect_ws.assert_called_once()
        mock_client.get_history.assert_called_once_with("test-prompt-id")

        # 验证输出
        assert len(outputs) == 1
        assert "output.png" in outputs[0]

    @pytest.mark.asyncio
    async def test_infer_execution_error_raises(self, engine, mock_client):
        """ComfyUI 执行错误 → RuntimeError"""
        engine._ready = True

        mock_wf_mgr = MagicMock()
        mock_wf_mgr.patch.return_value = {"nodes": []}
        engine._workflow_mgr = mock_wf_mgr

        # WS 返回 execution_error
        mock_client.ws_recv = AsyncMock(side_effect=[
            {"type": "execution_error", "data": {"error": "node failed"}},
        ])

        config = GenerationConfig()

        with pytest.raises(RuntimeError, match="ComfyUI execution error"):
            await engine.infer_txt2img(config)

    @pytest.mark.asyncio
    async def test_infer_cancel_raises(self, engine, mock_client):
        """取消推理 → CancelledError"""
        engine._ready = True

        mock_wf_mgr = MagicMock()
        mock_wf_mgr.patch.return_value = {"nodes": []}
        engine._workflow_mgr = mock_wf_mgr

        mock_client.ws_recv = AsyncMock(side_effect=[
            {"type": "progress", "data": {"value": 1, "max": 10}},
            {"type": "execution_interrupted", "data": {}},
        ])

        config = GenerationConfig()

        with pytest.raises(asyncio.CancelledError):
            await engine.infer_txt2img(config)


class TestComfyEngineCancel:
    """ComfyEngine.cancel()"""

    @pytest.mark.asyncio
    async def test_cancel_sets_flag(self, engine, mock_client):
        """cancel → 设置 _cancel_requested + 调用 client.interrupt"""
        await engine.cancel()
        assert engine._cancel_requested is True
        mock_client.interrupt.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_no_client(self):
        """cancel 无 client → 仅设置 flag"""
        engine = ComfyEngine(name="test")
        await engine.cancel()
        assert engine._cancel_requested is True


class TestComfyEngineUnload:
    """ComfyEngine.unload()"""

    @pytest.mark.asyncio
    async def test_unload_disconnects_client(self, engine, mock_client):
        """unload → 关闭 client 连接"""
        engine._ready = True
        await engine.unload()
        assert engine.is_ready() is False
        mock_client.disconnect.assert_called_once()
        assert engine._client is None

    @pytest.mark.asyncio
    async def test_unload_no_client(self):
        """unload 无 client → 不报错"""
        engine = ComfyEngine(name="test")
        await engine.unload()
        assert engine.is_ready() is False
