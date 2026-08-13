"""
routes/engine_routes.py — 引擎加载 / 切换 / 卸载（PRD §2.3.3 + I-15）

对应 MASTER_PLAN §5.1: POST /api/engine/load, /unload, GET /api/engines
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..comfy.client import ComfyClient
from ..comfy.engine import ComfyEngine
from ..config import get_config
from ..engine_interface import get_registry
from ..i18n import get_error_message
from ..model_manager import ModelState, get_model_manager
from ..native.engine import NativeEngine
from ..sse import get_sse_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engine", tags=["engine"])


class EngineLoadRequest(BaseModel):
    """POST /api/engine/load 请求体"""
    engine_name: str


class EngineLoadResponse(BaseModel):
    engine_name: str
    status: str  # loading | loaded | error
    message: str = ""


@router.get("/engines")
async def list_engines(request: Request) -> dict[str, Any]:
    """GET /api/engines — 引擎列表（含元数据 + 加载状态）"""
    cfg = get_config()
    model_mgr = get_model_manager()
    registry = get_registry()

    engines = []
    for eng_name, eng_cfg in cfg.models.engines.items():
        state = model_mgr.get_state(eng_name).value
        engines.append({
            "name": eng_name,
            "display_name": eng_cfg.display_name,
            "display_name_en": eng_cfg.display_name_en,
            "backend": eng_cfg.backend,
            "ready": state == "loaded",
            "state": state,
            "active": eng_name == registry.active_engine_name,
            "vram_gb": eng_cfg.vram_gb,
            "ram_gb": eng_cfg.ram_gb,
            "default_precision": eng_cfg.default_precision,
            "supported_features": eng_cfg.supported_features,
            "tags": eng_cfg.tags,
        })

    return {
        "engines": engines,
        "active_engine": registry.active_engine_name,
        "count": len(engines),
    }


@router.post("/load")
async def load_engine(req: EngineLoadRequest, request: Request) -> dict[str, Any]:
    """POST /api/engine/load — 加载引擎（生成器进度 → SSE model_status）"""
    cfg = get_config()
    engine_name = req.engine_name

    if engine_name not in cfg.models.engines:
        raise HTTPException(404, detail=get_error_message("engine_not_found", name=engine_name))

    eng_cfg = cfg.models.engines[engine_name]
    registry = get_registry()
    model_mgr = get_model_manager()
    sse_bus = get_sse_bus()

    # 注册引擎工厂（如果未注册）
    if engine_name not in registry._factories:
        if eng_cfg.backend == "native":
            # 原生引擎：comfy_source_dir 拼接为项目根下的绝对路径（相对路径不可靠）
            comfy_source_dir = str(Path(cfg.project_root) / eng_cfg.comfy_source_dir).replace("\\", "/")

            def native_factory(**kwargs):
                return NativeEngine(
                    name=engine_name,
                    display_name=eng_cfg.display_name,
                    display_name_en=eng_cfg.display_name_en,
                    config={
                        "comfy_source_dir": comfy_source_dir,
                        "custom_nodes_dir": eng_cfg.custom_nodes_dir,
                    },
                )
            registry.register(engine_name, native_factory)
        else:
            def factory(**kwargs):
                return ComfyEngine(
                    name=engine_name,
                    display_name=eng_cfg.display_name,
                    display_name_en=eng_cfg.display_name_en,
                    config={
                        "workflow_file": eng_cfg.workflow_file,
                        "parameter_schema": eng_cfg.parameter_schema,
                        "comfy_backend_preference": eng_cfg.comfy_backend_preference,
                    },
                )
            registry.register(engine_name, factory)

    # 注册 SSE 观察者（如果未注册）
    if not model_mgr._observers:
        main_loop = asyncio.get_event_loop()

        def on_model_status(eng: str, state: ModelState, extra: dict):
            asyncio.run_coroutine_threadsafe(
                sse_bus.publish("model_status", {
                    "engine": eng,
                    "state": state.value,
                    **extra,
                }),
                main_loop,
            )
        model_mgr.register_observer(on_model_status)

    engine = registry.get(engine_name)

    # 如果当前有活动引擎且不同，先卸载
    current_active = registry.active_engine_name
    if current_active and current_active != engine_name:
        try:
            old_engine = registry.get(current_active)
            await model_mgr.unload_engine(current_active, old_engine)
        except Exception as e:
            logger.warning(f"Failed to unload engine {current_active}: {e}")

    registry.set_active(engine_name)

    try:
        await model_mgr.load_engine(engine_name, engine)
        return {
            "engine_name": engine_name,
            "status": "loaded",
            "message": f"Engine '{eng_cfg.display_name}' loaded successfully",
        }
    except Exception as e:
        logger.error(f"Engine load failed: {e}")
        return {
            "engine_name": engine_name,
            "status": "error",
            "message": str(e),
        }


@router.post("/unload")
async def unload_engine(request: Request) -> dict[str, Any]:
    """POST /api/engine/unload — 卸载当前引擎"""
    registry = get_registry()
    model_mgr = get_model_manager()

    active = registry.active_engine_name
    if not active:
        return {"status": "ok", "message": "No active engine to unload"}

    engine = registry.get(active)
    try:
        await model_mgr.unload_engine(active, engine)
        return {
            "engine_name": active,
            "status": "unloaded",
            "message": f"Engine '{active}' unloaded",
        }
    except Exception as e:
        logger.error(f"Engine unload failed: {e}")
        raise HTTPException(500, detail=get_error_message("engine_unload_failed", detail=str(e)))


# ── D3: 释放显存（POST /api/comfy/free） ──────────────────


@router.post("/free")
async def free_vram(request: Request) -> dict[str, Any]:
    """POST /api/engine/free — 释放 ComfyUI 显存（转发 /free） → SSE gpu_status 刷新"""
    cfg = get_config()
    backend_name = "local"
    backend = cfg.comfy.backends.get(backend_name)
    if not backend:
        raise HTTPException(500, detail="ComfyUI backend not configured")

    client = ComfyClient(
        base_url=backend.base_url,
        ws_url=backend.ws_url,
        auth_token=backend.auth_token,
        client_id_prefix=backend.client_id_prefix,
    )
    try:
        await client.connect()
        await client.free(free_memory=True)
        await client.disconnect()

        # 发布 SSE gpu_status 刷新
        sse_bus = get_sse_bus()
        import time as _time

        from ..gpu_utils import get_gpu_info
        gpu = get_gpu_info()
        await sse_bus.publish("gpu_status", {
            "name": gpu.gpu_name,
            "backend": gpu.backend,
            "total_vram_gb": gpu.total_vram_gb,
            "used_vram_gb": gpu.used_vram_gb,
            "free_vram_gb": gpu.free_vram_gb,
            "timestamp": _time.time(),
            "freed": True,
        })

        return {"status": "ok", "message": "VRAM freed"}
    except Exception as e:
        logger.error(f"Free VRAM failed: {e}")
        raise HTTPException(500, detail=str(e))
