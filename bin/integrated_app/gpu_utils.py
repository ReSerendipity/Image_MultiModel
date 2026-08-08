"""
gpu_utils.py — 显存预检 + FP8 回退 + chunk 推荐

对应 MASTER_PLAN §4 / 附录 B4: gpu_utils.py
对应 PRD §2.4.3: vram_multisample_rule ×1.5 + FP8 回退
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU 显存信息"""
    total_vram_gb: float = 0.0
    used_vram_gb: float = 0.0
    free_vram_gb: float = 0.0
    gpu_name: str = "Unknown"
    backend: str = "cpu"  # cuda / rocm / mps / cpu


def get_gpu_info() -> GPUInfo:
    """
    获取当前 GPU 显存信息。
    优先使用 PyTorch CUDA，回退到 CPU。
    """
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            total = props.total_memory / (1024**3)
            free, _total = torch.cuda.mem_get_info(0)
            used = total - free / (1024**3)
            return GPUInfo(
                total_vram_gb=round(total, 2),
                used_vram_gb=round(used, 2),
                free_vram_gb=round(free / (1024**3), 2),
                gpu_name=props.name,
                backend="cuda",
            )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to get GPU info via torch: {e}")

    # CPU fallback
    return GPUInfo(backend="cpu")


@dataclass
class VRAMEstimate:
    """显存预检结果"""
    can_run: bool
    needed_vram_gb: float
    available_vram_gb: float
    recommended_precision: str  # fp8 / fp16 / bf16 / fp32
    recommended_chunk_size: int
    warning: str = ""


def estimate_vram_requirement(
    engine_vram_gb: float,
    width: int,
    height: int,
    batch_size: int,
    enable_seedvr2: bool = False,
    multisample_rule: float = 1.5,
    headroom_gb: float = 2.0,
) -> float:
    """
    估算推理所需显存（GB）。

    公式: base_vram × multisample_rule × resolution_factor × batch_factor + seedvr2_overhead

    Args:
        engine_vram_gb: 引擎基准显存需求
        width, height: 输出分辨率
        batch_size: 批量大小
        enable_seedvr2: 是否启用 SeedVR2 超分
        multisample_rule: 显存预检系数（默认 1.5）
        headroom_gb: 显存预留

    Returns:
        估算所需显存 (GB)
    """
    # 分辨率因子（以 1024×1024 为基准）
    base_pixels = 1024 * 1024
    actual_pixels = width * height
    resolution_factor = (actual_pixels / base_pixels) ** 0.5  # 平方根缩放

    # batch 因子（首张全量，后续增量）
    batch_factor = 1.0 + (batch_size - 1) * 0.3

    # 基础需求
    needed = engine_vram_gb * multisample_rule * resolution_factor * batch_factor

    # SeedVR2 超分额外需求
    if enable_seedvr2:
        seedvr2_overhead = 4.0 * resolution_factor  # SeedVR2 约需 4GB
        needed += seedvr2_overhead

    # 加上 headroom
    needed += headroom_gb

    return round(needed, 2)


def preflight_vram(
    engine_vram_gb: float,
    width: int,
    height: int,
    batch_size: int,
    enable_seedvr2: bool = False,
    fallback_precision: str = "fp8",
    default_precision: str = "fp8",
    multisample_rule: float = 1.5,
    headroom_gb: float = 2.0,
    gpu_info: Optional[GPUInfo] = None,
) -> VRAMEstimate:
    """
    显存预检：估算需求 vs 可用量，决定精度和 chunk 大小。

    Args:
        engine_vram_gb: 引擎基准显存
        width, height, batch_size: 推理参数
        enable_seedvr2: 是否开超分
        fallback_precision: 显存不足时回退精度
        default_precision: 默认精度
        multisample_rule: 预检系数
        headroom_gb: 显存预留
        gpu_info: GPU 信息（None 时实时获取）

    Returns:
        VRAMEstimate 结果
    """
    if gpu_info is None:
        gpu_info = get_gpu_info()

    needed = estimate_vram_requirement(
        engine_vram_gb, width, height, batch_size,
        enable_seedvr2, multisample_rule, headroom_gb,
    )

    available = gpu_info.free_vram_gb
    can_run = needed <= available

    # 精度推荐
    if can_run:
        recommended_precision = default_precision
    else:
        # 尝试回退精度
        recommended_precision = fallback_precision
        # fp8 约减半显存
        if fallback_precision == "fp8":
            needed_fp8 = needed * 0.5
            if needed_fp8 <= available:
                can_run = True
                needed = needed_fp8
            else:
                can_run = False

    # chunk 推荐（batch 拆分）
    if batch_size > 1 and not can_run:
        # 尝试拆分成更小的 chunk
        chunk_size = max(1, int(batch_size * available / needed))
        recommended_chunk_size = min(chunk_size, 16 if not enable_seedvr2 else 4)
    else:
        recommended_chunk_size = min(batch_size, 16 if not enable_seedvr2 else 4)

    warning = ""
    if not can_run:
        warning = (
            f"VRAM insufficient: need {needed}GB, available {available}GB. "
            f"Try reducing batch_size or resolution, or use {fallback_precision}."
        )
    elif needed > available * 0.8:
        warning = f"VRAM tight: need {needed}GB, available {available}GB (80% threshold)."

    return VRAMEstimate(
        can_run=can_run,
        needed_vram_gb=needed,
        available_vram_gb=available,
        recommended_precision=recommended_precision,
        recommended_chunk_size=recommended_chunk_size,
        warning=warning,
    )


def recommend_chunk_size(
    batch_size: int,
    enable_seedvr2: bool = False,
) -> int:
    """
    推荐 batch chunk 大小。

    规则（PRD 4.3.2 第5步）:
    - 不开超分：chunk = 16
    - 开超分：chunk = 4
    """
    if enable_seedvr2:
        return min(batch_size, 4)
    return min(batch_size, 16)
