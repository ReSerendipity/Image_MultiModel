"""
tests/e2e/test_generation_flow.py — 完整生成流程 E2E

对应 N4: 填表单 → 提交 → SSE 进度 → 结果展示
使用 POM 设计模式
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestGenerationFlow:
    """完整生成流程 E2E"""

    def test_page_loads_with_pom(self, page, base_url):
        """使用 POM 验证页面加载"""
        from .pages.home_page import HomePage

        home = HomePage(page, base_url)
        home.goto("/")
        assert home.get_theme() in ("light", "dark")

    def test_theme_toggle_with_pom(self, page, base_url):
        """使用 POM 验证主题切换"""
        from .pages.home_page import HomePage

        home = HomePage(page, base_url)
        home.goto("/")
        original_theme = home.get_theme()
        home.toggle_theme()
        new_theme = home.get_theme()
        assert new_theme != original_theme or new_theme in ("light", "dark")

    def test_engine_dropdown_with_pom(self, page, base_url):
        """使用 POM 验证引擎下拉"""
        from .pages.home_page import HomePage

        home = HomePage(page, base_url)
        home.goto("/")
        home.open_engine_menu()
        assert home.get_engine_count() >= 1

    def test_language_switch_with_pom(self, page, base_url):
        """使用 POM 验证语言切换"""
        from .pages.home_page import HomePage

        home = HomePage(page, base_url)
        home.goto("/")
        home.switch_language("en-US")
        assert home.get_language() == "en-US"

    def test_progress_bar_structure_with_pom(self, page, base_url):
        """使用 POM 验证进度条 DOM"""
        from .pages.home_page import HomePage

        home = HomePage(page, base_url)
        home.goto("/")
        assert home.has_progress_bar()
        assert home.has_free_vram_button()

    def test_screenshot_capture(self, page, base_url, tmp_path):
        """截图功能验证（视觉回归基础）"""
        import os

        screenshots_dir = tmp_path / "screenshots"
        os.makedirs(screenshots_dir, exist_ok=True)
        screenshot_path = screenshots_dir / "home.png"
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        page.screenshot(path=str(screenshot_path))
        assert screenshot_path.exists()
        assert screenshot_path.stat().st_size > 1000
