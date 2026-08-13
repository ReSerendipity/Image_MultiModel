"""
tests/test_content_filter.py — CLIP 安全内容检测器测试

对应全功能实施指南任务 1 验收标准：
- 拦截所有违规内容（召回率≥95%）
- 误杀率 < 5%
- 检查延迟 < 100ms（check_prompt 关键词过滤）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from integrated_app.security.content_filter import (
    ContentSafetyFilter,
    SafetyResult,
    filter_image_generation,
    get_content_filter,
)


class TestPromptSafetyCheck:
    """提示词安全检查（关键词匹配，无需 CLIP 模型）"""

    @pytest.fixture
    def cf(self):
        return ContentSafetyFilter()

    @pytest.mark.smoke
    def test_safe_prompt_passes(self, cf):
        """正常提示词应通过"""
        result = cf.check_prompt("a beautiful sunset over the ocean")
        assert result.is_safe is True
        assert result.violation_type is None

    def test_empty_prompt_passes(self, cf):
        """空提示词应通过"""
        result = cf.check_prompt("")
        assert result.is_safe is True

    def test_naked_keyword_blocked(self, cf):
        """'naked' 关键词应被拦截"""
        result = cf.check_prompt("a naked person on the beach")
        assert result.is_safe is False
        assert "naked" in result.violation_type

    def test_nude_keyword_blocked(self, cf):
        """'nude' 关键词应被拦截"""
        result = cf.check_prompt("a nude painting")
        assert result.is_safe is False
        assert "nude" in result.violation_type

    def test_violent_keyword_blocked(self, cf):
        """'violent' 关键词应被拦截"""
        result = cf.check_prompt("a violent scene with blood")
        assert result.is_safe is False
        assert "violent" in result.violation_type

    def test_gore_keyword_blocked(self, cf):
        """'gore' 关键词应被拦截"""
        result = cf.check_prompt("gore and horror movie scene")
        assert result.is_safe is False

    def test_suicide_keyword_blocked(self, cf):
        """'suicide' 关键词应被拦截"""
        result = cf.check_prompt("suicide and self-harm imagery")
        assert result.is_safe is False

    def test_weapon_keyword_blocked(self, cf):
        """'weapon' 关键词应被拦截"""
        result = cf.check_prompt("holding a weapon in hand")
        assert result.is_safe is False

    def test_drug_keyword_blocked(self, cf):
        """'drug' 关键词应被拦截"""
        result = cf.check_prompt("drug abuse scene")
        assert result.is_safe is False

    def test_case_insensitive(self, cf):
        """关键词匹配应不区分大小写"""
        result = cf.check_prompt("A NAKED person")
        assert result.is_safe is False

    def test_partial_match(self, cf):
        """关键词作为子串也应被匹配"""
        result = cf.check_prompt("some pornographic content here")
        assert result.is_safe is False

    def test_confidence_value(self, cf):
        """拦截时 confidence 应为正数"""
        result = cf.check_prompt("naked")
        assert result.is_safe is False
        assert 0 < result.confidence <= 1.0

    def test_details_contain_keyword(self, cf):
        """拦截时 details 应包含匹配的关键词"""
        result = cf.check_prompt("naked person")
        assert result.is_safe is False
        assert "keyword" in result.details
        assert result.details["keyword"] == "naked"


class TestFilterImageGeneration:
    """filter_image_generation 集成函数测试"""

    def test_safe_prompt_returns_true(self):
        """安全提示词应返回 (True, 'OK')"""
        is_safe, reason = filter_image_generation("a beautiful landscape")
        assert is_safe is True
        assert reason == "OK"

    def test_unsafe_prompt_returns_false(self):
        """违规提示词应返回 (False, reason)"""
        is_safe, reason = filter_image_generation("a naked person")
        assert is_safe is False
        assert "prompt_blocked" in reason

    def test_no_image_path_skips_image_check(self):
        """不传 image_path 时应跳过图片检查"""
        is_safe, reason = filter_image_generation("safe prompt", image_path=None)
        assert is_safe is True

    def test_safe_prompt_with_nonexistent_image(self, tmp_path):
        """安全提示词 + 不存在的图片路径 → check_image 保守拒绝"""
        # 注意：filter_image_generation 会尝试 check_image，
        # CLIP 未安装时降级放行
        is_safe, reason = filter_image_generation(
            "safe prompt",
            image_path=str(tmp_path / "nonexistent.png"),
        )
        # CLIP 未安装时降级为放行
        assert is_safe is True


class TestContentSafetyFilterSingleton:
    """全局单例测试"""

    def test_get_content_filter_returns_same_instance(self):
        """get_content_filter 应返回同一实例"""
        cf1 = get_content_filter()
        cf2 = get_content_filter()
        assert cf1 is cf2

    def test_safety_result_dataclass(self):
        """SafetyResult 数据类字段正确"""
        result = SafetyResult(is_safe=True)
        assert result.is_safe is True
        assert result.violation_type is None
        assert result.confidence == 1.0
        assert result.details == {}

    def test_safety_result_with_violation(self):
        """SafetyResult 违规结果"""
        result = SafetyResult(
            is_safe=False,
            violation_type="test_violation",
            confidence=0.9,
            details={"key": "value"},
        )
        assert result.is_safe is False
        assert result.violation_type == "test_violation"
        assert result.confidence == 0.9
        assert result.details == {"key": "value"}


class TestCheckImageDegraded:
    """图片检查降级测试（CLIP 未安装场景）"""

    def test_check_image_degraded_when_clip_not_available(self, tmp_path):
        """CLIP 未安装时 check_image 应降级放行"""
        cf = ContentSafetyFilter()
        # 创建一个临时图片文件
        img_path = tmp_path / "test.png"
        try:
            from PIL import Image
            img = Image.new("RGB", (64, 64), color="red")
            img.save(str(img_path))
        except ImportError:
            pytest.skip("Pillow not available")

        result = cf.check_image(str(img_path))
        # CLIP 未安装时降级，is_safe=True
        assert result.is_safe is True
        assert result.details.get("degraded") is True
