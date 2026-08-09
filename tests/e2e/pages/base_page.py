"""
tests/e2e/pages/base_page.py — Page Object Model 基类

对应 N2: POM 设计模式引入
封装 Playwright page 操作，隔离选择器变更
"""

from __future__ import annotations


class BasePage:
    """所有 Page Object 的基类"""

    def __init__(self, page, base_url: str = "http://127.0.0.1:8288"):
        self.page = page
        self.base_url = base_url

    def goto(self, path: str = "/") -> None:
        """导航到指定路径"""
        self.page.goto(f"{self.base_url}{path}")
        self.page.wait_for_selector(".topbar")

    def click(self, selector: str) -> None:
        """点击元素"""
        self.page.click(selector)

    def fill(self, selector: str, value: str) -> None:
        """填写输入框"""
        self.page.fill(selector, value)

    def get_text(self, selector: str) -> str:
        """获取元素文本"""
        return self.page.text_content(selector)

    def is_visible(self, selector: str) -> bool:
        """元素是否可见"""
        return self.page.is_visible(selector)

    def wait_for(self, selector: str, state: str = "visible") -> None:
        """等待元素"""
        self.page.wait_for_selector(selector, state=state)

    def screenshot(self, name: str) -> None:
        """截图（视觉回归用）"""
        self.page.screenshot(path=f"screenshots/{name}.png")

    @property
    def html_theme(self) -> str:
        """当前主题"""
        return self.page.get_attribute("html", "data-theme") or "light"

    @property
    def html_lang(self) -> str:
        """当前语言"""
        return self.page.get_attribute("html", "data-lang") or "zh-CN"
