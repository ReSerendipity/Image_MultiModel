"""
observability/generation_metrics.py — 生成链路指标埋点辅助

MLOps P0-3（运维稳定性评估）：统一 submitted/accepted/started/first_progress/
first_preview/completed/failed/cancelled 计数与端到端延迟分段。

所有函数直接调用 ``get_metrics()`` 单例，零额外依赖。调用点：
- routes/generate_routes.py：提交/接受/拒绝
- app_server.py 的 on_status / on_progress 回调：start/进度/预览/完成/失败/取消 + 延迟
"""

from __future__ import annotations

from .metrics import get_metrics


def record_generation_submitted(engine: str) -> None:
    get_metrics().generation_submitted_total.inc(1.0, engine=engine or "unknown")


def record_generation_accepted(engine: str) -> None:
    get_metrics().generation_accepted_total.inc(1.0, engine=engine or "unknown")


def record_generation_rejected(error_code: str) -> None:
    get_metrics().generation_rejected_total.inc(1.0, error_code=error_code or "unknown")


def record_generation_started(engine: str) -> None:
    get_metrics().generation_started_total.inc(1.0, engine=engine or "unknown")


def record_generation_first_progress(engine: str) -> None:
    get_metrics().generation_first_progress_total.inc(1.0, engine=engine or "unknown")


def record_generation_first_preview(engine: str) -> None:
    get_metrics().generation_first_preview_total.inc(1.0, engine=engine or "unknown")


def record_generation_completed(engine: str, duration_s: float) -> None:
    m = get_metrics()
    m.generation_completed_total.inc(1.0, engine=engine or "unknown")
    m.generation_duration_seconds.observe(max(0.0, float(duration_s)), engine=engine or "unknown")


def record_generation_failed(engine: str, error_code: str = "error") -> None:
    get_metrics().generation_failed_total.inc(1.0, engine=engine or "unknown", error_code=error_code or "error")


def record_generation_cancelled(engine: str) -> None:
    get_metrics().generation_cancelled_total.inc(1.0, engine=engine or "unknown")


def record_queue_wait(engine: str, wait_s: float) -> None:
    get_metrics().generation_queue_wait_seconds.observe(max(0.0, float(wait_s)), engine=engine or "unknown")


def record_inference_duration(engine: str, duration_s: float) -> None:
    get_metrics().generation_inference_seconds.observe(max(0.0, float(duration_s)), engine=engine or "unknown")


def classify_generation_error(error: str) -> str:
    """把异常文本归一到稳定的 error_code（便于告警去重与 SLO 分母排除）。

    返回低基数字符串，禁止把原始 traceback 直接作为 label。
    """
    if not error:
        return "unknown"
    e = error.lower()
    if "out of memory" in e or "cuda out of memory" in e or "oom" in e:
        return "oom"
    if "timeout" in e or "timed out" in e:
        return "timeout"
    if "cancel" in e:
        return "cancelled"
    if "content" in e or "safety" in e or "clip" in e:
        return "content_filter"
    if "weight" in e or "safetensors" in e or "corrupt" in e or "integrity" in e:
        return "weight_integrity"
    if "model" in e and ("not found" in e or "load" in e):
        return "model_load"
    return "inference_error"
