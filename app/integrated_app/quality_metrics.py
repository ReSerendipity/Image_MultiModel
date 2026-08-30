"""
quality_metrics.py — 生成质量基准度量（MLOps P1·质量）

对应审计反模式 #4（模型更新后无自动质量回归测试）：提供
- 图像级度量：PSNR / SSIM（灰度，无需 GPU，可单测）
- Golden File 回归：将生成图与已登记基线对比，低于阈值即判不合格
- CLIP-score：可选（需 transformers + openai/clip，离线环境自动跳过）

设计：所有重依赖（PIL / numpy / CLIP）均惰性导入，缺失时优雅降级，
保证本模块在无 GPU、无模型环境下也能导入并被单测覆盖。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:  # pragma: no cover - 依赖缺失
    _HAS_PIL = False
    Image = None  # type: ignore[assignment]

try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:  # pragma: no cover - 依赖缺失
    _HAS_NUMPY = False
    np = None  # type: ignore[assignment]


def _require_pil() -> None:
    if not _HAS_PIL:
        raise RuntimeError("Pillow 未安装，无法计算图像质量指标（pip install Pillow）")


def _require_numpy() -> None:
    if not _HAS_NUMPY:
        raise RuntimeError("numpy 未安装，无法计算图像质量指标（pip install numpy）")


def _to_gray_array(img: Any) -> np.ndarray:
    _require_pil()
    _require_numpy()
    arr = np.asarray(img.convert("L"), dtype=np.float64)  # type: ignore[union-attr]
    return arr


def _align(img_a: Any, img_b: Any) -> tuple[np.ndarray, np.ndarray]:
    """统一为灰度 float 数组，尺寸不一致时把 b resize 到 a。"""
    a = _to_gray_array(img_a)
    b = _to_gray_array(img_b)
    if a.shape != b.shape:
        b = _to_gray_array(img_b.resize(a.shape[::-1]))  # type: ignore[union-attr]
    return a, b


def compute_mse(img_a: Any, img_b: Any) -> float:
    """均方误差（灰度）。"""
    a, b = _align(img_a, img_b)
    return float(((a - b) ** 2).mean())


def compute_psnr(img_a: Any, img_b: Any, max_val: float = 255.0) -> float:
    """峰值信噪比（dB）。完全相同返回 ``inf``。"""
    mse = compute_mse(img_a, img_b)
    if mse == 0.0:
        return float("inf")
    return float(10.0 * (np.log10((max_val**2) / mse)))  # type: ignore[union-attr]


def compute_ssim(img_a: Any, img_b: Any, data_range: float = 255.0) -> float:
    """结构相似性（全局简化版，灰度）。范围 [-1, 1]，1 表示完全相同。"""
    a, b = _align(img_a, img_b)
    mu_a, mu_b = a.mean(), b.mean()
    sigma_a2 = ((a - mu_a) ** 2).mean()
    sigma_b2 = ((b - mu_b) ** 2).mean()
    sigma_ab = ((a - mu_a) * (b - mu_b)).mean()
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    num = (2 * mu_a * mu_b + c1) * (2 * sigma_ab + c2)
    den = (mu_a**2 + mu_b**2 + c1) * (sigma_a2 + sigma_b2 + c2)
    if den == 0.0:
        return 1.0 if num == 0.0 else 0.0
    return float(num / den)


def compute_clip_score(images: list[Any], prompts: list[str]) -> float:
    """CLIP-score（可选，需 transformers + openai/clip，离线自动抛错由调用方 skip）。

    Args:
        images: PIL.Image 列表
        prompts: 与 images 等长的文本描述

    Returns:
        clip_score = mean(100 * cos(clip_img, clip_txt))
    """
    _require_pil()
    try:
        import torch  # noqa: F401
        from transformers import CLIPModel, CLIPProcessor  # type: ignore
    except Exception as e:  # pragma: no cover - 离线环境
        raise RuntimeError("CLIP-score 需要 transformers + torch（离线环境不可用）") from e

    model_id = "openai/clip-vit-base-patch32"
    processor = CLIPProcessor.from_pretrained(model_id)  # type: ignore[attr-defined]
    model = CLIPModel.from_pretrained(model_id)  # type: ignore[attr-defined]
    inputs = processor(text=prompts, images=images, return_tensors="pt", padding=True, truncation=True)  # type: ignore[operator]
    with __import__("torch").no_grad():
        out = model(**inputs)
        img_feats = out.image_embeds / out.image_embeds.norm(dim=-1, keepdim=True)
        txt_feats = out.text_embeds / out.text_embeds.norm(dim=-1, keepdim=True)
        cos = (img_feats * txt_feats).sum(dim=-1)
    return float((100.0 * cos.mean()).item())


@dataclass
class GoldenComparison:
    """单次 Golden File 回归结果。"""

    name: str
    ssim: float
    psnr: float
    passed: bool
    ssim_threshold: float
    psnr_threshold: float
    detail: str = ""


class GoldenFileRegistry:
    """Golden File 回归登记与对比。

    用法::

        reg = GoldenFileRegistry("tests/fixtures/golden", ssim_threshold=0.95)
        # 首次建立基线：reg.compare("smoke", img, regenerate=True)
        result = reg.compare("smoke", generated_img)
        if not result.passed:
            logger.warning("质量回归: %s", result)

    基线图缺失且 ``regenerate=False`` 时视为失败（避免静默通过）。
    """

    def __init__(
        self,
        golden_dir: str | Path,
        *,
        ssim_threshold: float = 0.95,
        psnr_threshold: float = 20.0,
    ) -> None:
        self.golden_dir = Path(golden_dir)
        self.ssim_threshold = ssim_threshold
        self.psnr_threshold = psnr_threshold

    def golden_path(self, name: str) -> Path:
        p = self.golden_dir / name
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            p = p.with_suffix(".png")
        return p

    def has_golden(self, name: str) -> bool:
        p = self.golden_path(name)
        return p.exists() and p.is_file()

    def compare(self, name: str, generated: Any, *, regenerate: bool = False) -> GoldenComparison:
        _require_pil()
        gp = self.golden_path(name)
        if regenerate:
            gp.parent.mkdir(parents=True, exist_ok=True)
            generated.save(gp)
            return GoldenComparison(
                name=name, ssim=1.0, psnr=float("inf"),
                passed=True, ssim_threshold=self.ssim_threshold,
                psnr_threshold=self.psnr_threshold, detail="regenerated baseline",
            )
        if not gp.exists():
            return GoldenComparison(
                name=name, ssim=0.0, psnr=0.0,
                passed=False, ssim_threshold=self.ssim_threshold,
                psnr_threshold=self.psnr_threshold, detail="golden baseline missing",
            )
        ref = Image.open(gp).convert("RGB")  # type: ignore[union-attr]
        ssim = compute_ssim(ref, generated)
        psnr = compute_psnr(ref, generated)
        passed = ssim >= self.ssim_threshold and psnr >= self.psnr_threshold
        detail = "" if passed else f"ssim={ssim:.4f}<{self.ssim_threshold} or psnr={psnr:.2f}<{self.psnr_threshold}"
        return GoldenComparison(
            name=name, ssim=ssim, psnr=psnr, passed=passed,
            ssim_threshold=self.ssim_threshold, psnr_threshold=self.psnr_threshold,
            detail=detail,
        )


__all__ = [
    "compute_mse",
    "compute_psnr",
    "compute_ssim",
    "compute_clip_score",
    "GoldenComparison",
    "GoldenFileRegistry",
]
