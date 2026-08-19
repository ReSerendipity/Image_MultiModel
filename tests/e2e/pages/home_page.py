"""
tests/e2e/pages/home_page.py — 首页 Page Object

对应 N2: POM 设计模式
封装首页元素操作：主题切换、引擎选择、语言切换

P0-1 修复：移除已废弃的 #freeVramBtn（项目脱离 ComfyUI），改为 #engineSelect
"""

from __future__ import annotations

from .base_page import BasePage


class HomePage(BasePage):
    """首页 Page Object"""

    # ── 选择器常量 ────────────────────────────────
    TOPBAR = ".topbar"
    THEME_TOGGLE = "#themeToggle"
    LANG_SELECT = "#langSelect"
    ENGINE_ICON = "#engIcon"
    ENGINE_MENU = "#engMenu"
    ENGINE_SELECT = "#engineSelect"
    GEN_PROGRESS = "#genProgress"
    PROG_FILL = "#progFill"
    PHASE_TEXT = "#phaseText"
    POS_PROMPT = "#posPrompt"

    def toggle_theme(self) -> None:
        """切换主题"""
        self.page.click(self.THEME_TOGGLE)
        self.page.wait_for_selector("html[data-theme]", state="attached", timeout=3000)

    def get_theme(self) -> str:
        """获取当前主题"""
        return self.html_theme

    def switch_language(self, lang: str) -> None:
        """切换语言"""
        self.page.evaluate(f"""
            var sel = document.getElementById('langSelect');
            sel.value = '{lang}';
            sel.dispatchEvent(new Event('change'));
        """)
        self.page.wait_for_selector(f"html[data-lang='{lang}']", state="attached", timeout=3000)

    def get_language(self) -> str:
        """获取当前语言"""
        return self.html_lang

    def open_engine_menu(self) -> None:
        """打开引擎下拉菜单"""
        self.page.click(self.ENGINE_ICON)
        self.page.wait_for_selector(f"{self.ENGINE_MENU}.show", timeout=5000)

    def get_engine_count(self) -> int:
        """获取引擎数量"""
        items = self.page.query_selector_all(f"{self.ENGINE_MENU} .ip-item")
        return len(items)

    def select_first_engine(self) -> None:
        """选择第一个引擎"""
        self.open_engine_menu()
        first_item = self.page.query_selector(f"{self.ENGINE_MENU} .ip-item")
        if first_item:
            first_item.click()
            self.page.wait_for_selector(f"{self.ENGINE_SELECT}[value]:not([value=''])", timeout=5000)

    def has_progress_bar(self) -> bool:
        """进度条是否存在"""
        return self.page.query_selector(self.GEN_PROGRESS) is not None

    def has_engine_select(self) -> bool:
        """引擎选择器是否存在（替代已移除的 #freeVramBtn）"""
        return self.page.query_selector(self.ENGINE_SELECT) is not None
