"""
native/seedvr.py — SeedVR2 2x 超分（进程内）

复用 aki-v3 自定义节点 ``ComfyUI-SeedVR2_VideoUpscaler`` 的 ``VideoDiffusionInfer``
（src/core/infer.py）+ 参考 Comfy 的 ``comfy.ldm.seedvr``，在同一进程内完成 2x 超分。

真实超分需要 GPU + 大权重（seedvr2_ema_3b_fp16 + ema_vae_fp16），故本模块提供完整调用链，
但纯逻辑（config 构造、参数映射、返回类型）在单测中用 mock 验证；真实推理标记 slow 跳过。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import torch

from . import source

logger = logging.getLogger(__name__)

# 权重文件名（aki-v3 models/SEEDVR2/ 目录）
DIT_MODEL = "seedvr2_ema_3b_fp16.safetensors"
VAE_MODEL = "ema_vae_fp16.safetensors"
SEEDVR2_FOLDER = "SEEDVR2"

# 合法 color_correction 选项（对齐 video_upscaler.py）
VALID_COLOR_CORRECTION = ("lab", "wavelet", "wavelet_adaptive", "hsv", "adain", "none")

# 默认自定义节点源码根 & models 目录
_AKI_ROOT = Path(r"C:\\Users\\Doro\\APP\\ComfyUI-aki-v3\\ComfyUI")
_DEFAULT_SEEDVR2_SRC = (
    _AKI_ROOT / "custom_nodes" / "ComfyUI-SeedVR2_VideoUpscaler"
)
_DEFAULT_MODELS_DIR = _AKI_ROOT / "models" / SEEDVR2_FOLDER


def _seedvr_source_dir(seedvr_source_dir: str | Path | None = None) -> Path:
    """解析自定义节点源码根目录（含 ``src/`` 包）。"""
    if seedvr_source_dir:
        return Path(seedvr_source_dir).resolve()
    return _DEFAULT_SEEDVR2_SRC


def _inject(seedvr_source_dir: str | Path | None = None) -> Path:
    """把自定义节点根目录（含 src 包）注入 sys.path，返回其绝对路径。"""
    root = _seedvr_source_dir(seedvr_source_dir)
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    return root


def is_available(seedvr_source_dir: str | Path | None = None) -> bool:
    """检查依赖是否可导入（VideoDiffusionInfer / comfy.ldm.seedvr）。"""
    try:
        _inject(seedvr_source_dir)
        from src.core.infer import VideoDiffusionInfer  # noqa: F401

        return True
    except Exception as e:  # noqa: BLE001
        logger.debug("SeedVR2 unavailable: %s", e)
        return False


def build_sr_config(
    seedvr_source_dir: str | Path | None = None,
    dit_model: str = DIT_MODEL,
) -> Any:
    """构造 SeedVR2 推理配置（OmegaConf DictConfig）。

    读取 ``configs_3b/main.yaml``（含 diffusion.schedule / sampler / timesteps），
    并取消只读以便后续按需覆盖。

    Args:
        seedvr_source_dir: 自定义节点源码根目录
        dit_model: DiT 权重名（含 "7b" 时用 7B 配置）

    Returns:
        OmegaConf DictConfig（对齐 _create_new_runner 的加载方式）
    """
    from omegaconf import OmegaConf

    root = _seedvr_source_dir(seedvr_source_dir)
    cfg_dir = "configs_7b" if ("7b" in (dit_model or "").lower()) else "configs_3b"
    config_path = root / cfg_dir / "main.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"SeedVR2 config not found: {config_path}")
    config = OmegaConf.load(str(config_path))
    OmegaConf.set_readonly(config, False)
    return config


def resolve_weights(
    models_dir: str | Path | None = None,
    dit_model: str = DIT_MODEL,
    vae_model: str = VAE_MODEL,
) -> tuple[str, str]:
    """定位 DiT / VAE 权重绝对路径。

    Args:
        models_dir: aki-v3 models/SEEDVR2 目录；为 None 用默认路径
        dit_model: DiT 权重文件名
        vae_model: VAE 权重文件名

    Returns:
        ``(dit_path, vae_path)`` 绝对路径（正斜杠）
    """
    base = Path(models_dir).resolve() if models_dir else _DEFAULT_MODELS_DIR
    dit = base / dit_model
    vae = base / vae_model
    return str(dit).replace("\\", "/"), str(vae).replace("\\", "/")


def validate_color_correction(color_correction: str) -> str:
    """校验并返回合法的 color_correction 值（非法时回退到 "lab"）。"""
    if color_correction not in VALID_COLOR_CORRECTION:
        logger.warning("Invalid color_correction '%s', falling back to 'lab'", color_correction)
        return "lab"
    return color_correction


def _image_bytes_to_tensor(image_bytes: bytes) -> torch.Tensor:
    """把 PNG/JPEG 字节解码为 ``[1, H, W, 3]`` 的 [0,1] RGB 张量。"""
    import io

    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    arr = torch.from_numpy(np.asarray(img)).float() / 255.0
    return arr.unsqueeze(0)  # [1, H, W, 3]


def _tensor_to_image_bytes(tensor: torch.Tensor, fmt: str = "PNG") -> bytes:
    """把 ``[H, W, 3]`` 的 [0,1] 张量编码为图片字节。"""
    import io

    from PIL import Image

    arr = (tensor.clamp(0.0, 1.0).detach().cpu().numpy() * 255.0).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format=fmt)
    return buf.getvalue()


def _sr_noise_and_condition(
    runner: Any,
    latent: torch.Tensor,
    seed: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """构造 SR 的超分噪声（2x 上采样）+ 条件（task="sr"，单帧）。

    SeedVR2 SR 把输入 latent 上采样 2x 作为噪声底，并叠加模糊条件通道。
    """
    from torch.nn import functional as F

    # latent: [T, H, W, C]（channels_last）→ 上采样 2x
    t, h, w, c = latent.shape
    perm = latent.permute(0, 3, 1, 2).float()  # [T, C, H, W]
    up = F.interpolate(perm, scale_factor=2.0, mode="bilinear", align_corners=False)
    up = up.permute(0, 2, 3, 1).contiguous()  # [T, 2H, 2W, C]

    # 确定性噪声
    gen = torch.Generator(device=up.device).manual_seed(max(0, int(seed)))
    noise = torch.randn(up.shape, generator=gen, device=up.device, dtype=up.dtype)

    # 条件：低分辨率上采样后的 latent 作为注入（task="sr" 时 get_condition 用 latent_blur）
    cond = runner.get_condition(latent=up, latent_blur=up, task="sr")
    return noise, cond


def _load_sr_models(
    runner: Any,
    config: Any,
    dit_path: str,
    vae_path: str,
    device: torch.device,
) -> Any:
    """在 meta 设备建结构并物化 DiT / VAE 权重到目标设备。"""
    from src.core.model_loader import materialize_model, prepare_model_structure
    from src.utils.debug import Debug  # type: ignore

    debug = Debug(enabled=False)
    runner = prepare_model_structure(runner, "dit", dit_path, config, debug)
    runner = prepare_model_structure(runner, "vae", vae_path, config, debug)
    materialize_model(runner, "dit", device, config, debug)
    materialize_model(runner, "vae", device, config, debug)
    return runner


def _get_runner_class() -> Any:
    """延迟导入并返回 VideoDiffusionInfer 类（独立入口便于 mock）。"""
    from src.core.infer import VideoDiffusionInfer  # type: ignore

    return VideoDiffusionInfer


def upscale_2x(
    image_bytes: bytes,
    resolution: int = 2048,
    seed: int = -1,
    color_correction: str = "lab",
    models_dir: str | Path | None = None,
    seedvr_source_dir: str | Path | None = None,
    device: str | None = None,
) -> bytes:
    """对单张图像执行 SeedVR2 2x 超分，返回上采样后的 PNG 字节。

    Args:
        image_bytes: 输入图像字节（PNG/JPEG）
        resolution: 短边目标分辨率（像素）
        seed: 随机种子（-1 用固定确定性种子）
        color_correction: lab/wavelet/hsv/adain/none 之一
        models_dir: 权重目录（默认 aki-v3 models/SEEDVR2）
        seedvr_source_dir: 自定义节点源码根目录
        device: 推理设备（默认 cuda 优先 cpu 兜底）

    Returns:
        上采样后的 PNG 字节。

    Raises:
        RuntimeError: 依赖不可导入或模型加载失败。
    """
    if not is_available(seedvr_source_dir):
        raise RuntimeError(
            "SeedVR2 dependencies not importable. Ensure the custom node "
            "'ComfyUI-SeedVR2_VideoUpscaler' is available."
        )
    source.ensure_loaded()

    color_correction = validate_color_correction(color_correction)
    seed = max(0, int(seed)) if seed >= 0 else 120429878797176
    dev = torch.device(device) if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 1) 解码输入
    img = _image_bytes_to_tensor(image_bytes).to(dev)
    # 2) 构造配置
    config = build_sr_config(seedvr_source_dir)
    # 3) 构造 runner 并配置 diffusion
    VideoDiffusionInfer = _get_runner_class()
    runner = VideoDiffusionInfer(config, None)
    runner.configure_diffusion(device=dev, dtype=getattr(torch, config.vae.dtype))
    # 4) 加载模型
    dit_path, vae_path = resolve_weights(models_dir)
    runner = _load_sr_models(runner, config, dit_path, vae_path, dev)
    # 5) VAE 编码 → latent
    latents = runner.vae_encode([img])
    latent = latents[0]
    # 6) 构造噪声 + 条件，SR 扩散
    noise, cond = _sr_noise_and_condition(runner, latent, seed)
    texts_pos = _load_embeddings("pos")
    texts_neg = _load_embeddings("neg")
    upscaled = runner.inference(
        noises=[noise],
        conditions=[cond],
        texts_pos=[texts_pos],
        texts_neg=[texts_neg],
        cfg_scale=config.diffusion.cfg.scale,
    )
    # 7) VAE 解码 → 图像
    samples = runner.vae_decode(upscaled)
    out = samples[0]
    # 8) 裁剪到 [0,1] 并编码返回
    return _tensor_to_image_bytes(out.clamp(0.0, 1.0), fmt="PNG")


def _load_embeddings(kind: str) -> torch.Tensor:
    """加载 SeedVR2 预置文本嵌入（pos/neg）。"""
    from src.utils.constants import get_script_directory  # type: ignore

    path = os.path.join(get_script_directory(), f"{kind}_emb.pt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"SeedVR2 embedding not found: {path}")
    return torch.load(path, weights_only=True)
