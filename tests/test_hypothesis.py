"""
tests/test_hypothesis.py — Hypothesis 属性测试

对应 N14: 属性测试引入
使用 hypothesis 对 VRAM 估算和水印嵌入进行属性测试
"""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from integrated_app.gpu_utils import estimate_vram_requirement, recommend_chunk_size


class TestVRAMEstimationProperties:
    """VRAM 估算属性测试"""

    @given(
        engine_vram=st.floats(min_value=1.0, max_value=100.0),
        width=st.integers(min_value=256, max_value=4096),
        height=st.integers(min_value=256, max_value=4096),
        batch_size=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=30, deadline=2000, suppress_health_check=[HealthCheck.too_slow])
    def test_estimate_always_positive(self, engine_vram, width, height, batch_size):
        """VRAM 估算结果始终为正"""
        needed = estimate_vram_requirement(
            engine_vram_gb=engine_vram,
            width=width, height=height,
            batch_size=batch_size,
            enable_seedvr2=False,
            multisample_rule=1.5,
            headroom_gb=2.0,
        )
        assert needed > 0, f"VRAM estimate should be positive, got {needed}"

    @given(
        batch_size=st.integers(min_value=1, max_value=9999),
        enable_seedvr2=st.booleans(),
    )
    @settings(max_examples=50, deadline=2000)
    def test_chunk_size_always_positive_and_le_batch(self, batch_size, enable_seedvr2):
        """chunk size 始终 > 0 且 ≤ batch_size"""
        chunk = recommend_chunk_size(batch_size, enable_seedvr2)
        assert 1 <= chunk <= batch_size, (
            f"chunk={chunk} should be in [1, {batch_size}]"
        )

    @given(
        batch_size=st.integers(min_value=1, max_value=9999),
        enable_seedvr2=st.booleans(),
    )
    @settings(max_examples=50, deadline=2000)
    def test_chunk_count_covers_full_batch(self, batch_size, enable_seedvr2):
        """所有 chunk 之和 == batch_size"""
        chunk_size = recommend_chunk_size(batch_size, enable_seedvr2)
        chunk_count = (batch_size + chunk_size - 1) // chunk_size
        last_chunk = batch_size - (chunk_count - 1) * chunk_size
        assert 1 <= last_chunk <= chunk_size
        assert (chunk_count - 1) * chunk_size + last_chunk == batch_size


class TestWatermarkProperties:
    """水印嵌入属性测试"""

    @given(
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_watermark_roundtrip_with_different_seeds(self, seed):
        """不同 seed 的图像 → 水印嵌入/验证 roundtrip"""
        from bin.integrated_app import watermark

        rng = np.random.default_rng(seed)
        img = (128 + rng.normal(0, 5, (256, 256))).clip(0, 255)
        ts = 1786200000.0
        marked = watermark.embed_watermark(img, "img_multimodel", f"task_{seed}", ts)
        assert watermark.verify(marked, "img_multimodel", f"task_{seed}", ts) is True

    @given(
        product_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"))),
    )
    @settings(max_examples=15, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_watermark_imperceptible_always(self, product_id):
        """水印不可感知性始终满足"""
        from bin.integrated_app import watermark

        rng = np.random.default_rng(42)
        img = (128 + rng.normal(0, 5, (256, 256))).clip(0, 255)
        marked = watermark.embed_watermark(img, product_id, "task", 1.0)
        max_diff = float(np.abs(marked - img).max())
        assert max_diff < 25, f"Watermark too visible: max_diff={max_diff}"
