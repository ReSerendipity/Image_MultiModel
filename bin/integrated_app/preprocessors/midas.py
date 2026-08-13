"""
preprocessors/midas.py — MiDaS 深度估计预处理器

对应全功能实施指南任务 3 Step 2: MiDaS 深度估计

使用 PyTorch + MiDaS 模型进行单目深度估计。
模型懒加载，首次调用 process() 时才下载/加载。
依赖：torch, torchvision（已在 requirements.txt 中）
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class MiDaSDepthEstimator:
    """MiDaS 深度图估计器。

    使用 Intel ISL 的 MiDaS 模型（DPT_Large）进行单目深度估计。
    模型懒加载，首次调用 ``process()`` 时才从 torch.hub 下载。

    Attributes:
        model_type: MiDaS 模型类型，默认 "DPT_Large"。
    """

    def __init__(self, model_type: str = "DPT_Large") -> None:
        """初始化 MiDaS 深度估计器。

        Args:
            model_type: MiDaS 模型类型（DPT_Large / DPT_Hybrid / MiDaS_small）。
        """
        self._model_type: str = model_type
        self._model: Any = None
        self._transform: Any = None
        self._device: str = ""
        self._loaded: bool = False
        self._load_error: str | None = None

    @property
    def name(self) -> str:
        """预处理器名称"""
        return "midas"

    def is_available(self) -> bool:
        """检查 torch 和 torchvision 是否可用。

        Returns:
            True 如果 torch 和 torchvision 可导入。
        """
        try:
            import torch  # noqa: F401
            import torchvision  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_loaded(self) -> bool:
        """懒加载 MiDaS 模型。

        Returns:
            True 加载成功，False 失败。
        """
        if self._loaded:
            return True
        if self._load_error is not None:
            return False

        try:
            import torch
            import torchvision.transforms as T

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = torch.hub.load("intel-isl/MiDaS", self._model_type)
            self._model.to(self._device)
            self._model.eval()

            # 加载适当的变换
            midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
            if self._model_type in ("DPT_Large", "DPT_Hybrid"):
                self._transform = midas_transforms.dpt_transform
            else:
                self._transform = midas_transforms.small_transform

            self._loaded = True
            logger.info(f"MiDaS 模型加载成功: {self._model_type} @ {self._device}")
            return True
        except Exception as e:
            self._load_error = f"MiDaS 模型加载失败: {e}"
            logger.error(self._load_error)
            return False

    def process(self, image: np.ndarray) -> np.ndarray:
        """执行深度估计。

        Args:
            image: 输入图片 (H, W, 3) RGB uint8。

        Returns:
            深度图 (H, W) uint8，值域 0~255。

        Raises:
            RuntimeError: 模型加载失败。
            ValueError: 输入图片格式不正确。
        """
        if image is None or image.size == 0:
            raise ValueError("Input image is empty or None")

        if not self._ensure_loaded():
            raise RuntimeError(self._load_error or "MiDaS model not available")

        import torch

        # 应用变换
        input_batch = self._transform(image).to(self._device)

        with torch.no_grad():
            prediction = self._model(input_batch)

            # 插值到原始尺寸
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=image.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth = prediction.cpu().numpy()

        # 归一化到 0-255
        depth_min = depth.min()
        depth_max = depth.max()
        if depth_max - depth_min > 0:
            depth = ((depth - depth_min) / (depth_max - depth_min) * 255).astype(np.uint8)
        else:
            depth = np.zeros_like(depth, dtype=np.uint8)

        return depth


# ── 工厂注册 ────────────────────────────────────────────────────
def _create_midas() -> MiDaSDepthEstimator:
    return MiDaSDepthEstimator()
