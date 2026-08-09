"""
routes/config_routes.py — GET/PUT /api/config

对应 MASTER_PLAN §5.1: GET/PUT /api/config（脱敏 + host 只读校验）
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import get_config, save_config
from ..config_models import scan_resource_files

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/loras")
async def list_loras() -> dict[str, Any]:
    """GET /api/config/loras — 扫描 LoRA 目录，返回相对路径列表（前端下拉用）"""
    cfg = get_config()
    try:
        files = scan_resource_files(
            "lora", cfg.models, cfg.project_root, (".safetensors",)
        )
    except Exception as e:
        logger.error(f"LoRA scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"LoRA scan failed: {e}")
    return {"loras": files, "count": len(files), "mode": cfg.models.model_source_mode}


class ConfigUpdateRequest(BaseModel):
    """配置更新请求（部分更新）"""
    # 只允许更新非安全字段
    inference: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    ui: dict[str, Any] | None = None
    i18n: dict[str, Any] | None = None
    presets: dict[str, Any] | None = None


@router.get("")
async def get_config_api() -> dict[str, Any]:
    """GET /api/config — 读取配置（脱敏后返回前端）"""
    cfg = get_config()
    return cfg.get_safe_config_dict()


@router.put("")
async def update_config_api(req: ConfigUpdateRequest) -> dict[str, Any]:
    """
    PUT /api/config — 更新配置（写回 config.yaml）
    host 字段只读，不允许通过 API 修改
    """
    cfg = get_config()

    # 应用部分更新
    changed = False
    if req.inference is not None:
        # 更新推理参数
        for k, v in req.inference.items():
            if hasattr(cfg.inference, k):
                setattr(cfg.inference, k, v)
                changed = True

    if req.output is not None:
        for k, v in req.output.items():
            if hasattr(cfg.output, k):
                setattr(cfg.output, k, v)
                changed = True

    if req.ui is not None:
        for k, v in req.ui.items():
            if hasattr(cfg.ui, k):
                setattr(cfg.ui, k, v)
                changed = True

    if req.i18n is not None:
        for k, v in req.i18n.items():
            if hasattr(cfg.i18n, k):
                setattr(cfg.i18n, k, v)
                changed = True

    if req.presets is not None:
        for k, v in req.presets.items():
            if hasattr(cfg.presets, k):
                setattr(cfg.presets, k, v)
                changed = True

    if not changed:
        return {"status": "ok", "message": "No changes"}

    try:
        save_config(cfg)
        logger.info("Config updated and saved")
        return {"status": "ok", "message": "Config saved successfully"}
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail=f"Config save failed: {e}")
