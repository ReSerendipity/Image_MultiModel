"""
config.py — YAML 配置文件加载与管理

对应 MASTER_PLAN §4: config.py / config_models.py
对应 PRD §10.2: 唯一配置源 config.yaml
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .config_models import AppConfig

# ── 全局单例 ──────────────────────────────────────────────────
_config: AppConfig | None = None
_config_path: Path | None = None


def get_project_root() -> Path:
    """获取项目根目录（config.yaml 所在目录）"""
    # 从当前文件向上查找 config.yaml
    p = Path(__file__).resolve()
    for _ in range(10):
        if (p / "config.yaml").exists():
            return p
        p = p.parent
    # fallback: 向上 3 层
    return Path(__file__).resolve().parent.parent.parent


def load_config(config_path: str | None = None) -> AppConfig:
    """
    从 YAML 文件加载配置并构建 AppConfig。

    Args:
        config_path: config.yaml 的路径，None 时自动探测
    Returns:
        AppConfig 实例
    """
    global _config, _config_path

    if config_path:
        p = Path(config_path).resolve()
    else:
        p = get_project_root() / "config.yaml"

    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")

    _config_path = p
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    project_root = str(p.parent.resolve())
    _config = AppConfig.from_yaml(raw, project_root=project_root)

    # 设置环境变量
    _apply_environment(_config)

    return _config


def get_config() -> AppConfig:
    """获取全局配置单例，首次调用时自动加载"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def save_config(config: AppConfig, config_path: str | None = None) -> None:
    """
    将配置写回 YAML 文件（PUT /api/config 调用）。

    Args:
        config: 更新后的 AppConfig
        config_path: 目标路径，None 时使用加载时的路径
    """
    global _config, _config_path
    p = Path(config_path) if config_path else (_config_path or get_project_root() / "config.yaml")
    p = p.resolve()

    # 序列化为 YAML 字典（脱敏后不写回敏感字段）
    d = _serialize_for_yaml(config)

    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(d, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    _config = config
    _config_path = p

    # 重新设置环境变量
    _apply_environment(_config)


def _serialize_for_yaml(config: AppConfig) -> dict[str, Any]:
    """
    将 AppConfig 序列化为可写入 YAML 的字典。
    注意：不脱敏 auth_token / password（这些是原值，需要保留）。
    但 project_root 字段排除。
    """
    d = config.model_dump(exclude={"project_root"})
    return d


def _apply_environment(config: AppConfig) -> None:
    """设置环境变量（离线优先级）"""
    env = config.environment
    os.environ["HF_HUB_OFFLINE"] = env.HF_HUB_OFFLINE
    os.environ["TRANSFORMERS_OFFLINE"] = env.TRANSFORMERS_OFFLINE
    os.environ["MODELSCOPE_OFFLINE"] = env.MODELSCOPE_OFFLINE
    os.environ["COMFYUI_DISABLE_UPDATE_CHECK"] = env.COMFYUI_DISABLE_UPDATE_CHECK


def reload_config() -> AppConfig:
    """重新加载配置（热重载）"""
    global _config
    _config = load_config(str(_config_path)) if _config_path else load_config()
    return _config
