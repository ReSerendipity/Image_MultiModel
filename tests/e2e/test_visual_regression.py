"""
tests/e2e/test_visual_regression.py — 视觉回归基线比对

对应测试体系评估 P1-4（反模式 #6：视觉回归截图存临时目录即弃、无基线比对）。

使用 Playwright 内置的 to_have_screenshot 进行像素比对：
- 首次运行（无基线）自动写入基线快照到 tests/e2e/__snapshots__/，测试通过；
- 后续运行与基线像素比对，差异超阈值则失败。
所有快照基线需随仓库提交（git add tests/e2e/__snapshots__），可被 review。
本测试仅截首页（无需 GPU），标记 @pytest.mark.e2e（非 slow），纳入默认 E2E CI。
手动更新基线：pytest tests/e2e/test_visual_regression.py --update-snapshots
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_homepage_visual_regression(page, base_url, screenshot) -> None:
    """首页布局像素比对（基线见 tests/e2e/__snapshots__）。"""
    page.goto(base_url)
    page.wait_for_selector("#genBtn", state="visible", timeout=15000)
    page.wait_for_load_state("networkidle")
    # 像素比对：首次运行写入基线，之后每次比对
    expect(page).to_have_screenshot(
        "homepage.png",
        full_page=False,
        max_diff_ratio=0.02,  # 允许 2% 像素差异（抗抗字体渲染微差）
    )
