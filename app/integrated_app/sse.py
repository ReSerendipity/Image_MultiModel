"""
sse.py — SSE 单连接事件总线

对应 MASTER_PLAN §5.2: SSE（单连接事件总线，附录 C2）
事件类型: task_status / preview / model_status / gpu_status / queue_status
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """SSE 事件"""
    event: str  # 事件类型
    data: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    retry: int | None = None

    def format(self) -> str:
        """格式化为 SSE 文本"""
        lines = []
        if self.id:
            lines.append(f"id: {self.id}")
        if self.event:
            lines.append(f"event: {self.event}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        lines.append(f"data: {json.dumps(self.data, ensure_ascii=False)}")
        return "\n".join(lines) + "\n\n"


class SSEBus:
    """
    SSE 事件总线（单连接推送）。

    前端只建一个 EventSource，所有事件类型通过 event 字段分派。
    """

    def __init__(
        self,
        heartbeat_interval_s: int = 30,
        max_duration_s: int = 3600,
    ) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._heartbeat_interval = heartbeat_interval_s
        self._max_duration = max_duration_s
        self._running = False

    async def subscribe(self) -> asyncio.Queue:
        """订阅 SSE 事件流，返回一个 Queue"""
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        logger.info(f"SSE subscriber added (total: {len(self._subscribers)})")
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """取消订阅"""
        self._subscribers.discard(q)
        logger.info(f"SSE subscriber removed (total: {len(self._subscribers)})")

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        """发布事件到所有订阅者"""
        sse_event = SSEEvent(event=event, data=data, id=str(int(time.time() * 1000)))
        msg = sse_event.format()

        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                logger.warning("SSE queue full, dropping event")
                # 丢弃最旧的消息
                try:
                    q.get_nowait()
                    q.put_nowait(msg)
                except asyncio.QueueEmpty:
                    pass

    async def start_heartbeat(self) -> None:
        """启动心跳（防止连接超时）"""
        self._running = True
        while self._running:
            await asyncio.sleep(self._heartbeat_interval)
            await self.publish("heartbeat", {"timestamp": time.time()})

    def stop(self) -> None:
        self._running = False

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# ── 全局单例 ──────────────────────────────────────────────────
_global_sse: SSEBus | None = None


def get_sse_bus() -> SSEBus:
    global _global_sse
    if _global_sse is None:
        _global_sse = SSEBus()
    return _global_sse
