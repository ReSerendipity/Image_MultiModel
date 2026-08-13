"""
preprocessors/openpose.py — OpenPose 人体姿态检测预处理器

对应全功能实施指南任务 3 Step 3: OpenPose 姿态检测

使用 controlnet_aux 库的 OpenPoseDetector 进行人体姿态估计。
模型懒加载，首次调用 process() 时才下载/加载。
依赖：controlnet_aux（需额外安装）
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class OpenPosePreprocessor:
    """OpenPose 人体姿态估计预处理器。

    使用 ``controlnet_aux.OpenPoseDetector`` 进行人体关键点检测。
    模型懒加载，首次调用 ``process()`` 时才从 HuggingFace 下载。

    依赖 ``controlnet_aux`` 包，如果未安装则 ``is_available()`` 返回 False。
    """

    def __init__(self) -> None:
        """初始化 OpenPose 预处理器。"""
        self._detector: Any = None
        self._loaded: bool = False
        self._load_error: str | None = None

    @property
    def name(self) -> str:
        """预处理器名称"""
        return "openpose"

    def is_available(self) -> bool:
        """检查 controlnet_aux 是否可用。

        Returns:
            True 如果 controlnet_aux 可导入。
        """
        try:
            from controlnet_aux import OpenPoseDetector  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_loaded(self) -> bool:
        """懒加载 OpenPose 模型。

        Returns:
            True 加载成功，False 失败。
        """
        if self._loaded:
            return True
        if self._load_error is not None:
            return False

        try:
            from controlnet_aux import OpenPoseDetector

            self._detector = OpenPoseDetector.from_pretrained("lllyasviel/Annotators")
            self._loaded = True
            logger.info("OpenPose 模型加载成功")
            return True
        except Exception as e:
            self._load_error = f"OpenPose 模型加载失败: {e}"
            logger.error(self._load_error)
            return False

    def process(self, image: np.ndarray) -> np.ndarray:
        """执行人体姿态检测。

        Args:
            image: 输入图片 (H, W, 3) RGB uint8。

        Returns:
            姿态图 (H, W, 3) RGB uint8，包含人体骨架关键点。

        Raises:
            RuntimeError: 模型加载失败。
            ValueError: 输入图片格式不正确。
        """
        if image is None or image.size == 0:
            raise ValueError("Input image is empty or None")

        if not self._ensure_loaded():
            raise RuntimeError(self._load_error or "OpenPose model not available")

        from PIL import Image

        # numpy → PIL → 处理 → numpy
        pil_image = Image.fromarray(image)
        pose_map = self._detector(pil_image)
        return np.array(pose_map)


# ── 工厂注册 ────────────────────────────────────────────────────
def _create_openpose() -> OpenPosePreprocessor:
    return OpenPosePreprocessor()
