"""
routes/task_routes.py — 任务历史 + 取消 + 重绘 + 批量删除

对应 MASTER_PLAN §5.1: GET /api/tasks, GET /api/tasks/{id}, POST cancel, POST redraw, DELETE
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..config import get_config
from ..history_db import HistoryDB
from ..task_queue import TaskQueue, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    request: Request,
    status: Optional[str] = None,
    engine: Optional[str] = None,
    q: Optional[str] = None,
    favorite: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """GET /api/tasks — 历史分页筛选"""
    history_db: HistoryDB = request.app.state.history_db
    tasks, total = history_db.list_tasks(
        status=status, engine=engine, q=q, favorite=favorite,
        page=page, page_size=page_size,
    )
    return {
        "tasks": tasks,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request) -> Dict[str, Any]:
    """GET /api/tasks/{id} — 任务详情（含 generation_config 22 项 + 三路输出）"""
    history_db: HistoryDB = request.app.state.history_db
    task = history_db.get_task(task_id)
    if not task:
        raise HTTPException(404, detail=f"Task not found: {task_id}")
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request) -> Dict[str, Any]:
    """POST /api/tasks/{id}/cancel — 取消（/interrupt + 队列清理）"""
    task_queue: TaskQueue = request.app.state.task_queue
    success = await task_queue.cancel(task_id)
    if not success:
        raise HTTPException(404, detail=f"Task not found or not cancellable: {task_id}")
    # 更新历史状态
    history_db: HistoryDB = request.app.state.history_db
    history_db.update_task_status(task_id, "cancelled")
    return {"status": "cancelled", "task_id": task_id}


@router.post("/{task_id}/redraw")
async def redraw_task(task_id: str, request: Request) -> Dict[str, Any]:
    """POST /api/tasks/{id}/redraw — 相同参数重绘"""
    history_db: HistoryDB = request.app.state.history_db
    task_queue: TaskQueue = request.app.state.task_queue

    original = history_db.get_task(task_id)
    if not original:
        raise HTTPException(404, detail=f"Task not found: {task_id}")

    # 使用原始参数创建新任务
    from ..engine_interface import GenerationConfig
    gen_config = GenerationConfig.from_dict(original.get("generation_config", {}))

    new_task_id = task_queue.generate_task_id()
    from ..task_queue import Task
    task = Task(
        task_id=new_task_id,
        engine=original["engine"],
        config=gen_config.to_dict(),
        mode=original.get("mode", "txt2img"),
    )

    history_db.create_task(
        task_id=new_task_id,
        engine=original["engine"],
        mode=original.get("mode", "txt2img"),
        prompt=original.get("prompt", ""),
        negative_prompt=original.get("negative_prompt", ""),
        generation_config=gen_config.to_dict(),
    )

    await task_queue.submit(task)
    return {"task_id": new_task_id, "status": "pending", "source_task_id": task_id}


@router.delete("")
async def delete_tasks(
    request: Request,
    task_ids: List[str] = Query(default=[]),
) -> Dict[str, Any]:
    """DELETE /api/tasks — 批量删除"""
    history_db: HistoryDB = request.app.state.history_db
    if not task_ids:
        raise HTTPException(400, detail="No task_ids provided")
    count = history_db.delete_tasks(task_ids)
    return {"deleted": count}
