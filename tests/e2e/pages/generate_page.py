"""
tests/e2e/pages/generate_page.py — 生成页面 Page Object

对应 N2/N4: POM 设计模式 + 完整生成流程
封装生成表单操作：填写 prompt、选择参数、提交生成
"""

from __future__ import annotations

from .base_page import BasePage


class GeneratePage(BasePage):
    """生成页面 Page Object"""

    # ── 选择器常量 ────────────────────────────────
    PROMPT_INPUT = "#promptInput"
    NEGATIVE_INPUT = "#negInput"
    GEN_BTN = "#genBtn"
    CANCEL_BTN = "#cancelBtn"
    STEPS_INPUT = "#stepsInput"
    CFG_INPUT = "#cfgInput"
    WIDTH_INPUT = "#widthInput"
    HEIGHT_INPUT = "#heightInput"
    SEED_INPUT = "#seedInput"
    BATCH_INPUT = "#batchInput"
    OUTPUT_GRID = "#outputGrid"
    PROGRESS_BAR = "#genProgress"
    PROGRESS_FILL = "#progFill"

    def fill_prompt(self, text: str) -> None:
        """填写正向 prompt"""
        self.page.fill(self.PROMPT_INPUT, text)

    def fill_negative(self, text: str = "") -> None:
        """填写负向 prompt"""
        if self.page.query_selector(self.NEGATIVE_INPUT):
            self.page.fill(self.NEGATIVE_INPUT, text)

    def set_steps(self, steps: int) -> None:
        """设置步数"""
        self.page.fill(self.STEPS_INPUT, str(steps))

    def set_batch_size(self, batch: int) -> None:
        """设置 batch 大小"""
        self.page.fill(self.BATCH_INPUT, str(batch))

    def click_generate(self) -> None:
        """点击生成按钮"""
        self.page.click(self.GEN_BTN)

    def click_cancel(self) -> None:
        """点击取消按钮"""
        self.page.click(self.CANCEL_BTN)

    def is_generating(self) -> bool:
        """是否正在生成"""
        return self.page.is_visible(self.PROGRESS_BAR)

    def get_progress_text(self) -> str:
        """获取进度文本"""
        return self.page.text_content(self.PROGRESS_FILL) or ""

    def wait_for_output(self, timeout: int = 30000) -> None:
        """等待输出出现"""
        self.page.wait_for_selector(f"{self.OUTPUT_GRID} img", timeout=timeout)

    def take_screenshot(self, name: str = "generate") -> None:
        """截图"""
        self.screenshot(name)
