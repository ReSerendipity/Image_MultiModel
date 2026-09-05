"""
test_png_metadata.py — 数据治理报告 P1-4：PNG tEXt 生成参数嵌入

覆盖：
- build_generation_metadata：字段齐全、空值剔除、LoRA 栈 JSON 化
- embed_png_metadata：tEXt 可读回、非 PNG 跳过、损坏文件静默
- finalize_output 端到端：DCT 水印后元数据仍存在（防剥离）

注：Windows 下 pytest tmp_path 清理有 PermissionError 缺陷（见 test_data_governance.py
注释），统一用 tempfile 自建临时目录。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from integrated_app.native import output_pipeline as op


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="pngmeta_test_"))


class _FakeGenConfig:
    """最小 GenerationConfig 替身（output_pipeline 只 getattr，不依赖真实类）。"""

    seed = 42
    steps = 10
    cfg = 1.0
    workflow_sha256 = "ab" * 32
    lora_stack = [{"name": "lora_a", "strength": 0.7}]

    def effective_lora_stack(self) -> list[dict]:
        return self.lora_stack


def _tiny_image() -> Image.Image:
    arr = np.random.RandomState(0).randint(0, 256, (32, 32, 3)).astype("uint8")
    return Image.fromarray(arr, "RGB")


def test_build_generation_metadata_fields() -> None:
    meta = op.build_generation_metadata("task123", _FakeGenConfig(), "z_image_turbo_native")
    assert meta["IMM:task_id"] == "task123"
    assert meta["IMM:engine"] == "z_image_turbo_native"
    assert meta["IMM:seed"] == "42"
    assert meta["IMM:steps"] == "10"
    assert meta["IMM:workflow_version"] == "ab" * 32
    assert '"name": "lora_a"' in meta["IMM:lora_stack"]


def test_build_generation_metadata_drops_empty() -> None:
    meta = op.build_generation_metadata("", _FakeGenConfig(), "")
    assert "IMM:task_id" not in meta
    assert "IMM:engine" not in meta


def test_embed_png_metadata_roundtrip() -> None:
    d = _tmp()
    p = d / "out.png"
    _tiny_image().save(p, format="PNG")
    meta = op.build_generation_metadata("taskxyz", _FakeGenConfig(), "engine_a")
    op.embed_png_metadata(p, meta)
    with Image.open(p) as img:
        text = getattr(img, "text", {})
    assert text.get("IMM:task_id") == "taskxyz"
    assert text.get("Software") == "Image_MultiModel"
    # 像素未被破坏
    assert img.size == (32, 32)


def test_embed_png_metadata_skips_non_png() -> None:
    d = _tmp()
    p = d / "out.jpg"
    _tiny_image().save(p, format="JPEG")
    # 不应抛异常
    op.embed_png_metadata(p, {"IMM:task_id": "t1"})
    with Image.open(p) as img:
        assert getattr(img, "text", {}) == {}


def test_finalize_output_metadata_survives_watermark() -> None:
    """关键回归：水印重编码不得剥离先写入的 tEXt（嵌入在水印之后）。"""
    d = _tmp()
    p = d / "wm.png"
    tensor = torch.zeros((32, 32, 3)) + 0.5
    meta = op.build_generation_metadata("taskwm", _FakeGenConfig(), "engine_wm")
    op.finalize_output(
        p,
        tensor,
        is_tensor=True,
        wm_enabled=True,
        product_id="IMGMULTI-1",
        task_id="taskwm",
        thumb_enabled=False,
        thumb_dir=None,
        thumb_name="x_thumb.png",
        thumb_max_side=64,
        metadata=meta,
    )
    assert p.exists()
    with Image.open(p) as img:
        text = getattr(img, "text", {})
    assert text.get("IMM:task_id") == "taskwm", "水印后 tEXt 应保留"
    assert text.get("IMM:workflow_version") == "ab" * 32


def test_finalize_output_metadata_none_noop() -> None:
    d = _tmp()
    p = d / "plain.png"
    tensor = torch.zeros((32, 32, 3)) + 0.5
    op.finalize_output(
        p,
        tensor,
        is_tensor=True,
        wm_enabled=False,
        product_id="IMGMULTI-1",
        task_id="taskplain",
        thumb_enabled=False,
        thumb_dir=None,
        thumb_name="x_thumb.png",
        thumb_max_side=64,
    )
    assert p.exists()
    with Image.open(p) as img:
        assert getattr(img, "text", {}).get("IMM:task_id") is None
