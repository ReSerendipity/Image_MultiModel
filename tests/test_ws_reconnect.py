"""
tests/test_ws_reconnect.py — WebSocket 断连重连混沌测试

对应 N10: ComfyClient WS 连接中断 → 重连机制验证
使用 Mock 模拟 WS 连接中断，验证 _queue_with_retry 重连逻辑
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrated_app.comfy.client import ComfyClient


class TestWSReconnect:
    """WS 断连重连"""

    @pytest.mark.asyncio
    async def test_ws_closed_returns_none(self):
        """WS 已关闭 → ws_recv 返回 None"""
        client = ComfyClient()

        mock_ws = MagicMock()
        mock_ws.closed = True
        client._ws = mock_ws

        result = await client.ws_recv()
        assert result is None

    @pytest.mark.asyncio
    async def test_ws_connect_after_disconnect(self):
        """断连后重新连接 → 新 WS 连接"""
        client = ComfyClient()

        # Mock HTTP session
        mock_session = MagicMock()
        mock_session.closed = False

        # 第一次 WS 连接成功
        mock_ws1 = AsyncMock()
        mock_ws1.closed = False
        mock_session.ws_connect = AsyncMock(return_value=mock_ws1)

        client._http_session = mock_session

        # 第一次连接
        await client.connect_ws()
        assert client._ws is mock_ws1

        # 模拟断连
        mock_ws1.closed = True

        # 第二次连接（重连）
        mock_ws2 = AsyncMock()
        mock_ws2.closed = False
        mock_session.ws_connect = AsyncMock(return_value=mock_ws2)

        await client.connect_ws()
        assert client._ws is mock_ws2

    @pytest.mark.asyncio
    async def test_ws_recv_text_message(self):
        """WS TEXT 消息 → JSON dict"""
        import aiohttp

        client = ComfyClient()

        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.TEXT
        mock_msg.data = '{"type": "progress", "data": {"value": 5, "max": 10}}'

        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        client._ws = mock_ws

        result = await client.ws_recv()
        assert result is not None
        assert result["type"] == "progress"
        assert result["data"]["value"] == 5

    @pytest.mark.asyncio
    async def test_ws_recv_closed_message(self):
        """WS CLOSED 消息 → None"""
        import aiohttp

        client = ComfyClient()

        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.CLOSED

        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        client._ws = mock_ws

        result = await client.ws_recv()
        assert result is None

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up(self):
        """disconnect → WS + HTTP 均关闭"""
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

    @pytest.mark.asyncio
    async def test_connect_failure_then_retry(self):
        """连接失败 → is_connected=False → 重试可成功"""
        client = ComfyClient()

        # 构建一个 mock session，第一次 get 抛异常，第二次返回 200
        call_count = [0]
        mock_resp_ok = AsyncMock()
        mock_resp_ok.status = 200

        def mock_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # 第一次失败
                raise Exception("Connection refused")
            # 第二次成功
            return AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp_ok),
                __aexit__=AsyncMock(return_value=None),
            )

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(side_effect=mock_get)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            # 第一次连接失败
            with pytest.raises(ConnectionError):
                await client.connect()
            assert client.is_connected is False

            # 第二次连接成功（重试）
            await client.connect()
            assert client.is_connected is True
