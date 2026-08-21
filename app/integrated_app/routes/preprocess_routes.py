"""
routes/preprocess_routes.py — ControlNet 预处理 API 路由

对应全功能实施指南任务 3: ControlNet 预处理器系统

路由列表：
- GET  /api/preprocess/list       — 列出可用预处理器
- POST /api/preprocess/canny      — Canny 边缘检测
- POST /api/preprocess/depth      — MiDaS 深度估计
- POST /api/preprocess/pose       — OpenPose 姿态检测
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..i18n import get_error_message
from ..preprocessors import get_preprocessor, list_preprocessors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preprocess", tags=["preprocess"])


# ── 请求/响应模型 ──────────────────────────────────────────────
class PreprocessRequest(BaseModel):
    """预处理请求体（Base64 图片输入）"""
    image_b64: str = Field(..., min_length=10, description="Base64 编码的图片数据")
    # Canny 专用参数
    low_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
    high_threshold: float = Field(default=0.2, ge=0.0, le=1.0)


class PreprocessResponse(BaseModel):
    """预处理结果"""
    status: str = "ok"
    preprocessor: str
    result_b64: str
    width: int
    height: int


# ── 工具函数 ────────────────────────────────────────────────────
def _decode_b64_image(image_b64: str) -> np.ndarray:
    """解码 Base64 图片为 numpy 数组。

    Args:
        image_b64: Base64 编码的图片数据（含或不含 data:image 前缀）。

    Returns:
        RGB numpy 数组 (H, W, 3) uint8。

    Raises:
        HTTPException: 解码失败。
    """
    try:
        from PIL import Image

        # 去除 data:image/xxx;base64, 前缀
        if "," in image_b64 and image_b64.startswith("data:"):
            image_b64 = image_b64.split(",", 1)[1]

        img_data = base64.b64decode(image_b64)

        # SECURITY: 显式魔数校验（对齐 SeedVR2），阻断伪装/非图片数据
        from app.integrated_app.security.magic_check import validate_image_magic
        is_magic, detected_type, error = validate_image_magic(img_data)
        if not is_magic:
            raise HTTPException(400, detail=f"Image decode failed: {error}")

        img = Image.open(io.BytesIO(img_data))
        # 校验图片内容完整性（防"伪图片头但损坏内容"）
        img.verify()
        img = Image.open(io.BytesIO(img_data))
        return np.array(img.convert("RGB"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, detail=f"Image decode failed: {e}")


def _encode_b64_image(image: np.ndarray, fmt: str = "PNG") -> str:
    """编码 numpy 数组为 Base64 图片字符串。

    Args:
        image: numpy 数组 (H, W) 或 (H, W, C)。
        fmt: 图片格式（PNG / JPEG）。

    Returns:
        Base64 编码字符串。
    """
    from PIL import Image

    if len(image.shape) == 2:
        # 灰度图 → 转为 RGB 三通道（Canny / Depth 输出）
        image = np.stack([image] * 3, axis=-1)

    img = Image.fromarray(image.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ── 路由 ────────────────────────────────────────────────────────
@router.get("/list")
async def list_available() -> dict[str, Any]:
    """GET /api/preprocess/list — 列出可用预处理器"""
    names = list_preprocessors()
    result = []
    for name in names:
        pp = get_preprocessor(name)
        if pp is not None:
            result.append({
                "name": name,
                "available": pp.is_available(),
            })
    return {"preprocessors": result, "count": len(result)}


@router.post("/canny", response_model=PreprocessResponse)
async def preprocess_canny(req: PreprocessRequest) -> PreprocessResponse:
    """POST /api/preprocess/canny — Canny 边缘检测"""
    from ..preprocessors.canny import CannyPreprocessor

    pp = CannyPreprocessor(
        low_threshold=req.low_threshold,
        high_threshold=req.high_threshold,
    )
    if not pp.is_available():
        raise HTTPException(
            503,
            detail=get_error_message("preprocess_not_available", name="canny"),
        )

    image = _decode_b64_image(req.image_b64)
    try:
        edges = pp.process(image)
        result_b64 = _encode_b64_image(edges)
        return PreprocessResponse(
            preprocessor="canny",
            result_b64=result_b64,
            width=edges.shape[1],
            height=edges.shape[0],
        )
    except Exception as e:
        raise HTTPException(500, detail=get_error_message("preprocess_failed", detail=str(e)))


@router.post("/depth", response_model=PreprocessResponse)
async def preprocess_depth(req: PreprocessRequest) -> PreprocessResponse:
    """POST /api/preprocess/depth — MiDaS 深度估计"""
    from ..preprocessors.midas import MiDaSDepthEstimator

    pp = MiDaSDepthEstimator()
    if not pp.is_available():
        raise HTTPException(
            503,
            detail=get_error_message("preprocess_not_available", name="midas"),
        )

    image = _decode_b64_image(req.image_b64)
    try:
        depth = pp.process(image)
        result_b64 = _encode_b64_image(depth)
        return PreprocessResponse(
            preprocessor="midas",
            result_b64=result_b64,
            width=depth.shape[1],
            height=depth.shape[0],
        )
    except Exception as e:
        raise HTTPException(500, detail=get_error_message("preprocess_failed", detail=str(e)))


@router.post("/pose", response_model=PreprocessResponse)
async def preprocess_pose(req: PreprocessRequest) -> PreprocessResponse:
    """POST /api/preprocess/pose — OpenPose 姿态检测"""
    from ..preprocessors.openpose import OpenPosePreprocessor

    pp = OpenPosePreprocessor()
    if not pp.is_available():
        raise HTTPException(
            503,
            detail=get_error_message("preprocess_not_available", name="openpose"),
        )

    image = _decode_b64_image(req.image_b64)
    try:
        pose = pp.process(image)
        result_b64 = _encode_b64_image(pose)
        return PreprocessResponse(
            preprocessor="openpose",
            result_b64=result_b64,
            width=pose.shape[1],
            height=pose.shape[0],
        )
    except Exception as e:
        raise HTTPException(500, detail=get_error_message("preprocess_failed", detail=str(e)))
