"""共享输出管线：保存 PNG → 来源标识 → 缩略图。

engine.py（NativeEngine）与 diffusers_engine.py（ZImageDiffusersEngine）共用，
避免输出处理逻辑重复维护。职责边界：只做「落盘 + 标识 + 缩略图」三件事，
不涉及推理、命名策略与相对路径计算。
"""
from __future__ import annotations

import io
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..watermark import embed_watermark

logger = logging.getLogger(__name__)


def save_png(path: Path, image: Any, *, is_tensor: bool = False) -> None:
    """把 PIL 图像或 [0,1] 范围 (H,W,3) 张量保存为 PNG。"""
    if is_tensor:
        arr = image.detach().cpu().numpy()
        arr = (arr * 255.0).clip(0, 255).astype("uint8")
        Image.fromarray(arr).save(path, format="PNG")
    else:
        image.save(path, format="PNG")


def embed_provenance(path: Path, product_id: str, task_id: str) -> None:
    """对已保存的 PNG 嵌入来源标识（失败静默，不影响输出）。"""
    try:
        img = Image.open(path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        arr = np.array(img).astype(np.float64)
        wm_arr = embed_watermark(arr, product_id, task_id, time.time())
        wm_img = Image.fromarray(np.clip(wm_arr, 0, 255).astype(np.uint8))
        buf = io.BytesIO()
        wm_img.save(buf, format="PNG")
        path.write_bytes(buf.getvalue())
        logger.debug("Watermark embedded: %s", path.name)
    except Exception as e:
        logger.debug("Watermark embedding failed for %s: %s", path.name, e)


def make_thumbnail(src: Path, thumb_dir: Path, name: str, max_side: int) -> None:
    """生成缩略图（失败不影响主输出）。"""
    try:
        img = Image.open(src)
        w, h = img.size
        scale = max_side / max(w, h)
        if scale < 1.0:
            thumb = img.resize(
                (int(w * scale), int(h * scale)), Image.Resampling.LANCZOS
            )
        else:
            thumb = img
        thumb.save(thumb_dir / name, format="PNG")
    except Exception as e:
        logger.warning("Thumbnail generation failed: %s", e)


def finalize_output(
    path: Path,
    image: Any,
    *,
    is_tensor: bool,
    wm_enabled: bool,
    product_id: str,
    task_id: str,
    thumb_enabled: bool,
    thumb_dir: Path | None,
    thumb_name: str,
    thumb_max_side: int,
) -> None:
    """输出管线唯一入口：落盘 + 来源标识 + 缩略图。"""
    save_png(path, image, is_tensor=is_tensor)
    if wm_enabled:
        embed_provenance(path, product_id, task_id)
    if thumb_enabled and thumb_dir is not None:
        make_thumbnail(path, thumb_dir, thumb_name, thumb_max_side)
