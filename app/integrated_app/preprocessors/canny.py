"""
preprocessors/canny.py — Canny 边缘检测预处理器

对应全功能实施指南任务 3 Step 1: Canny 边缘检测

使用 OpenCV 的 Canny 算法，支持自适应阈值。
依赖：opencv-python-headless（已在 requirements.txt 中）
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class CannyPreprocessor:
    """Canny 边缘检测预处理器。

    使用自适应百分位阈值，自动适应不同亮度范围的图片。

    Attributes:
        low_threshold: 低阈值百分位（0.0~1.0），默认 0.1。
        high_threshold: 高阈值百分位（0.0~1.0），默认 0.2。
    """

    def __init__(
        self,
        low_threshold: float = 0.1,
        high_threshold: float = 0.2,
    ) -> None:
        """初始化 Canny 预处理器。

        Args:
            low_threshold: 低阈值百分位（0.0~1.0）。
            high_threshold: 高阈值百分位（0.0~1.0）。
        """
        self._low: float = low_threshold
        self._high: float = high_threshold

    @property
    def name(self) -> str:
        """预处理器名称"""
        return "canny"

    def is_available(self) -> bool:
        """检查 OpenCV 是否可用。

        Returns:
            True 如果 cv2 可导入。
        """
        try:
            import cv2  # noqa: F401
            return True
        except ImportError:
            return False

    def process(self, image: np.ndarray) -> np.ndarray:
        """执行 Canny 边缘检测。

        Args:
            image: 输入图片 (H, W, 3) RGB uint8。

        Returns:
            边缘图 (H, W) uint8，边缘为 255，背景为 0。

        Raises:
            ImportError: OpenCV 未安装。
            ValueError: 输入图片格式不正确。
        """
        import cv2

        if image is None or image.size == 0:
            raise ValueError("Input image is empty or None")

        if len(image.shape) == 3:
            # RGB → 灰度
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        elif len(image.shape) == 2:
            gray = image
        else:
            raise ValueError(f"Unexpected image shape: {image.shape}")

        # 自适应阈值（百分位）
        low_val = float(np.percentile(gray, self._low * 100))
        high_val = float(np.percentile(gray, self._high * 100))

        # 确保阈值在有效范围
        low_val = max(0, min(255, low_val))
        high_val = max(low_val + 1, min(255, high_val))

        edges = cv2.Canny(gray, int(low_val), int(high_val))
        return edges


# ── 工厂注册 ────────────────────────────────────────────────────
def _create_canny() -> CannyPreprocessor:
    return CannyPreprocessor()
