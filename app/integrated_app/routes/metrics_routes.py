"""
routes/metrics_routes.py — GET /api/metrics（Prometheus exposition）+ GET /api/alerts

MLOps P0-2 / P0-4（运维稳定性评估）：
- /api/metrics：统一指标抓取端点（零依赖 exposition，标签仅低基数字段）。
- /api/alerts：基于当前指标快照评估告警规则，返回 firing/pending 告警 + Runbook 链接。

路由只做「指标读取 + 渲染 + 告警评估」，不含任何 torch/numpy/推理逻辑，
符合 AGENTS.md §3 硬约束 #1（路由不写业务逻辑/推理代码）。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Request, Response

from ..config import get_config
from ..cost_governance import get_metrics_store
from ..gpu_utils import get_gpu_info
from ..observability.alerts import get_alert_engine, health_unhealthy
from ..observability.generation_metrics import classify_generation_error
from ..observability.metrics import get_metrics
from ..sse import get_sse_bus
from ..task_queue import TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["metrics"])


def _disk_info() -> dict[str, float]:
    try:
        import shutil

        total, _used, free = shutil.disk_usage("/")
        return {"total": float(total), "free": float(free)}
    except Exception:
        return {"total": 0.0, "free": 0.0}


def _refresh_resource_gauges(request: Request) -> None:
    """在渲染前把进程内可观测的瞬时量写入 MetricsStore 风格的单例。"""
    m = get_metrics()

    # 队列
    task_queue = getattr(request.app.state, "task_queue", None)
    if task_queue is not None:
        try:
            size = task_queue.queue_size
            m.queue_depth.set(float(size))
            processing = sum(
                1 for t in task_queue.list_tasks()
                if t.status == TaskStatus.PROCESSING
            )
            m.queue_processing.set(float(processing))
            now = time.time()
            oldest = None
            for t in task_queue.list_tasks():
                if t.status == TaskStatus.PENDING and t.created_at:
                    age = now - t.created_at
                    oldest = age if oldest is None else min(oldest, age)
            m.queue_oldest_age_seconds.set(float(oldest) if oldest is not None else 0.0)
        except Exception as e:  # noqa: BLE001
            logger.debug("refresh queue gauges failed: %s", e)

    # GPU
    try:
        gpu = get_gpu_info()
        if gpu.total_vram_gb:
            m.gpu_memory_used_bytes.set(gpu.used_vram_gb * 1024**3)
            m.gpu_memory_total_bytes.set(gpu.total_vram_gb * 1024**3)
    except Exception as e:  # noqa: BLE001
        logger.debug("refresh gpu gauges failed: %s", e)

    # SSE
    try:
        bus = get_sse_bus()
        m.sse_connected.set(float(bus.subscriber_count))
        m.sse_events_dropped_total.set(float(bus.dropped_events))
    except Exception as e:  # noqa: BLE001
        logger.debug("refresh sse gauges failed: %s", e)

    # 磁盘（按项目根所在卷）
    try:
        d = _disk_info()
        if d["total"]:
            m.disk_total_bytes.set(d["total"])
            m.disk_free_bytes.set(d["free"])
    except Exception as e:  # noqa: BLE001
        logger.debug("refresh disk gauges failed: %s", e)


@router.get("/metrics/prometheus")
async def metrics(request: Request) -> Response:
    """GET /api/metrics/prometheus — Prometheus text exposition。

    与既有 /api/metrics（JSON 成本看板）区分，避免破坏前端看板；Prometheus 抓取此端点。
    每次抓取时刷新进程内瞬时量（队列/SSE/GPU/磁盘），使 gauge 与实际状态一致。
    """
    _refresh_resource_gauges(request)
    body = get_metrics().render()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


def _build_alert_snapshot(request: Request) -> dict[str, Any]:
    cfg = get_config()
    m = get_metrics()

    # 队列填充率
    task_queue = getattr(request.app.state, "task_queue", None)
    fill_ratio = 0.0
    if task_queue is not None:
        maxsize = float(getattr(cfg.runtime.task_queue, "maxsize", 0) or 0)
        if maxsize > 0:
            fill_ratio = min(1.0, task_queue.queue_size / maxsize)

    # 生成失败率（累计 failed / (completed+failed)）
    failed = m.generation_failed_total.total()
    completed = m.generation_completed_total.total()
    failure_rate = (failed / (failed + completed)) if (failed + completed) > 0 else 0.0

    # GPU 可用显存百分比
    gpu_free_pct: float | None = None
    try:
        store = get_metrics_store()
        g = store.latest_gpu
        if g and g.get("total_vram_gb"):
            gpu_free_pct = (g["free_vram_gb"] / g["total_vram_gb"]) * 100.0
    except Exception:
        gpu_free_pct = None

    # 磁盘可用百分比
    d = _disk_info()
    disk_free_pct = (d["free"] / d["total"] * 100.0) if d["total"] else None

    return {
        "queue_fill_ratio": fill_ratio,
        "generation_failure_rate": failure_rate,
        "gpu_free_pct": gpu_free_pct,
        "disk_free_pct": disk_free_pct,
        "health_unhealthy": health_unhealthy(),
        "now": time.time(),
    }


@router.get("/alerts")
async def alerts(request: Request) -> dict[str, Any]:
    """GET /api/alerts — 返回当前 firing/pending 告警与生成健康摘要。"""
    snapshot = _build_alert_snapshot(request)
    active = get_alert_engine().evaluate(snapshot)
    m = get_metrics()
    completed = m.generation_completed_total.total()
    failed = m.generation_failed_total.total()
    accepted = m.generation_accepted_total.total()
    rejected = m.generation_rejected_total.total()

    return {
        "status": "ok",
        "generated_at": snapshot["now"],
        "snapshot": {
            "queue_fill_ratio": round(snapshot["queue_fill_ratio"], 4),
            "generation_failure_rate": round(snapshot["generation_failure_rate"], 4),
            "gpu_free_pct": round(snapshot["gpu_free_pct"], 2) if snapshot["gpu_free_pct"] is not None else None,
            "disk_free_pct": round(snapshot["disk_free_pct"], 2) if snapshot["disk_free_pct"] is not None else None,
            "health_unhealthy": snapshot["health_unhealthy"],
        },
        "alerts": [a.to_dict() for a in active],
        "firing_count": sum(1 for a in active if a.firing),
        "generation_health": {
            "accepted": accepted,
            "completed": completed,
            "failed": failed,
            "rejected": rejected,
            "success_rate": round(completed / (completed + failed), 4) if (completed + failed) > 0 else None,
            "classify_example": classify_generation_error("CUDA out of memory"),
        },
    }
