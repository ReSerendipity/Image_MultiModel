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

import asyncio
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

        # M-03: 体积 + 解压炸弹（像素）上限校验，超过即 413
        from ..config import get_config
        from ..security.upload_limits import enforce_upload_limits

        cfg = get_config()
        enforce_upload_limits(
            img_data, cfg.output.uploads.max_size_mb, cfg.output.uploads.max_pixels
        )

        # SECURITY: 显式魔数校验（对齐 SeedVR2），阻断伪装/非图片数据
        from ..security.magic_check import validate_image_magic
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


async def _run_preprocess(pp: Any, image_b64: str, name: str) -> PreprocessResponse:
    """在线程池中执行「解码 → 预处理 → 编码」，避免阻塞事件循环（反模式 #3）。

    Canny / MiDaS / OpenPose 均为 CPU（或 GPU）密集型同步算子，图片解码与
    PNG 编码同样阻塞；直接在 async 路由中调用会冻结整个服务，导致 SSE 心跳、
    进度推送与其他请求全部停顿。此处统一卸载到默认线程池执行。

    Args:
        pp: 预处理器实例（需实现 ``process(ndarray) -> ndarray``）。
        image_b64: Base64 图片数据。
        name: 预处理器名称（写入响应）。

    Raises:
        HTTPException: 解码失败(400) / 预处理失败(500)。
    """
    loop = asyncio.get_running_loop()
    image = await loop.run_in_executor(None, _decode_b64_image, image_b64)
    try:
        result = await loop.run_in_executor(None, pp.process, image)
        result_b64 = await loop.run_in_executor(None, _encode_b64_image, result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=get_error_message("preprocess_failed", detail=str(e)))

    return PreprocessResponse(
        preprocessor=name,
        result_b64=result_b64,
        width=result.shape[1],
        height=result.shape[0],
    )


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

    return await _run_preprocess(pp, req.image_b64, "canny")


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

    return await _run_preprocess(pp, req.image_b64, "midas")


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

    return await _run_preprocess(pp, req.image_b64, "openpose")
