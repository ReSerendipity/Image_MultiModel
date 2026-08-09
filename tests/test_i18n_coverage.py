"""
test_i18n_coverage.py — 5 语言键集合一致性校验

对应 AUDIT_REPORT_2.0 Y1: 5 文件键集合一致、无空值
P1-2 改造：新增 backend_errors namespace 校验
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
        """5 个语言的键集合 100% 一致（含 backend_errors）"""
        zh_keys = set(locale_data["zh"].keys())
        for loc in EXPECTED_LOCALES:
            loc_keys = set(locale_data[loc].keys())
            assert loc_keys == zh_keys, (
                f"Locale '{loc}' key set mismatch with 'zh': "
                f"missing={zh_keys - loc_keys}, extra={loc_keys - zh_keys}"
            )

    def test_no_empty_values(self, locale_data):
        """所有值非空（backend_errors 允许 dict，其他顶层 key 必须为 str）"""
        for loc in EXPECTED_LOCALES:
            for key, value in locale_data[loc].items():
                assert value, f"Empty value in '{loc}' for key '{key}'"
                if key == "backend_errors":
                    assert isinstance(value, dict), f"backend_errors should be dict in '{loc}'"
                else:
                    assert isinstance(value, str), f"Non-string value in '{loc}' for key '{key}'"

    def test_zh_tw_is_traditional(self, locale_data):
        """zh-tw 应为繁体中文（至少包含繁体特征字）"""
        tw_text = locale_data["zh-tw"]["nav_generate"]
        assert tw_text == "生圖", f"zh-tw nav_generate should be '生圖', got '{tw_text}'"

        tw_settings = locale_data["zh-tw"]["settings"]
        assert tw_settings == "設定", f"zh-tw settings should be '設定', got '{tw_settings}'"

    def test_key_count_minimum(self, locale_data):
        """键数量至少 40 个（含 backend_errors）"""
        zh_count = len(locale_data["zh"])
        assert zh_count >= 40, f"Only {zh_count} keys, expected >=40"

    def test_backend_errors_key_sets_identical(self, locale_data):
        """backend_errors 5 语言键集合 100% 一致"""
        zh_be_keys = set(locale_data["zh"].get("backend_errors", {}).keys())
        assert len(zh_be_keys) >= 20, f"Only {len(zh_be_keys)} backend_errors keys, expected >=20"
        for loc in EXPECTED_LOCALES:
            loc_be = locale_data[loc].get("backend_errors", {})
            assert isinstance(loc_be, dict), f"backend_errors not dict in '{loc}'"
            loc_be_keys = set(loc_be.keys())
            assert loc_be_keys == zh_be_keys, (
                f"Locale '{loc}' backend_errors key set mismatch with 'zh': "
                f"missing={zh_be_keys - loc_be_keys}, extra={loc_be_keys - zh_be_keys}"
            )

    def test_backend_errors_no_empty_values(self, locale_data):
        """backend_errors 所有值非空且为字符串"""
        for loc in EXPECTED_LOCALES:
            be = locale_data[loc].get("backend_errors", {})
            for key, value in be.items():
                assert value, f"Empty backend_errors value in '{loc}' for key '{key}'"
                assert isinstance(value, str), f"Non-string backend_errors value in '{loc}' for key '{key}'"
