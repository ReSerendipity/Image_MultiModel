"""
tests/test_sse.py — SSE 事件总线测试

对应 TEST_AUDIT_REPORT P1-1: SSEBus 零测试
"""

from __future__ import annotations

import asyncio
import json

import pytest

from integrated_app.sse import SSEBus, SSEEvent, get_sse_bus


class TestSSEEvent:
    """SSE 事件格式化"""

    def test_basic_format(self):
        """基本 SSE 格式"""
        evt = SSEEvent(event="test", data={"msg": "hello"})
        formatted = evt.format()
        assert "event: test" in formatted
        assert "data:" in formatted
        assert '"msg": "hello"' in formatted
        assert formatted.endswith("\n\n")

    def test_format_with_id(self):
        """带 id 的 SSE 格式"""
        evt = SSEEvent(event="test", data={}, id="123")
        formatted = evt.format()
        assert "id: 123" in formatted

    def test_format_with_retry(self):
        """带 retry 的 SSE 格式"""
        evt = SSEEvent(event="test", data={}, retry=5000)
        formatted = evt.format()
        assert "retry: 5000" in formatted

    def test_unicode_data(self):
        """中文数据正确序列化"""
        evt = SSEEvent(event="test", data={"msg": "你好世界"})
        formatted = evt.format()
        assert "你好世界" in formatted


class TestSSEBusSubscribe:
    """SSEBus 订阅/取消订阅"""

    @pytest.mark.asyncio
    async def test_subscribe_returns_queue(self):
        bus = SSEBus()
        q = await bus.subscribe()
        assert isinstance(q, asyncio.Queue)
        assert bus.subscriber_count == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = SSEBus()
        q1 = await bus.subscribe()
        q2 = await bus.subscribe()
        assert bus.subscriber_count == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = SSEBus()
        q = await bus.subscribe()
        assert bus.subscriber_count == 1
        bus.unsubscribe(q)
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self):
        """取消不存在的订阅 → 不报错"""
        bus = SSEBus()
        fake_q = asyncio.Queue()
        bus.unsubscribe(fake_q)
        assert bus.subscriber_count == 0


class TestSSEBusPublish:
    """SSEBus 发布事件"""

    @pytest.mark.asyncio
    async def test_publish_to_single_subscriber(self):
        bus = SSEBus()
        q = await bus.subscribe()

        await bus.publish("task_status", {"task_id": "test-001", "status": "completed"})

        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert "task_status" in msg
        assert "test-001" in msg
        assert "completed" in msg

    @pytest.mark.asyncio
    async def test_publish_to_multiple_subscribers(self):
        """广播到多个订阅者"""
        bus = SSEBus()
        q1 = await bus.subscribe()
        q2 = await bus.subscribe()

        await bus.publish("test", {"msg": "broadcast"})

        msg1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        msg2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert "broadcast" in msg1
        assert "broadcast" in msg2

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self):
        """无订阅者时发布 → 不报错"""
        bus = SSEBus()
        await bus.publish("test", {"msg": "nobody"})
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_publish_includes_id(self):
        """发布的事件包含 id"""
        bus = SSEBus()
        q = await bus.subscribe()

        await bus.publish("test", {"msg": "has-id"})
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert "id:" in msg


class TestSSEBusHeartbeat:
    """SSEBus 心跳"""

    @pytest.mark.asyncio
    async def test_heartbeat_sends_events(self):
        """心跳发送 heartbeat 事件"""
        bus = SSEBus(heartbeat_interval_s=0.1)
        q = await bus.subscribe()

        # 启动心跳
        task = asyncio.create_task(bus.start_heartbeat())
        await asyncio.sleep(0.25)

        # 应收到至少 1 条心跳
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert "heartbeat" in msg

        bus.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def test_stop_heartbeat(self):
        """stop → _running=False"""
        bus = SSEBus()
        bus.stop()
        assert bus._running is False


class TestSSEBusGlobal:
    """全局 SSEBus 单例"""

    def test_get_sse_bus_singleton(self):
        bus1 = get_sse_bus()
        bus2 = get_sse_bus()
        assert bus1 is bus2
