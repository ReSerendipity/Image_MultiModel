"""
routes/generate_routes.py — POST /api/generate + 批量

对应 MASTER_PLAN §5.1: POST /api/generate → {task_id}
对应 MASTER_PLAN §5.1: POST /api/generate/batch

架构评估 P0-1 改造：业务逻辑（校验 / 安全过滤 / VRAM 预检 / 过载策略 /
血缘落库 / 入队 / 成本埋点）已下沉至 ``services.generation_service``。
本模块仅保留 API 契约：请求绑定、响应装配、HTTP 语义。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..services.generation_service import (
    BatchGenerateRequest,
    GenerateRequest,
    GenerateResponse,
    GenerationService,
)
from ..task_queue import TaskQueue, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])

# re-export：保持既有 `from ..routes.generate_routes import GenerateRequest` 导入路径可用
__all__ = ["BatchGenerateRequest", "GenerateRequest", "GenerateResponse", "router"]


def _service(request: Request) -> GenerationService:
    """从 app.state 组装 GenerationService（Controller → Service 的唯一装配点）。"""
    return GenerationService(
        task_queue=request.app.state.task_queue,
        history_db=request.app.state.history_db,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, request: Request) -> GenerateResponse:
    """POST /api/generate — 提交 txt2img 任务 → {task_id}"""
    return await _service(request).submit_txt2img(req)


@router.post("/generate/batch")
async def generate_batch(req: BatchGenerateRequest, request: Request) -> dict[str, Any]:
    """POST /api/generate/batch — 批量生成（Prompt 文件 × Grid 6 维）"""
    return await _service(request).submit_batch(req)


@router.get("/tasks/batch/{batch_id}")
async def get_batch_status(batch_id: str, request: Request) -> dict[str, Any]:
    """GET /api/tasks/batch/{id} — 查询批量进度"""
    task_queue: TaskQueue = request.app.state.task_queue
    tasks = [t for t in task_queue.list_tasks() if t.batch_id == batch_id]

    if not tasks:
        raise HTTPException(404, detail="Batch not found")

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    cancelled = sum(1 for t in tasks if t.status == TaskStatus.CANCELLED)
    processing = sum(1 for t in tasks if t.status == TaskStatus.PROCESSING)
    pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)

    return {
        "batch_id": batch_id,
        "total": total,
        "completed": completed,
        "failed": failed,
        "cancelled": cancelled,
        "processing": processing,
        "pending": pending,
        "progress_pct": int(completed / total * 100) if total > 0 else 0,
    }
