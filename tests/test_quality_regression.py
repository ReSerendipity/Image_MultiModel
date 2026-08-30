"""
test_quality_regression.py — 生成质量基准度量（MLOps P1·质量）单测

覆盖：PSNR / SSIM 度量正确性、Golden File 回归判定。
无需 GPU；CLIP-score 因依赖模型下载，离线环境用 importorskip 跳过。
"""

from __future__ import annotations

import pytest
from PIL import Image

from integrated_app import quality_metrics as qm

pytest.importorskip("PIL")
pytest.importorskip("numpy")


def _solid(color: tuple[int, int, int], size=(32, 32)) -> Image.Image:
    return Image.new("RGB", size, color)


def _noise(size=(32, 32)):  # 伪随机扰动图
    import numpy as np

    arr = np.random.RandomState(0).randint(0, 256, (*size, 3)).astype("uint8")
    return Image.fromarray(arr, "RGB")


def test_psnr_identical_is_inf() -> None:
    a = _solid((120, 60, 200))
    assert qm.compute_psnr(a, a) == float("inf")


def test_psnr_differs_by_noise() -> None:
    a = _solid((120, 60, 200))
    b = _solid((200, 60, 120))
    assert 0 < qm.compute_psnr(a, b) < 30


def test_ssim_identical_is_one() -> None:
    a = _solid((120, 60, 200))
    res = qm.compute_ssim(a, a)
    assert res == pytest.approx(1.0, abs=1e-6)


def test_ssim_different_lower() -> None:
    a = _solid((255, 255, 255))
    b = _solid((0, 0, 0))
    assert qm.compute_ssim(a, b) < 0.5


def test_ssim_robust_to_resize() -> None:
    a = _solid((100, 150, 50), size=(64, 64))
    b = _solid((100, 150, 50), size=(32, 32))
    # 同图缩放后 SSIM 应接近 1
    assert qm.compute_ssim(a, b) > 0.99


def test_golden_regression_passes_for_identical(tmp_path) -> None:
    reg = qm.GoldenFileRegistry(tmp_path, ssim_threshold=0.95)
    ref = _solid((10, 20, 30))
    # 建立基线
    reg.compare("smoke", ref, regenerate=True)
    assert reg.has_golden("smoke")
    # 相同图对比应通过
    res = reg.compare("smoke", ref)
    assert res.passed is True
    assert res.ssim == pytest.approx(1.0, abs=1e-6)


def test_golden_regression_fails_for_different(tmp_path) -> None:
    reg = qm.GoldenFileRegistry(tmp_path, ssim_threshold=0.95)
    reg.compare("smoke", _solid((10, 20, 30)), regenerate=True)
    # 完全不同图应判不合格
    res = reg.compare("smoke", _noise())
    assert res.passed is False
    assert "ssim" in res.detail


def test_golden_missing_without_regenerate_fails(tmp_path) -> None:
    reg = qm.GoldenFileRegistry(tmp_path, ssim_threshold=0.95)
    res = reg.compare("nope", _solid((1, 2, 3)))
    assert res.passed is False
    assert "regenerated" not in res.detail


def test_clip_score_skips_offline() -> None:
    pytest.importorskip("transformers")
    # 若 transformers 存在但无网络/clip 权重，应优雅抛错而非崩溃
    with pytest.raises(Exception):
        qm.compute_clip_score([_solid((1, 2, 3))], ["a red square"])
