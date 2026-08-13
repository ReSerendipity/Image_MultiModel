"""
routes/prompt_routes.py — 提示词扩展 API 路由

对应全功能实施指南任务 2 Step 2: UI 集成 → API 接口

路由列表：
- POST /api/prompt/expand — 扩写提示词
- POST /api/prompt/suggest — 智能推荐提示词组合
- GET  /api/prompt/styles — 列出可用风格
- GET  /api/prompt/scenes — 列出可用场景
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..prompt_expander import get_prompt_expander

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompt", tags=["prompt"])


# ── 请求/响应模型 ──────────────────────────────────────────────
class ExpandPromptRequest(BaseModel):
    """POST /api/prompt/expand 请求体"""
    prompt: str = Field(..., min_length=1, max_length=10000)
    style: str = Field(default="none")
    auto_enhance: bool = Field(default=True)
    user_negative: str = Field(default="")


class ExpandPromptResponse(BaseModel):
    """扩写结果"""
    expanded_prompt: str
    negative_prompt: str
    original_prompt: str
    style: str
    auto_enhance: bool


class SuggestRequest(BaseModel):
    """POST /api/prompt/suggest 请求体"""
    subject: str = Field(..., min_length=1, max_length=5000)


class SuggestResponse(BaseModel):
    """推荐结果"""
    positive: str
    style: str
    negative: str


@router.post("/expand", response_model=ExpandPromptResponse)
async def expand_prompt(req: ExpandPromptRequest) -> ExpandPromptResponse:
    """POST /api/prompt/expand — 扩写提示词

    根据风格模板和自动质量增强扩写原始提示词。
    """
    expander = get_prompt_expander()
    expanded = expander.expand(req.prompt, style=req.style, auto_enhance=req.auto_enhance)
    negative = expander.generate_negative_prompt(req.user_negative)
    return ExpandPromptResponse(
        expanded_prompt=expanded,
        negative_prompt=negative,
        original_prompt=req.prompt,
        style=req.style,
        auto_enhance=req.auto_enhance,
    )


@router.post("/suggest", response_model=SuggestResponse)
async def suggest_prompt(req: SuggestRequest) -> SuggestResponse:
    """POST /api/prompt/suggest — 智能推荐提示词组合

    根据主体关键词匹配预设场景模板。
    """
    expander = get_prompt_expander()
    result = expander.smart_suggest(req.subject)
    return SuggestResponse(
        positive=result["positive"],
        style=result["style"],
        negative=result["negative"],
    )


@router.get("/styles")
async def list_styles() -> dict[str, Any]:
    """GET /api/prompt/styles — 列出可用风格"""
    expander = get_prompt_expander()
    styles = expander.list_styles()
    return {
        "styles": styles,
        "count": len(styles),
    }


@router.get("/scenes")
async def list_scenes() -> dict[str, Any]:
    """GET /api/prompt/scenes — 列出可用场景"""
    expander = get_prompt_expander()
    scenes = expander.list_scenes()
    return {
        "scenes": scenes,
        "count": len(scenes),
    }
