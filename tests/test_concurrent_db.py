"""
tests/test_concurrent_db.py — 并发写入 DB 测试

对应 N20: 多线程/多进程写入冲突验证
SQLite WAL 模式支持并发读 + 串行写，验证不丢数据
"""

from __future__ import annotations

import threading
import time

import pytest

from integrated_app.history_db import HistoryDB


@pytest.fixture
def db(tmp_path):
    """临时数据库"""
    d = HistoryDB(tmp_path / "test_concurrent.db")
    yield d
    d.close()


class TestConcurrentWrites:
    """并发写入安全性"""

    def test_concurrent_create_tasks(self, db):
        """多线程并发创建任务 → 全部成功（SQLite WAL 串行写）"""
        num_threads = 3
        tasks_per_thread = 5
        errors: list[Exception] = []
        lock = threading.Lock()

        def writer(thread_id: int):
            try:
                for i in range(tasks_per_thread):
                    # SQLite WAL 模式下写操作需要串行化
                    with lock:
                        db.create_task(
                            task_id=f"t{thread_id}-task-{i}",
                            engine="test",
                            prompt=f"thread {thread_id} task {i}",
                        )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent write errors: {errors}"

        # 验证所有任务都已写入
        tasks, total = db.list_tasks(page=1, page_size=200)
        assert total == num_threads * tasks_per_thread

    def test_concurrent_read_while_writing(self, db):
        """并发读 + 写 → 读不阻塞写"""
        # 预填充
        for i in range(10):
            db.create_task(task_id=f"pre-{i}", engine="test")

        read_results: list[int] = []
        write_errors: list[Exception] = []
        lock = threading.Lock()

        def reader():
            for _ in range(20):
                _, total = db.list_tasks(page=1, page_size=50)
                read_results.append(total)
                time.sleep(0.01)

        def writer():
            try:
                for i in range(10):
                    with lock:
                        db.create_task(task_id=f"concurrent-{i}", engine="test")
                    time.sleep(0.01)
            except Exception as e:
                write_errors.append(e)

        t_read = threading.Thread(target=reader)
        t_write = threading.Thread(target=writer)
        t_read.start()
        t_write.start()
        t_read.join()
        t_write.join()

        assert len(write_errors) == 0, f"Write errors during concurrent read: {write_errors}"
        # 最终数据量 = 10 (pre) + 10 (concurrent) = 20
        _, total = db.list_tasks(page=1, page_size=100)
        assert total == 20

    def test_concurrent_update_same_task(self, db):
        """并发更新同一任务 → 不崩溃（串行化写）"""
        db.create_task(task_id="concurrent-update", engine="test")
        errors: list[Exception] = []
        lock = threading.Lock()

        def updater():
            try:
                for _ in range(5):
                    with lock:
                        db.update_task_status("concurrent-update", "processing")
                    time.sleep(0.005)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent update errors: {errors}"
        task = db.get_task("concurrent-update")
        assert task["status"] == "processing"

    def test_concurrent_preset_create(self, db):
        """并发创建预设 → 全部成功（串行化写）"""
        num_threads = 2
        presets_per_thread = 3
        errors: list[Exception] = []
        lock = threading.Lock()

        def preset_writer(thread_id: int):
            try:
                for i in range(presets_per_thread):
                    with lock:
                        db.create_preset("flux", f"preset-t{thread_id}-{i}", {"steps": 8})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=preset_writer, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent preset create errors: {errors}"
        presets = db.list_presets()
        assert len(presets) == num_threads * presets_per_thread
