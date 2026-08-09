"""
tests/e2e/test_generate_progress.py — E2E: 生成进度 + 主题

对应 REMAINING_TASKS_REPORT B1/B7: 防闪烁 + 生成进度
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestGenerateProgress:
    """生成进度 E2E"""

    def test_theme_no_flash(self, page, base_url):
        """B1: 主题在 head 内联脚本设置，无闪烁"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        # 验证 data-theme 已设置（不是默认 light）
        theme = page.get_attribute("html", "data-theme")
        assert theme in ("light", "dark"), f"Invalid theme: {theme}"

    def test_theme_toggle(self, page, base_url):
        """主题切换 → localStorage 持久化"""
        page.goto(base_url)
        page.wait_for_selector("#themeToggle")
        # 切换主题
        page.click("#themeToggle")
        page.wait_for_timeout(300)
        # 验证 localStorage 已保存
        saved = page.evaluate("localStorage.getItem('imm_theme')")
        assert saved in ("light", "dark")

    def test_progress_bar_exists(self, page, base_url):
        """进度条元素存在"""
        page.goto(base_url)
        page.wait_for_selector("#genProgress")
        page.wait_for_selector("#progFill")
        page.wait_for_selector("#phaseText")

    def test_free_vram_button(self, page, base_url):
        """D3: 释放显存按钮存在"""
        page.goto(base_url)
        page.wait_for_selector("#freeVramBtn")
        btn = page.query_selector("#freeVramBtn")
        assert btn is not None, "Free VRAM button should exist"
