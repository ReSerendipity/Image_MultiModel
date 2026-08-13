"""
prompt_expander.py — 智能提示词扩展系统（Fooocus 风格 Enhancer）

对应全功能实施指南任务 2: Fooocus 风格提示词扩展

功能：
- 风格模板扩写（cinematic / anime / photorealistic / oil_painting / digital_art / fantasy）
- 自动质量增强（masterpiece / best quality / ultra detailed / 8k）
- keyword:weight 加权语法处理
- 智能负面提示词生成
- 场景智能推荐（portrait / landscape / still_life / architecture）
"""

from __future__ import annotations

import re
from typing import Any

# ── 风格模板库 ──────────────────────────────────────────────────
STYLE_TEMPLATES: dict[str, str] = {
    "cinematic": (
        "cinematic lighting, dramatic shadows, movie still, "
        "highly detailed, 8k resolution, film grain"
    ),
    "anime": (
        "anime style, cel shaded, vibrant colors, "
        "studio Ghibli inspired, soft lighting"
    ),
    "photorealistic": (
        "photorealistic, ultra detailed, 8k, RAW photo, "
        "professional photography, depth of field"
    ),
    "oil_painting": (
        "oil painting, textured brushstrokes, impasto, "
        "classical art, rich colors, canvas texture"
    ),
    "digital_art": (
        "digital art, concept art, trending on artstation, "
        "highly detailed, sharp focus, vibrant"
    ),
    "fantasy": (
        "fantasy art, ethereal, magical atmosphere, "
        "intricate details, mystical lighting, epic"
    ),
}

# ── 质量增强词 ──────────────────────────────────────────────────
QUALITY_BOOSTERS: list[tuple[str, float]] = [
    ("masterpiece", 1.5),
    ("best quality", 1.4),
    ("ultra detailed", 1.3),
    ("8k", 1.2),
]

# ── 默认负面提示词 ──────────────────────────────────────────────
NEGATIVE_DEFAULTS: list[str] = [
    "low quality",
    "worst quality",
    "blurry",
    "deformed",
    "ugly",
    "disfigured",
    "bad anatomy",
    "extra limbs",
    "watermark",
    "text",
]

# ── 场景推荐模板 ────────────────────────────────────────────────
SCENE_SUGGESTIONS: dict[str, dict[str, str]] = {
    "portrait": {
        "positive": (
            "a beautiful portrait of {subject}, "
            "detailed face, expressive eyes, "
            "soft lighting, bokeh background"
        ),
        "style": "photorealistic",
        "negative": "cartoon, anime, drawing, sketch",
    },
    "landscape": {
        "positive": (
            "a stunning landscape of {subject}, "
            "scenic view, golden hour, majestic"
        ),
        "style": "cinematic",
        "negative": "urban, buildings, people, cars",
    },
    "still_life": {
        "positive": (
            "a still life of {subject}, "
            "carefully arranged, soft natural light, "
            "rich textures, detailed"
        ),
        "style": "oil_painting",
        "negative": "people, animals, motion, blur",
    },
    "architecture": {
        "positive": (
            "a grand architecture of {subject}, "
            "wide angle, dramatic perspective, "
            "clear sky, professional architectural photography"
        ),
        "style": "photorealistic",
        "negative": "people, clutter, informal, snapshot",
    },
    "fantasy": {
        "positive": (
            "a magical fantasy scene of {subject}, "
            "ethereal lighting, mystical atmosphere, "
            "intricate details, epic composition"
        ),
        "style": "fantasy",
        "negative": "modern, mundane, realistic, ordinary",
    },
}


