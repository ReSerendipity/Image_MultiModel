"""
engine_interface.py — ImageEngine Protocol + InMemoryEngineRegistry

对应 MASTER_PLAN §4 / 附录 A1: engine_interface.py
对应 PRD §4.1: ImageEngine Protocol 4 方法 + Registry
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ── 进度回调类型 ──────────────────────────────────────────────
ProgressCallback = Callable[[int, str, Optional[Dict[str, Any]]], None]
# 参数: (progress_pct, phase_text, extra_data)


# ── generation_config 类型 ────────────────────────────────────
@dataclass
class GenerationConfig:
    """
    generation_config 22 项（PRD 2.4.2/2.5.2 / MASTER_PLAN §5.3）

    8 基础 + LoRA 6 层 × (name, strength) + SeedVR2 + Eses + VRAM + 输出 + 引擎版本
    """
    # ── 8 基础参数 ──
    positive_prompt: str = ""
    negative_prompt: str = ""
    cfg: float = 1.0
    steps: int = 8
    width: int = 1024
    height: int = 1024
    seed: int = -1
    batch_size: int = 1

    # ── LoRA 6 层（id=16~21） ──
    lora_1_name: str = ""
    lora_1_strength: float = 1.0
    lora_2_name: str = ""
    lora_2_strength: float = 0.7
    lora_3_name: str = ""
    lora_3_strength: float = 0.5
    lora_4_name: str = ""
    lora_4_strength: float = 0.4
    lora_5_name: str = ""
    lora_5_strength: float = 0.3
    lora_6_name: str = ""
    lora_6_strength: float = 0.2

    # ── SeedVR2 超分（id=61/62/63） ──
    seedvr2_enable: bool = True
    seedvr2_resolution: int = 2048
    seedvr2_seed: int = -1
    seedvr2_color_correction: str = "lab"

    # ── Eses 双图对比（id=59） ──
    eses_enable: bool = True
    eses_compare_axis: str = "horizontal"

    # ── ReservedVRAM（id=60） ──
    vram_enable: bool = True
    vram_reserved_gb: float = 0.6
    vram_mode: str = "auto"
    vram_seed: int = -1

    # ── 输出 ──
    output_format: str = "png"
    output_prefix: str = ""

    # ── 引擎版本 / 工作流 SHA256 ──
    engine_name: str = ""
    workflow_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 可存储的字典"""
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GenerationConfig":
        """从字典恢复"""
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        return cls(**{k: v for k, v in d.items() if k in known})


# ── ImageEngine Protocol ─────────────────────────────────────
@runtime_checkable
class ImageEngine(Protocol):
    """
    引擎协议（PRD §4.1）：
    - is_ready / load / unload / infer_txt2img / cancel
    """

    @property
    def name(self) -> str:
        """引擎唯一标识"""
        ...

    @property
    def display_name(self) -> str:
        """引擎显示名称"""
        ...

    def is_ready(self) -> bool:
        """引擎是否已加载就绪"""
        ...

    async def load(self, on_progress: Optional[ProgressCallback] = None) -> None:
        """
        加载引擎模型到 GPU。

        Args:
            on_progress: 加载进度回调 (pct, phase, extra)
        """
        ...

    async def unload(self) -> None:
        """卸载引擎模型，释放 GPU 显存"""
        ...

    async def infer_txt2img(
        self,
        config: GenerationConfig,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[str]:
        """
        执行文生图推理。

        Args:
            config: 完整的 generation_config
            on_progress: 推理进度回调

        Returns:
            输出图像路径列表（original / upscaled / compare）
        """
        ...

    async def cancel(self) -> None:
        """取消当前推理（发送 /interrupt + 清理队列）"""
        ...


# ── InMemoryEngineRegistry ───────────────────────────────────
class InMemoryEngineRegistry:
    """
    引擎注册表（附录 A1）
    - register(name, engine_class, config)
    - get(name) → engine instance
    - list_engines() → [name, display_name, ready]
    """

    def __init__(self) -> None:
        self._factories: Dict[str, Callable[..., ImageEngine]] = {}
        self._instances: Dict[str, ImageEngine] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._active: Optional[str] = None

    def register(
        self,
        name: str,
        factory: Callable[..., ImageEngine],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """注册引擎工厂"""
        self._factories[name] = factory
        self._configs[name] = config or {}
        logger.info(f"Engine registered: {name}")

    def get(self, name: str) -> ImageEngine:
        """获取引擎实例（懒加载）"""
        if name not in self._factories:
            raise KeyError(f"Engine not registered: {name}")
        if name not in self._instances:
            factory = self._factories[name]
            self._instances[name] = factory(**self._configs.get(name, {}))
        return self._instances[name]

    def list_engines(self) -> List[Dict[str, Any]]:
        """列出所有已注册引擎"""
        result = []
        for name, factory in self._factories.items():
            eng = self._instances.get(name)
            result.append({
                "name": name,
                "display_name": getattr(eng, "display_name", name) if eng else name,
                "ready": eng.is_ready() if eng else False,
                "active": name == self._active,
            })
        return result

    def set_active(self, name: str) -> None:
        """设置当前活动引擎"""
        if name not in self._factories:
            raise KeyError(f"Engine not registered: {name}")
        self._active = name

    @property
    def active_engine_name(self) -> Optional[str]:
        return self._active

    def get_active(self) -> Optional[ImageEngine]:
        if self._active:
            return self.get(self._active)
        return None

    def clear(self) -> None:
        """清除所有引擎实例"""
        for eng in self._instances.values():
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(eng.unload())
                else:
                    loop.run_until_complete(eng.unload())
            except Exception as e:
                logger.warning(f"Error unloading engine: {e}")
        self._instances.clear()
        self._active = None


# ── 全局注册表单例 ────────────────────────────────────────────
_global_registry: Optional[InMemoryEngineRegistry] = None


def get_registry() -> InMemoryEngineRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = InMemoryEngineRegistry()
    return _global_registry
