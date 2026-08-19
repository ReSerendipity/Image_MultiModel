"""
tests/e2e/test_engine_switch.py — E2E: 引擎切换

对应 REMAINING_TASKS_REPORT B7: Playwright E2E 落地

P2-3 改进：page.wait_for_selector 超时增加，替代固定 timeout
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestEngineSwitch:
    """引擎切换 E2E"""

    def test_engine_dropdown(self, page, base_url):
        """点击引擎图标 → 下拉菜单显示"""
        page.goto(base_url)
        page.wait_for_selector("#engIcon", timeout=10000)
        page.click("#engIcon")
        # 条件等待：等待菜单显示（替代固定 timeout）
        page.wait_for_selector("#engMenu.show", timeout=5000)
        items = page.query_selector_all("#engMenu .ip-item")
        assert len(items) >= 1

    def test_engine_select(self, page, base_url):
        """选择引擎 → engineSelect 值更新"""
        page.goto(base_url)
        page.wait_for_selector("#engIcon", timeout=10000)
        page.click("#engIcon")
        page.wait_for_selector("#engMenu.show", timeout=5000)
        first_item = page.query_selector("#engMenu .ip-item")
        if first_item:
            first_item.click()
            # 条件等待：等待 engineSelect 有值
            page.wait_for_selector("#engineSelect[value]:not([value=''])", timeout=5000)
            val = page.evaluate("document.getElementById('engineSelect').value")
            assert val, "Engine select should have a value"
