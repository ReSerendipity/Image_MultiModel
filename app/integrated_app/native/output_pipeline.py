"""共享输出管线：保存 PNG → 来源标识 → 缩略图。

engine.py（NativeEngine）与 diffusers_engine.py（ZImageDiffusersEngine）共用，
避免输出处理逻辑重复维护。职责边界：只做「落盘 + 标识 + 缩略图」三件事，
不涉及推理、命名策略与相对路径计算。
"""
from __future__ import annotations

import io
import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from ..watermark import embed_watermark

logger = logging.getLogger(__name__)


def _normalize_format(image_format: str) -> str:
    """把配置的图像格式归一化为 PIL 接受的格式名（大写）。"""
    fmt = (image_format or "png").lower()
    if fmt in ("jpg", "jpeg"):
        return "JPEG"
    if fmt == "webp":
        return "WEBP"
    return "PNG"


def save_image(
    path: Path,
    image: Any,
    *,
    is_tensor: bool = False,
    image_format: str = "png",
    quality: int = 95,
) -> None:
    """把 PIL 图像或 [0,1] 范围 (H,W,3) 张量保存为指定格式（PNG/WebP/JPEG）。

    WebP/JPEG 支持有损压缩（quality），可显著降低存储与带宽成本（P0）。
    """
    fmt = _normalize_format(image_format)
    if is_tensor:
        arr = image.detach().cpu().numpy()
        arr = (arr * 255.0).clip(0, 255).astype("uint8")
        pil = Image.fromarray(arr)
    else:
        pil = image
    if fmt == "JPEG" and pil.mode != "RGB":
        pil = pil.convert("RGB")
    save_kwargs: dict[str, Any] = {}
    if fmt in ("WEBP", "JPEG"):
        save_kwargs["quality"] = max(1, min(100, int(quality)))
    pil.save(path, format=fmt, **save_kwargs)


