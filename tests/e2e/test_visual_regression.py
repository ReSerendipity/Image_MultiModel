"""
tests/e2e/test_visual_regression.py — 视觉回归基线比对

对应测试体系评估 P1-4（反模式 #6：视觉回归截图存临时目录即弃、无基线比对）。

- 首次运行（无基线）自动写入基线快照到 tests/e2e/__snapshots__/，测试通过；
- 后续运行与基线做像素比对，差异超阈值（默认 2%）则失败；
- 所有快照基线需随仓库提交，可被 review。

本测试仅截首页（无需 GPU），标记 @pytest.mark.e2e，纳入默认 E2E CI。
手动更新基线：pytest tests/e2e/test_visual_regression.py --update-snapshots

⚠️ 坑（2026-09-01）：原实现使用 ``expect(page).to_have_screenshot(...)``，
但 Playwright Python 1.62 的同步 API **不提供** 该方法（``PageAssertions``
无 to_have_screenshot，``Page.expect_screenshot`` 亦已移除），必然抛
AttributeError。现改为 page.screenshot() 落盘 + PIL/numpy 像素 diff 自实现。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__"
# 允许 2% 像素差异（抗字体渲染 / 抗锯齿微差）
MAX_DIFF_RATIO = 0.02
# 单像素 RGB 通道差超过该阈值才计为"差异像素"
PIXEL_THRESHOLD = 24


def _baseline_name(browser: str) -> str:
    """生成与「平台 + 浏览器」绑定的基线文件名。

    ⚠️ 坑（2026-09-01）：字体渲染 / 抗锯齿在不同 OS 上差异可达 10%+，
    若共用单个 homepage.png 基线，Windows 上生成的基线会让 ubuntu CI
    必然误报失败（假阳性）。按 platform-browser 分桶，保证同一环境内
    的比对才有意义。

    Args:
        browser: 当前浏览器名（chromium / firefox / webkit）。

    Returns:
        str: 基线文件名，如 ``homepage.win32-chromium.png``。
    """
    import sys

    return f"homepage.{sys.platform}-{browser}.png"


def _diff_ratio(baseline: Path, current: Path) -> float:
    """计算两张 PNG 的差异像素占比。

    Args:
        baseline: 基线图片路径。
        current: 本次运行截图路径。

    Returns:
        float: 差异像素数 / 总像素数，取值 [0.0, 1.0]。
    """
    from PIL import Image  # 局部导入：仅在真正执行比对时需要

    with Image.open(baseline) as b_img, Image.open(current) as c_img:
        base = b_img.convert("RGB")
        cur = c_img.convert("RGB")

    if base.size != cur.size:
        # 尺寸不同视为整体失效，直接返回 1.0 触发失败并给出可读信息
        return 1.0

    import numpy as np

    b_arr = np.asarray(base, dtype=np.int16)
    c_arr = np.asarray(cur, dtype=np.int16)
    diff_mask = np.abs(b_arr - c_arr).max(axis=2) > PIXEL_THRESHOLD
    return float(diff_mask.mean())


def test_homepage_visual_regression(page, base_url, screenshot, request) -> None:
    """首页布局像素比对（基线见 tests/e2e/__snapshots__/homepage.png）。"""
    page.goto(base_url)
    page.wait_for_selector("#genBtn", state="visible", timeout=15000)
    page.wait_for_load_state("networkidle")

    browser = request.config.getoption("--browser", default=None)
    browser = (browser[0] if isinstance(browser, list) and browser else None) or "chromium"
    baseline = SNAPSHOT_DIR / _baseline_name(browser)
    current = Path(screenshot("homepage_current"))

    update = request.config.getoption("--update-snapshots", default=False)
    if update or not baseline.is_file():
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(current, baseline)
        pytest.skip(
            f"基线快照已写入：{baseline.name}（首次在本平台/浏览器运行，仅生成基线不做比对；再次运行即进入像素比对）"
        )

    ratio = _diff_ratio(baseline, current)
    assert ratio <= MAX_DIFF_RATIO, (
        f"首页视觉回归差异 {ratio:.2%} 超过阈值 {MAX_DIFF_RATIO:.2%}；"
        f"若为预期 UI 变更，请执行 "
        f"`pytest tests/e2e/test_visual_regression.py --update-snapshots` 更新基线"
    )
