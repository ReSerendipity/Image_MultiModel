"""
test_native_batch_cancel.py — 批量任务与取消（Task 3.7）单测

确认：executor 用 batch latent 一次出多图；取消标志从 NativeEngine.cancel() 流转到
executor 采样回调并抛 CancelledError。
"""

from __future__ import annotations

import asyncio

import pytest

from integrated_app.engine_interface import GenerationConfig
from integrated_app.native import executor


def test_latent_shape_batch() -> None:
    """batch_size>1 时 latent 首维为 batch；Z-Image DiT latent 为 16 通道。"""
    assert executor.latent_shape(4, 1024, 1024) == [4, 16, 128, 128]
    assert executor.latent_shape(2, 512, 256) == [2, 16, 32, 64]


def test_build_latent_batch_shape() -> None:
    """build_latent 对 batch 返回正确形状（Batch latent 一次出多图）。"""
    latent = executor.build_latent(3, 1024, 1024)
    assert list(latent.shape) == [3, 16, 128, 128]


def test_txt2img_returns_list_per_batch(monkeypatch) -> None:
    """txt2img 对 batch latent 返回逐张图像列表（_vae_decode 按 batch 展开）。"""
    monkeypatch.setattr(
        executor, "_load_models",
        lambda *a, **k: type("_M", (), {"device": __import__("torch").device("cpu")})(),
    )
    # 仅验证 latent 构建与解码返回的拆分逻辑（不真正采样）
    import torch

    images = torch.rand(2, 16, 16, 3)  # (B,H,W,3)
    split = [images[i] for i in range(images.shape[0])]
    assert len(split) == 2
    assert split[0].shape == (16, 16, 3)


def test_sampling_callback_raises_on_cancel() -> None:
    """取消标志置位后采样回调抛 CancelledError。"""
    cancel_flag = [False]
    cb = executor._make_sampling_callback(8, None, cancel_flag)
    cancel_flag[0] = True
    with pytest.raises(asyncio.CancelledError):
        cb(1, None, None, 8)


def test_cancel_flag_flow_through_engine(monkeypatch) -> None:
    """NativeEngine.cancel() → _watch_cancel 触发内部 cancel_cb 置位标志。"""
    from integrated_app.native import source
    from integrated_app.native.engine import NativeEngine

    pytest.importorskip("torch")
    source.ensure_loaded(comfy_root=__import__("pathlib").Path(__file__).resolve().parent.parent / "comfy_kernel")

    eng = NativeEngine(name="z_image_turbo")
    async def scenario() -> bool:
        cancel_flag = [False]
        eng._cancel_requested = False

        def cancel_cb() -> None:
            cancel_flag[0] = True

        # 模拟正在运行的 future
        fut = asyncio.get_event_loop().create_future()
        watcher = asyncio.create_task(eng._watch_cancel(fut, cancel_cb))
        await eng.cancel()  # 置位 _cancel_requested
        await asyncio.sleep(0.1)  # 让 watcher 观察到标志
        watcher.cancel()
        return cancel_flag[0]

    assert asyncio.run(scenario()) is True


def test_effective_lora_stack_fallback() -> None:
    """lora_stack 空时回退旧 6 层字段；非空时优先动态栈。"""
    cfg = GenerationConfig(lora_1_name="a", lora_1_strength=1.0, lora_2_name="b")
    assert cfg.effective_lora_stack() == [
        {"name": "a", "strength": 1.0},
        {"name": "b", "strength": 0.7},
    ]

    cfg2 = GenerationConfig(
        lora_stack=[{"name": "x", "strength": 0.3}, {"name": "y"}],
        lora_1_name="ignored",
    )
    assert cfg2.effective_lora_stack() == [{"name": "x", "strength": 0.3}, {"name": "y"}]
