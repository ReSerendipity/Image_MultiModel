"""
tests/test_prompt_expander.py — 提示词扩展系统测试

对应全功能实施指南任务 2 验收标准：
- 扩写准确率≥90%（人工评估）
- 支持 keyword:weight 语法
- 提供至少 5 种预设风格
"""

from __future__ import annotations

import pytest

from integrated_app.prompt_expander import (
    NEGATIVE_DEFAULTS,
    QUALITY_BOOSTERS,
    SCENE_SUGGESTIONS,
    STYLE_TEMPLATES,
    PromptExpander,
    expand_prompt,
    get_prompt_expander,
)


class TestStyleTemplates:
    """风格模板测试"""

    def test_at_least_5_styles_available(self):
        """至少 5 种预设风格"""
        assert len(STYLE_TEMPLATES) >= 5

    def test_cinematic_style_exists(self):
        """cinematic 风格存在"""
        assert "cinematic" in STYLE_TEMPLATES

    def test_anime_style_exists(self):
        """anime 风格存在"""
        assert "anime" in STYLE_TEMPLATES

    def test_photorealistic_style_exists(self):
        """photorealistic 风格存在"""
        assert "photorealistic" in STYLE_TEMPLATES

    def test_oil_painting_style_exists(self):
        """oil_painting 风格存在"""
        assert "oil_painting" in STYLE_TEMPLATES

    def test_all_styles_non_empty(self):
        """所有风格模板非空"""
        for name, template in STYLE_TEMPLATES.items():
            assert template.strip(), f"Style '{name}' has empty template"


class TestExpand:
    """expand() 方法测试"""

    @pytest.fixture
    def expander(self):
        return PromptExpander()

    @pytest.mark.smoke
    def test_basic_expand(self, expander):
        """基本扩写：提示词 + 质量增强"""
        result = expander.expand("a cat sitting on a chair")
        assert "a cat sitting on a chair" in result
        assert "masterpiece" in result
        assert "best quality" in result

    def test_expand_with_style(self, expander):
        """带风格扩写"""
        result = expander.expand("a cat", style="cinematic")
        assert "cinematic lighting" in result

    def test_expand_without_auto_enhance(self, expander):
        """关闭自动增强"""
        result = expander.expand("a cat", auto_enhance=False, style="none")
        assert result == "a cat"

    def test_expand_empty_prompt(self, expander):
        """空提示词返回空字符串"""
        assert expander.expand("") == ""
        assert expander.expand("   ") == ""

    def test_expand_no_duplicate_boosters(self, expander):
        """已有质量词时不重复添加"""
        result = expander.expand("a cat, masterpiece")
        # masterpiece 只出现一次（原始 + 扩展不重复）
        assert result.count("masterpiece") == 1

    def test_expand_with_unknown_style(self, expander):
        """未知风格不崩溃，只做质量增强"""
        result = expander.expand("a cat", style="nonexistent_style")
        assert "a cat" in result
        assert "masterpiece" in result

    def test_quality_boosters_applied(self, expander):
        """所有质量增强词被添加"""
        result = expander.expand("a cat")
        for booster, _ in QUALITY_BOOSTERS:
            assert booster in result, f"Booster '{booster}' not found in expanded prompt"

    def test_weight_syntax_in_boosters(self, expander):
        """质量增强词使用加权语法"""
        result = expander.expand("a cat")
        assert "(masterpiece:1.5)" in result or "(( masterpiece ):1.5)" in result


class TestWeightSyntax:
    """keyword:weight 加权语法测试"""

    @pytest.fixture
    def expander(self):
        return PromptExpander()

    def test_weight_syntax_converted(self, expander):
        """(keyword:weight) → (( keyword ):weight)"""
        result = expander._apply_weight_syntax("(beautiful:1.2)")
        assert "(( beautiful ):1.2)" in result

    def test_weight_syntax_with_decimal(self, expander):
        """小数权重"""
        result = expander._apply_weight_syntax("(sky:0.8)")
        assert "(( sky ):0.8)" in result

    def test_weight_syntax_not_double_wrapped(self, expander):
        """已包装的不再重复包装"""
        result = expander._apply_weight_syntax("(( already ):1.0)")
        # 不应该变成 ((( already ):1.0))
        assert result.count("(( already ):1.0)") == 1

    def test_weight_syntax_preserves_other_text(self, expander):
        """保留其他文本"""
        result = expander._apply_weight_syntax("a (cat:1.5) on a chair")
        assert "a " in result
        assert "on a chair" in result
        assert "(( cat ):1.5)" in result


