"""
seedvr2_service.py — SeedVR2 超分服务集成

对应 MASTER_PLAN M9: SeedVR2 超分集成（diffusers_engine 自动调用）
参考 SeedVR2-Toolkit 的 SeedVR2Engine 实现（Apache-2.0，独立项目）

架构设计：
- 懒加载模式：首次调用时才加载模型（不影响冷启动时间）
- 单例管理：全局唯一实例，避免重复加载占用显存
- 显存感知：主引擎推理完成后自动卸载 SeedVR2，避免 OOM

用户操作（仅需一次）：
    # 下载模型权重到 portable 目录
    huggingface-cli download ByteDance/SeedVR2 --local-dir pretrained_models/SeedVR2/3b
    # 或使用 ModelScope（国内更快）
    modelscope download --model ByteDance/SeedVR2 --local_dir pretrained_models/SeedVR2/3b
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import torch

logger = logging.getLogger(__name__)

# 尝试导入 SeedVR2-Toolkit（懒导入，不安装时优雅降级）
SEEDVR2_AVAILABLE = False
try:
    # SeedVR2-Toolkit 的引擎类（独立项目，Apache-2.0）
    from bin.integrated_app.engines.seedvr2_engine import SeedVR2Engine, ImageInferenceConfig
    SEEDVR2_AVAILABLE = True
    logger.debug("SeedVR2-Toolkit available")
except ImportError:
    logger.debug("SeedVR2-Toolkit not installed, super-resolution disabled")
    SeedVR2Engine = None  # type: ignore
    ImageInferenceConfig = None  # type: ignore


class SeedVR2Service:
    """线程安全的 SeedVR2 单例管理器。
    
    生命周期：
    1. 应用启动时不加载任何模型（仅注册服务）
    2. 首次调用 ensure_loaded() 时加载 SeedVR2Engine + 模型权重
    3. 推理时临时加载，完成后自动卸载（避免与主引擎争抢显存）
    4. 应用退出时清理所有引用
    """
    
    def __init__(self) -> None:
        self._engine: Any | None = None
        self._loaded = False
        self._model_size = ""
        self._project_root = ""
    
    @property
    def available(self) -> bool:
        """SeedVR2-Toolkit 是否已安装。"""
        return SEEDVR2_AVAILABLE
    
    @property
    def is_loaded(self) -> bool:
        """模型是否已加载到显存。"""
        return self._loaded and self._engine is not None
    
    async def ensure_loaded(
        self,
        model_size: str = "3b",
        precision: str = "fp16",
        project_root: str = "",
    ) -> None:
        """首次使用时加载模型（懒加载，不影响冷启动时间）。
        
        Args:
            model_size: 模型尺寸（"3b" 或 "7b"，默认 3b 显存友好）
            precision: 精度（"fp16" 或 "bf16"，默认 fp16）
            project_root: 项目根目录（用于解析模型路径）
        
        Raises:
            RuntimeError: SeedVR2-Toolkit 未安装或模型文件缺失
        """
        if self._loaded:
            return
        
        if not SEEDVR2_AVAILABLE:
            raise RuntimeError(
                "SeedVR2-Toolkit not installed. "
                "Please run: pip install seedvr2_toolkit "
                "or download from https://github.com/ReSerendipity/SeedVR2-Toolkit"
            )
        
        self._project_root = project_root
        
        # 构建配置（参考 SeedVR2-Toolkit 的配置格式）
        # 模型路径：pretrained_models/SeedVR2/{model_size}/
        if project_root:
            models_root = str(Path(project_root) / "pretrained_models" / "SeedVR2" / model_size)
        else:
            models_root = str(Path("pretrained_models") / "SeedVR2" / model_size)
        
        config = {
            "model": {
                "models_root": models_root,
            },
        }
        
        logger.info(f"Loading SeedVR2 model: {model_size} ({precision}) from {models_root}")
        self._engine = SeedVR2Engine(config=config)
        
        try:
            success = await self._engine.load_model(
                model_size=model_size,
                precision=precision,
            )
            if not success:
                raise RuntimeError(f"SeedVR2 model load failed for {model_size}")
        except Exception as e:
            logger.error(f"SeedVR2 model load failed: {e}")
            self._engine = None
            raise RuntimeError(
                f"Failed to load SeedVR2 {model_size} model. "
                f"Ensure model weights are in: {models_root}"
            ) from e
        
        self._model_size = model_size
        self._loaded = True
        logger.info(f"SeedVR2 {model_size} model loaded successfully")
    
    async def upscale_single(
        self,
        image_path: str,
        target_resolution: int = 2048,
        color_correction: str = "lab",
        seed: int = -1,
    ) -> str:
        """超分单张图片，返回输出路径。
        
        Args:
            image_path: 输入图片路径（必须存在）
            target_resolution: 目标分辨率（长边，默认 2048）
            color_correction: 色彩校正模式（"lab" / "none"）
            seed: 随机种子（-1 = 随机）
        
        Returns:
            输出图片路径
        
        Raises:
            RuntimeError: 模型未加载或推理失败
        """
        if not self._loaded or self._engine is None:
            raise RuntimeError("SeedVR2 model not loaded, call ensure_loaded() first")
        
        input_path = Path(image_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")
        
        # 创建临时输出目录
        output_dir = input_path.parent / f"{input_path.stem}_sr_{target_resolution}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"SeedVR2 upscaling: {input_path.name} → {target_resolution}px "
            f"(color_correction={color_correction}, seed={seed})"
        )
        
        try:
            result = await self._engine.infer_image(
                image_path=str(input_path),
                output_dir=str(output_dir),
                config=ImageInferenceConfig(
                    resolution=target_resolution,
                    seed=seed,
                    color_correction=color_correction,
                ) if ImageInferenceConfig else None,
            )
            logger.info(f"SeedVR2 upscale completed: {result.output_path}")
            return result.output_path
        except Exception as e:
            logger.error(f"SeedVR2 upscale failed: {e}")
            raise RuntimeError(f"SeedVR2 upscale failed: {e}") from e
    
    async def unload(self) -> None:
        """释放 SeedVR2 显存（避免与主引擎争抢）。"""
        if self._engine is not None:
            try:
                await self._engine.unload_model()
            except Exception as e:
                logger.warning(f"Error unloading SeedVR2: {e}")
            self._engine = None
            self._loaded = False
            self._model_size = ""
            
            # 清理 GPU 缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("SeedVR2 model unloaded, CUDA cache cleared")


# ── 全局单例 ──────────────────────────────────────────────────
_seedvr2_service: SeedVR2Service | None = None


def get_seedvr2_service() -> SeedVR2Service:
    """获取 SeedVR2 服务单例。"""
    global _seedvr2_service
    if _seedvr2_service is None:
        _seedvr2_service = SeedVR2Service()
    return _seedvr2_service
