"""
native/compares.py — ESES 双图对比 diff mask

复用 ``ComfyUI-EsesImageCompare/image_compare.py`` 的 ``EsesImageCompare.execute``
中的灰度差计算逻辑（去掉对 ``PromptServer`` 的依赖，纯张量运算），返回 diff_mask。
"""

from __future__ import annotations

from typing import Any

import torch

# ESES 采用的 Rec.709 亮度加权系数（与 image_compare.py 一致）
_R = 0.2126
_G = 0.7152
_B = 0.0722


def _grayscale(image: torch.Tensor) -> torch.Tensor:
    """把 RGB 图像张量转为灰度张量（沿最后一维加权求和）。

    Args:
        image: 形状 ``[..., H, W, C]`` 的 RGB 张量

    Returns:
        形状 ``[..., H, W]`` 的灰度张量
    """
    return _R * image[..., 0] + _G * image[..., 1] + _B * image[..., 2]


def diff_mask(image_a: torch.Tensor, image_b: torch.Tensor) -> torch.Tensor:
    """计算两张图像的灰度差 mask。

    对齐 ``EsesImageCompare.execute``：仅当两图形状一致时计算
    ``abs(grayscale_a - grayscale_b)``；否则返回全零 mask（形状与 image_a 单通道一致）。

    Args:
        image_a: 图像 A，形状 ``[..., H, W, C]``
        image_b: 图像 B，形状 ``[..., H, W, C]``

    Returns:
        diff_mask 张量。形状一致时返回 ``[..., H, W]`` 的灰度差；否则返回
        ``torch.zeros_like(image_a[..., 0])``。
    """
    if image_b is not None and image_a.shape == image_b.shape:
        return torch.abs(_grayscale(image_a) - _grayscale(image_b))
    return torch.zeros_like(image_a[..., 0])


def compare(
    image_a: Any,
    image_b: Any,
    compare_axis: str = "horizontal",
) -> dict[str, Any]:
    """高层封装：返回 ``{"image_a": ..., "diff_mask": ...}``。

    Args:
        image_a: 图像 A 张量 ``[N, H, W, C]``
        image_b: 图像 B 张量（可为 None）
        compare_axis: 对比轴（horizontal/vertical），仅前端预览使用，本实现原样保留

    Returns:
        含 ``image_a`` 与 ``diff_mask`` 的字典，与 EsesVideoCompare 节点输出对齐。
    """
    _ = compare_axis  # 前端预览用，后端不参与计算
    return {"image_a": image_a, "diff_mask": diff_mask(image_a, image_b)}