def embed_provenance(path: Path, product_id: str, task_id: str, image_format: str = "png") -> None:
    """对已保存的图像嵌入来源标识（失败静默，不影响输出），保留原格式。"""
    try:
        img: Image.Image = Image.open(path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        arr = np.array(img).astype(np.float64)
        wm_arr = embed_watermark(arr, product_id, task_id, time.time())
        wm_img = Image.fromarray(np.clip(wm_arr, 0, 255).astype(np.uint8))
        fmt = _normalize_format(image_format)
        buf = io.BytesIO()
        save_kwargs: dict[str, Any] = {}
        if fmt in ("WEBP", "JPEG"):
            # 水印后统一以较高质量回写，避免二次有损劣化
            save_kwargs["quality"] = 95
        wm_img.save(buf, format=fmt, **save_kwargs)
        path.write_bytes(buf.getvalue())
        logger.debug("Watermark embedded: %s", path.name)
    except Exception as e:
        logger.debug("Watermark embedding failed for %s: %s", path.name, e)


def build_generation_metadata(task_id: str, config: Any, engine_name: str) -> dict[str, str]:
    """构造 PNG tEXt 生成参数元数据（数据治理报告 P1-4）。

    目的：图片脱离本系统后仍可凭 tEXt 溯源 task_id / seed / 模型 / LoRA 栈 /
    workflow 指纹，补齐「图片自描述层」血缘断点。
    """
    meta: dict[str, str] = {
        "Software": "Image_MultiModel",
        "IMM:task_id": task_id,
        "IMM:engine": engine_name,
        "IMM:seed": str(getattr(config, "seed", "") if getattr(config, "seed", -1) != -1 else ""),
        "IMM:steps": str(getattr(config, "steps", "") or ""),
        "IMM:cfg": str(getattr(config, "cfg", "") or ""),
        "IMM:workflow_version": str(getattr(config, "workflow_sha256", "") or ""),
    }
    try:
        stack = config.effective_lora_stack()
    except Exception:  # noqa: BLE001 - 元数据失败不影响输出
        stack = getattr(config, "lora_stack", []) or []
    if stack:
        try:
            meta["IMM:lora_stack"] = json.dumps(stack, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            pass
    return {k: v for k, v in meta.items() if v != ""}


def embed_png_metadata(path: Path, metadata: dict[str, str]) -> None:
    """把生成参数写入 PNG tEXt 块（失败静默，不影响输出）。

    必须在 DCT 水印**之后**调用：水印重编码会重建图像缓冲，先写会被剥离。
    仅 PNG 生效（JPEG/WebP 的 EXIF/_comment 属另一链路，暂不展开）。
    """
    if not metadata:
        return
    try:
        if _normalize_format(path.suffix.lstrip(".")) != "PNG":
            logger.debug("PNG metadata skipped (non-png): %s", path.name)
            return
        img = Image.open(path)
        pnginfo = PngInfo()
        for k, v in metadata.items():
            pnginfo.add_text(k, str(v))
        img.save(path, format="PNG", pnginfo=pnginfo)
        logger.debug("PNG metadata embedded: %s (%d keys)", path.name, len(metadata))
    except Exception as e:  # noqa: BLE001
        logger.debug("PNG metadata embedding failed for %s: %s", path.name, e)


def make_thumbnail(
    src: Path,
    thumb_dir: Path,
    name: str,
    max_side: int,
    image_format: str = "png",
    quality: int = 90,
) -> None:
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
        fmt = _normalize_format(image_format)
        save_kwargs: dict[str, Any] = {}
        if fmt in ("WEBP", "JPEG"):
            save_kwargs["quality"] = max(1, min(100, int(quality)))
        thumb.save(thumb_dir / name, format=fmt, **save_kwargs)
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
    image_format: str = "png",
    image_quality: int = 95,
    thumb_format: str = "png",
    thumb_quality: int = 90,
    metadata: dict[str, str] | None = None,
) -> None:
    """输出管线唯一入口：落盘 + 来源标识 + 缩略图 + 生成参数 tEXt。

    image_format/image_quality 控制主图压缩（P0 WebP/有损）；thumb_* 控制缩略图；
    metadata 为 PNG tEXt 生成参数（数据治理 P1-4，水印后嵌入防剥离）。
    """
    save_image(path, image, is_tensor=is_tensor, image_format=image_format, quality=image_quality)
    # 数据治理：基础生成质量/artifact 检测（§4.1 / 中期-质量 SLA），仅告警不阻断
    try:
        from ..native.preview import assess_image_quality
        _qflags = assess_image_quality(image)
        if any(_qflags.values()):
            logger.warning(
                "Low-quality generation detected (task=%s, path=%s): %s",
                task_id, path.name, _qflags,
            )
    except Exception as e:  # noqa: BLE001
        logger.debug("quality assessment skipped: %s", e)
    if wm_enabled:
        embed_provenance(path, product_id, task_id, image_format=image_format)
    # 生成参数 tEXt 必须在水印之后：embed_provenance 重编码会剥离先写入的元数据
    if metadata:
        embed_png_metadata(path, metadata)
    if thumb_enabled and thumb_dir is not None:
        make_thumbnail(
            path, thumb_dir, thumb_name, thumb_max_side,
            image_format=thumb_format, quality=thumb_quality,
        )


def generate_compare_image(img_a: Any, img_b: Any, axis: str = "horizontal") -> Any:
    """生成 EsEs 双图对比图（M9：batch > 1 时的差异可视化）。

    - horizontal: 左 A / 右 B（白色垂直分割线）
    - vertical: 上 A / 下 B（白色水平分割线）
    - slider: 左右各半 + 灰色虚线标记中轴
    """
    from PIL import Image

    max_w = max(img_a.width, img_b.width)
    max_h = max(img_a.height, img_b.height)
    if img_a.size != (max_w, max_h):
        img_a = img_a.resize((max_w, max_h), Image.Resampling.LANCZOS)
    if img_b.size != (max_w, max_h):
        img_b = img_b.resize((max_w, max_h), Image.Resampling.LANCZOS)

    arr_a = np.array(img_a)
    arr_b = np.array(img_b)
    half_color = np.array([255, 255, 255], dtype=np.uint8)

    if axis == "horizontal":
        combined = np.hstack([arr_a, arr_b])
        combined[:, max_w // 2] = half_color
    elif axis == "vertical":
        combined = np.vstack([arr_a, arr_b])
        combined[max_h // 2, :] = half_color
    elif axis == "slider":
        combined = np.hstack([arr_a, arr_b])
        line_x = max_w // 2
        for dy in range(0, combined.shape[0], 4):
            combined[dy, line_x] = [128, 128, 128]
    else:
        combined = np.hstack([arr_a, arr_b])
        combined[:, max_w // 2] = half_color

    return Image.fromarray(combined)
