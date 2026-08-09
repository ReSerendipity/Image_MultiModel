"""
tests/test_comfy_vram_scheduler.py — VRAM 调度器参数化测试

P2-1 改造：构造不同 VRAM 水位场景验证调度器行为
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

from integrated_app.comfy.vram_scheduler import ComfyVramScheduler
from integrated_app.config_models import VRamSchedulerConfig
from integrated_app.gpu_utils import GPUInfo


def _make_gpu_info(used_pct: float, total_gb: float = 12.0) -> GPUInfo:
    """构造指定使用率的 GPUInfo。"""
    used = total_gb * used_pct / 100
    return GPUInfo(
        total_vram_gb=total_gb,
        used_vram_gb=round(used, 2),
        free_vram_gb=round(total_gb - used, 2),
        gpu_name="Mock GPU",
        backend="cuda",
    )


class TestComfyVramSchedulerDisabled:
    """调度器关闭时行为"""

    def test_disabled_always_allows(self):
        """关闭时 always allow，不调整参数"""
        config = VRamSchedulerConfig(enabled=False)
        scheduler = ComfyVramScheduler(config)
        params = {"batch_size": 4, "steps": 8}
        allowed, adjusted = scheduler.before_submit(params)
        assert allowed is True
        assert adjusted == params

    def test_disabled_no_vram_sampling(self):
        """关闭时不采样"""
        config = VRamSchedulerConfig(enabled=False)
        scheduler = ComfyVramScheduler(config)
        with patch("integrated_app.comfy.vram_scheduler.get_gpu_info") as mock:
            scheduler.before_submit({"batch_size": 1})
            mock.assert_not_called()


class TestComfyVramSchedulerEnabled:
    """调度器开启时行为"""

    @pytest.fixture
    def enabled_config(self):
        return VRamSchedulerConfig(
            enabled=True,
            vram_high_watermark_pct=90,
            vram_low_watermark_pct=70,
            sample_interval_s=0,
            max_batch_size=4,
            min_batch_size=1,
        )

    def test_high_watermark_reduces_batch(self, enabled_config):
        """高水位时自动降低 batch_size"""
        scheduler = ComfyVramScheduler(enabled_config)
        with patch(
            "integrated_app.comfy.vram_scheduler.get_gpu_info",
            return_value=_make_gpu_info(95),
        ):
            allowed, adjusted = scheduler.before_submit({"batch_size": 4, "steps": 8})
        assert allowed is True
        assert adjusted["batch_size"] == 2  # 4 // 2 = 2
        assert adjusted["steps"] == 8  # 其他参数不变

    def test_low_watermark_keeps_params(self, enabled_config):
        """低水位时维持原始参数"""
        scheduler = ComfyVramScheduler(enabled_config)
        with patch(
            "integrated_app.comfy.vram_scheduler.get_gpu_info",
            return_value=_make_gpu_info(50),
        ):
            allowed, adjusted = scheduler.before_submit({"batch_size": 4, "steps": 8})
        assert allowed is True
        assert adjusted["batch_size"] == 4

    def test_mid_watermark_keeps_params(self, enabled_config):
        """中间水位时维持原始参数"""
        scheduler = ComfyVramScheduler(enabled_config)
        with patch(
            "integrated_app.comfy.vram_scheduler.get_gpu_info",
            return_value=_make_gpu_info(80),
        ):
            allowed, adjusted = scheduler.before_submit({"batch_size": 4, "steps": 8})
        assert allowed is True
        assert adjusted["batch_size"] == 4

    def test_min_batch_not_reduced_below_min(self, enabled_config):
        """batch 不会降到低于 min_batch_size"""
        scheduler = ComfyVramScheduler(enabled_config)
        with patch(
            "integrated_app.comfy.vram_scheduler.get_gpu_info",
            return_value=_make_gpu_info(95),
        ):
            allowed, adjusted = scheduler.before_submit({"batch_size": 1})
        assert allowed is True
        assert adjusted["batch_size"] == 1  # 已经最小

    def test_recovery_from_degraded(self, enabled_config):
        """从降级恢复到正常"""
        scheduler = ComfyVramScheduler(enabled_config)
        # 高水位降级
        with patch(
            "integrated_app.comfy.vram_scheduler.get_gpu_info",
            return_value=_make_gpu_info(95),
        ):
            _, adjusted_high = scheduler.before_submit({"batch_size": 4})
        assert adjusted_high["batch_size"] == 2

        # 低水位恢复
        with patch(
            "integrated_app.comfy.vram_scheduler.get_gpu_info",
            return_value=_make_gpu_info(50),
        ):
            _, adjusted_low = scheduler.before_submit({"batch_size": 4})
        assert adjusted_low["batch_size"] == 4

    def test_get_status(self, enabled_config):
        """get_status 返回正确结构"""
        scheduler = ComfyVramScheduler(enabled_config)
        with patch(
            "integrated_app.comfy.vram_scheduler.get_gpu_info",
            return_value=_make_gpu_info(60),
        ):
            status = scheduler.get_status()
        assert status["enabled"] is True
        assert "vram_used_pct" in status
        assert "degraded" in status

    def test_vram_sampling_failure_allows(self, enabled_config):
        """VRAM 采样失败时放行不调整"""
        scheduler = ComfyVramScheduler(enabled_config)
        with patch(
            "integrated_app.comfy.vram_scheduler.get_gpu_info",
            side_effect=RuntimeError("GPU not available"),
        ):
            allowed, adjusted = scheduler.before_submit({"batch_size": 4, "steps": 8})
        assert allowed is True
        assert adjusted["batch_size"] == 4
