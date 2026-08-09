"""
comfy/client.py — ComfyUI HTTP + WebSocket 连接池

对应 MASTER_PLAN §4 / PRD §4.1: comfy/client.py
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class ComfyClient:
    """
    ComfyUI HTTP + WebSocket 客户端。

    - HTTP: /prompt, /interrupt, /object_info, /history, /view
    - WS: /ws → 实时进度 + 预览图
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        ws_url: str = "ws://127.0.0.1:8188/ws",
        auth_token: str = "",
        client_id_prefix: str = "img_multimodel_",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url
        self.auth_token = auth_token
        self.client_id = client_id_prefix + uuid.uuid4().hex[:8]
        self._http_session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """建立 HTTP + WS 连接"""
        if self._http_session is None or self._http_session.closed:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = self.auth_token
            self._http_session = aiohttp.ClientSession(
                base_url=self.base_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=300),
            )
        # 测试 HTTP 连接
        try:
            async with self._http_session.get("/system_stats") as resp:
                if resp.status == 200:
                    self._connected = True
                    logger.info(f"ComfyUI HTTP connected: {self.base_url}")
                else:
                    raise ConnectionError(f"ComfyUI HTTP status {resp.status}")
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Cannot connect to ComfyUI at {self.base_url}: {e}")

    async def disconnect(self) -> None:
        """关闭连接"""
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        self._connected = False
        logger.info("ComfyUI client disconnected")

    async def queue_prompt(self, workflow_data: dict[str, Any]) -> str:
        """
        提交工作流到队列。

        Returns:
            prompt_id
        """
        assert self._http_session is not None
        payload = {"prompt": workflow_data, "client_id": self.client_id}
        async with self._http_session.post("/prompt", json=payload) as resp:
            if resp.status != 200:
                try:
                    body = await resp.json()
                except Exception:
                    body = await resp.text()
                raise RuntimeError(f"ComfyUI /prompt error {resp.status}: {body}")
            data = await resp.json()
            prompt_id = data.get("prompt_id", "")
            logger.info(f"ComfyUI prompt queued: {prompt_id}")
            return prompt_id

    async def interrupt(self) -> None:
        """中断当前生成"""
        assert self._http_session is not None
        async with self._http_session.post("/interrupt") as resp:
            logger.info(f"ComfyUI interrupt: status {resp.status}")

    async def get_object_info(self) -> dict[str, Any]:
        """获取所有节点定义（缓存用）"""
        assert self._http_session is not None
        async with self._http_session.get("/object_info") as resp:
            return await resp.json()

    async def get_history(self, prompt_id: str = "") -> dict[str, Any]:
        """获取执行历史；prompt_id 为空时返回全量历史"""
        assert self._http_session is not None
        path = f"/history/{prompt_id}" if prompt_id else "/history"
        async with self._http_session.get(path) as resp:
            return await resp.json()

    async def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """获取输出图片"""
        assert self._http_session is not None
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        async with self._http_session.get("/view", params=params) as resp:
            return await resp.read()

    async def connect_ws(self) -> None:
        """建立 WebSocket 连接（需带 clientId 才会收到本任务的执行事件）"""
        assert self._http_session is not None
        ws_url = self.ws_url
        sep = "&" if "?" in ws_url else "?"
        self._ws = await self._http_session.ws_connect(f"{ws_url}{sep}clientId={self.client_id}")
        logger.info(f"ComfyUI WS connected: {ws_url}")

    async def ws_recv(self) -> dict[str, Any] | None:
        """接收一条 WS 消息"""
        if self._ws is None or self._ws.closed:
            return None
        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            return json.loads(msg.data)
        elif msg.type == aiohttp.WSMsgType.CLOSED:
            logger.warning("ComfyUI WS closed")
            return None
        return None

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if self._http_session is None or self._http_session.closed:
                return False
            async with self._http_session.get("/system_stats") as resp:
                return resp.status == 200
        except Exception:
            return False
