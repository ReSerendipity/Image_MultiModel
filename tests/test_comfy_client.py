"""
tests/test_comfy_client.py — ComfyUI HTTP+WebSocket 客户端 Mock 测试

对应 TEST_AUDIT_REPORT P0-11: ComfyClient 零测试
使用 unittest.mock.AsyncMock 隔离外部 HTTP/WS 依赖
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrated_app.comfy.client import ComfyClient


class TestComfyClientInit:
    """ComfyClient 初始化"""

    def test_default_config(self):
        client = ComfyClient()
        assert client.base_url == "http://127.0.0.1:8188"
        assert client.ws_url == "ws://127.0.0.1:8188/ws"
        assert client.is_connected is False

    def test_custom_config(self):
        client = ComfyClient(
            base_url="http://192.168.1.100:9999",
            ws_url="ws://192.168.1.100:9999/ws",
            auth_token="my-secret-token",
        )
        assert client.base_url == "http://192.168.1.100:9999"
        assert client.ws_url == "ws://192.168.1.100:9999/ws"
        assert client.auth_token == "my-secret-token"
        assert client.client_id.startswith("img_multimodel_")

    def test_base_url_trailing_slash_stripped(self):
        client = ComfyClient(base_url="http://localhost:8188/")
        assert client.base_url == "http://localhost:8188"


class TestComfyClientConnect:
    """ComfyClient.connect() HTTP 连接"""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """成功连接"""
        client = ComfyClient()

        # Mock aiohttp.ClientSession
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_session.closed = False

        with patch("aiohttp.ClientSession", return_value=mock_session):
            await client.connect()

        assert client.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_failure_raises(self):
        """连接失败抛出 ConnectionError"""
        client = ComfyClient()

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(side_effect=Exception("Connection refused"))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ConnectionError, match="Cannot connect to ComfyUI"):
                await client.connect()

        assert client.is_connected is False


class TestComfyClientQueuePrompt:
    """ComfyClient.queue_prompt() 提交工作流"""

    @pytest.mark.asyncio
    async def test_queue_prompt_success(self):
        """成功提交 → 返回 prompt_id"""
        client = ComfyClient()

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"prompt_id": "test-prompt-123"})

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))

        client._http_session = mock_session

        workflow = {"nodes": [{"id": 1}]}
        prompt_id = await client.queue_prompt(workflow)

        assert prompt_id == "test-prompt-123"

    @pytest.mark.asyncio
    async def test_queue_prompt_error_status(self):
        """ComfyUI 返回错误状态 → RuntimeError"""
        client = ComfyClient()

        mock_resp = AsyncMock()
        mock_resp.status = 400
        mock_resp.json = AsyncMock(return_value={"error": "bad workflow"})

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))

        client._http_session = mock_session

        with pytest.raises(RuntimeError, match="ComfyUI /prompt error"):
            await client.queue_prompt({"nodes": []})


class TestComfyClientInterrupt:
    """ComfyClient.interrupt() 中断"""

    @pytest.mark.asyncio
    async def test_interrupt_calls_post(self):
        """interrupt → POST /interrupt"""
        client = ComfyClient()

        mock_resp = AsyncMock()
        mock_resp.status = 200

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))

        client._http_session = mock_session
        await client.interrupt()


class TestComfyClientHealthCheck:
    """ComfyClient.health_check()"""

    @pytest.mark.asyncio
    async def test_health_check_true(self):
        """健康检查成功 → True"""
        client = ComfyClient()

        mock_resp = AsyncMock()
        mock_resp.status = 200

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))

        client._http_session = mock_session
        result = await client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_no_session(self):
        """无 session → False"""
        client = ComfyClient()
        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """异常 → False"""
        client = ComfyClient()

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(side_effect=Exception("Network error"))

        client._http_session = mock_session
        result = await client.health_check()
        assert result is False


class TestComfyClientDisconnect:
    """ComfyClient.disconnect()"""

    @pytest.mark.asyncio
    async def test_disconnect_closes_connections(self):
        """disconnect → 关闭 WS + HTTP"""
        client = ComfyClient()

        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_session = AsyncMock()
        mock_session.closed = False

        client._ws = mock_ws
        client._http_session = mock_session
        client._connected = True

        await client.disconnect()

        assert client.is_connected is False
        mock_ws.close.assert_called_once()
        mock_session.close.assert_called_once()
