"""
tests/e2e/test_engine_switch.py — E2E: 引擎切换

对应 REMAINING_TASKS_REPORT B7: Playwright E2E 落地
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestEngineSwitch:
    """引擎切换 E2E"""

    def test_engine_dropdown(self, page, base_url):
        """点击引擎图标 → 下拉菜单显示"""
        page.goto(base_url)
        page.wait_for_selector("#engIcon")
        page.click("#engIcon")
        page.wait_for_selector("#engMenu.show")
        # 验证菜单中有引擎选项
        items = page.query_selector_all("#engMenu .ip-item")
        assert len(items) >= 1

    def test_engine_select(self, page, base_url):
        """选择引擎 → engineSelect 值更新"""
        page.goto(base_url)
        page.wait_for_selector("#engIcon")
        page.click("#engIcon")
        page.wait_for_selector("#engMenu.show")
        # 点击第一个引擎选项
        first_item = page.query_selector("#engMenu .ip-item")
        if first_item:
            first_item.click()
            page.wait_for_timeout(500)
            # 验证 engineSelect 有值
            val = page.evaluate("document.getElementById('engineSelect').value")
            assert val, "Engine select should have a value"
