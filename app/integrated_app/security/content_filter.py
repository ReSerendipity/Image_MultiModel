"""
security/content_filter.py — CLIP 安全内容检测器

对应全功能实施指南任务 1: CLIP 安全内容检测

设计要点（适配项目架构）：
- CLIP 模型 **懒加载**（首次调用 check_image 时才加载，避免 import 时卡住）
- CLIP 未安装时 **优雅降级**（check_prompt 关键词过滤仍然生效）
- 所有路径操作过 PathGuard
- 错误文案走 i18n 三层 fallback
- 全局单例通过 get_content_filter() 获取
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 结果数据类 ──────────────────────────────────────────────────
@dataclass
class SafetyResult:
    """安全检测结果。

    Attributes:
        is_safe: 是否安全（True=通过，False=拦截）。
        violation_type: 违规类型（安全时为 None）。
        confidence: 置信度 0.0~1.0。
        details: 附加详情字典。
    """

    is_safe: bool
    violation_type: str | None = None
    confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)


# ── 不安全关键词列表 ────────────────────────────────────────────
_UNSAFE_KEYWORDS: list[str] = [
    "naked", "nude", "sexy", "pornographic", "nsfw",
    "violent", "gore", "bloodbath", "massacre",
    "hate", "racist", "kill", "murder", "assassinate",
    "death", "suicide", "self-harm", "selfharm",
    "weapon", "bomb", "explosive", "terrorist",
    "drug", "cocaine", "heroin",
    "child abuse", "underage",
]

# CLIP 文本提示（英文，CLIP 原生支持英文最佳）
_UNSAFE_CLIP_PROMPTS: list[str] = [
    "a violent or gory image",
    "an explicit adult NSFW content image",
    "a hate speech or racist image",
    "a self-harm or suicide image",
    "an image depicting illegal drug use",
    "a weapon or explosive image",
]


class ContentSafetyFilter:
    """基于 CLIP 的内容安全过滤器。

    CLIP 模型懒加载，首次调用 ``check_image`` 时才加载到 GPU/CPU。
    如果 ``clip`` 包未安装，``check_image`` 返回保守放行结果，
    ``check_prompt`` 关键词过滤仍然生效。
    """

    def __init__(
        self,
        model_name: str = "ViT-B/32",
        fail_closed_on_clip_missing: bool = False,
    ) -> None:
        """初始化安全过滤器。

        Args:
            model_name: CLIP 模型名称（默认 ViT-B/32，体积小速度快）。
            fail_closed_on_clip_missing: CLIP 模型缺失时的降级策略。
                False=降级放行（fail-open，默认，向后兼容）；True=降级拦截（fail-closed）。
        """
        self._model_name: str = model_name
        self._fail_closed_on_clip_missing: bool = fail_closed_on_clip_missing
        self._model: Any = None
        self._preprocess: Any = None
        self._device: str = ""
        self._loaded: bool = False
        self._load_error: str | None = None

    # ── 降级策略（运行时可更新）──────────────────────────────────
    def set_fail_closed_on_clip_missing(self, value: bool) -> None:
        """运行时更新 CLIP 缺失时的降级策略（默认 fail-open）。

        Args:
            value: True=CLIP 缺失时拦截（fail-closed）；False=放行（fail-open）。
        """
        self._fail_closed_on_clip_missing = bool(value)

    # ── 模型懒加载 ──────────────────────────────────────────────
    def _ensure_loaded(self) -> bool:
        """懒加载 CLIP 模型。

        Returns:
            True 加载成功，False 加载失败（clip 未安装或其他错误）。
        """
        if self._loaded:
            return True
        if self._load_error is not None:
            return False

        try:
            import clip as clip_lib
            import torch
            from PIL import Image  # noqa: F401 — 确认 Pillow 可用

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model, self._preprocess = clip_lib.load(
                self._model_name, device=self._device
            )
            self._loaded = True
            logger.info(f"CLIP 模型加载成功: {self._model_name} @ {self._device}")
            return True
        except ImportError:
            self._load_error = "clip 包未安装，图片安全检查降级为关键词过滤"
            logger.warning(self._load_error)
            return False
        except Exception as e:
            self._load_error = f"CLIP 模型加载失败: {e}"
            logger.error(self._load_error)
            return False

    # ── 图片安全检查 ────────────────────────────────────────────
    def check_image(self, image_path: str | Path) -> SafetyResult:
        """检查图片是否包含违规内容。

        使用 CLIP 计算图片与不安全文本提示的相似度。
        如果 CLIP 未安装：默认返回降级放行（is_safe=True，向后兼容）；
        配置 fail_closed_on_clip_missing=True 时返回拦截（is_safe=False）。
        两种情况均在 details 中记录 degraded 降级信息。

        Args:
            image_path: 图片路径（已经过 PathGuard 校验）。

        Returns:
            SafetyResult: 安全检测结果。
        """
        if not self._ensure_loaded():
            details = {
                "degraded": True,
                "reason": self._load_error or "CLIP not available",
            }
            if self._fail_closed_on_clip_missing:
                # fail-closed：CLIP 不可用时拦截（violation_type 供上层区分原因）
                return SafetyResult(
                    is_safe=False,
                    violation_type="clip_unavailable",
                    confidence=0.0,
                    details=details,
                )
            # fail-open（默认，向后兼容）：降级放行，记录 degraded 标记
            return SafetyResult(
                is_safe=True,
                violation_type=None,
                confidence=0.0,
                details=details,
            )

        try:
            import torch
            from PIL import Image

            image = self._preprocess(Image.open(str(image_path))).unsqueeze(0).to(self._device)

            import clip as clip_lib
            text_tokens = clip_lib.tokenize(_UNSAFE_CLIP_PROMPTS).to(self._device)

            with torch.no_grad():
                image_features = self._model.encode_image(image)
                text_features = self._model.encode_text(text_tokens)
                # 计算余弦相似度并 softmax
                similarities = (100.0 * image_features @ text_features.T).softmax(dim=-1)
                max_sim = similarities.max().item()
                max_idx = similarities.argmax().item()

            threshold = 0.7
            if max_sim > threshold:
                return SafetyResult(
                    is_safe=False,
                    violation_type="content_warning",
                    confidence=max_sim,
                    details={
                        "similarity": max_sim,
                        "matched_prompt": _UNSAFE_CLIP_PROMPTS[max_idx],
                        "threshold": threshold,
                    },
                )

            return SafetyResult(
                is_safe=True,
                violation_type=None,
                confidence=1.0 - max_sim,
                details={"max_similarity": max_sim, "threshold": threshold},
            )

        except Exception as e:
            logger.error(f"图片安全检查失败: {e}")
            # 失败时保守策略：拒绝
            return SafetyResult(
                is_safe=False,
                violation_type="check_error",
                confidence=0.0,
                details={"error": str(e)},
            )

    # ── 提示词安全检查 ──────────────────────────────────────────
    def check_prompt(self, prompt: str) -> SafetyResult:
        """检查提示词是否包含违规关键词。

        使用关键词匹配，无需 CLIP 模型，始终可用。

        Args:
            prompt: 用户输入的提示词。

        Returns:
            SafetyResult: 安全检测结果。
        """
        prompt_lower = prompt.lower()

        for keyword in _UNSAFE_KEYWORDS:
            if keyword in prompt_lower:
                return SafetyResult(
                    is_safe=False,
                    violation_type=f"suspicious_keyword:{keyword}",
                    confidence=0.8,
                    details={"keyword": keyword},
                )

        return SafetyResult(
            is_safe=True,
            violation_type=None,
            confidence=1.0,
            details={},
        )


# ── 全局单例 ────────────────────────────────────────────────────
_content_filter: ContentSafetyFilter | None = None


def get_content_filter(
    fail_closed_on_clip_missing: bool | None = None,
) -> ContentSafetyFilter:
    """获取全局 ContentSafetyFilter 单例。

    Args:
        fail_closed_on_clip_missing: 可选。CLIP 缺失时是否 fail-closed 拦截。
            单例创建时作为初始值；单例已存在且该值不为 None 时同步更新。

    Returns:
        ContentSafetyFilter 实例。
    """
    global _content_filter
    if _content_filter is None:
        _content_filter = ContentSafetyFilter(
            fail_closed_on_clip_missing=bool(fail_closed_on_clip_missing)
        )
    elif fail_closed_on_clip_missing is not None:
        _content_filter.set_fail_closed_on_clip_missing(fail_closed_on_clip_missing)
    return _content_filter


def filter_image_generation(
    prompt: str,
    image_path: str | Path | None = None,
    fail_closed_on_clip_missing: bool | None = None,
) -> tuple[bool, str]:
    """过滤图像生成请求（提示词 + 可选参考图）。

    集成到 generate 路由的入口函数：
    1. 先检查提示词（关键词匹配，始终生效）
    2. 再检查参考图（CLIP 检测，需模型加载）

    Args:
        prompt: 用户提示词。
        image_path: 可选的参考图路径（已过 PathGuard）。
        fail_closed_on_clip_missing: CLIP 缺失时是否拦截（None=跟随单例当前配置）。

    Returns:
        (is_safe, reason): 通过=True/原因="OK"；拦截=False/原因=违规详情。
    """
    cf = get_content_filter(fail_closed_on_clip_missing=fail_closed_on_clip_missing)

    # 检查提示词
    prompt_result = cf.check_prompt(prompt)
    if not prompt_result.is_safe:
        return False, f"prompt_blocked:{prompt_result.violation_type}"

    # 检查参考图（如果有）
    if image_path:
        img_result = cf.check_image(image_path)
        if not img_result.is_safe:
            return False, f"image_blocked:{img_result.violation_type}"

    return True, "OK"
