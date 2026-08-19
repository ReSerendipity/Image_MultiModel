"""
tests/e2e/conftest.py — Playwright E2E 测试公共 fixture

对应 REMAINING_TASKS_REPORT B7: Playwright E2E 落地
对应 N3: 截图比对/视觉回归工具基础设施

P2-5 改进：添加跨浏览器配置（Chromium + Firefox）
"""

from __future__ import annotations

import os

import pytest

try:
    import pytest_playwright  # noqa: F401
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


@pytest.fixture(scope="session")
def base_url():
    """应用基础 URL（支持环境变量覆盖）"""
    return os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8288")


@pytest.fixture(scope="session")
def screenshots_dir(tmp_path_factory):
    """截图目录（视觉回归基础）"""
    d = tmp_path_factory.mktemp("screenshots")
    return str(d)


@pytest.fixture
def screenshot(page, screenshots_dir):
    """截图函数 fixture"""
    def _screenshot(name: str):
        path = os.path.join(screenshots_dir, f"{name}.png")
        page.screenshot(path=path)
        return path
    return _screenshot


# ── P2-5: 跨浏览器配置 ──────────────────────────────────────
# 默认使用 Chromium；CI 可通过 BROWSER=firefox 切换 Firefox
# 在 CI 中运行 Firefox：BROWSER=firefox python -m pytest tests/e2e -m e2e
def pytest_generate_tests(metafunc):
    """根据 BROWSER 环境变量生成浏览器参数化"""
    if "browser_name" in metafunc.fixturenames:
        browsers = os.environ.get("BROWSERS", "chromium").split(",")
        metafunc.parametrize("browser_name", browsers, ids=browsers)


# 如果 playwright 未安装，自动跳过所有 E2E 测试
if not HAS_PLAYWRIGHT:
    def pytest_collection_modifyitems(items):
        skip_marker = pytest.mark.skip(reason="pytest-playwright not installed")
        for item in items:
            item.add_marker(skip_marker)
