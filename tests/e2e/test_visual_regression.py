"""
tests/e2e/test_visual_regression.py — 视觉回归基线比对

对应测试体系评估 P1-4（反模式 #6：视觉回归截图存临时目录即弃、无基线比对）。

- 无基线时写入基线快照到 tests/e2e/__snapshots__/ 并 skip（PR 允许这一次）；
  push 到 main 时设了 E2E_REQUIRE_BASELINE=true，缺基线直接失败而非 skip；
- 有基线则与本次截图做像素比对，差异超阈值（默认 2%）则失败；
- 基线**按平台分桶入库**（win32 与 linux 各一份，两者实测差 5.05% 像素，
  不可互换）。actions/cache 只是加速与「同 key 优先用当次产物」，不能当唯一来源：
  本仓 pip 缓存体积顶穿 Actions 10GB 配额后，条目会在相邻两次运行之间就被回收。
- ⚠️ UI 真变了要让 linux 基线跟着更新：本地 `--update-snapshots` 只能生成自己
  平台那份（Windows 出不了 linux 基线），做法是从红掉的 CI 里下载
  `e2e-snapshots` 产物（该 job 失败时上传当次截图），取
  `homepage.linux-chromium.png` 覆盖入库后重跑。

本测试仅截首页（无需 GPU），标记 @pytest.mark.e2e，纳入默认 E2E CI。
手动更新基线：pytest tests/e2e/test_visual_regression.py --update-snapshots

⚠️ 坑（2026-09-01）：原实现使用 ``expect(page).to_have_screenshot(...)``，
但 Playwright Python 1.62 的同步 API **不提供** 该方法（``PageAssertions``
无 to_have_screenshot，``Page.expect_screenshot`` 亦已移除），必然抛
AttributeError。现改为 page.screenshot() 落盘 + PIL/numpy 像素 diff 自实现。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__"
REPO_ROOT = Path(__file__).resolve().parents[2]
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
        # main push 上"生成基线"不是一种结局，而是比对这个维度根本没跑：
        # 仓库里只提交过 win32 基线，linux 基线只能来自 actions/cache，
        # 缓存一miss 就 skip，于是 CI 常年绿色却从未比过一个像素。
        # CI 用 E2E_REQUIRE_BASELINE=${{ github.event_name == 'push' }} 关掉这条退路。
        if os.environ.get("E2E_REQUIRE_BASELINE", "").lower() == "true":
            pytest.fail(
                f"缺少可比对的基线：{baseline.name}（push 事件要求真比对，不允许现生成）。"
                f"基线本应随仓库提交在 {SNAPSHOT_DIR.relative_to(REPO_ROOT)}/ 下；"
                "补齐办法见本文件 docstring（从失败 CI 的 e2e-snapshots 产物取当次截图入库）"
            )
        pytest.skip(
            f"基线快照已写入：{baseline.name}（首次在本平台/浏览器运行，仅生成基线不做比对；再次运行即进入像素比对）"
        )

    ratio = _diff_ratio(baseline, current)
    assert ratio <= MAX_DIFF_RATIO, (
        f"首页视觉回归差异 {ratio:.2%} 超过阈值 {MAX_DIFF_RATIO:.2%}；"
        f"若为预期 UI 变更，请执行 "
        f"`pytest tests/e2e/test_visual_regression.py --update-snapshots` 更新基线"
    )
