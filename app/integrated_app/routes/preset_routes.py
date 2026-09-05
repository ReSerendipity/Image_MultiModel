"""
routes/preset_routes.py — 预设 CRUD + 导入导出 + apply

对应 MASTER_PLAN §5.1: GET /api/presets, POST/PUT/DELETE, POST apply
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..history_db import HistoryDB

logger = logging.getLogger(__name__)

# P1-1：history_db 为同步 sqlite3；async 路由里直调会阻塞事件循环（本报告 P1-1），
# 因此本模块所有 history_db 调用统一经 ``asyncio.to_thread`` 下沉线程池。

router = APIRouter(prefix="/api/presets", tags=["presets"])


class PresetCreate(BaseModel):
    engine_name: str
    name: str
    config: dict[str, Any]
    thumbnail: str = ""


class PresetUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    thumbnail: str | None = None


@router.get("")
async def list_presets(
    request: Request,
    engine_name: str | None = None,
) -> list[dict[str, Any]]:
    """GET /api/presets — 列出预设"""
    history_db: HistoryDB = request.app.state.history_db
    return await asyncio.to_thread(history_db.list_presets, engine_name)


@router.post("")
async def create_preset(req: PresetCreate, request: Request) -> dict[str, Any]:
    """POST /api/presets — 创建预设"""
    history_db: HistoryDB = request.app.state.history_db
    try:
        preset_id = await asyncio.to_thread(
            history_db.create_preset,
            engine_name=req.engine_name,
            name=req.name,
            config=req.config,
            thumbnail=req.thumbnail,
        )
        return {"id": preset_id, "status": "created"}
    except ValueError as e:
        raise HTTPException(409, detail=str(e))


@router.get("/{preset_id:int}")
async def get_preset(preset_id: int, request: Request) -> dict[str, Any]:
    """GET /api/presets/{id} — 获取预设详情"""
    history_db: HistoryDB = request.app.state.history_db
    preset = await asyncio.to_thread(history_db.get_preset, preset_id)
    if not preset:
        raise HTTPException(404, detail="Preset not found")
    return preset


@router.put("/{preset_id}")
async def update_preset(
    preset_id: int, req: PresetUpdate, request: Request,
) -> dict[str, Any]:
    """PUT /api/presets/{id} — 更新预设"""
    history_db: HistoryDB = request.app.state.history_db
    if not await asyncio.to_thread(history_db.get_preset, preset_id):
        raise HTTPException(404, detail="Preset not found")
    await asyncio.to_thread(
        history_db.update_preset,
        preset_id, name=req.name, config=req.config, thumbnail=req.thumbnail,
    )
    return {"status": "updated"}


@router.delete("/{preset_id}")
async def delete_preset(preset_id: int, request: Request) -> dict[str, Any]:
    """DELETE /api/presets/{id} — 删除预设"""
    history_db: HistoryDB = request.app.state.history_db
    if not await asyncio.to_thread(history_db.delete_preset, preset_id):
        raise HTTPException(404, detail="Preset not found")
    return {"status": "deleted"}


@router.delete("")
async def delete_presets(ids: str, request: Request) -> dict[str, Any]:
    """DELETE /api/presets?ids=1,2,3 — 批量删除预设（与 /api/tasks?task_ids= 模式对齐）"""
    history_db: HistoryDB = request.app.state.history_db
    try:
        preset_ids = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, detail="ids must be comma-separated integers")
    if not preset_ids:
        raise HTTPException(422, detail="ids must not be empty")
    deleted = await asyncio.to_thread(history_db.delete_presets, preset_ids)
    return {"deleted": deleted, "status": "deleted"}


@router.post("/{preset_id}/apply")
async def apply_preset(preset_id: int, request: Request) -> dict[str, Any]:
    """POST /api/presets/{id}/apply — 应用预设 → 返回参数回填前端"""
    history_db: HistoryDB = request.app.state.history_db
    preset = await asyncio.to_thread(history_db.get_preset, preset_id)
    if not preset:
        raise HTTPException(404, detail="Preset not found")
    # 返回 config 用于前端回填
    return {
        "status": "applied",
        "engine_name": preset["engine_name"],
        "config": preset["config"],
    }


@router.post("/import")
async def import_presets(req: list[dict[str, Any]], request: Request) -> dict[str, Any]:
    """POST /api/presets/import — 批量导入预设"""
    history_db: HistoryDB = request.app.state.history_db
    imported = 0
    errors: list[str] = []
    for p in req:
        try:
            await asyncio.to_thread(
                history_db.create_preset,
                engine_name=p.get("engine_name", ""),
                name=p.get("name", ""),
                config=p.get("config", {}),
                thumbnail=p.get("thumbnail", ""),
            )
            imported += 1
        except Exception as e:
            errors.append(str(e))
    return {"imported": imported, "errors": errors}


@router.get("/export")
async def export_presets(
    request: Request,
    engine_name: str | None = None,
) -> list[dict[str, Any]]:
    """GET /api/presets/export — 导出所有/指定引擎的预设"""
    history_db: HistoryDB = request.app.state.history_db
    return await asyncio.to_thread(history_db.list_presets, engine_name)
