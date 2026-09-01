"""
security/upload_limits.py — 上传图片大小 / 像素安全限制（安全评估 M-03）

防止两类 DoS：
1. 超大字节体积：解码后的原始字节超过 uploads.max_size_mb 即拒绝。
2. 解压炸弹（decompression bomb）：单图宽×高超过 uploads.max_pixels 即拒绝，
   同时设置 PIL.Image.MAX_IMAGE_PIXELS 作为进程级纵深防御。
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

# 默认像素上限（2 亿像素），仅当调用方未显式传入 max_pixels 时使用。
DEFAULT_MAX_PIXELS = 200_000_000


def enforce_upload_limits(
    image_data: bytes,
    max_size_mb: int,
    max_pixels: int | None = None,
) -> None:
    """校验上传图片的解码后字节大小与像素总量。

    Args:
        image_data: 已 Base64 解码的原始图片字节。
        max_size_mb: 允许的最大体积（MB）。超过即拒绝（413）。
        max_pixels: 允许的最大像素总量（宽×高）。为空时使用
            :data:`DEFAULT_MAX_PIXELS`。

    Raises:
        HTTPException: 体积或像素超限时返回 413。
    """
    from fastapi import HTTPException

    max_pixels = int(max_pixels) if max_pixels else DEFAULT_MAX_PIXELS
    limit_bytes = int(max_size_mb) * 1024 * 1024

    if len(image_data) > limit_bytes:
        msg = (
            f"Uploaded image too large: {len(image_data)} bytes "
            f"exceeds limit {limit_bytes} bytes ({max_size_mb} MB)"
        )
        logger.warning("[UPLOAD-LIMIT] %s", msg)
        raise HTTPException(413, detail=msg)

    # 显式像素总量校验：返回干净的 413 而非 PIL 内部异常。
    # 注意：PIL 自身的 DecompressionBomb 守卫会在 Image.open 时直接抛错，
    # 因此先临时关闭它，读取尺寸后做我们自己的判定，再恢复为纵深防御阈值。
    from PIL import Image

    prev_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None  # 临时禁用，避免 open 即抛 DecompressionBombError
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            width, height = img.size
    except Exception:
        # 无法读取尺寸（图像可能损坏）：交给调用方 decode 阶段统一失败，此处不阻断。
        logger.debug("[UPLOAD-LIMIT] 无法读取图像尺寸，跳过像素预检")
        return
    finally:
        # 恢复为显式上限（阈值 ×2，正常图不会触发），保留进程级纵深防御。
        Image.MAX_IMAGE_PIXELS = max_pixels

    if width * height > max_pixels:
        msg = (
            f"Uploaded image pixel count {width * height} "
            f"exceeds limit {max_pixels}"
        )
        logger.warning("[UPLOAD-LIMIT] %s", msg)
        raise HTTPException(413, detail=msg)
