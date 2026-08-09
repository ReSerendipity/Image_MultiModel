"""
comfy/vram_scheduler.py — ComfyUI VRAM 感知调度适配层

P2-1 改造（来源：Seedvr2 BlockSwap 思路）：
在推理提交前检查 VRAM 水位，高水位时自动降低 batch/chunk 参数，
低水位时恢复正常参数。作为 ComfyUI 任务调度的显存准入控制层。

核心 API:
    scheduler = ComfyVramScheduler(config)
    allowed, adjusted = scheduler.before_submit(prompt_params)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..gpu_utils import get_gpu_info

logger = logging.getLogger(__name__)


@dataclass
class VRamSample:
    """单次 VRAM 采样数据。"""
    timestamp: float
    used_pct: float
    free_gb: float
    total_gb: float


@dataclass
class SchedulerDecision:
    """调度器决策结果。"""
    allowed: bool
    adjusted_params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    vram_used_pct: float = 0.0


class ComfyVramScheduler:
    """ComfyUI VRAM 感知调度器。

    内部维护 VRAM 水位滑动窗口，在 before_submit 时检查水位：
    - 高水位（> high_watermark_pct）：降低 batch_size，返回 adjusted_params
    - 低水位（< low_watermark_pct）：恢复正常参数
    - 中间水位：维持当前参数

    调度器开关关闭时，before_submit 总是返回 allowed=True 且不调整参数。
    """

    def __init__(
        self,
        config: Any | None = None,
        high_watermark_pct: int = 90,
        low_watermark_pct: int = 70,
        sample_interval_s: float = 0.5,
        max_batch_size: int = 4,
        min_batch_size: int = 1,
        window_size: int = 10,
    ) -> None:
        """初始化调度器。

        Args:
            config: VRamSchedulerConfig 实例（优先使用其字段值）。
            high_watermark_pct: 高水位线百分比。
            low_watermark_pct: 低水位线百分比。
            sample_interval_s: 采样间隔（秒）。
            max_batch_size: 最大允许的 batch_size。
            min_batch_size: 最小允许的 batch_size。
            window_size: 滑动窗口大小（采样点数）。
        """
        if config is not None:
            self.enabled: bool = getattr(config, "enabled", False)
            self.high_watermark_pct: int = getattr(config, "vram_high_watermark_pct", 90)
            self.low_watermark_pct: int = getattr(config, "vram_low_watermark_pct", 70)
            self.sample_interval_s: float = getattr(config, "sample_interval_s", 0.5)
            self.max_batch_size: int = getattr(config, "max_batch_size", 4)
            self.min_batch_size: int = getattr(config, "min_batch_size", 1)
        else:
            self.enabled = False
            self.high_watermark_pct = high_watermark_pct
            self.low_watermark_pct = low_watermark_pct
            self.sample_interval_s = sample_interval_s
            self.max_batch_size = max_batch_size
            self.min_batch_size = min_batch_size

        self._window: deque[VRamSample] = deque(maxlen=window_size)
        self._last_sample_time: float = 0.0
        self._degraded: bool = False  # 是否处于降级状态

    def _sample_vram(self) -> VRamSample | None:
        """采样一次 VRAM 水位。"""
        try:
            gpu = get_gpu_info()
            if gpu.total_vram_gb <= 0:
                return None
            used_pct = (gpu.used_vram_gb / gpu.total_vram_gb) * 100 if gpu.total_vram_gb > 0 else 0
            return VRamSample(
                timestamp=time.time(),
                used_pct=round(used_pct, 1),
                free_gb=gpu.free_vram_gb,
                total_gb=gpu.total_vram_gb,
            )
        except Exception as e:
            logger.warning(f"VRAM sampling failed: {e}")
            return None

    def _get_avg_vram_pct(self) -> float | None:
        """获取滑动窗口平均 VRAM 使用率。"""
        now = time.time()
        # 按间隔采样
        if now - self._last_sample_time >= self.sample_interval_s or not self._window:
            sample = self._sample_vram()
            if sample is not None:
                self._window.append(sample)
                self._last_sample_time = now

        if not self._window:
            return None

        return sum(s.used_pct for s in self._window) / len(self._window)

    def before_submit(self, prompt_params: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """准入检查：在向 ComfyUI 提交前检查 VRAM 水位。

        Args:
            prompt_params: 原始提交参数（含 batch_size 等）。

        Returns:
            (allowed, adjusted_params):
                - allowed: 是否允许提交
                - adjusted_params: 可能调整后的参数
        """
        if not self.enabled:
            return True, prompt_params

        avg_pct = self._get_avg_vram_pct()

        if avg_pct is None:
            # 无法获取 VRAM 信息，放行不调整
            return True, prompt_params

        decision = self._make_decision(avg_pct, prompt_params)

        if decision.adjusted_params != prompt_params:
            logger.info(
                f"[VRAM-Scheduler] 参数调整: "
                f"batch_size {prompt_params.get('batch_size', 1)} → "
                f"{decision.adjusted_params.get('batch_size', 1)}, "
                f"VRAM {avg_pct:.1f}%, "
                f"reason={decision.reason}"
            )

        return decision.allowed, decision.adjusted_params

    def _make_decision(self, avg_pct: float, params: dict[str, Any]) -> SchedulerDecision:
        """根据 VRAM 水位做调度决策。"""
        original_batch = params.get("batch_size", 1)
        adjusted = dict(params)

        if avg_pct > self.high_watermark_pct:
            # 高水位：降级
            self._degraded = True
            if original_batch > self.min_batch_size:
                new_batch = max(self.min_batch_size, original_batch // 2)
                adjusted["batch_size"] = new_batch
                return SchedulerDecision(
                    allowed=True,
                    adjusted_params=adjusted,
                    reason=f"high_watermark ({avg_pct:.1f}% > {self.high_watermark_pct}%)",
                    vram_used_pct=avg_pct,
                )
            else:
                # 已经是最小 batch，仍然允许但发出警告
                return SchedulerDecision(
                    allowed=True,
                    adjusted_params=adjusted,
                    reason="high_watermark but batch already at minimum",
                    vram_used_pct=avg_pct,
                )

        elif avg_pct < self.low_watermark_pct:
            # 低水位：恢复
            if self._degraded:
                self._degraded = False
                logger.info(f"[VRAM-Scheduler] VRAM 恢复正常 ({avg_pct:.1f}% < {self.low_watermark_pct}%)")
            return SchedulerDecision(
                allowed=True,
                adjusted_params=adjusted,
                reason="normal",
                vram_used_pct=avg_pct,
            )

        else:
            # 中间水位：维持当前
            return SchedulerDecision(
                allowed=True,
                adjusted_params=adjusted,
                reason="mid_range",
                vram_used_pct=avg_pct,
            )

    def get_status(self) -> dict[str, Any]:
        """获取调度器当前状态（供调试/SSE 推送）。"""
        avg_pct = self._get_avg_vram_pct()
        return {
            "enabled": self.enabled,
            "vram_used_pct": avg_pct,
            "high_watermark_pct": self.high_watermark_pct,
            "low_watermark_pct": self.low_watermark_pct,
            "degraded": self._degraded,
            "window_size": len(self._window),
        }
