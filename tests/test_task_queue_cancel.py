"""
test_task_queue_cancel.py — 取消 → GPU 释放 ≤5s（Mock）

对应 AUDIT_REPORT_2.0 Y2: test_task_queue_cancel.py
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

from integrated_app.task_queue import Task, TaskQueue, TaskStatus


@pytest.fixture
def task_queue():
    return TaskQueue(maxsize=10, cancel_timeout_s=5)


class TestTaskQueueCancel:
    """取消 → GPU 释放 ≤5s"""

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self, task_queue):
        """取消排队中的任务"""
        task = Task(
            task_id="test-cancel-1",
            engine="test",
            config={},
        )
        await task_queue.submit(task)
        assert task.status == TaskStatus.PENDING

        success = await task_queue.cancel("test-cancel-1")
        assert success is True
        assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, task_queue):
        """取消不存在的任务返回 False"""
        success = await task_queue.cancel("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_cancel_processing_task(self, task_queue):
        """取消正在处理的任务（Mock worker）"""
        cancel_event = asyncio.Event()

        def mock_worker(task):
            # 模拟长时间运行
            start = time.time()
            while not task.cancel_requested and time.time() - start < 10:
                time.sleep(0.1)
            if task.cancel_requested:
                task.status = TaskStatus.CANCELLED
            else:
                task.status = TaskStatus.COMPLETED

        await task_queue.start(mock_worker)
        try:
            task = Task(
                task_id="test-cancel-2",
                engine="test",
                config={},
            )
            await task_queue.submit(task)

            # 等待任务开始处理
            await asyncio.sleep(0.3)
            assert task.status == TaskStatus.PROCESSING

            # 取消
            cancel_start = time.time()
            success = await task_queue.cancel("test-cancel-2")
            cancel_duration = time.time() - cancel_start

            assert success is True
            assert cancel_duration <= 5.0, f"Cancel took {cancel_duration}s, expected ≤5s"

        finally:
            await task_queue.stop()

    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, task_queue):
        """队列满时拒绝新任务"""
        small_queue = TaskQueue(maxsize=1)
        t1 = Task(task_id="q1", engine="test", config={})
        t2 = Task(task_id="q2", engine="test", config={})

        await small_queue.submit(t1)
        success = await small_queue.submit(t2)
        assert success is False, "Should reject when queue is full"

    @pytest.mark.asyncio
    async def test_task_status_callback(self, task_queue):
        """状态变更回调被触发"""
        statuses = []

        def callback(task_id, status, extra=None):
            statuses.append((task_id, status))

        task_queue.add_status_callback(callback)

        task = Task(task_id="cb-test", engine="test", config={})
        await task_queue.submit(task)
        await task_queue.cancel("cb-test")

        # 至少有 PENDING 和 CANCELLED 状态
        assert len(statuses) >= 2
        assert any(s == TaskStatus.PENDING for _, s in statuses)
        assert any(s == TaskStatus.CANCELLED for _, s in statuses)

    @pytest.mark.asyncio
    async def test_get_queue_status(self, task_queue):
        """队列状态摘要"""
        status = task_queue.get_queue_status()
        assert "queue_size" in status
        assert "total_tasks" in status
        assert "running" in status
