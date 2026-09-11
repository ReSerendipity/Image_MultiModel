"""回归测试：配置单例被整体替换后，测试期 HistoryDB 重定向必须仍然生效。

背景（2026-09-11 CI run 34562117669 复发）：
``tests/conftest.py::_isolate_history_db_for_tests`` 早期只把**当前单例**的
``output.history.db_path`` 改到 worker 临时目录。但 ``load_config()`` /
``load_validated_config()`` / ``reload_config()`` 会 ``global _config``
**整体替换**单例（``tests/test_config_save.py`` 等会触发），替换后新单例的
``db_path`` 回到默认 ``data/history.db``，重定向失效；同 worker 后续
``create_app()`` 便落回真实 ``data/history.db``，pytest-xdist 多 worker 并发
初始化时 ``PRAGMA journal_mode=WAL`` 抛
``sqlite3.OperationalError: database is locked``。

2026-09-05 的修法只覆盖了「双导入身份」，未覆盖「单例被替换」这条路径。
本文件锁定「替换后仍被重定向」这一契约，防止再次回归。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

# conftest 用 tempfile.mkdtemp(prefix="imm-hist-<pid>-") 建 worker 级临时目录
_REDIRECT_MARKER = "imm-hist-"


class TestHistoryDbRedirectSurvivesConfigReload:
    """load_config / reload_config 替换单例后，db_path 仍须指向 worker 临时目录。"""

    def test_redirect_active_at_session_start(self):
        """前置条件：会话级重定向本身已生效。"""
        from integrated_app.config import get_config

        db_path = get_config().output.history.db_path
        assert _REDIRECT_MARKER in db_path, f"会话级重定向未生效，db_path={db_path}"

    def test_redirect_survives_load_config(self):
        """load_config() 整体替换单例后，新单例仍被重定向。"""
        from integrated_app.config import get_config, load_config

        load_config()

        db_path = get_config().output.history.db_path
        assert (
            _REDIRECT_MARKER in db_path
        ), f"load_config() 替换单例后 db_path 落回真实路径，测试期重定向被打穿：{db_path}"

    def test_redirect_survives_reload_config(self):
        """reload_config() 整体替换单例后，新单例仍被重定向。"""
        from integrated_app.config import get_config, reload_config

        reload_config()

        db_path = get_config().output.history.db_path
        assert (
            _REDIRECT_MARKER in db_path
        ), f"reload_config() 替换单例后 db_path 落回真实路径，测试期重定向被打穿：{db_path}"
