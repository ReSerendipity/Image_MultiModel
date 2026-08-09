"""
tests/test_i18n.py — i18n get_error_message() 单元测试

对应 TEST_AUDIT_REPORT P1-8: get_error_message() 未测试
"""

from __future__ import annotations

import pytest

from integrated_app.i18n import get_error_message, ERROR_MESSAGES


class TestGetErrorMessage:
    """get_error_message() 函数测试"""

    def test_default_locale_zh(self):
        """默认 locale=zh"""
        msg = get_error_message("engine_not_found", name="flux")
        assert "flux" in msg
        assert "引擎不存在" in msg

    def test_locale_en(self):
        """locale=en"""
        msg = get_error_message("engine_not_found", locale="en", name="flux")
        assert "flux" in msg
        assert "Engine not found" in msg

    def test_locale_ja(self):
        """locale=ja"""
        msg = get_error_message("engine_not_found", locale="ja", name="flux")
        assert "flux" in msg
        assert "エンジン" in msg

    def test_locale_ko(self):
        """locale=ko"""
        msg = get_error_message("engine_not_found", locale="ko", name="flux")
        assert "flux" in msg
        assert "엔진" in msg

    def test_locale_zh_tw(self):
        """locale=zh-tw → 繁体中文"""
        msg = get_error_message("engine_not_found", locale="zh-tw", name="flux")
        assert "flux" in msg
        assert "引擎不存在" in msg

    def test_unknown_locale_falls_back_to_zh(self):
        """未知 locale → fallback 到 zh"""
        msg = get_error_message("engine_not_found", locale="fr", name="flux")
        assert "引擎不存在" in msg

    def test_unknown_key_returns_key(self):
        """未知 key → 返回 key 本身"""
        msg = get_error_message("nonexistent_key_xyz")
        assert msg == "nonexistent_key_xyz"

    def test_template_variables(self):
        """模板变量正确填充"""
        msg = get_error_message("vram_insufficient", need=26, avail=14)
        assert "26" in msg
        assert "14" in msg

    def test_missing_template_variable(self):
        """模板变量缺失 → 返回原模板（不报错）"""
        msg = get_error_message("vram_insufficient")
        # 不报错，返回包含 {need} 的原模板
        assert "need" in msg or "顯存" in msg or "显存" in msg

    def test_no_variables_needed(self):
        """无需变量的消息"""
        msg = get_error_message("task_queue_full")
        assert "队列" in msg or "佇列" in msg


class TestErrorMessagesConsistency:
    """ERROR_MESSAGES 字典一致性"""

    def test_all_5_locales_exist(self):
        """5 种语言都有错误消息"""
        expected = {"zh", "en", "ja", "ko", "zh-tw"}
        assert set(ERROR_MESSAGES.keys()) == expected

    def test_key_sets_identical(self):
        """5 种语言的 key 集合一致"""
        zh_keys = set(ERROR_MESSAGES["zh"].keys())
        for locale in ["en", "ja", "ko", "zh-tw"]:
            assert set(ERROR_MESSAGES[locale].keys()) == zh_keys, \
                f"Locale '{locale}' key set mismatch"

    def test_no_empty_values(self):
        """无空值"""
        for locale, messages in ERROR_MESSAGES.items():
            for key, value in messages.items():
                assert value, f"Empty value in '{locale}' for key '{key}'"
