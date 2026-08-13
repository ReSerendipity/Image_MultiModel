"""
native/preview.py — 采样中实时预览

把解码中间结果转成低分辨率 b64，通过 SSE ``comfy_preview`` 通道推送。格式对齐
``bin/integrated_app/comfy/engine.py`` 的 b_preview 消息：``{"preview_b64": ...,
"preview_format": ...}``，以及 ``app_server.py`` 的 ``publish("comfy_preview", ...)``。
"""

from __future__ import annotations

import base64
import io
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_FORMAT = "jpg"
DEFAULT_MAX_WIDTH = 256


def tensor_to_preview_b64(
    images: Any,
    max_width: int = DEFAULT_MAX_WIDTH,
    fmt: str = DEFAULT_FORMAT,
) -> str:
    """把 ``[N, H, W, C]`` 的 [0,1] 张量转为低分辨率 b64 字符串。

    Args:
        images: RGB 张量，形状 ``[batch, H, W, 3]``，取值范围 [0,1]
        max_width: 预览图最大宽度（像素），超出则按比例缩小
        fmt: 图片格式（jpg/png）

    Returns:
        base64 编码的图片数据（不含 data: 前缀）。
    """
    from PIL import Image

    img = images[0].detach().cpu()
    if img.ndim == 4:
        img = img[0]
    arr = (img.clamp(0.0, 1.0) * 255.0).numpy().astype("uint8")
    pil = Image.fromarray(arr)

    w, h = pil.size
    if w > max_width:
        scale = max_width / w
        pil = pil.resize((max_width, int(h * scale)), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    if fmt == "png":
        pil.save(buf, format="PNG")
    else:
        pil = pil.convert("RGB")
        pil.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def publish_preview(
    sse_bus: Any,
    b64: str,
    width: int = DEFAULT_MAX_WIDTH,
    fmt: str = DEFAULT_FORMAT,
    task_id: str = "",
) -> Awaitable[None] | None:
    """推送一条 ``comfy_preview`` 事件到 SSE 总线。

    Args:
        sse_bus: SSEBus 实例（``get_sse_bus()``），或具有 ``publish(event, data)``
            协程的对象
        b64: 预览图 base64
        width: 预览图宽度（透传，供前端展示尺寸）
        fmt: 图片格式（jpg/png）
        task_id: 关联任务 id（可选）

    Returns:
        ``publish()`` 的 awaitable（SSEBus.publish 为 async）；若总线为同步对象
        则返回其返回值。
    """
    data = {
        "task_id": task_id,
        "b64": b64,
        "format": fmt,
        "width": width,
    }
    logger.debug("Publishing comfy_preview (task=%s, width=%d)", task_id, width)
    return sse_bus.publish("comfy_preview", data)


# 便捷同步入口：在 worker 线程中把中间结果直接推送（需用户自行桥接到事件循环）
def publish_preview_tensor(
    sse_bus: Any,
    images: Any,
    max_width: int = DEFAULT_MAX_WIDTH,
    fmt: str = DEFAULT_FORMAT,
    task_id: str = "",
) -> Awaitable[None] | None:
    """编码并推送预览（组合 tensor_to_preview_b64 + publish_preview）。"""
    b64 = tensor_to_preview_b64(images, max_width=max_width, fmt=fmt)
    return publish_preview(sse_bus, b64, width=max_width, fmt=fmt, task_id=task_id)


PreviewPublisher = Callable[[Any, str, int, str], Awaitable[None] | None]
