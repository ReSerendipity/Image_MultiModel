"""
tests/test_comfy_client_extra.py — ComfyClient 额外方法测试

对应覆盖率提升: comfy/client.py 60% → 目标 ≥80%
覆盖：get_history, get_image, get_object_info, connect_ws, free, ws_recv BINARY
"""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from integrated_app.comfy.client import ComfyClient


class TestComfyClientGetHistory:
    """get_history()"""

    @pytest.mark.asyncio
    async def test_get_history_with_prompt_id(self):
        client = ComfyClient()
        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value={"test-prompt": {"outputs": {}}})

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))
        client._http_session = mock_session

        result = await client.get_history("test-prompt")
        assert "test-prompt" in result

    @pytest.mark.asyncio
    async def test_get_history_all(self):
        """无 prompt_id → 全量历史"""
        client = ComfyClient()
        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value={"p1": {}, "p2": {}})

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))
        client._http_session = mock_session

        result = await client.get_history()
        assert len(result) == 2


class TestComfyClientGetImage:
    """get_image()"""

    @pytest.mark.asyncio
    async def test_get_image_success(self):
        client = ComfyClient()
        mock_resp = AsyncMock()
        mock_resp.read = AsyncMock(return_value=b"fake-png-data")

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))
        client._http_session = mock_session

        data = await client.get_image("output.png", subfolder="test", folder_type="output")
        assert data == b"fake-png-data"


class TestComfyClientGetObjectInfo:
    """get_object_info()"""

    @pytest.mark.asyncio
    async def test_get_object_info(self):
        client = ComfyClient()
        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value={"CheckpointLoader": {}})

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=None),
        ))
        client._http_session = mock_session

        result = await client.get_object_info()
        assert "CheckpointLoader" in result


class TestComfyClientFree:
    """free()"""

    @pytest.mark.asyncio
    async def test_free_calls_post(self):
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

        await client.free(free_memory=True)
        mock_session.post.assert_called_once()


class TestComfyClientConnectWs:
    """connect_ws()"""

    @pytest.mark.asyncio
    async def test_connect_ws_success(self):
        client = ComfyClient()
        mock_ws = AsyncMock()
        mock_ws.closed = False

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.ws_connect = AsyncMock(return_value=mock_ws)
        client._http_session = mock_session

        await client.connect_ws()
        assert client._ws is mock_ws


class TestComfyClientWsRecvBinary:
    """ws_recv() BINARY 预览图"""

    @pytest.mark.asyncio
    async def test_ws_recv_binary_preview_jpg(self):
        """BINARY 消息 → b_preview 解析"""
        client = ComfyClient()

        # 构造 b_preview 二进制: [type=1][format=1(jpg)][size][image data]
        header = struct.pack("<HHI", 1, 1, 5)
        image_data = b"\xff\xd8\xff\xe0\x00"  # JPEG SOI + marker
        binary_data = header + image_data

        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.BINARY
        mock_msg.data = binary_data

        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        client._ws = mock_ws
        result = await client.ws_recv()

        assert result is not None
        assert result["type"] == "b_preview"
        assert result["data"]["format"] == "jpg"
        assert "b64" in result["data"]

    @pytest.mark.asyncio
    async def test_ws_recv_binary_too_short(self):
        """BINARY 消息过短 → None"""
        client = ComfyClient()

        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.BINARY
        mock_msg.data = b"\x01\x02"  # 太短

        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_ws.receive = AsyncMock(return_value=mock_msg)
        client._ws = mock_ws

        result = await client.ws_recv()
        assert result is None

    @pytest.mark.asyncio
    async def test_ws_recv_unknown_type(self):
        """未知 WS 消息类型 → None"""
        client = ComfyClient()

        mock_msg = MagicMock()
        mock_msg.type = aiohttp.WSMsgType.ERROR

        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_ws.receive = AsyncMock(return_value=mock_msg)
        client._ws = mock_ws

        result = await client.ws_recv()
        assert result is None

    @pytest.mark.asyncio
    async def test_ws_recv_no_ws(self):
        """无 WS 连接 → None"""
        client = ComfyClient()
        result = await client.ws_recv()
        assert result is None
