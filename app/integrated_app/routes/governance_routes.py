"""
routes/governance_routes.py — 成本资源治理 API

对应 COST_GOVERNANCE_ASSESSMENT_v2.0.0.md 整改路线（自动被 app_server 发现注册）：
- GET  /api/metrics            : GPU/资源指标时序 + 泄漏状态（反模式 #5 修复）
- GET  /api/vram-scheduler     : VRAM 动态 batch 上限状态（P1）
- GET  /api/models/orphans     : 多版本权重孤儿扫描（P1 存储去重）
- POST /api/models/orphans/prune: 删除孤儿权重文件（回收存储）
- GET  /api/finops/cost-report : 成本分摊报表（P2 FinOps）
- GET  /api/finops/budget      : 预算阈值告警（P3）
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from ..config import get_config
from ..cost_governance import (
    budget_check,
    finops_cost_report,
    get_idle_unload_manager,
    get_metrics_store,
    get_vram_scheduler,
    scan_orphan_weights,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["governance"])


def _storage_usage(project_root: Path, base_dir: str) -> dict[str, Any]:
    d = project_root / base_dir
    if not d.exists():
        return {"path": str(d), "used_gb": 0.0, "exists": False}
    try:
        usage = shutil.disk_usage(str(d))
        # 目录自身大小（而非所在磁盘）近似用 du 式遍历代价高，这里用所在分区已用做参考，
        # 同时给出 outputs 目录递归字节数（小目录可接受）。
        total_bytes = 0
        for p in d.rglob("*"):
            if p.is_file():
                total_bytes += p.stat().st_size
        return {
            "path": str(d),
            "used_gb": round(total_bytes / (1024**3), 3),
            "disk_used_gb": round(usage.used / (1024**3), 1),
            "exists": True,
        }
    except Exception as e:  # noqa: BLE001
        return {"path": str(d), "used_gb": 0.0, "error": str(e), "exists": True}


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, Any]:
    """GET /api/metrics — 资源指标时序与泄漏状态。"""
    cfg = get_config()
    store = get_metrics_store()
    project_root = Path(cfg.project_root)
    return {
        "gpu_history": store.get_gpu_history(limit=120),
        "gpu_stats": store.gpu_utilization_stats(),
        "leak": store.leak_status,
        "storage": {
            "outputs": _storage_usage(project_root, cfg.output.base_dir),
            "data": _storage_usage(project_root, "data"),
        },
        "vram_scheduler": {
            "enabled": get_vram_scheduler().enabled,
            "current_max_batch_size": get_vram_scheduler().current_max_batch_size,
        },
        "idle_unload": {
            "enabled": get_idle_unload_manager().idle_unload_minutes > 0,
            "idle_minutes": get_idle_unload_manager().idle_minutes,
        },
        "queue_size": getattr(request.app.state, "task_queue", None) and len(
            getattr(request.app.state.task_queue, "list_tasks", lambda: [])()
        ),
    }


@router.get("/vram-scheduler")
async def vram_scheduler_status() -> dict[str, Any]:
    """GET /api/vram-scheduler — VRAM 水位感知 batch 上限。"""
    s = get_vram_scheduler()
    return {
        "enabled": s.enabled,
        "high_watermark_pct": s.high,
        "low_watermark_pct": s.low,
        "max_batch_size": s.max,
        "min_batch_size": s.min,
        "current_max_batch_size": s.current_max_batch_size,
    }


@router.get("/models/orphans")
async def model_orphans(request: Request) -> dict[str, Any]:
    """GET /api/models/orphans — 多版本权重孤儿扫描。"""
    cfg = get_config()
    result = scan_orphan_weights(cfg, cfg.project_root)
    return result


@router.post("/models/orphans/prune")
async def prune_model_orphans(request: Request, confirm: bool = Query(False)) -> dict[str, Any]:
    """POST /api/models/orphans/prune — 删除孤儿权重文件（需 confirm=true）。

    仅删除 scan_orphan_weights 识别出的、位于模型目录内的孤儿文件，安全回收存储。
    """
    if not confirm:
        raise HTTPException(400, detail="Set confirm=true to prune orphan weights")
    cfg = get_config()
    result = scan_orphan_weights(cfg, cfg.project_root)
    freed = 0.0
    removed = 0
    roots = []
    if cfg.models.model_source_mode == "portable":
        roots.append(Path(cfg.project_root) / cfg.models.portable.internal_models_dir)
        if cfg.models.shared_cache_dir:
            roots.append(Path(cfg.models.shared_cache_dir))
    else:
        roots.append(Path(cfg.models.shared.comfy_models_dir))
    for orphan in result["orphans"]:
        p = Path(orphan["path"])
        if not p.exists() or not p.is_file():
            continue
        # 安全护栏：必须位于已知模型根目录内
        if not any(str(p.resolve()).startswith(str(r.resolve())) for r in roots if r.exists()):
            logger.warning("Skip pruning %s (outside known model roots)", p)
            continue
        try:
            freed += p.stat().st_size / (1024 * 1024)
            p.unlink()
            removed += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to prune %s: %s", p, e)
    return {"removed": removed, "freed_mb": round(freed, 2)}


@router.get("/finops/cost-report")
async def finops_cost_report_endpoint(request: Request) -> dict[str, Any]:
    """GET /api/finops/cost-report — 成本分摊报表。"""
    cfg = get_config()
    history_db = getattr(request.app.state, "history_db", None)
    if history_db is None:
        return {"by_engine": [], "totals": {}, "note": "history_db unavailable"}
    return finops_cost_report(history_db, cfg)


@router.get("/finops/budget")
async def finops_budget_endpoint(request: Request) -> dict[str, Any]:
    """GET /api/finops/budget — 预算阈值告警。"""
    cfg = get_config()
    store = get_metrics_store()
    project_root = Path(cfg.project_root)
    metrics = {
        "gpu": store.latest_gpu or {},
        "storage": {
            "used_gb": _storage_usage(project_root, cfg.output.base_dir).get("used_gb", 0.0),
        },
        "cost": (finops_cost_report(getattr(request.app.state, "history_db", None), cfg)
                 if getattr(request.app.state, "history_db", None) else {"est_gpu_hours": 0.0}),
    }
    return budget_check(cfg, metrics)