class TestNegativePrompt:
    """负面提示词生成测试"""

    @pytest.fixture
    def expander(self):
        return PromptExpander()

    def test_default_negatives(self, expander):
        """默认负面词全部包含"""
        result = expander.generate_negative_prompt()
        for neg in NEGATIVE_DEFAULTS:
            assert neg in result

    def test_user_negatives_merged(self, expander):
        """用户负面词合并"""
        result = expander.generate_negative_prompt("custom neg, another neg")
        assert "custom neg" in result
        assert "another neg" in result

    def test_no_duplicate_negatives(self, expander):
        """不重复添加已有负面词"""
        result = expander.generate_negative_prompt("low quality, blurry")
        assert result.count("low quality") == 1
        assert result.count("blurry") == 1

    def test_empty_user_negative(self, expander):
        """空用户负面词只用默认"""
        result = expander.generate_negative_prompt("")
        assert "low quality" in result

    def test_whitespace_handling(self, expander):
        """空格处理"""
        result = expander.generate_negative_prompt("  spaced  ,  word  ")
        assert "spaced" in result
        assert "word" in result


class TestSmartSuggest:
    """智能推荐测试"""

    @pytest.fixture
    def expander(self):
        return PromptExpander()

    def test_portrait_suggestion(self, expander):
        """肖像推荐"""
        result = expander.smart_suggest("a portrait of a girl")
        assert "portrait" in result["positive"].lower() or "girl" in result["positive"].lower()
        assert result["style"] == "photorealistic"

    def test_landscape_suggestion(self, expander):
        """风景推荐"""
        result = expander.smart_suggest("mountain landscape")
        assert "landscape" in result["positive"].lower() or "mountain" in result["positive"].lower()
        assert result["style"] == "cinematic"

    def test_fantasy_suggestion(self, expander):
        """奇幻推荐"""
        result = expander.smart_suggest("a fantasy castle")
        assert "fantasy" in result["positive"].lower() or "castle" in result["positive"].lower()
        assert result["style"] == "fantasy"

    def test_default_suggestion_no_match(self, expander):
        """无匹配时返回默认"""
        result = expander.smart_suggest("xyzabc random text")
        assert result["positive"] == "xyzabc random text"
        assert result["style"] == "none"

    def test_subject_substitution(self, expander):
        """主体词替换"""
        result = expander.smart_suggest("portrait of a beautiful woman")
        assert "beautiful woman" in result["positive"]

    def test_all_scenes_have_fields(self, expander):
        """所有场景模板都有 positive/style/negative"""
        for key, tmpl in SCENE_SUGGESTIONS.items():
            assert "positive" in tmpl, f"Scene '{key}' missing 'positive'"
            assert "style" in tmpl, f"Scene '{key}' missing 'style'"
            assert "negative" in tmpl, f"Scene '{key}' missing 'negative'"


class TestListMethods:
    """列表方法测试"""

    @pytest.fixture
    def expander(self):
        return PromptExpander()

    def test_list_styles(self, expander):
        """list_styles 返回风格列表"""
        styles = expander.list_styles()
        assert len(styles) >= 5
        for s in styles:
            assert "name" in s
            assert "description" in s

    def test_list_scenes(self, expander):
        """list_scenes 返回场景列表"""
        scenes = expander.list_scenes()
        assert len(scenes) >= 4
        assert "portrait" in scenes
        assert "landscape" in scenes


class TestGlobalInstance:
    """全局单例测试"""

    def test_get_prompt_expander_returns_same_instance(self):
        """get_prompt_expander 返回同一实例"""
        e1 = get_prompt_expander()
        e2 = get_prompt_expander()
        assert e1 is e2

    def test_expand_prompt_function(self):
        """expand_prompt 便捷函数"""
        result = expand_prompt("a cat", style="anime", auto_enhance=True)
        assert "expanded_prompt" in result
        assert "negative_prompt" in result
        assert "original_prompt" in result
        assert result["original_prompt"] == "a cat"
        assert "anime" in result["expanded_prompt"].lower() or "cel shaded" in result["expanded_prompt"]
        assert "low quality" in result["negative_prompt"]
