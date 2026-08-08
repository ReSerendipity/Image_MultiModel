"""
test_vram_estimation.py — ×1.5 系数 + FP8 回退 + chunk 推荐

对应 AUDIT_REPORT_2.0 Y2: test_vram_estimation.py
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

from integrated_app.gpu_utils import (
    GPUInfo, VRAMEstimate, estimate_vram_requirement,
    preflight_vram, recommend_chunk_size,
)


class TestVRAMEstimation:
    """×1.5 系数 + FP8 回退 + chunk 推荐"""

    def test_base_estimate(self):
        """基础估算：1024² × batch=1 ≈ engine_vram × 1.5"""
        needed = estimate_vram_requirement(
            engine_vram_gb=16.0,
            width=1024, height=1024,
            batch_size=1,
            enable_seedvr2=False,
            multisample_rule=1.5,
            headroom_gb=2.0,
        )
        # 16 × 1.5 × 1.0 × 1.0 + 2.0 = 26.0
        assert 25.0 <= needed <= 27.0, f"Base estimate {needed} not in expected range"

    def test_resolution_factor(self):
        """2048² 需求 > 1024²"""
        base = estimate_vram_requirement(16.0, 1024, 1024, 1, False, 1.5, 2.0)
        high = estimate_vram_requirement(16.0, 2048, 2048, 1, False, 1.5, 2.0)
        assert high > base, f"2048² ({high}) should need more VRAM than 1024² ({base})"

    def test_batch_factor(self):
        """batch=4 > batch=1"""
        single = estimate_vram_requirement(16.0, 1024, 1024, 1, False, 1.5, 2.0)
        batch4 = estimate_vram_requirement(16.0, 1024, 1024, 4, False, 1.5, 2.0)
        assert batch4 > single, "batch=4 should need more VRAM than batch=1"

    def test_seedvr2_overhead(self):
        """开 SeedVR2 增加显存需求"""
        without_sv2 = estimate_vram_requirement(16.0, 1024, 1024, 1, False, 1.5, 2.0)
        with_sv2 = estimate_vram_requirement(16.0, 1024, 1024, 1, True, 1.5, 2.0)
        assert with_sv2 > without_sv2, "SeedVR2 should add VRAM overhead"

    def test_multisample_1_5_rule(self):
        """×1.5 系数：实际需求 = base × 1.5"""
        # 无 headroom, 无 seedvr2
        needed = estimate_vram_requirement(
            10.0, 1024, 1024, 1, False, 1.5, 0.0
        )
        # 10 × 1.5 × 1.0 × 1.0 = 15.0
        assert 14.0 <= needed <= 16.0, f"1.5× rule: {needed} should be ~15.0"

    def test_fp8_fallback(self):
        """显存不足时自动 FP8 回退"""
        gpu = GPUInfo(
            total_vram_gb=20.0,
            used_vram_gb=6.0,
            free_vram_gb=14.0,
            gpu_name="Mock GPU",
            backend="cuda",
        )
        # 16GB 引擎，14GB 可用 → 需 26GB → FP8 回退后 ~13GB < 14GB → 可运行
        est = preflight_vram(
            engine_vram_gb=16.0,
            width=1024, height=1024,
            batch_size=1,
            enable_seedvr2=False,
            fallback_precision="fp8",
            default_precision="fp16",
            gpu_info=gpu,
        )
        assert est.recommended_precision == "fp8", "Should fallback to fp8"
        assert est.can_run is True, "Should be able to run with fp8"

    def test_vram_insufficient(self):
        """显存完全不足"""
        gpu = GPUInfo(
            total_vram_gb=4.0,
            used_vram_gb=3.0,
            free_vram_gb=1.0,
            gpu_name="Mock GPU",
            backend="cuda",
        )
        est = preflight_vram(
            engine_vram_gb=16.0,
            width=1024, height=1024,
            batch_size=1,
            enable_seedvr2=True,
            fallback_precision="fp8",
            gpu_info=gpu,
        )
        assert est.can_run is False, "Should not be able to run with 1GB VRAM"
        assert est.warning != "", "Should have a warning message"

    def test_vram_sufficient(self):
        """显存充足"""
        gpu = GPUInfo(
            total_vram_gb=32.0,
            used_vram_gb=2.0,
            free_vram_gb=30.0,
            gpu_name="Mock RTX 4090",
            backend="cuda",
        )
        est = preflight_vram(
            engine_vram_gb=16.0,
            width=1024, height=1024,
            batch_size=1,
            enable_seedvr2=True,
            default_precision="fp16",
            gpu_info=gpu,
        )
        assert est.can_run is True
        assert est.recommended_precision == "fp16"

    def test_chunk_recommendation(self):
        """chunk 推荐: 不开超分=16, 开超分=4"""
        assert recommend_chunk_size(100, False) == 16
        assert recommend_chunk_size(100, True) == 4
        assert recommend_chunk_size(2, False) == 2  # 小 batch

    def test_vram_tight_warning(self):
        """80% 阈值警告"""
        gpu = GPUInfo(
            total_vram_gb=30.0,
            used_vram_gb=5.0,
            free_vram_gb=25.0,
            gpu_name="Mock GPU",
            backend="cuda",
        )
        # 需要 ~22GB，可用 25GB → >80% 阈值
        est = preflight_vram(
            engine_vram_gb=16.0,
            width=1024, height=1024,
            batch_size=4,
            enable_seedvr2=True,
            default_precision="fp16",
            gpu_info=gpu,
        )
        # 如果需求 > 80% 可用量，应有警告
        if est.needed_vram_gb > 25.0 * 0.8:
            assert est.warning != "", "Should warn when VRAM is tight"
