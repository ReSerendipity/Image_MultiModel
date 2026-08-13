"""
test_native_compares.py — ESES 双图对比 diff mask（Task 3.4）单测

纯张量逻辑，直接可测。
"""

from __future__ import annotations

import pytest
import torch

from integrated_app.native import compares


def test_grayscale_weights() -> None:
    """灰度加权与 ESES 一致（Rec.709）。"""
    img = torch.tensor([[[[1.0, 0.0, 0.0]]]])  # [1,1,1,3] 纯红
    out = compares._grayscale(img)
    assert out[0, 0, 0] == pytest.approx(0.2126)


def test_diff_mask_identical_images() -> None:
    """相同图像 diff mask 全零。"""
    img = torch.rand(1, 8, 8, 3)
    mask = compares.diff_mask(img, img.clone())
    assert mask.shape == (1, 8, 8)
    assert torch.allclose(mask, torch.zeros_like(mask))


def test_diff_mask_difference() -> None:
    """不同图像 diff mask 等于灰度差绝对值。"""
    a = torch.zeros(1, 4, 4, 3)
    b = torch.ones(1, 4, 4, 3)
    mask = compares.diff_mask(a, b)
    expected = torch.abs(compares._grayscale(a) - compares._grayscale(b))
    assert torch.allclose(mask, expected)
    assert mask.max() > 0


def test_diff_mask_shape_mismatch_returns_zeros() -> None:
    """形状不一致时返回全零 mask（对齐 ESES）。"""
    a = torch.rand(1, 4, 4, 3)
    b = torch.rand(1, 8, 8, 3)
    mask = compares.diff_mask(a, b)
    assert mask.shape == (1, 4, 4)
    assert (mask == 0).all()


def test_diff_mask_none_b() -> None:
    """image_b=None 时返回全零 mask。"""
    a = torch.rand(1, 4, 4, 3)
    mask = compares.diff_mask(a, None)
    assert (mask == 0).all()


def test_compare_returns_dict() -> None:
    """compare 高层封装返回 image_a + diff_mask。"""
    a = torch.rand(1, 4, 4, 3)
    b = torch.rand(1, 4, 4, 3)
    res = compares.compare(a, b, compare_axis="horizontal")
    assert set(res.keys()) == {"image_a", "diff_mask"}
    assert res["image_a"] is a
    assert res["diff_mask"].shape == (1, 4, 4)
