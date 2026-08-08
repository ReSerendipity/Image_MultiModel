"""
routes/output_routes.py — 图库 + 收藏

对应 MASTER_PLAN §5.1: GET /api/outputs, POST /api/outputs/{file}/fav
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from ..config import get_config
from ..history_db import HistoryDB
from ..security.path_guard import PathGuard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/outputs", tags=["outputs"])


@router.get("")
async def list_outputs(
    request: Request,
    type: Optional[str] = None,
    fav: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """GET /api/outputs — 图库真实文件（宽高→masonry 比例）"""
    history_db: HistoryDB = request.app.state.history_db
    outputs, total = history_db.list_outputs(
        output_type=type, favorite=fav, page=page, page_size=page_size,
    )
    return {
        "outputs": outputs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{file_path:path}")
async def get_output_file(file_path: str, request: Request) -> FileResponse:
    """GET /api/outputs/{file} — 获取输出图片"""
    cfg = get_config()
    guard = PathGuard(cfg.security.allowed_base_dirs, cfg.project_root)

    try:
        safe_path = guard.resolve(file_path, base_dir="outputs/")
    except Exception as e:
        raise HTTPException(403, detail=f"Path not allowed: {e}")

    if not safe_path.exists():
        raise HTTPException(404, detail=f"File not found: {file_path}")

    return FileResponse(str(safe_path))


@router.post("/{file_path:path}/fav")
async def toggle_favorite(file_path: str, request: Request) -> Dict[str, Any]:
    """POST /api/outputs/{file}/fav — 收藏标记"""
    cfg = get_config()
    guard = PathGuard(cfg.security.allowed_base_dirs, cfg.project_root)

    try:
        safe_path = guard.resolve(file_path, base_dir="outputs/")
    except Exception as e:
        raise HTTPException(403, detail=f"Path not allowed: {e}")

    history_db: HistoryDB = request.app.state.history_db
    # 切换收藏状态
    history_db.set_output_favorite(str(safe_path), True)
    return {"status": "favorited", "path": str(safe_path)}
