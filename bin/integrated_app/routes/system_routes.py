"""
routes/system_routes.py — health / SSE / GPU 状态

对应 MASTER_PLAN §5.1: GET /api/health
对应 MASTER_PLAN §5.2: SSE 单连接事件总线
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..config import get_config
from ..gpu_utils import get_gpu_info
from ..sse import get_sse_bus

logger = logging.getLogger(__name__)


def _disk_info() -> dict[str, Any]:
    """获取磁盘空间信息"""
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        return {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0}

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    GET /api/health — 后端/引擎/队列状态摘要
    """
    cfg = get_config()

    # 获取队列状态（如果已初始化）
    queue_status: dict[str, Any] = {}
    # queue 实例由 app_server 注入到 request.app.state

    # GPU 状态
    gpu = get_gpu_info()

    # 引擎状态
    engines: list = []
    for eng_name, eng_cfg in cfg.models.engines.items():
        engines.append({
            "name": eng_name,
            "display_name": eng_cfg.display_name,
            "ready": False,  # M0 阶段无引擎加载
            "active": eng_name == cfg.models.default_engine,
        })

    return {
        "status": "ok",
        "version": cfg.version,
        "timestamp": time.time(),
        "server": {
            "host": cfg.server.host,
            "port": cfg.server.port,
        },
        "gpu": {
            "name": gpu.gpu_name,
            "backend": gpu.backend,
            "total_vram_gb": gpu.total_vram_gb,
            "free_vram_gb": gpu.free_vram_gb,
        },
        "disk": _disk_info(),
        "engines": engines,
        "queue": queue_status,
    }


@router.get("/events")
async def sse_events(request: Request) -> StreamingResponse:
    """
    GET /api/events — SSE 单连接事件总线

    事件类型: task_status / comfy_preview / model_status / gpu_status / queue_status / heartbeat
    """
    bus = get_sse_bus()
    queue = await bus.subscribe()

    async def event_stream():
        try:
            # 发送初始连接事件
            init_data = json.dumps({"type": "connected", "timestamp": time.time()})
            yield f"event: connected\ndata: {init_data}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield msg
                except TimeoutError:
                    # 发送心跳
                    heartbeat = json.dumps({"timestamp": time.time()})
                    yield f"event: heartbeat\ndata: {heartbeat}\n\n"
        finally:
            bus.unsubscribe(queue)
            logger.info("SSE client disconnected")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/gpu")
async def gpu_status() -> dict[str, Any]:
    """GET /api/gpu — GPU 状态"""
    gpu = get_gpu_info()
    return {
        "name": gpu.gpu_name,
        "backend": gpu.backend,
        "total_vram_gb": gpu.total_vram_gb,
        "used_vram_gb": gpu.used_vram_gb,
        "free_vram_gb": gpu.free_vram_gb,
    }
