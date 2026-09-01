"""
model_compat.py — LoRA / Checkpoint 兼容性矩阵消费（数据治理 §4.6 / 长期-兼容性矩阵）

把 ``EngineConfig.compatibility_matrix`` 字段从「声明但未消费」变为「运行时可校验」。
矩阵约定（单一约定，避免歧义）：
    compatibility_matrix: { "<lora_or_asset_name>": ["<compatible_engine_or_checkpoint>", ...], ... }

若某 LoRA 在矩阵中被显式声明，则其仅在与列表中的引擎/checkpoint 组合时兼容；
未声明的 LoRA 默认兼容（不阻断，保留社区 LoRA 免注册即可部署的 Growth 阶段策略）。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def validate_compatibility_matrix(engine_cfg: Any) -> list[str]:
    """校验引擎 compatibility_matrix 结构合法。

    Returns:
        错误列表（空表示合法）。
    """
    matrix = getattr(engine_cfg, "compatibility_matrix", None) or {}
    if not isinstance(matrix, dict):
        return ["compatibility_matrix must be an object"]
    errors: list[str] = []
    for key, value in matrix.items():
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            errors.append(f"compatibility_matrix['{key}'] must be a list of strings")
    return errors


def is_lora_compatible(engine_cfg: Any, lora_name: str) -> bool:
    """判断 LoRA 是否与当前引擎兼容（按 compatibility_matrix 约定）。

    Args:
        engine_cfg: 引擎配置（含 ``name`` 与 ``compatibility_matrix``）。
        lora_name: LoRA 名称（不含扩展）。

    Returns:
        True=兼容；若 LoRA 在矩阵中被显式声明但不含当前引擎名则为 False。
    """
    matrix = getattr(engine_cfg, "compatibility_matrix", None) or {}
    if lora_name in matrix:
        return engine_cfg.name in matrix[lora_name]
    return True
