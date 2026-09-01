"""
observability — 运维可观测性包（MLOps P0-2 / P0-3 / P0-4）

统一指标 / 生成链路埋点 / 告警评估，零外部依赖。
"""

from __future__ import annotations

from .alerts import (
    AlertEngine,
    get_alert_engine,
    health_unhealthy,
    record_health_failure,
    record_health_success,
    reset_alert_engine,
)
from .generation_metrics import (
    classify_generation_error,
    record_generation_accepted,
    record_generation_cancelled,
    record_generation_completed,
    record_generation_failed,
    record_generation_first_preview,
    record_generation_first_progress,
    record_generation_rejected,
    record_generation_started,
    record_generation_submitted,
    record_inference_duration,
    record_queue_wait,
)
from .http_metrics import MetricsMiddleware, normalize_path
from .metrics import Gauge, Histogram, MetricsRegistry, get_metrics, reset_metrics

__all__ = [
    "AlertEngine",
    "get_alert_engine",
    "health_unhealthy",
    "record_health_failure",
    "record_health_success",
    "reset_alert_engine",
    "classify_generation_error",
    "record_generation_accepted",
    "record_generation_cancelled",
    "record_generation_completed",
    "record_generation_failed",
    "record_generation_first_preview",
    "record_generation_first_progress",
    "record_generation_rejected",
    "record_generation_started",
    "record_generation_submitted",
    "record_inference_duration",
    "record_queue_wait",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "get_metrics",
    "reset_metrics",
    "MetricsMiddleware",
    "normalize_path",
]
