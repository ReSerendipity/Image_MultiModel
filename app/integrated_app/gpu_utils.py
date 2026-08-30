"""
gpu_utils.py — 显存预检 + FP8 回退 + chunk 推荐

对应 MASTER_PLAN §4 / 附录 B4: gpu_utils.py
对应 PRD §2.4.3: vram_multisample_rule ×1.5 + FP8 回退
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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

    # nvidia-smi 兜底（无 torch 环境，Windows/Linux 通用）
    try:
        import subprocess

        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
            name = parts[0]
            # nvidia-smi nounits 输出为 MiB → 换算为 GB
            n_total: float = float(parts[1]) / 1024
            n_used: float = float(parts[2]) / 1024
            n_free: float = float(parts[3]) / 1024
            return GPUInfo(
                total_vram_gb=round(n_total, 2),
                used_vram_gb=round(n_used, 2),
                free_vram_gb=round(n_free, 2),
                gpu_name=name,
                backend="cuda",
            )
    except Exception as e:
        logger.warning(f"Failed to get GPU info via nvidia-smi: {e}")

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
    lora_increment_gb: float = 0.0  # MLOps P0-2: LoRA 栈增量显存
    warning: str = ""


def estimate_vram_requirement(
    engine_vram_gb: float,
    width: int,
    height: int,
    batch_size: int,
    enable_seedvr2: bool = False,
    multisample_rule: float = 1.5,
    headroom_gb: float = 2.0,
    lora_extra_vram_gb: float = 0.0,
) -> float:
    """
    估算推理所需显存（GB）。

    公式: base_vram × multisample_rule × resolution_factor × batch_factor + seedvr2_overhead + lora_extra

    Args:
        engine_vram_gb: 引擎基准显存需求
        width, height: 输出分辨率
        batch_size: 批量大小
        enable_seedvr2: 是否启用 SeedVR2 超分
        multisample_rule: 显存预检系数（默认 1.5）
        headroom_gb: 显存预留
        lora_extra_vram_gb: MLOps P0-2: 多 LoRA 叠加的增量显存（GB）

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

    # MLOps P0-2: 多 LoRA 叠加增量显存
    if lora_extra_vram_gb > 0:
        needed += lora_extra_vram_gb

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
    gpu_info: GPUInfo | None = None,
    allow_tight: bool = False,
    lora_extra_vram_gb: float = 0.0,
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
        allow_tight: 估算不足时是否放行（依赖后端低显存分块换入换出，如 --lowvram）
        lora_extra_vram_gb: MLOps P0-2: 多 LoRA 叠加增量显存（GB）

    Returns:
        VRAMEstimate 结果
    """
    if gpu_info is None:
        gpu_info = get_gpu_info()

    # MLOps P0-2: LoRA 增量以「满精度」计入（保守，避免低估致 OOM）；
    # 精度回退（fp8 约减半）只作用于引擎本体，不缩放 LoRA 增量。
    base_needed = estimate_vram_requirement(
        engine_vram_gb, width, height, batch_size,
        enable_seedvr2, multisample_rule, headroom_gb, lora_extra_vram_gb=0.0,
    )

    available = gpu_info.free_vram_gb
    can_run = base_needed <= available

    # 精度推荐
    if can_run:
        recommended_precision = default_precision
    else:
        recommended_precision = fallback_precision

    # 引擎本体精度缩放（仅回退场景 fp8 约减半；默认精度下即使声明 fp8 也不缩放，与原行为一致）
    scaled_base = base_needed
    if not can_run and recommended_precision == "fp8" and base_needed * 0.5 <= available:
        scaled_base = base_needed * 0.5
        can_run = True

    # 紧张放行：估算仍不足但后端支持低显存分块（--lowvram 换入换出）
    tight_continue = False
    if not can_run and allow_tight:
        can_run = True
        tight_continue = True
        if recommended_precision == "fp8":
            scaled_base = base_needed * 0.5

    # 叠加 LoRA 满精度增量（不被 fp8 缩放，偏保守，防 OOM 低估）
    needed = scaled_base + lora_extra_vram_gb
    # 叠加后若超出可用显存则重新判定（allow_tight 仍放行）
    if lora_extra_vram_gb > 0 and needed > available and not allow_tight:
        can_run = False

    # chunk 推荐（batch 拆分）
    if batch_size > 1 and not can_run:
        # 尝试拆分成更小的 chunk
        chunk_size = max(1, int(batch_size * available / needed))
        recommended_chunk_size = min(chunk_size, 16 if not enable_seedvr2 else 4)
    else:
        recommended_chunk_size = min(batch_size, 16 if not enable_seedvr2 else 4)

    warning = ""
    if tight_continue:
        warning = (
            f"VRAM tight: need {needed}GB, available {available}GB. "
            f"已放行（后端低显存分块换入换出），可能较慢；如 OOM 请降低分辨率或 batch。"
        )
    elif not can_run:
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
        lora_increment_gb=lora_extra_vram_gb,
        warning=warning,
    )


def preflight_vram_with_loras(
    engine_vram_gb: float,
    lora_stack: list[dict],
    width: int,
    height: int,
    batch_size: int,
    lora_paths: dict[str, str] | None = None,
    enable_seedvr2: bool = False,
    fallback_precision: str = "fp8",
    default_precision: str = "fp8",
    multisample_rule: float = 1.5,
    headroom_gb: float = 2.0,
    gpu_info: GPUInfo | None = None,
    allow_tight: bool = False,
) -> VRAMEstimate:
    """MLOps P0-2: 含多 LoRA 叠加增量显存的显存预检便捷封装。

    自动根据 ``lora_stack``（``[{"name","strength"}]``）与 ``lora_paths``（name→绝对路径）
    估算 LoRA 栈增量显存，再委托 :func:`preflight_vram`。

    Args:
        engine_vram_gb: 引擎基准显存
        lora_stack: 生效 LoRA 栈
        width, height, batch_size: 推理参数
        lora_paths: ``{name: abs_path}``（由 ``lora.resolve_lora_paths`` 生成）
        enable_seedvr2 / fallback_precision / default_precision / multisample_rule /
        headroom_gb / gpu_info / allow_tight: 同 :func:`preflight_vram`

    Returns:
        VRAMEstimate 结果（含 ``lora_increment_gb``）
    """
    from .native.vram import estimate_lora_stack_vram_from_stack

    lora_extra = estimate_lora_stack_vram_from_stack(lora_stack or [], lora_paths or {})
    return preflight_vram(
        engine_vram_gb, width, height, batch_size,
        enable_seedvr2=enable_seedvr2,
        fallback_precision=fallback_precision,
        default_precision=default_precision,
        multisample_rule=multisample_rule,
        headroom_gb=headroom_gb,
        gpu_info=gpu_info,
        allow_tight=allow_tight,
        lora_extra_vram_gb=lora_extra,
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


# ──────────────────────────────────────────────────────────────
#  MLOps P1·可观测：长运行显存泄漏监控
# ──────────────────────────────────────────────────────────────
@dataclass
class VRAMSample:
    """单次显存采样快照。"""

    timestamp: float
    allocated_bytes: int  # torch.cuda.max_memory_allocated（进程峰值分配）
    reserved_bytes: int  # torch.cuda.memory_reserved（缓存预留）
    free_vram_gb: float
    total_vram_gb: float


def _default_vram_sampler() -> dict[str, float]:
    """默认采样器：组合 get_gpu_info 与 torch 峰值分配（无 torch 时全 0）。"""
    info = get_gpu_info()
    allocated = 0
    reserved = 0
    try:
        import torch

        if torch.cuda.is_available():
            allocated = int(torch.cuda.max_memory_allocated() or 0)
            reserved = int(torch.cuda.memory_reserved() or 0)
    except Exception:  # pragma: no cover - torch 缺失
        pass
    return {
        "allocated_bytes": allocated,
        "reserved_bytes": reserved,
        "free_vram_gb": info.free_vram_gb,
        "total_vram_gb": info.total_vram_gb,
    }


class VRAMLeakMonitor:
    """长运行显存泄漏监控器。

    周期性调用 :meth:`sample` 采集 ``max_memory_allocated``，若窗口内分配量
    **单调不降** 且累计增长超过阈值，则判定存在显存泄漏（对应反模式 #5）。

    ``sample_fn`` 可注入，便于无 GPU 环境下单测。
    """

    def __init__(
        self,
        *,
        window: int = 20,
        growth_threshold_gb: float = 2.0,
        monotonic_tolerance_bytes: int = 1024 * 1024,
        sample_fn: Callable[[], dict[str, float]] | None = None,
    ) -> None:
        self.window = window
        self.growth_threshold_gb = growth_threshold_gb
        self._tolerance = monotonic_tolerance_bytes
        self._sample_fn = sample_fn or _default_vram_sampler
        self._samples: list[VRAMSample] = []
        self.leak_detected: bool = False

    def sample(self, now: float | None = None) -> VRAMSample:
        """采集一次样本并维护滑动窗口。"""
        data = self._sample_fn()
        ts = now if now is not None else time.time()
        s = VRAMSample(
            timestamp=ts,
            allocated_bytes=int(data.get("allocated_bytes", 0)),
            reserved_bytes=int(data.get("reserved_bytes", 0)),
            free_vram_gb=float(data.get("free_vram_gb", 0.0)),
            total_vram_gb=float(data.get("total_vram_gb", 0.0)),
        )
        self._samples.append(s)
        if len(self._samples) > self.window:
            self._samples.pop(0)
        return s

    def check_leak(self) -> dict[str, Any]:
        """基于当前窗口判定是否泄漏。

        Returns:
            ``{"leak_detected", "growth_gb", "samples", "monotonic", "reason"}``
        """
        if len(self._samples) < 2:
            return {
                "leak_detected": False,
                "growth_gb": 0.0,
                "samples": len(self._samples),
                "monotonic": False,
                "reason": "insufficient_samples",
            }
        recent = self._samples[-self.window:]
        monotonic = all(
            recent[i + 1].allocated_bytes >= recent[i].allocated_bytes - self._tolerance
            for i in range(len(recent) - 1)
        )
        growth_gb = (recent[-1].allocated_bytes - recent[0].allocated_bytes) / (1024**3)
        leak = bool(monotonic and growth_gb >= self.growth_threshold_gb)
        self.leak_detected = leak
        return {
            "leak_detected": leak,
            "growth_gb": round(growth_gb, 4),
            "samples": len(recent),
            "monotonic": monotonic,
            "reason": "monotonic_growth" if leak else "ok",
        }

    def reset(self) -> None:
        self._samples.clear()
        self.leak_detected = False
