"""
tests/test_watermark.py — DCT 水印嵌入/提取/校验（PRD §8.6）

仅依赖 numpy（已装）。验证：
- 嵌入后 verify() 可正确还原 product_id|task_id|timestamp
- 不可感知性：嵌入前后最大像素差在可接受范围
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bin.integrated_app import watermark  # noqa: E402

pytest.importorskip("numpy")


def _smooth_image(h: int = 256, w: int = 256, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    base = 128 + 60 * np.sin(x / 18.0) * np.cos(y / 22.0)
    noise = rng.normal(0, 3, (h, w))
    return np.clip(base + noise, 0, 255)


def test_watermark_roundtrip() -> None:
    img = _smooth_image()
    ts = 1786200000.0
    marked = watermark.embed_watermark(img, "img_multimodel", "task_abc123", ts)
    assert watermark.verify(marked, "img_multimodel", "task_abc123", ts) is True


def test_watermark_wrong_payload_fails() -> None:
    img = _smooth_image()
    ts = 1786200000.0
    marked = watermark.embed_watermark(img, "img_multimodel", "task_abc123", ts)
    assert watermark.verify(marked, "img_multimodel", "task_OTHER", ts) is False


def test_watermark_imperceptible() -> None:
    img = _smooth_image()
    marked = watermark.embed_watermark(img, "p", "t", 1.0)
    max_diff = float(np.abs(marked - img).max())
    # 量化步长上限 MAX_Q=16 经 IDCT 扩散后单像素差应远小于亮度全量程
    assert max_diff < 20, f"watermark too visible: max_diff={max_diff}"


def test_watermark_png_roundtrip() -> None:
    """真实管线路径：float64 → uint8 裁剪 → PNG 编码 → 读回，仍可校验（回归 #1）"""
    import io

    from PIL import Image

    img = _smooth_image()
    ts = 1786200000.0
    marked = watermark.embed_watermark(img, "img_multimodel", "task_png_rt", ts)
    marked = np.clip(marked, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(marked).save(buf, format="PNG")
    reloaded = np.asarray(Image.open(io.BytesIO(buf.getvalue())), dtype=np.float64)
    assert watermark.verify(reloaded, "img_multimodel", "task_png_rt", ts) is True


def test_watermark_rgb_only_first_channel() -> None:
    gray = _smooth_image()
    rgb = np.stack([gray, gray, gray], axis=-1)
    marked = watermark.embed_watermark(rgb, "p", "t", 1.0)
    assert marked.shape == rgb.shape
    # 第 2/3 通道应保持不变
    assert np.allclose(marked[:, :, 1], rgb[:, :, 1])
    assert np.allclose(marked[:, :, 2], rgb[:, :, 2])
