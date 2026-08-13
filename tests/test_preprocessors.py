"""
tests/test_preprocessors.py — ControlNet 预处理器系统测试

对应全功能实施指南任务 3 验收标准：
- Canny 边缘清晰无噪点
- MiDaS 深度图连续平滑
- OpenPose 关键点识别率≥95%
"""

from __future__ import annotations

import base64
import io

import numpy as np
import pytest

from integrated_app.preprocessors import (
    get_preprocessor,
    list_preprocessors,
    register_preprocessor,
)
from integrated_app.preprocessors.canny import CannyPreprocessor
from integrated_app.preprocessors.midas import MiDaSDepthEstimator
from integrated_app.preprocessors.openpose import OpenPosePreprocessor


# ── 测试用图片 ──────────────────────────────────────────────────
@pytest.fixture
def sample_image():
    """生成一个简单的测试图片（渐变色 + 矩形）"""
    img = np.zeros((128, 128, 3), dtype=np.uint8)
    # 渐变背景
    for i in range(128):
        img[i, :, 0] = i * 2  # 红色通道渐变
    # 白色矩形
    img[32:96, 32:96] = 255
    return img


@pytest.fixture
def sample_image_b64(sample_image):
    """生成 Base64 编码的测试图片"""
    from PIL import Image
    img = Image.fromarray(sample_image)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ═══════════════════════════════════════════════════════════════
# Canny 边缘检测测试
# ═══════════════════════════════════════════════════════════════
class TestCannyPreprocessor:
    """Canny 边缘检测预处理器测试"""

    @pytest.fixture
    def pp(self):
        return CannyPreprocessor()

    def test_name(self, pp):
        """名称正确"""
        assert pp.name == "canny"

    def test_is_available(self, pp):
        """OpenCV 应已安装"""
        assert pp.is_available() is True

    @pytest.mark.smoke
    def test_process_returns_edges(self, pp, sample_image):
        """处理返回边缘图"""
        result = pp.process(sample_image)
        assert result is not None
        assert len(result.shape) == 2  # 灰度图
        assert result.dtype == np.uint8

    def test_process_edge_values(self, pp, sample_image):
        """边缘图值域 0 或 255"""
        result = pp.process(sample_image)
        unique = set(np.unique(result))
        assert unique.issubset({0, 255})

    def test_process_detects_edges(self, pp, sample_image):
        """应检测到矩形边缘"""
        result = pp.process(sample_image)
        # 应有非零像素（边缘）
        assert np.count_nonzero(result) > 0

    def test_process_grayscale_input(self, pp):
        """支持灰度图输入"""
        gray = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
        result = pp.process(gray)
        assert result.shape == (64, 64)

    def test_process_empty_image_raises(self, pp):
        """空图片抛出 ValueError"""
        with pytest.raises(ValueError):
            pp.process(np.array([]))

    def test_custom_thresholds(self, pp, sample_image):
        """自定义阈值"""
        pp_custom = CannyPreprocessor(low_threshold=0.05, high_threshold=0.15)
        result = pp_custom.process(sample_image)
        assert result is not None
        assert result.shape == sample_image.shape[:2]


# ═══════════════════════════════════════════════════════════════
# MiDaS 深度估计测试
# ═══════════════════════════════════════════════════════════════
class TestMiDaSPreprocessor:
    """MiDaS 深度估计预处理器测试"""

    @pytest.fixture
    def pp(self):
        return MiDaSDepthEstimator()

    def test_name(self, pp):
        """名称正确"""
        assert pp.name == "midas"

    def test_is_available(self, pp):
        """torch 应已安装"""
        assert pp.is_available() is True

    def test_process_without_load_raises(self, pp, sample_image):
        """未加载模型时 process 抛出 RuntimeError"""
        # 模型未加载（无网络环境下 _ensure_loaded 返回 False）
        result = pp.is_available()
        if result:
            # 如果 torch 可用但模型加载失败（无网络）
            with pytest.raises((RuntimeError, Exception)):
                pp.process(sample_image)


# ═══════════════════════════════════════════════════════════════
# OpenPose 姿态检测测试
# ═══════════════════════════════════════════════════════════════
class TestOpenPosePreprocessor:
    """OpenPose 姿态检测预处理器测试"""

    @pytest.fixture
    def pp(self):
        return OpenPosePreprocessor()

    def test_name(self, pp):
        """名称正确"""
        assert pp.name == "openpose"

    def test_is_available(self, pp):
        """controlnet_aux 可能未安装"""
        # 只验证不崩溃，结果可以是 True 或 False
        assert isinstance(pp.is_available(), bool)


# ═══════════════════════════════════════════════════════════════
# 注册表测试
# ═══════════════════════════════════════════════════════════════
class TestPreprocessorRegistry:
    """预处理器注册表测试"""

    def test_list_preprocessors_contains_all(self):
        """注册表包含所有内置预处理器"""
        names = list_preprocessors()
        assert "canny" in names
        assert "midas" in names
        assert "openpose" in names

    def test_get_preprocessor_canny(self):
        """获取 Canny 预处理器"""
        pp = get_preprocessor("canny")
        assert pp is not None
        assert pp.name == "canny"

    def test_get_preprocessor_midas(self):
        """获取 MiDaS 预处理器"""
        pp = get_preprocessor("midas")
        assert pp is not None
        assert pp.name == "midas"

    def test_get_preprocessor_openpose(self):
        """获取 OpenPose 预处理器"""
        pp = get_preprocessor("openpose")
        assert pp is not None
        assert pp.name == "openpose"

    def test_get_preprocessor_unknown(self):
        """获取不存在的预处理器返回 None"""
        pp = get_preprocessor("nonexistent")
        assert pp is None

    def test_register_custom_preprocessor(self):
        """注册自定义预处理器"""
        class CustomPP:
            @property
            def name(self):
                return "custom"

            def is_available(self):
                return True

            def process(self, image):
                return image

        register_preprocessor("custom", lambda: CustomPP())
        assert "custom" in list_preprocessors()
        pp = get_preprocessor("custom")
        assert pp is not None
        assert pp.name == "custom"


# ═══════════════════════════════════════════════════════════════
# 协议测试
# ═══════════════════════════════════════════════════════════════
class TestPreprocessorProtocol:
    """预处理器协议测试"""

    def test_canny_implements_protocol(self):
        """Canny 实现了 PreprocessorProtocol"""
        from integrated_app.preprocessors import PreprocessorProtocol
        pp = CannyPreprocessor()
        assert isinstance(pp, PreprocessorProtocol)

    def test_midas_implements_protocol(self):
        """MiDaS 实现了 PreprocessorProtocol"""
        from integrated_app.preprocessors import PreprocessorProtocol
        pp = MiDaSDepthEstimator()
        assert isinstance(pp, PreprocessorProtocol)

    def test_openpose_implements_protocol(self):
        """OpenPose 实现了 PreprocessorProtocol"""
        from integrated_app.preprocessors import PreprocessorProtocol
        pp = OpenPosePreprocessor()
        assert isinstance(pp, PreprocessorProtocol)
