"""
test_vram_leak_monitor.py — 长运行显存泄漏监控（MLOps P1·可观测）单测

通过注入采样器验证 VRAMLeakMonitor 的泄漏判定逻辑，无需 GPU / torch。
"""

from __future__ import annotations

from integrated_app.gpu_utils import VRAMLeakMonitor


def _make_sampler(values_gb):
    """返回一个按序产出 allocated_bytes（GB→bytes）的采样器工厂。"""
    seq = [int(v * 1024**3) for v in values_gb]
    it = iter(seq)

    def sampler():
        try:
            alloc = next(it)
        except StopIteration:
            alloc = int(values_gb[-1] * 1024**3)
        return {"allocated_bytes": alloc, "reserved_bytes": alloc, "free_vram_gb": 8.0, "total_vram_gb": 24.0}

    return sampler


def test_no_leak_when_constant() -> None:
    mon = VRAMLeakMonitor(window=5, growth_threshold_gb=2.0, sample_fn=_make_sampler([1, 1, 1, 1, 1]))
    for _ in range(5):
        mon.sample()
    rep = mon.check_leak()
    assert rep["leak_detected"] is False
    assert rep["monotonic"] is True  # 恒等仍算单调，但增长为 0 < 阈值


def test_leak_detected_on_monotonic_growth() -> None:
    # 单调增长超过 2GB 阈值
    mon = VRAMLeakMonitor(window=6, growth_threshold_gb=2.0, sample_fn=_make_sampler([1, 1.5, 2, 2.5, 3, 4]))
    for i in range(6):
        mon.sample(now=i)
    rep = mon.check_leak()
    assert rep["leak_detected"] is True
    assert rep["growth_gb"] >= 2.0


def test_no_leak_when_growth_below_threshold() -> None:
    mon = VRAMLeakMonitor(window=6, growth_threshold_gb=2.0, sample_fn=_make_sampler([1, 1.2, 1.4, 1.6, 1.8, 2.0]))
    for i in range(6):
        mon.sample(now=i)
    rep = mon.check_leak()
    assert rep["leak_detected"] is False


def test_no_leak_when_allocated_drops() -> None:
    # 中间有回落 → 非单调 → 不误报
    mon = VRAMLeakMonitor(window=6, growth_threshold_gb=2.0, sample_fn=_make_sampler([1, 3, 1, 3, 1, 4]))
    for i in range(6):
        mon.sample(now=i)
    rep = mon.check_leak()
    # 即使净增长 3GB，但非单调，应不报泄漏
    assert rep["monotonic"] is False
    assert rep["leak_detected"] is False


def test_insufficient_samples() -> None:
    mon = VRAMLeakMonitor(window=5, growth_threshold_gb=2.0, sample_fn=_make_sampler([1, 2]))
    mon.sample(now=0)
    rep = mon.check_leak()
    assert rep["leak_detected"] is False
    assert rep["reason"] == "insufficient_samples"


def test_reset_clears_state() -> None:
    mon = VRAMLeakMonitor(window=5, growth_threshold_gb=2.0, sample_fn=_make_sampler([1, 2, 3, 4, 5]))
    for i in range(5):
        mon.sample(now=i)
    assert mon.check_leak()["leak_detected"] is True
    mon.reset()
    assert mon.check_leak()["reason"] == "insufficient_samples"
