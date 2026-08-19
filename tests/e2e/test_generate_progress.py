"""
tests/e2e/test_generate_progress.py — E2E: 生成进度 + 主题

对应 REMAINING_TASKS_REPORT B1/B7: 防闪烁 + 生成进度

P0-1 修复：移除已废弃的 #freeVramBtn 选择器（项目已脱离 ComfyUI）
P2-3 改进：page.wait_for_timeout 改为条件等待
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
        theme = page.get_attribute("html", "data-theme")
        assert theme in ("light", "dark"), f"Invalid theme: {theme}"

    def test_theme_toggle(self, page, base_url):
        """主题切换 → localStorage 持久化"""
        page.goto(base_url)
        page.wait_for_selector("#themeToggle")
        page.click("#themeToggle")
        # 条件等待：等待 data-theme 属性出现（替代 wait_for_selector state=attached）
        page.wait_for_selector("html[data-theme]", timeout=3000)
        saved = page.evaluate("localStorage.getItem('imm_theme')")
        assert saved in ("light", "dark")

    def test_progress_bar_exists(self, page, base_url):
        """进度条元素存在（不一定可见，仅验证 DOM 结构）"""
        page.goto(base_url)
        # 条件等待：等待元素 attached（替代 goto + wait_for_selector）
        page.wait_for_selector("#genProgress", state="attached", timeout=10000)
        page.wait_for_selector("#progFill", state="attached", timeout=5000)
        page.wait_for_selector("#phaseText", state="attached", timeout=5000)

    def test_engine_status_displayed(self, page, base_url):
        """引擎状态在状态栏显示（替代已移除的 #freeVramBtn）"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")
        # 项目已脱离 ComfyUI，#freeVramBtn 已移除
        # 改为验证引擎选择器和连接状态元素存在
        engine_select = page.query_selector("#engineSelect")
        assert engine_select is not None, "Engine select (#engineSelect) should exist"
        sb_conn = page.query_selector("#sbConnText")
        assert sb_conn is not None, "Connection status (#sbConnText) should exist"
