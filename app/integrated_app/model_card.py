"""
model_card.py — 权重级 Model Card / 元数据注册表（MLOps P2·治理）

对应审计反模式 #3（每个 checkpoint 缺 model card 文档）：
- ``ModelCard`` 聚合引擎的权重治理元数据（SHA256 / 版本 / 训练溯源 / 兼容矩阵）
- ``build_model_card`` / ``build_registry`` 由 ``EngineConfig`` 生成 model card
- ``is_complete`` 用于校验治理元数据是否齐备（CI / 启动自检可据此告警）

字段来源：``config_models.EngineConfig`` 的 MLOps P2 扩展字段。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .config_models import EngineConfig

logger = logging.getLogger(__name__)


@dataclass
class ModelCard:
    """权重级 Model Card（治理元数据聚合）。"""

    name: str
    display_name: str = ""
    backend: str = ""
    weight_sha256: str = ""
    weight_version: str = ""
    training_data_source: str = ""
    license: str = ""
    compatibility_matrix: dict[str, list[str]] = field(default_factory=dict)
    vram_gb: float = 0.0

    # 治理所需的最小字段集合
    _REQUIRED = ("weight_sha256", "weight_version", "training_data_source")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "backend": self.backend,
            "weight_sha256": self.weight_sha256,
            "weight_version": self.weight_version,
            "training_data_source": self.training_data_source,
            "license": self.license,
            "compatibility_matrix": self.compatibility_matrix,
            "vram_gb": self.vram_gb,
        }

    def is_complete(self) -> bool:
        """治理元数据是否齐备（SHA256 / 版本 / 训练溯源均非空）。"""
        return all(getattr(self, f) for f in self._REQUIRED)

    def missing_fields(self) -> list[str]:
        return [f for f in self._REQUIRED if not getattr(self, f)]


def build_model_card(engine_cfg: EngineConfig) -> ModelCard:
    """由 ``EngineConfig`` 生成权重级 Model Card。"""
    return ModelCard(
        name=engine_cfg.name,
        display_name=engine_cfg.display_name or engine_cfg.name,
        backend=engine_cfg.backend,
        weight_sha256=engine_cfg.weight_sha256,
        weight_version=engine_cfg.weight_version,
        training_data_source=engine_cfg.training_data_source,
        license=engine_cfg.license,
        compatibility_matrix=engine_cfg.compatibility_matrix,
        vram_gb=engine_cfg.vram_gb,
    )


def build_registry(models_cfg: Any) -> dict[str, ModelCard]:
    """由 ``ModelsConfig`` 生成全部引擎的 Model Card 注册表。

    Args:
        models_cfg: 含 ``engines: dict[str, EngineConfig]`` 的配置对象

    Returns:
        ``{engine_name: ModelCard}``
    """
    registry: dict[str, ModelCard] = {}
    engines = getattr(models_cfg, "engines", {}) or {}
    for name, ecfg in engines.items():
        try:
            registry[name] = build_model_card(ecfg)
        except Exception as e:  # noqa: BLE001
            logger.warning("生成 Model Card 失败 (%s): %s", name, e)
    return registry


def audit_registry(registry: dict[str, ModelCard]) -> dict[str, Any]:
    """审计注册表治理完备度，返回不完整项。

    Returns:
        ``{"total", "complete", "incomplete", "details": {name: [missing_fields]}}``
    """
    total = len(registry)
    complete = sum(1 for c in registry.values() if c.is_complete())
    details = {name: c.missing_fields() for name, c in registry.items() if not c.is_complete()}
    return {
        "total": total,
        "complete": complete,
        "incomplete": total - complete,
        "details": details,
    }


__all__ = [
    "ModelCard",
    "build_model_card",
    "build_registry",
    "audit_registry",
]
