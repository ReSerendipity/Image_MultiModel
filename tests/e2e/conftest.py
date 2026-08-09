"""
tests/e2e/conftest.py — Playwright E2E 测试公共 fixture

对应 REMAINING_TASKS_REPORT B7: Playwright E2E 落地
"""

from __future__ import annotations

import pytest

try:
    import pytest_playwright  # noqa: F401
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


@pytest.fixture
def base_url():
    """应用基础 URL"""
    return "http://127.0.0.1:8288"


# 如果 playwright 未安装，自动跳过所有 E2E 测试
if not HAS_PLAYWRIGHT:
    def pytest_collection_modifyitems(items):
        skip_marker = pytest.mark.skip(reason="pytest-playwright not installed")
        for item in items:
            item.add_marker(skip_marker)
