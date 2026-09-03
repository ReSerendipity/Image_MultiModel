"""
tests/test_shutdown_close_race.py — 关闭期 SQLite use-after-close 回归测试

背景（2026-09-03 首次发现，见 docs/agents/GOTCHAS.md）：
CI 的 ``Test + Coverage`` 偶发直接 ``Fatal Python error: Segmentation fault``，
pytest 只报 ``worker 'gw0' crashed``，没有任何 Python 栈。根因是关闭顺序竞态：

1. ``TaskQueue._worker_loop`` 把 ``worker_func`` 丢进线程池执行；
2. ``TaskQueue.stop()`` 只 ``cancel()`` 了 asyncio 协程，**杀不掉已提交的线程**，
   于是 stop() 立刻返回；
3. ``lifespan`` 随即 ``history_db.close()`` 关掉 SQLite 连接；
4. worker 线程紧接着 ``history_db.add_output()``，用的是**已被另一线程关闭的连接**
   → sqlite3 C 扩展 use-after-close → 解释器级崩溃。

本文件锁定三件事：
- 已关闭的连接被误用时抛明确的 ``HistoryDBClosedError``，而不是段错误；
- ``HistoryDB.close()`` 与数据库调用互斥；
- ``TaskQueue.stop()`` 返回后，在飞行的 worker 线程**一定已经结束**。
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from app.integrated_app.history_db import HistoryDB, HistoryDBClosedError
from app.integrated_app.task_queue import Task, TaskQueue, TaskStatus


# ════════════════════════════════════════════════════════════
# 1. 连接关闭护栏
# ════════════════════════════════════════════════════════════
class TestClosedConnectionGuard:
    """close() 之后再写库：抛异常，不崩溃"""

    def test_held_connection_raises_after_close(self, tmp_path):
        """持有的连接句柄在 close() 后使用 → HistoryDBClosedError（非段错误）"""
        db = HistoryDB(tmp_path / "guard.db")
        conn = db.conn  # 模拟 worker 线程已取到连接
        conn.execute("SELECT 1")

        db.close()

        with pytest.raises(HistoryDBClosedError):
            conn.execute("SELECT 1")

    def test_close_is_idempotent(self, tmp_path):
        """重复 close() 不抛异常"""
        db = HistoryDB(tmp_path / "guard2.db")
        db.close()
        db.close()  # 幂等
        assert db._conn is None

    def test_conn_property_returns_guard_not_raw_connection(self, tmp_path):
        """对外只暴露护栏代理，拿不到裸 sqlite3 连接"""
        import sqlite3

        db = HistoryDB(tmp_path / "guard3.db")
        try:
            assert not isinstance(db.conn, sqlite3.Connection)
            assert hasattr(db.conn, "execute")
            # row_factory 等属性仍能正常转发
            assert db.conn.row_factory is sqlite3.Row
        finally:
            db.close()

    def test_concurrent_write_during_close_does_not_crash(self, tmp_path):
        """一边写库一边 close()：不会段错误，只允许成功或 HistoryDBClosedError"""
        db = HistoryDB(tmp_path / "guard4.db")
        db.create_task(task_id="race-1", engine="test")
        errors: list[BaseException] = []
        stop = threading.Event()

        def writer() -> None:
            while not stop.is_set():
                try:
                    db.add_output("race-1", "out.png")
                except HistoryDBClosedError:
                    return
                except Exception as e:  # noqa: BLE001
                    errors.append(e)
                    return
                time.sleep(0.001)

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        time.sleep(0.05)
        db.close()  # 与写库线程竞争
        stop.set()
        t.join(timeout=5)

        assert not errors, f"写库线程出现非预期异常: {errors}"
        assert not t.is_alive()


# ════════════════════════════════════════════════════════════
# 2. TaskQueue.stop() 必须排空在飞行线程
# ════════════════════════════════════════════════════════════
class TestTaskQueueStopDrainsWorker:
    """stop() 返回后，worker 线程不得仍在运行"""

    def test_stop_waits_for_inflight_worker(self):
        """worker 仍在跑时 stop() 必须等它结束才返回"""
        finished = threading.Event()

        def slow_worker(task: Task) -> None:
            time.sleep(0.6)  # 模拟耗时的收尾写库
            finished.set()
            task.result = ["out.png"]

        async def run() -> float:
            q = TaskQueue()
            task = Task(task_id="drain-1", engine="test", config={})
            await q.start(slow_worker)
            await q.submit(task)
            await asyncio.sleep(0.2)  # 确保 worker 已进入执行
            assert not finished.is_set(), "前置条件：worker 应仍在执行"
            t0 = time.time()
            await q.stop()
            return time.time() - t0, finished.is_set()

        elapsed, done = asyncio.run(run())

        # 关键断言：stop() 返回时在飞行线程已经结束（否则上层 close() 会踩到它）
        assert done is True, "stop() 返回后 worker 线程仍在运行 → 关闭顺序竞态"
        assert elapsed >= 0.3, f"stop() 未等待在飞行线程（仅耗时 {elapsed:.2f}s）"

    def test_stop_does_not_hang_when_worker_never_returns(self):
        """worker 卡死时 stop() 必须在排空上限内返回，不能挂死关闭流程"""
        release = threading.Event()

        def stuck_worker(task: Task) -> None:
            release.wait(timeout=30)

        async def run() -> float:
            q = TaskQueue(shutdown_drain_timeout_s=0.5)
            task = Task(task_id="drain-2", engine="test", config={})
            await q.start(stuck_worker)
            await q.submit(task)
            await asyncio.sleep(0.2)
            t0 = time.time()
            await q.stop()
            return time.time() - t0

        elapsed = asyncio.run(run())

        assert elapsed < 5, f"stop() 未在排空上限内返回（耗时 {elapsed:.2f}s）"
        release.set()

    def test_stop_without_running_worker_is_noop(self):
        """未 start() 就 stop() 不报错"""
        q = TaskQueue()
        asyncio.run(q.stop())

    def test_worker_exception_still_finalizes_task(self):
        """worker 抛异常时任务置 FAILED，且 stop() 正常返回"""
        def boom(task: Task) -> None:
            raise RuntimeError("boom")

        async def run() -> Task:
            q = TaskQueue(max_retries=0)
            task = Task(task_id="drain-3", engine="test", config={})
            await q.start(boom)
            await q.submit(task)
            for _ in range(200):
                await asyncio.sleep(0.02)
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    break
            await q.stop()
            return task

        task = asyncio.run(run())
        assert task.status == TaskStatus.FAILED
        assert "boom" in task.error
