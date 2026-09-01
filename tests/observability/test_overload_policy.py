"""
tests/observability/test_overload_policy.py — P1-8 队列分级过载策略单测

覆盖评估 §9-P1-8 的 70/85/95/100% 分级与 Retry-After / 拒绝原因：
- 70%：proceed（仅观察）
- 85%：小 batch proceed；大 batch 429 + Retry-After
- 95%：429 + Retry-After
- 100%：503
"""

from __future__ import annotations

from app.integrated_app.overload_policy import (
    LARGE_BATCH_THRESHOLD,
    evaluate_overload,
    fill_ratio_of,
)


def test_fill_ratio_of_guards_zero_maxsize():
    assert fill_ratio_of(0, 0) == 1.0
    assert fill_ratio_of(5, 100) == 0.05
    assert fill_ratio_of(200, 100) == 1.0


def test_below_70_proceeds():
    d = evaluate_overload(0.5, batch_size=1)
    assert d.action == "proceed"
    assert d.status == 200
    assert d.retry_after_s == 0


def test_70_warning_proceeds():
    d = evaluate_overload(0.70, batch_size=1)
    assert d.action == "proceed"
    assert d.tier == 1


def test_85_small_batch_proceeds():
    d = evaluate_overload(0.85, batch_size=2)
    assert d.action == "proceed"


def test_85_large_batch_rejected_429():
    d = evaluate_overload(0.85, batch_size=LARGE_BATCH_THRESHOLD + 1)
    assert d.action == "reject_429"
    assert d.status == 429
    assert d.reason == "queue_85_large_batch"
    assert d.retry_after_s > 0


def test_95_rejected_429():
    d = evaluate_overload(0.95, batch_size=1)
    assert d.action == "reject_429"
    assert d.status == 429
    assert d.reason == "queue_95"
    assert d.retry_after_s > 0


def test_100_rejected_503():
    d = evaluate_overload(1.0, batch_size=1)
    assert d.action == "reject_503"
    assert d.status == 503
    assert d.reason == "queue_full"
    assert d.retry_after_s > 0
