"""
test_i18n_coverage.py — 5 语言键集合一致性校验

对应 AUDIT_REPORT_2.0 Y1: 5 文件键集合一致、无空值
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIR = PROJECT_ROOT / "bin" / "integrated_app" / "locales"

EXPECTED_LOCALES = ["zh", "en", "ja", "ko", "zh-tw"]


@pytest.fixture
def locale_data():
    """加载所有语言文件"""
    data = {}
    for loc in EXPECTED_LOCALES:
        p = LOCALE_DIR / f"{loc}.json"
        assert p.exists(), f"Locale file missing: {p}"
        with open(p, encoding="utf-8") as f:
            data[loc] = json.load(f)
    return data


class TestI18nCoverage:
    """5 语言键集合一致性 + 无空值"""

    def test_all_5_locales_exist(self, locale_data):
        """5 个语言文件都存在"""
        assert len(locale_data) == 5
        for loc in EXPECTED_LOCALES:
            assert loc in locale_data, f"Locale '{loc}' not found"

    def test_key_sets_identical(self, locale_data):
        """5 个语言的键集合 100% 一致"""
        zh_keys = set(locale_data["zh"].keys())
        for loc in EXPECTED_LOCALES:
            loc_keys = set(locale_data[loc].keys())
            assert loc_keys == zh_keys, (
                f"Locale '{loc}' key set mismatch with 'zh': "
                f"missing={zh_keys - loc_keys}, extra={loc_keys - zh_keys}"
            )

    def test_no_empty_values(self, locale_data):
        """所有值非空"""
        for loc in EXPECTED_LOCALES:
            for key, value in locale_data[loc].items():
                assert value, f"Empty value in '{loc}' for key '{key}'"
                assert isinstance(value, str), f"Non-string value in '{loc}' for key '{key}'"

    def test_zh_tw_is_traditional(self, locale_data):
        """zh-tw 应为繁体中文（至少包含繁体特征字）"""
        tw_text = locale_data["zh-tw"]["nav_generate"]
        assert tw_text == "生圖", f"zh-tw nav_generate should be '生圖', got '{tw_text}'"

        tw_settings = locale_data["zh-tw"]["settings"]
        assert tw_settings == "設定", f"zh-tw settings should be '設定', got '{tw_settings}'"

    def test_key_count_minimum(self, locale_data):
        """键数量至少 40 个"""
        zh_count = len(locale_data["zh"])
        assert zh_count >= 40, f"Only {zh_count} keys, expected >=40"
