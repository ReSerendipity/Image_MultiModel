"""
tests/test_i18n_backend.py — 后端错误文案 5 语言 100% 非空校验

对应 REMAINING_TASKS_REPORT §3.5: i18n 后端错误文案 5 语
"""

from __future__ import annotations

from integrated_app.native.engine import PHASE_KEY_MAP
from integrated_app.i18n import ERROR_MESSAGES, get_error_message

EXPECTED_LOCALES = ["zh", "en", "ja", "ko", "zh-tw"]


class TestI18nBackendCoverage:
    """后端错误文案 5 语言 100% 非空"""

    def test_all_5_locales_exist(self):
        """5 个语言都在 ERROR_MESSAGES 中"""
        for loc in EXPECTED_LOCALES:
            assert loc in ERROR_MESSAGES, f"Locale '{loc}' missing from ERROR_MESSAGES"

    def test_key_sets_identical(self):
        """5 个语言的键集合 100% 一致"""
        zh_keys = set(ERROR_MESSAGES["zh"].keys())
        assert len(zh_keys) >= 20, f"Only {len(zh_keys)} keys, expected >=20"
        for loc in EXPECTED_LOCALES:
            loc_keys = set(ERROR_MESSAGES[loc].keys())
            assert loc_keys == zh_keys, (
                f"Locale '{loc}' key set mismatch with 'zh': "
                f"missing={zh_keys - loc_keys}, extra={loc_keys - zh_keys}"
            )

    def test_no_empty_values(self):
        """所有值非空且为字符串"""
        for loc in EXPECTED_LOCALES:
            for key, value in ERROR_MESSAGES[loc].items():
                assert value, f"Empty value in '{loc}' for key '{key}'"
                assert isinstance(value, str), f"Non-string value in '{loc}' for key '{key}'"

    def test_get_error_message_with_format(self):
        """get_error_message 正确格式化模板变量"""
        msg = get_error_message("engine_not_found", locale="zh", name="test_engine")
        assert "test_engine" in msg
        assert "引擎不存在" in msg

    def test_get_error_message_fallback_to_zh(self):
        """未知 locale 回退到 zh"""
        msg = get_error_message("engine_not_found", locale="fr", name="test")
        assert "引擎不存在" in msg

    def test_get_error_message_unknown_key(self):
        """未知 key 返回 key 本身"""
        msg = get_error_message("nonexistent_key", locale="zh")
        assert msg == "nonexistent_key"

    def test_all_messages_have_placeholders_filled(self):
        """带占位符的模板在提供参数时正确填充"""
        template_keys = [
            ("engine_not_found", {"name": "X"}),
            ("task_not_found", {"task_id": "T1"}),
            ("vram_insufficient", {"need": 10.0, "avail": 8.0}),
            ("invalid_param", {"param": "seed", "value": "abc"}),
        ]
        for key, kwargs in template_keys:
            for loc in EXPECTED_LOCALES:
                msg = get_error_message(key, locale=loc, **kwargs)
                # 确保模板中没有被替换的 {xxx} 残留
                assert "{" not in msg or "}" not in msg, (
                    f"Unfilled placeholder in '{loc}' for key '{key}': {msg}"
                )

    def test_phase_keys_in_all_locales(self):
        """PHASE_KEY_MAP 的全部键在 5 语 locale JSON 中非空"""
        import json as _json
        from pathlib import Path as _Path

        locale_dir = _Path(__file__).resolve().parent.parent / "app" / "integrated_app" / "locales"
        # 收集所有 phase 键
        phase_keys = set(PHASE_KEY_MAP.values())
        phase_keys.update({"phase_sampling", "phase_executing"})  # 动态生成的键
        for loc in EXPECTED_LOCALES:
            loc_file = locale_dir / f"{loc}.json"
            assert loc_file.exists(), f"Locale file missing: {loc_file}"
            data = _json.loads(loc_file.read_text(encoding="utf-8"))
            for pk in phase_keys:
                assert pk in data, f"Phase key '{pk}' missing in locale '{loc}'"
                assert data[pk], f"Phase key '{pk}' empty in locale '{loc}'"
