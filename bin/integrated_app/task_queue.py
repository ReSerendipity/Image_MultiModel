"""
task_queue.py — 单 Worker 串行任务队列

对应 MASTER_PLAN §4 / 附录 B1/B2: task_queue.py
对应 PRD §7: runtime.task_queue
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


@dataclass
class Task:
    """队列中的任务"""
    task_id: str
    engine: str
    config: dict[str, Any]
    mode: str = "txt2img"  # txt2img | batch
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    progress: int = 0  # 0-100
    phase: str = ""
    result: list[str] | None = None  # 输出文件路径列表
    error: str = ""
    cancel_requested: bool = False
    batch_id: str | None = None  # 批量任务的批次 ID


class TaskQueue:
    """
    单 Worker 串行任务队列。

    特性:
    - 串行执行（GPU 独占，防 OOM）
    - 取消回调（cancel_timeout_s 内生效）
    - 进度推送（通过 SSE）
    - 自动重试（batch.max_retries）
    """

    def __init__(
        self,
        maxsize: int = 100,
        cancel_timeout_s: int = 5,
        max_timeout_s: int = 86400,
    ) -> None:
        self._queue: asyncio.Queue[Task] = asyncio.Queue(maxsize=maxsize)
        self._tasks: dict[str, Task] = {}
        self._worker_task: asyncio.Task | None = None
        self._current_task: Task | None = None
        self._cancel_event = asyncio.Event()
        self._cancel_timeout_s = cancel_timeout_s
        self._max_timeout_s = max_timeout_s
        self._running = False
        self._progress_callbacks: list[Callable[[str, int, str, dict], None]] = []
        self._status_callbacks: list[Callable[[str, TaskStatus, dict | None], None]] = []

    def add_progress_callback(self, cb: Callable[[str, int, str, dict], None]) -> None:
        """注册进度回调（task_id, progress, phase, extra）"""
        self._progress_callbacks.append(cb)

    def add_status_callback(self, cb: Callable[[str, TaskStatus, dict | None], None]) -> None:
        """注册状态变更回调（task_id, status, extra）"""
        self._status_callbacks.append(cb)

    def _notify_progress(self, task_id: str, progress: int, phase: str, extra: dict | None = None) -> None:
        for cb in self._progress_callbacks:
            try:
                cb(task_id, progress, phase, extra or {})
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def _notify_status(self, task_id: str, status: TaskStatus, extra: dict | None = None) -> None:
        for cb in self._status_callbacks:
            try:
                cb(task_id, status, extra or {})
            except Exception as e:
                logger.warning(f"Status callback error: {e}")

    def generate_task_id(self) -> str:
        """生成唯一任务 ID"""
        return uuid.uuid4().hex[:16]

    async def submit(self, task: Task) -> bool:
        """
        提交任务到队列。

        Returns:
            True 如果成功入队，False 如果队列已满
        """
        try:
            self._tasks[task.task_id] = task
            self._queue.put_nowait(task)
            self._notify_status(task.task_id, TaskStatus.PENDING)
            logger.info(f"Task submitted: {task.task_id} ({task.engine})")
            return True
        except asyncio.QueueFull:
            logger.warning(f"Queue full, task rejected: {task.task_id}")
            return False

    async def cancel(self, task_id: str) -> bool:
        """
        取消任务。

        Returns:
            True 如果取消请求已发送
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            self._notify_status(task_id, TaskStatus.CANCELLED)
            return True

        if task.status == TaskStatus.PROCESSING:
            task.cancel_requested = True
            self._cancel_event.set()
            self._notify_progress(task_id, 0, "cancelling...")
            return True

        return False

    async def start(self, worker_func: Callable[[Task], None]) -> None:
        """启动 Worker"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop(worker_func))
        logger.info("TaskQueue worker started")

    async def stop(self) -> None:
        """停止 Worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("TaskQueue worker stopped")

    async def _worker_loop(self, worker_func: Callable[[Task], None]) -> None:
        """主 Worker 循环

        使用 ``get_nowait()`` + ``asyncio.sleep`` 轮询取任务，避免
        ``asyncio.wait_for(queue.get(), timeout=...)`` 在该运行环境下
        超时不触发导致 worker 永久挂起的问题（Known Gotcha #22）。
        """
        logger.info("TaskQueue worker loop started")
        while self._running:
            try:
                task = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.2)
                continue

            if task.status == TaskStatus.CANCELLED:
                continue

            self._current_task = task
            task.status = TaskStatus.PROCESSING
            task.started_at = time.time()
            self._cancel_event.clear()
            self._notify_status(task.task_id, TaskStatus.PROCESSING)

            try:
                # 超时检测
                try:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, worker_func, task),
                        timeout=self._max_timeout_s,
                    )
                except TimeoutError:
                    task.error = f"Task timed out after {self._max_timeout_s}s"
                    task.status = TaskStatus.FAILED

                if task.cancel_requested:
                    task.status = TaskStatus.CANCELLED
                    self._notify_status(task.task_id, TaskStatus.CANCELLED)
                elif task.error:
                    task.status = TaskStatus.FAILED
                    self._notify_status(task.task_id, TaskStatus.FAILED, {"error": task.error})
                else:
                    task.status = TaskStatus.COMPLETED
                    self._notify_status(
                        task.task_id, TaskStatus.COMPLETED,
                        {"result": task.result or []},
                    )

            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.FAILED
                self._notify_status(task.task_id, TaskStatus.FAILED, {"error": str(e)})
                logger.exception(f"Task {task.task_id} failed")

            finally:
                task.completed_at = time.time()
                self._current_task = None
                self._queue.task_done()

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def current_task(self) -> Task | None:
        return self._current_task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())

    def get_queue_status(self) -> dict[str, Any]:
        """获取队列状态摘要"""
        return {
            "queue_size": self.queue_size,
            "current_task": self._current_task.task_id if self._current_task else None,
            "total_tasks": len(self._tasks),
            "running": self._running,
        }
