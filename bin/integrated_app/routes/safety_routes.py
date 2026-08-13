"""
routes/safety_routes.py — 内容安全检测 API 路由

对应全功能实施指南任务 1 Step 3: 集成到生成流程 + 独立检测接口

路由列表：
- POST /api/safety/check-prompt — 检查提示词安全
- POST /api/safety/check-image — 检查图片安全
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..i18n import get_error_message
from ..security.content_filter import get_content_filter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/safety", tags=["safety"])


class CheckPromptRequest(BaseModel):
    """POST /api/safety/check-prompt 请求体"""
    prompt: str = Field(..., min_length=1, max_length=10000)


class CheckPromptResponse(BaseModel):
    """提示词检测结果"""
    is_safe: bool
    violation_type: str | None = None
    confidence: float
    details: dict[str, Any] = Field(default_factory=dict)


@router.post("/check-prompt", response_model=CheckPromptResponse)
async def check_prompt(req: CheckPromptRequest) -> CheckPromptResponse:
    """POST /api/safety/check-prompt — 检查提示词是否违规

    使用关键词匹配，始终可用，延迟 < 1ms。
    """
    cf = get_content_filter()
    result = cf.check_prompt(req.prompt)
    return CheckPromptResponse(
        is_safe=result.is_safe,
        violation_type=result.violation_type,
        confidence=result.confidence,
        details=result.details,
    )


class CheckImageRequest(BaseModel):
    """POST /api/safety/check-image 请求体"""
    image_path: str = Field(..., min_length=1, max_length=2000)


class CheckImageResponse(BaseModel):
    """图片检测结果"""
    is_safe: bool
    violation_type: str | None = None
    confidence: float
    details: dict[str, Any] = Field(default_factory=dict)


@router.post("/check-image", response_model=CheckImageResponse)
async def check_image(req: CheckImageRequest, request: Request) -> CheckImageResponse:
    """POST /api/safety/check-image — 检查图片是否违规

    使用 CLIP 模型检测，首次调用会加载模型（约 2-5 秒）。
    如果 CLIP 未安装，返回降级结果。
    """
    # PathGuard 校验图片路径
    from ..config import get_config
    from ..security.path_guard import PathGuard, PathGuardError

    cfg = get_config()
    guard = PathGuard(cfg.security.allowed_base_dirs, cfg.project_root)
    try:
        safe_path = guard.resolve(req.image_path)
    except PathGuardError:
        raise HTTPException(403, detail=get_error_message("path_traversal", path=req.image_path))

    if not safe_path.exists():
        raise HTTPException(404, detail=get_error_message("file_not_found", path=req.image_path))

    cf = get_content_filter()
    result = cf.check_image(str(safe_path))
    return CheckImageResponse(
        is_safe=result.is_safe,
        violation_type=result.violation_type,
        confidence=result.confidence,
        details=result.details,
    )
