"""视觉回归像素比对函数单测（不依赖浏览器）。

``tests/e2e/test_visual_regression.py`` 需要 Playwright + 真实服务，只在 E2E
作业里跑；但其中的像素比对算法（``_diff_ratio``）是纯函数，必须被默认测试套件
覆盖，否则"视觉回归门禁"可能是一个永远通过的空转断言。

本文件用合成图片验证：
1. 完全相同 → 0.0
2. 大面积差异 → 接近 1.0
3. 微小差异 → 落在阈值内（证明确实做了像素级比较而非简单跳过）
4. 尺寸不一致 → 直接判为 1.0（失效保护）
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

# tests/ 与 tests/e2e/ 均已标记为包，可直接按包路径导入
from tests.e2e.test_visual_regression import MAX_DIFF_RATIO, _diff_ratio  # noqa: E402


@pytest.fixture
def img_dir(tmp_path: Path) -> Path:
    """提供生成临时图片的目录。

    Args:
        tmp_path: pytest 内置临时目录 fixture。

    Returns:
        Path: 用于存放测试图片的目录路径。
    """
    return tmp_path


def _write(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> Path:
    """生成纯色 PNG。

    Args:
        path: 输出文件路径。
        color: RGB 颜色元组。
        size: 图片尺寸（宽, 高）。

    Returns:
        Path: 写入的图片路径。
    """
    Image.new("RGB", size, color).save(path)
    return path


def _write_patch(
    path: Path, base: tuple[int, int, int], patch_ratio: float, size: tuple[int, int] = (100, 100)
) -> Path:
    """生成「底部若干行为对比色」的图片，用于精确控制差异占比。

    Args:
        path: 输出文件路径。
        base: 底色 RGB。
        patch_ratio: 差异区域占总面积的比例（0~1）。
        size: 图片尺寸（宽, 高）。

    Returns:
        Path: 写入的图片路径。
    """
    img = Image.new("RGB", size, base)
    rows = int(size[1] * patch_ratio)
    if rows:
        for y in range(size[1] - rows, size[1]):
            for x in range(size[0]):
                img.putpixel((x, y), (255, 0, 0))
    img.save(path)
    return path


def test_identical_images_zero_diff(img_dir: Path) -> None:
    """完全相同的图片差异率为 0。"""
    a = _write(img_dir / "a.png", (10, 20, 30))
    b = _write(img_dir / "b.png", (10, 20, 30))
    assert _diff_ratio(a, b) == 0.0


def test_fully_different_images_ratio_is_one(img_dir: Path) -> None:
    """黑白反色应被判为 100% 差异。"""
    a = _write(img_dir / "black.png", (0, 0, 0))
    b = _write(img_dir / "white.png", (255, 255, 255))
    assert _diff_ratio(a, b) == 1.0


def test_small_diff_below_threshold(img_dir: Path) -> None:
    """1% 面积的差异应低于 2% 阈值（验证是像素级比较，而非一刀切）。"""
    a = _write(img_dir / "base.png", (0, 0, 0))
    b = _write_patch(img_dir / "patch1.png", (0, 0, 0), 0.01)
    ratio = _diff_ratio(a, b)
    assert 0.0 < ratio < MAX_DIFF_RATIO


def test_large_diff_above_threshold(img_dir: Path) -> None:
    """10% 面积的差异应超过 2% 阈值，触发视觉回归失败。"""
    a = _write(img_dir / "base.png", (0, 0, 0))
    b = _write_patch(img_dir / "patch10.png", (0, 0, 0), 0.10)
    assert _diff_ratio(a, b) > MAX_DIFF_RATIO


def test_size_mismatch_fails_closed(img_dir: Path) -> None:
    """尺寸不一致时判为完全差异（失效保护，避免 IndexError/静默通过）。"""
    a = _write(img_dir / "s1.png", (0, 0, 0), (100, 100))
    b = _write(img_dir / "s2.png", (0, 0, 0), (120, 100))
    assert _diff_ratio(a, b) == 1.0


def test_baseline_name_is_platform_scoped() -> None:
    """基线图名必须带平台与浏览器后缀，避免跨 OS 字体渲染导致假阳性。"""
    from tests.e2e.test_visual_regression import _baseline_name

    name = _baseline_name("chromium")
    assert name.startswith("homepage.")
    assert "chromium" in name
    assert name.endswith(".png")
