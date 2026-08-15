"""
test_native_preview.py — 实时预览（Task 3.6）单测

验证张量→低分辨率 b64 编码、SSE comfy_preview 事件格式。
"""

from __future__ import annotations

import base64
import io

import torch
from PIL import Image

from integrated_app.native import preview


def test_tensor_to_preview_b64_roundtrip() -> None:
    """[0,1] 张量编码为可解码 b64。"""
    img = torch.zeros(1, 32, 32, 3)
    b64 = preview.tensor_to_preview_b64(img)
    raw = base64.b64decode(b64)
    pil = Image.open(io.BytesIO(raw))
    assert pil.size == (32, 32)


def test_tensor_to_preview_b64_resizes() -> None:
    """超过 max_width 时缩小预览。"""
    img = torch.rand(1, 64, 128, 3)  # W=128
    b64 = preview.tensor_to_preview_b64(img, max_width=32)
    raw = base64.b64decode(b64)
    pil = Image.open(io.BytesIO(raw))
    assert pil.size[0] == 32
    assert pil.size[1] == 16


def test_publish_preview_event_format() -> None:
    """publish_preview 推送 comfy_preview 事件，含 b64/format/width/task_id。"""
    captured: dict = {}

    class _Bus:
        async def publish(self, event: str, data: dict):
            captured["event"] = event
            captured["data"] = data

    import asyncio

    asyncio.run(preview.publish_preview(_Bus(), "abc", width=256, fmt="jpg", task_id="t1"))
    assert captured["event"] == "preview"
    assert captured["data"]["b64"] == "abc"
    assert captured["data"]["format"] == "jpg"
    assert captured["data"]["width"] == 256
    assert captured["data"]["task_id"] == "t1"


def test_publish_preview_tensor_combines() -> None:
    """publish_preview_tensor 编码并推送。"""
    captured: dict = {}

    class _Bus:
        async def publish(self, event: str, data: dict):
            captured["event"] = event
            captured["data"] = data

    import asyncio

    img = torch.zeros(1, 16, 16, 3)
    asyncio.run(preview.publish_preview_tensor(_Bus(), img, max_width=8, task_id="t2"))
    assert captured["event"] == "preview"
    assert captured["data"]["format"] == "jpg"
    assert captured["data"]["width"] == 8
    # b64 可解码
    raw = base64.b64decode(captured["data"]["b64"])
    pil = Image.open(io.BytesIO(raw))
    assert pil.size[0] == 8


def test_preview_format_matches_comfy_engine() -> None:
    """与 comfy/engine.py 的 b_preview 消息承载字段一致。"""
    img = torch.rand(1, 16, 16, 3)
    b64 = preview.tensor_to_preview_b64(img)
    # comfy/engine.py 用 {"preview_b64": b64, "preview_format": "jpg"}
    progress_extra = {"preview_b64": b64, "preview_format": "jpg"}
    assert progress_extra["preview_b64"]
    assert progress_extra["preview_format"] == "jpg"
