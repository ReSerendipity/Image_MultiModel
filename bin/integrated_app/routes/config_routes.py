"""
routes/config_routes.py — GET/PUT /api/config

对应 MASTER_PLAN §5.1: GET/PUT /api/config（脱敏 + host 只读校验）
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import get_config, save_config, reload_config
from ..config_models import AppConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigUpdateRequest(BaseModel):
    """配置更新请求（部分更新）"""
    # 只允许更新非安全字段
    inference: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    ui: Optional[Dict[str, Any]] = None
    i18n: Optional[Dict[str, Any]] = None
    presets: Optional[Dict[str, Any]] = None


@router.get("")
async def get_config_api() -> Dict[str, Any]:
    """GET /api/config — 读取配置（脱敏后返回前端）"""
    cfg = get_config()
    return cfg.get_safe_config_dict()


@router.put("")
async def update_config_api(req: ConfigUpdateRequest) -> Dict[str, Any]:
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
