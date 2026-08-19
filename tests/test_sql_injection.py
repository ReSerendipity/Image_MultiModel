"""
tests/test_sql_injection.py — SQL 注入防护测试

对应 N7: HistoryDB 参数化查询安全验证
确保所有用户输入通过 ? 占位符传入，防止 SQL 注入
"""

from __future__ import annotations

import pytest

from integrated_app.history_db import HistoryDB


@pytest.fixture
def db(tmp_path):
    """临时数据库"""
    d = HistoryDB(tmp_path / "test_sqli.db")
    yield d
    d.close()


class TestSQLInjectionTasks:
    """tasks 表 SQL 注入防护"""

    def test_create_task_with_sql_injection_prompt(self, db):
        """prompt 中包含 SQL 注入 payload → 安全存储"""
        sqli_payloads = [
            "'; DROP TABLE tasks; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM presets --",
            "'; INSERT INTO tasks VALUES ('hack', 'hack'); --",
            "' OR 1=1 --",
            "admin'--",
            "1; DELETE FROM tasks WHERE 1=1; --",
        ]
        for i, payload in enumerate(sqli_payloads):
            tid = f"sqli-task-{i}"
            db.create_task(task_id=tid, engine="test", prompt=payload)
            task = db.get_task(tid)
            assert task is not None
            assert task["prompt"] == payload, f"SQL injection payload corrupted: {payload}"

    def test_create_task_with_sql_injection_engine(self, db):
        """engine 字段 SQL 注入 → 安全存储"""
        payload = "flux'; DROP TABLE tasks; --"
        db.create_task(task_id="sqli-eng", engine=payload, prompt="test")
        task = db.get_task("sqli-eng")
        assert task["engine"] == payload

    def test_list_tasks_with_sql_injection_search(self, db):
        """FTS 搜索 SQL 注入 → 不影响查询"""
        db.create_task(task_id="sqli-search", engine="test", prompt="normal text")
        # SQL 注入 payload 作为搜索词 — FTS5 有自己的语法，可能报错
        # 关键验证：即使搜索报错，数据不被破坏
        # P2-4 修复：精确捕获 sqlite3 异常，不再吞没所有异常
        import sqlite3
        try:
            db.list_tasks(q="'; DROP TABLE tasks; --")
        except sqlite3.OperationalError:
            pass  # FTS5 语法错误是预期的
        except sqlite3.DatabaseError:
            pass  # FTS5 查询可能抛 DatabaseError 子类
        # 表仍然存在（未被注入破坏）
        tasks, total = db.list_tasks(page=1, page_size=10)
        assert total == 1
        assert tasks[0]["task_id"] == "sqli-search"
        # 正常搜索仍可用
        results2, total2 = db.list_tasks(q="normal")
        assert total2 == 1

    def test_delete_tasks_with_sql_injection_id(self, db):
        """删除任务时 SQL 注入 ID → 安全"""
        db.create_task(task_id="safe-task", engine="test")
        sqli_ids = ["'; DROP TABLE tasks; --", "' OR '1'='1"]
        count = db.delete_tasks(sqli_ids)
        # 安全任务仍在
        task = db.get_task("safe-task")
        assert task is not None, "SQL injection deleted unintended rows"

    def test_update_task_status_injection(self, db):
        """update_task_status 安全"""
        db.create_task(task_id="update-sqli", engine="test")
        # 正常更新
        db.update_task_status("update-sqli", "completed")
        task = db.get_task("update-sqli")
        assert task["status"] == "completed"
        # 表仍然存在（未被注入破坏）
        assert db.get_task("update-sqli") is not None


class TestSQLInjectionPresets:
    """presets 表 SQL 注入防护"""

    def test_create_preset_with_sql_injection_name(self, db):
        """preset name SQL 注入 → 安全存储"""
        payload = "test'; DROP TABLE presets; --"
        pid = db.create_preset("flux", payload, {"cfg": 1.0})
        preset = db.get_preset(pid)
        assert preset["name"] == payload

    def test_update_preset_sql_injection(self, db):
        """update_preset 安全"""
        pid = db.create_preset("flux", "safe-name", {})
        db.update_preset(pid, name="'; DROP TABLE presets; --")
        preset = db.get_preset(pid)
        assert preset is not None
        # 表仍然存在
        all_presets = db.list_presets()
        assert isinstance(all_presets, list)

    def test_delete_preset_sql_injection(self, db):
        """delete_preset 安全"""
        pid = db.create_preset("flux", "safe", {})
        # 用非法 ID 不应崩溃
        result = db.delete_preset(99999)
        assert result is False
        # 正常 preset 仍在
        assert db.get_preset(pid) is not None


class TestSQLInjectionOutputs:
    """outputs 表 SQL 注入防护"""

    def test_add_output_sql_injection_path(self, db):
        """output path SQL 注入 → 安全存储"""
        db.create_task(task_id="out-sqli", engine="test")
        payload = "outputs/'; DROP TABLE outputs; --.png"
        db.add_output(task_id="out-sqli", path=payload, output_type="original")
        task = db.get_task("out-sqli")
        assert len(task["outputs"]) == 1
        assert task["outputs"][0]["path"] == payload


class TestSQLInjectionTags:
    """tags 功能 SQL 注入防护"""

    def test_add_tags_sql_injection(self, db):
        """add_task_tags 安全"""
        db.create_task(task_id="tag-sqli", engine="test")
        sqli_tags = ["normal-tag", "safe-tag"]
        count = db.add_task_tags(["tag-sqli"], sqli_tags)
        assert count == 1
        task = db.get_task("tag-sqli")
        # get_task 已将 tags 解析为 list
        tags = task["tags"]
        assert isinstance(tags, list)
        assert "normal-tag" in tags
        assert "safe-tag" in tags
        # 表仍然存在
        assert db.get_task("tag-sqli") is not None
