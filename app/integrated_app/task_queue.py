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
from concurrent.futures import ThreadPoolExecutor
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
    attempts: int = 0  # 已重试次数（P2-6 自动重试）


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
        max_retries: int = 0,
        retry_base_delay_s: float = 1.0,
        retry_max_delay_s: float = 30.0,
        shutdown_drain_timeout_s: float = 30.0,
    ) -> None:
        self._queue: asyncio.Queue[Task] = asyncio.Queue(maxsize=maxsize)
        self._tasks: dict[str, Task] = {}
        self._worker_task: asyncio.Task | None = None
        self._current_task: Task | None = None
        self._cancel_event = asyncio.Event()
        self._cancel_timeout_s = cancel_timeout_s
        self._max_timeout_s = max_timeout_s
        self._max_retries = max(0, int(max_retries))
        self._retry_base_delay_s = float(retry_base_delay_s)
        self._retry_max_delay_s = float(retry_max_delay_s)
        # 关闭时等待在飞行 worker 线程的最长时间（详见 stop() 注释）
        self._shutdown_drain_timeout_s = float(shutdown_drain_timeout_s)
        self._running = False
        # 独占线程池：stop() 需排空其中在飞行的 worker_func
        self._executor: ThreadPoolExecutor | None = None
        # 在飞行任务（run_in_executor 返回的 asyncio.Future，映射线程池里的 worker_func）
        self._inflight: asyncio.Future | None = None
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
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="taskqueue-worker"
        )
        self._worker_task = asyncio.create_task(self._worker_loop(worker_func))
        logger.info("TaskQueue worker started")

    async def stop(self, drain_timeout_s: float | None = None) -> None:
        """停止 Worker，并**等待在飞行的 worker 线程真正退出**。

        ⚠️ 为什么必须排空（Known Gotcha）：``worker_func`` 跑在线程池里，
        ``asyncio`` 的 cancel() 只能取消协程，**杀不掉已经在跑的操作系统线程**。
        若 stop() 直接返回，上层 ``lifespan`` 会立刻 ``history_db.close()``，
        而 worker 线程随后调用 ``history_db.add_output()`` —— 拿到的是已被另一
        线程关闭的 sqlite 连接，在 C 扩展层 **段错误**（整个解释器崩溃，pytest
        只报 ``worker 'gw0' crashed``，没有任何 Python 栈）。

        因此这里必须等 ``_inflight`` 结束（上限 ``drain_timeout_s``），
        保证调用方返回后不会再有任何线程写库；超时只能记日志后继续——
        此时由 ``HistoryDB`` 的关闭护栏把误用变成明确异常，而不是崩溃。
        """
        timeout = (
            self._shutdown_drain_timeout_s if drain_timeout_s is None else float(drain_timeout_s)
        )
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001 - stop 不应因 worker 异常中断关闭
                logger.warning(f"TaskQueue worker raised during stop: {e}")
            self._worker_task = None

        inflight = self._inflight
        if inflight is not None and not inflight.done():
            logger.info(
                "TaskQueue: 等待在飞行的 worker 线程结束（最多 %.1fs）…", timeout
            )
            try:
                await asyncio.wait_for(asyncio.shield(inflight), timeout=timeout)
                logger.info("TaskQueue: 在飞行 worker 线程已结束")
            except TimeoutError:  # asyncio.TimeoutError 自 3.11 起即内置 TimeoutError
                logger.warning(
                    "TaskQueue: 等待在飞行 worker 线程超时（%.1fs），"
                    "关闭流程继续，但数据库可能仍被写入",
                    timeout,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"TaskQueue: 在飞行 worker 线程异常结束: {e}")

        self._shutdown_executor()
        logger.info("TaskQueue worker stopped")

    def _shutdown_executor(self) -> None:
        """关闭独占线程池（非阻塞；在飞行任务已在上方排空）。"""
        executor, self._executor = self._executor, None
        if executor is None:
            return
        try:
            # 已在飞行任务排空后 shutdown 立即返回；未排空时丢弃排队任务，
            # 运行中的线程由其在结束后自行退出（线程无法被强制杀掉）。
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - Python < 3.9 无 cancel_futures
            executor.shutdown(wait=False)

    def _forget_inflight(self, fut: asyncio.Future) -> None:
        """在飞行任务结束后清理引用（供 add_done_callback 使用）。"""
        if self._inflight is fut:
            self._inflight = None

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
                # 超时检测（worker 异常也在此捕获，确保下方状态判定/重试逻辑统一执行）
                loop = asyncio.get_running_loop()
                inflight = loop.run_in_executor(self._executor, worker_func, task)
                # 记录在飞行任务：stop() 需要 await 它才能真正排空线程，
                # asyncio 的 cancel() 对已提交进线程池的任务无效。
                self._inflight = inflight
                inflight.add_done_callback(self._forget_inflight)
                try:
                    # shield：超时只结束等待，不取消底层 future——线程无法被取消，
                    # 取消 future 只会让 stop() 失去排空它的句柄。
                    await asyncio.wait_for(
                        asyncio.shield(inflight),
                        timeout=self._max_timeout_s,
                    )
                except TimeoutError:
                    task.error = f"Task timed out after {self._max_timeout_s}s"
                except Exception as e:  # worker 执行抛错（含线程池内异常）
                    task.error = str(e)

                if task.cancel_requested:
                    task.status = TaskStatus.CANCELLED
                    self._notify_status(task.task_id, TaskStatus.CANCELLED)
                elif task.error:
                    # P2-6 自动重试：尚未达到上限且非用户取消的任务，按指数退避重新入队
                    if task.attempts < self._max_retries:
                        task.attempts += 1
                        delay = min(
                            self._retry_base_delay_s * (2 ** (task.attempts - 1)),
                            self._retry_max_delay_s,
                        )
                        logger.warning(
                            "Task %s failed (attempt %d/%d), retrying in %.1fs: %s",
                            task.task_id,
                            task.attempts,
                            self._max_retries,
                            delay,
                            task.error,
                        )
                        task.status = TaskStatus.PENDING
                        task.error = ""
                        task.started_at = 0.0
                        task.progress = 0
                        self._notify_status(
                            task.task_id,
                            TaskStatus.PENDING,
                            {"retry": task.attempts, "retry_delay_s": delay},
                        )
                        await asyncio.sleep(delay)
                        await self._queue.put(task)
                    else:
                        task.status = TaskStatus.FAILED
                        self._notify_status(task.task_id, TaskStatus.FAILED, {"error": task.error})
                else:
                    task.status = TaskStatus.COMPLETED
                    self._notify_status(
                        task.task_id,
                        TaskStatus.COMPLETED,
                        {"result": task.result or []},
                    )

            except Exception as e:
                # 状态判定/重试编排自身的兜底异常（极少见）
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
