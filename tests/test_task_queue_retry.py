"""
单元测试：task_queue.py 自动重试（P2-6）

验证单 Worker 串行队列在任务失败后按 max_retries 指数退避自动重试，
重试次数耗尽后最终置 FAILED；成功重试后最终 COMPLETED。
"""

import asyncio

from app.integrated_app.task_queue import Task, TaskQueue, TaskStatus


def _run_worker(q, worker, task, max_polls=400):
    async def run():
        await q.start(worker)
        await q.submit(task)
        for _ in range(max_polls):
            await asyncio.sleep(0.05)
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                break
        await q.stop()
        return task

    return asyncio.run(run())


def test_retry_then_success():
    q = TaskQueue(max_retries=2, retry_base_delay_s=0, retry_max_delay_s=0)
    state = {"n": 0}

    def worker(task):
        state["n"] += 1
        if state["n"] < 3:
            task.error = f"boom-{state['n']}"
            raise RuntimeError(task.error)
        task.result = ["out.png"]

    task = Task(task_id="t1", engine="e", config={})
    result = _run_worker(q, worker, task)

    assert result.status == TaskStatus.COMPLETED
    assert result.attempts == 2  # 初始 + 2 次重试中的第 3 次成功
    assert state["n"] == 3


def test_retry_exhausted_then_failed():
    q = TaskQueue(max_retries=1, retry_base_delay_s=0, retry_max_delay_s=0)
    state = {"n": 0}

    def worker(task):
        state["n"] += 1
        task.error = "always"
        raise RuntimeError("always")

    task = Task(task_id="t2", engine="e", config={})
    result = _run_worker(q, worker, task)

    assert result.status == TaskStatus.FAILED
    assert result.attempts == 1  # 仅 1 次重试
    assert state["n"] == 2  # 初始 + 1 重试


def test_no_retry_when_disabled():
    q = TaskQueue(max_retries=0, retry_base_delay_s=0, retry_max_delay_s=0)
    state = {"n": 0}

    def worker(task):
        state["n"] += 1
        task.error = "always"
        raise RuntimeError("always")

    task = Task(task_id="t3", engine="e", config={})
    result = _run_worker(q, worker, task)

    assert result.status == TaskStatus.FAILED
    assert result.attempts == 0
    assert state["n"] == 1  # 仅执行一次


def test_retry_not_triggered_on_cancel():
    """用户取消的任务不应重试（取消非失败）。"""
    q = TaskQueue(max_retries=2, retry_base_delay_s=0, retry_max_delay_s=0)
    state = {"n": 0}

    async def run():
        await q.start(lambda t: None)
        task = Task(task_id="t4", engine="e", config={})
        await q.submit(task)
        # 立即取消（PENDING 阶段）
        await q.cancel(task.task_id)
        for _ in range(20):
            await asyncio.sleep(0.05)
            if task.status == TaskStatus.CANCELLED:
                break
        await q.stop()
        return task

    result = asyncio.run(run())
    assert result.status == TaskStatus.CANCELLED
    assert result.attempts == 0
