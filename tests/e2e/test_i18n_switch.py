"""
tests/e2e/test_i18n_switch.py — E2E: 5 语言切换无裸键

对应 REMAINING_TASKS_REPORT B5/B7: 5 语切换 + 阶段文案
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestI18nSwitch:
    """5 语言切换 E2E"""

    @pytest.mark.parametrize(
        "lang,expected_text",
        [
            ("zh-CN", "首页"),
            ("zh-TW", "首頁"),
            ("en-US", "Home"),
            ("ja-JP", "ホーム"),
            ("ko-KR", "홈"),
        ],
    )
    def test_language_switch(self, page, base_url, lang, expected_text):
        """切换到每种语言，验证界面文案正确且无裸键"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")

        # 通过 langSelect 切换语言
        page.evaluate(f"""
            var sel = document.getElementById('langSelect');
            sel.value = '{lang}';
            sel.dispatchEvent(new Event('change'));
        """)
        page.wait_for_selector(f"html[data-lang='{lang}']", state="attached")

        # 验证 data-lang 属性
        assert page.get_attribute("html", "data-lang") == lang

        # 验证界面文案不为空且不是裸键。
        # ⚠️ 坑（2026-09-01）：原实现固定取 [data-i18n='sub']，但 index.html 中
        # 并不存在该 key（实际 key 为 btn_* / recent / neg_add / batch_*），
        # 导致 Playwright 等待 30s 后 TimeoutError。改为对页面内所有
        # [data-i18n] 元素做全量扫描，覆盖率更高且不会因单个元素改名而失效。
        items = page.eval_on_selector_all(
            "[data-i18n]",
            """els => els.map(el => ({
                key: el.getAttribute('data-i18n'),
                text: (el.textContent || '').trim()
            }))""",
        )
        assert items, f"No [data-i18n] element found on page (lang={lang})"

        empty = [it["key"] for it in items if not it["text"]]
        assert not empty, f"Empty i18n text for lang={lang}, keys={empty}"

        bare = [it["key"] for it in items if it["text"] == it["key"] or it["text"].startswith("phase_")]
        assert not bare, f"Bare i18n keys for lang={lang}: {bare}"

    def test_phase_keys_no_bare(self, page, base_url):
        """验证 phase_* 键在前端 I18N 字典中存在"""
        page.goto(base_url)
        page.wait_for_selector(".topbar")

        result = page.evaluate("""
            () => {
                var langs = ['zh-CN', 'zh-TW', 'en-US', 'ja-JP', 'ko-KR'];
                var phaseKeys = ['phase_connecting', 'phase_loading_workflow',
                    'phase_engine_ready', 'phase_patching', 'phase_queuing',
                    'phase_sampling', 'phase_executing', 'phase_image_saved',
                    'phase_completed', 'phase_cancelling'];
                var missing = [];
                for (var l of langs) {
                    var d = window.I18N[l];
                    if (!d) { missing.push('No dict for ' + l); continue; }
                    for (var k of phaseKeys) {
                        if (!d[k]) missing.push(l + '.' + k);
                    }
                }
                return missing;
            }
        """)
        assert result == [], f"Missing phase keys: {result}"
