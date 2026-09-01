"""
routes/task_routes.py — 任务历史 + 取消 + 重绘 + 批量删除

对应 MASTER_PLAN §5.1: GET /api/tasks, GET /api/tasks/{id}, POST cancel, POST redraw, DELETE
"""

from __future__ import annotations

import io
import logging
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ..config import get_config
from ..history_db import HistoryDB
from ..security.path_guard import PathGuard, PathGuardError
from ..task_queue import TaskQueue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    request: Request,
    status: str | None = None,
    engine: str | None = None,
    q: str | None = None,
    favorite: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
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


@router.get("/export")
async def export_tasks(
    request: Request,
    ids: str = Query(..., description="逗号分隔的任务 ID"),
    type: str | None = Query(None, description="original/upscaled/compare"),
) -> StreamingResponse:
    """GET /api/tasks/export?ids= — 打包 ZIP 导出

    注意：本静态路由必须注册在 ``/{task_id}`` 之前，否则会被动态路由
    吞掉并始终返回 404（Full test regression 阶段发现并修复）。
    """
    history_db: HistoryDB = request.app.state.history_db
    cfg = get_config()
    task_ids = [t.strip() for t in ids.split(",") if t.strip()]
    if not task_ids:
        raise HTTPException(400, detail="No task_ids provided")

    # M-01 修复：此前直接用 Path(db_path) 拼接，既无 PathGuard（DB 被污染即任意文件
    # 读取），又因 outputs 存的是相对路径、按 cwd 解析导致导出空 ZIP（功能已坏）。
    # 改为用 PathGuard 以 outputs 基目录解析，越界路径跳过，缺失文件跳过。
    guard = PathGuard(cfg.security.allowed_base_dirs, cfg.project_root)
    base_dir = cfg.output.base_dir

    buf = io.BytesIO()
    written = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for tid in task_ids:
            task = history_db.get_task(tid)
            if not task:
                continue
            for out in task.get("outputs", []):
                out_type = out.get("output_type", "original")
                if type and out_type != type:
                    continue
                rel = out.get("path", "")
                if not rel:
                    continue
                try:
                    safe_path = guard.resolve(rel, base_dir=base_dir)
                except PathGuardError:
                    logger.warning("[EXPORT] 跳过越权输出路径: %s (task=%s)", rel, tid)
                    continue
                if not safe_path.exists() or not safe_path.is_file():
                    continue
                arcname = f"{tid}/{safe_path.name}"
                zf.write(str(safe_path), arcname)
                written += 1
    if written == 0:
        raise HTTPException(404, detail="No exportable outputs found for the given task ids")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=export.zip"},
    )


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request) -> dict[str, Any]:
    """GET /api/tasks/{id} — 任务详情（含 generation_config 22 项 + 三路输出）"""
    history_db: HistoryDB = request.app.state.history_db
    task = history_db.get_task(task_id)
    if not task:
        raise HTTPException(404, detail=f"Task not found: {task_id}")
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request) -> dict[str, Any]:
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
async def redraw_task(task_id: str, request: Request) -> dict[str, Any]:
    """POST /api/tasks/{id}/redraw — 相同参数重绘"""
    history_db: HistoryDB = request.app.state.history_db
    task_queue: TaskQueue = request.app.state.task_queue

    original = history_db.get_task(task_id)
    if not original:
        raise HTTPException(404, detail=f"Task not found: {task_id}")

    # 使用原始参数创建新任务
    from ..engine_interface import GenerationConfig
    from ..lineage import compute_lora_checksums, compute_workflow_version
    gen_config = GenerationConfig.from_dict(original.get("generation_config", {}))
    cfg = get_config()

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
        workflow_version=compute_workflow_version(cfg.models.engines[original["engine"]], cfg.project_root),
        lora_checksums=compute_lora_checksums(gen_config.effective_lora_stack(), cfg),
    )

    await task_queue.submit(task)
    return {"task_id": new_task_id, "status": "pending", "source_task_id": task_id}


@router.delete("")
async def delete_tasks(
    request: Request,
    task_ids: list[str] = Query(default=[]),
) -> dict[str, Any]:
    """DELETE /api/tasks — 批量删除"""
    history_db: HistoryDB = request.app.state.history_db
    if not task_ids:
        raise HTTPException(400, detail="No task_ids provided")
    count = history_db.delete_tasks(task_ids)
    return {"deleted": count}


@router.post("/tags")
async def add_tags(
    request: Request,
    task_ids: list[str] = Query(default=[]),
    tags: list[str] = Query(default=[]),
) -> dict[str, Any]:
    """POST /api/tasks/tags — 批量加标签"""
    history_db: HistoryDB = request.app.state.history_db
    if not task_ids or not tags:
        raise HTTPException(400, detail="task_ids and tags are required")
    count = history_db.add_task_tags(task_ids, tags)
    return {"tagged": count}


@router.post("/cleanup")
async def cleanup_tasks(
    request: Request,
    keep_days: int = Query(30, ge=0),
    max_gb: float = Query(0, ge=0),
) -> dict[str, Any]:
    """POST /api/tasks/cleanup — 清理超期任务（保留策略）"""
    history_db: HistoryDB = request.app.state.history_db
    deleted = history_db.cleanup_old_tasks(keep_days=keep_days, max_gb=max_gb)
    return {"deleted": deleted, "keep_days": keep_days, "max_gb": max_gb}
