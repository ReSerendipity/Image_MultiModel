"""
test_native_seedvr.py — SeedVR2 2x 超分（Task 3.3）单测

纯逻辑（config 构造、参数映射、权重定位、字节编解码、返回类型）直接验证；
真实模型加载/DF 推理用 mock 验证调用链；真实推理标记 slow 默认跳过。
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import torch
from PIL import Image

from integrated_app.native import seedvr

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_validate_color_correction_valid() -> None:
    """合法值原样返回。"""
    for c in seedvr.VALID_COLOR_CORRECTION:
        assert seedvr.validate_color_correction(c) == c


def test_validate_color_correction_invalid_falls_back() -> None:
    """非法值回退到 lab。"""
    assert seedvr.validate_color_correction("bogus") == "lab"


def test_resolve_weights_default_paths() -> None:
    """权重定位到 models/SEEDVR2 目录下的两个文件。"""
    dit, vae = seedvr.resolve_weights()
    assert dit.endswith(seedvr.DIT_MODEL)
    assert vae.endswith(seedvr.VAE_MODEL)
    assert "SEEDVR2" in dit


def test_resolve_weights_custom_dir(tmp_path) -> None:
    """自定义 models_dir 时拼在该目录下。"""
    dit, vae = seedvr.resolve_weights(models_dir=tmp_path)
    assert dit == str(tmp_path / seedvr.DIT_MODEL).replace("\\", "/")
    assert vae == str(tmp_path / seedvr.VAE_MODEL).replace("\\", "/")


def test_build_sr_config_contains_diffusion() -> None:
    """config 构造含 diffusion.schedule / sampler / timesteps。"""
    src = PROJECT_ROOT.parent / "APP" / "ComfyUI-aki-v3" / "ComfyUI" / "custom_nodes" / "ComfyUI-SeedVR2_VideoUpscaler"
    if not src.exists():
        pytest.skip("SeedVR2 custom node source not present")
    cfg = seedvr.build_sr_config(src)
    assert cfg.diffusion.schedule.type
    assert cfg.diffusion.sampler.type
    assert cfg.diffusion.timesteps.sampling.steps > 0
    assert cfg.vae.scaling_factor > 0


def test_image_bytes_roundtrip() -> None:
    """PNG 字节 → tensor → 字节 往返。"""
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (128, 64, 32)).save(buf, format="PNG")
    tensor = seedvr._image_bytes_to_tensor(buf.getvalue())
    assert tensor.shape == (1, 8, 8, 3)
    assert tensor.max() <= 1.0 and tensor.min() >= 0.0
    out = seedvr._tensor_to_image_bytes(tensor[0])
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


def test_sr_noise_and_condition_shapes() -> None:
    """噪声 2x 上采样；条件比噪声多一个 mask 通道。"""
    latent = torch.zeros(1, 4, 4, 16)

    class _Runner:
        def get_condition(self, latent, latent_blur, task):
            assert task == "sr"
            return torch.cat([latent, torch.ones_like(latent[..., :1])], dim=-1)

    noise, cond = seedvr._sr_noise_and_condition(_Runner(), latent, seed=42)
    assert noise.shape == (1, 8, 8, 16)  # 2x 上采样
    assert cond.shape == (1, 8, 8, 17)  # c + 1 个 mask 通道


def test_upscale_2x_mocked_pipeline(monkeypatch) -> None:
    """mock 整个调用链，验证返回类型为 PNG 字节（参数映射正确）。"""
    monkeypatch.setattr(seedvr, "is_available", lambda *a, **k: True)
    monkeypatch.setattr(seedvr, "source", _FakeSource())

    class _Runner:
        def __init__(self, config, debug):
            self.config = config
            self.out = torch.full((16, 16, 3), 0.5)  # [H, W, C]

        def configure_diffusion(self, device, dtype):
            return None

        def vae_encode(self, images):
            return [torch.zeros(1, 8, 8, 16)]

        def get_condition(self, **kw):
            return torch.zeros(1, 16, 16, 16)

        def inference(self, **kw):
            return [torch.zeros(1, 16, 16, 16)]

        def vae_decode(self, latents):
            return [self.out]

    monkeypatch.setattr(seedvr, "_get_runner_class", lambda: _Runner)
    monkeypatch.setattr(seedvr, "build_sr_config", lambda *a, **k: type("_C", (), {
        "vae": type("_V", (), {"dtype": "float32"})(),
        "diffusion": type("_D", (), {"cfg": type("_CFG", (), {"scale": 1.0})()})(),
    })())
    monkeypatch.setattr(seedvr, "resolve_weights", lambda *a, **k: ("/dit", "/vae"))
    monkeypatch.setattr(seedvr, "_load_sr_models", lambda runner, *a, **k: runner)
    monkeypatch.setattr(seedvr, "_load_embeddings", lambda *a, **k: torch.zeros(1, 1, 1))

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="PNG")
    out = seedvr.upscale_2x(buf.getvalue(), resolution=16)
    assert out[:8] == b"\x89PNG\r\n\x1a\n"  # 返回 PNG 字节


@pytest.mark.slow
@pytest.mark.skip(reason="真实 SeedVR2 超分需 GPU + 大权重，默认跳过")
def test_real_upscale_skipped_by_default() -> None:
    """真实推理不在默认测试集合执行。"""
    raise AssertionError("真实超分推理不应被默认执行")


class _FakeSource:
    def ensure_loaded(self, *a, **k):
        return None
