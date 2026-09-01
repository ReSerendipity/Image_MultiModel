"""
tests/observability/test_metrics.py — 指标原语 + 生成链路埋点单元测试

MLOps P0-2 / P0-3：验证零依赖指标 exposition、标签低基数、直方图分位、以及
generation_metrics 辅助函数。无需 GPU / 应用实例。
"""

from __future__ import annotations

import pytest

from app.integrated_app.observability import alerts as alerts_mod
from app.integrated_app.observability.generation_metrics import classify_generation_error
from app.integrated_app.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    get_metrics,
    reset_metrics,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_metrics()
    alerts_mod.reset_alert_engine()
    yield
    reset_metrics()
    alerts_mod.reset_alert_engine()


def test_counter_inc_and_total():
    c = Counter("x_total", "desc", labelnames=("engine",))
    c.inc(2.0, engine="a")
    c.inc(3.0, engine="a")
    c.inc(1.0, engine="b")
    assert c.value(engine="a") == 5.0
    assert c.total() == 6.0


def test_counter_rejects_negative():
    c = Counter("x_total", "desc")
    with pytest.raises(ValueError):
        c.inc(-1.0)


def test_gauge_set_and_dec():
    g = Gauge("g", "desc")
    g.set(10.0)
    assert g.value() == 10.0
    g.dec(3.0)
    assert g.value() == 7.0


def test_histogram_buckets_and_quantile():
    h = Histogram("lat", "desc")
    for v in [0.1, 0.5, 1.0, 2.0, 5.0]:
        h.observe(v)
    rendered = h.render()
    assert any("lat_bucket" in line for line in rendered)
    assert any("le=\"+Inf\"" in line for line in rendered)
    assert any("lat_count" in line for line in rendered)


def test_metrics_registry_render_contains_core_metrics():
    m = get_metrics()
    m.http_requests_total.inc(1.0, method="GET", route="/api/health", status="200")
    m.generation_completed_total.inc(1.0, engine="z_image_turbo_native")
    body = m.render()
    for name in (
        "http_requests_total",
        "generation_submitted_total",
        "generation_completed_total",
        "queue_depth",
        "gpu_memory_used_bytes",
        "sse_connected",
        "disk_free_bytes",
    ):
        assert f"# TYPE {name}" in body, f"missing metric {name}"


def test_exposition_format_is_valid():
    m = get_metrics()
    m.http_requests_total.inc(1.0, method="GET", route="/api/health", status="200")
    body = m.render()
    # 校验 HELP/TYPE/样本行结构
    assert "# HELP http_requests_total" in body
    assert "# TYPE http_requests_total counter" in body
    sample = [row for row in body.splitlines() if row.startswith("http_requests_total{")]
    assert sample and 'method="GET"' in sample[0] and 'status="200"' in sample[0]


def test_classify_generation_error_normalizes():
    assert classify_generation_error("CUDA out of memory") == "oom"
    assert classify_generation_error("task timed out after 100s") == "timeout"
    assert classify_generation_error("content blocked by CLIP") == "content_filter"
    assert classify_generation_error("weight sha256 mismatch") == "weight_integrity"
    assert classify_generation_error("") == "unknown"
    assert classify_generation_error("some weird failure") == "inference_error"


def test_registry_singleton_identity():
    assert get_metrics() is get_metrics()
    reset_metrics()
    assert get_metrics() is not None