class PromptExpander:
    """智能提示词扩写器（Fooocus 风格）。

    功能：
    - ``expand()``: 扩写提示词（风格模板 + 质量增强 + 加权语法）
    - ``generate_negative_prompt()``: 生成负面提示词
    - ``smart_suggest()``: 根据主体关键词智能推荐提示词组合
    - ``list_styles()``: 列出所有可用风格
    - ``list_scenes()``: 列出所有可用场景
    """

    def __init__(self) -> None:
        self.style_templates: dict[str, str] = dict(STYLE_TEMPLATES)
        self.quality_boosters: list[tuple[str, float]] = list(QUALITY_BOOSTERS)
        self.negative_defaults: list[str] = list(NEGATIVE_DEFAULTS)

    def expand(
        self,
        prompt: str,
        style: str = "none",
        auto_enhance: bool = True,
    ) -> str:
        """扩写提示词。

        Args:
            prompt: 原始提示词。
            style: 艺术风格（cinematic / anime / photorealistic / oil_painting /
                   digital_art / fantasy / none）。
            auto_enhance: 是否自动添加质量修饰语。

        Returns:
            扩写后的提示词。
        """
        expanded = prompt.strip()
        if not expanded:
            return ""

        # 自动质量增强
        if auto_enhance:
            for booster, weight in self.quality_boosters:
                if booster not in expanded.lower():
                    expanded += f", ({booster}:{weight})"

        # 应用风格模板
        if style != "none" and style in self.style_templates:
            style_prompt = self.style_templates[style]
            expanded += f", {style_prompt}"

        # 语法解析与权重调整
        expanded = self._apply_weight_syntax(expanded)

        return expanded

    def _apply_weight_syntax(self, prompt: str) -> str:
        """处理加权语法 keyword:weight，统一为 ((keyword):weight) 格式。

        避免重复包装：如果已经是 ((keyword):weight) 格式则不再处理。

        Args:
            prompt: 含加权语法的提示词。

        Returns:
            统一格式后的提示词。
        """
        def replace_weight(match: re.Match[str]) -> str:
            keyword = match.group(1).strip()
            weight = float(match.group(2))
            return f"(( {keyword} ):{weight})"

        # 匹配 (keyword:weight) 但不匹配 (( keyword ):weight)
        # 负向断言确保前面不是 (
        return re.sub(r'(?<!\()\(([^()]+):([\d.]+)\)', replace_weight, prompt)

    def generate_negative_prompt(self, user_negative: str = "") -> str:
        """生成负面提示词。

        合并默认负面词和用户提供的负面词，去重。

        Args:
            user_negative: 用户自定义负面提示词（逗号分隔）。

        Returns:
            合并后的负面提示词。
        """
        negatives = list(self.negative_defaults)

        if user_negative:
            for word in user_negative.split(","):
                word = word.strip().lower()
                if word and word not in negatives:
                    negatives.append(word)

        return ", ".join(negatives)

    def smart_suggest(self, subject: str) -> dict[str, str]:
        """智能推荐提示词组合。

        根据主体关键词匹配预设场景模板。

        Args:
            subject: 主体描述（如 "a girl"、"mountain landscape"）。

        Returns:
            包含 positive / style / negative 的推荐字典。
        """
        subject_lower = subject.lower()

        for key, templates in SCENE_SUGGESTIONS.items():
            if key in subject_lower:
                return {
                    "positive": templates["positive"].format(subject=subject),
                    "style": templates["style"],
                    "negative": templates["negative"],
                }

        # 默认推荐：通用
        return {
            "positive": subject,
            "style": "none",
            "negative": "",
        }

    def list_styles(self) -> list[dict[str, str]]:
        """列出所有可用风格。

        Returns:
            风格列表，每项含 name 和 description。
        """
        return [
            {"name": name, "description": desc}
            for name, desc in self.style_templates.items()
        ]

    def list_scenes(self) -> list[str]:
        """列出所有可用场景关键词。

        Returns:
            场景关键词列表。
        """
        return list(SCENE_SUGGESTIONS.keys())


# ── 全局实例 ────────────────────────────────────────────────────
_prompt_expander: PromptExpander | None = None


def get_prompt_expander() -> PromptExpander:
    """获取全局 PromptExpander 单例。

    Returns:
        PromptExpander 实例。
    """
    global _prompt_expander
    if _prompt_expander is None:
        _prompt_expander = PromptExpander()
    return _prompt_expander


def expand_prompt(
    prompt: str,
    style: str = "none",
    auto_enhance: bool = True,
    user_negative: str = "",
) -> dict[str, Any]:
    """扩写提示词的便捷函数。

    Args:
        prompt: 原始提示词。
        style: 艺术风格。
        auto_enhance: 是否自动增强。
        user_negative: 用户自定义负面提示词。

    Returns:
        含 expanded_prompt 和 negative_prompt 的字典。
    """
    expander = get_prompt_expander()
    expanded = expander.expand(prompt, style=style, auto_enhance=auto_enhance)
    negative = expander.generate_negative_prompt(user_negative)
    return {
        "expanded_prompt": expanded,
        "negative_prompt": negative,
        "original_prompt": prompt,
        "style": style,
        "auto_enhance": auto_enhance,
    }
