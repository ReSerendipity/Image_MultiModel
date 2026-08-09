"""
config.py — YAML 配置文件加载与管理

对应 MASTER_PLAN §4: config.py / config_models.py
对应 PRD §10.2: 唯一配置源 config.yaml

P0-1 改造：save_config() 原子写入（来源：Seedvr2），使用 tempfile + os.replace
避免写入过程中断导致配置文件半写损坏。

P0-2 改造：load_config() 宽松接口 + load_validated_config() 严格接口分层
（来源：Seedvr2），Pydantic 验证失败时回退到原始 YAML 加载，保证启动不被阻塞。

P1-3 改造：_load_dotenv() .env 文件支持（来源：TTS_MultiModel），
敏感配置可通过 .env 文件管理，.env 不提交到 Git。
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .config_models import AppConfig

logger = logging.getLogger("integrated_app")

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


# ── P1-3: .env 文件支持（来源：TTS_MultiModel） ──────────────


def _load_dotenv() -> None:
    """加载项目根目录下的 .env 文件（无第三方依赖，纯标准库实现）。

    解析简单的 KEY=VALUE 行，忽略 # 注释和空行。
    使用 os.environ.setdefault 写入，保证显式系统环境变量优先级高于 .env 文件。
    支持去除首尾单引号/双引号，以及将字面量 \\n 转换为真实换行（多行 PEM 密钥等场景）。

    .env 文件路径为项目根目录下的 .env（与 config.yaml 同级）。
    文件不存在时静默返回，不影响应用启动。
    """
    env_path = get_project_root() / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # 去除首尾引号（单引号或双引号）
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                # 将字面量 \n 转换为真实换行（多行 PEM 密钥等场景）
                value = value.replace("\\n", "\n")
                if key:
                    os.environ.setdefault(key, value)
    except Exception as e:
        logger.warning(f".env 文件加载失败: {e}")


def _resolve_path(config_path: str | None) -> Path:
    """解析配置文件路径"""
    if config_path:
        return Path(config_path).resolve()
    return get_project_root() / "config.yaml"


# ── P0-2: 配置加载回退机制（来源：Seedvr2） ──────────────────


def load_validated_config(config_path: str | None = None) -> AppConfig:
    """严格加载并验证配置，Pydantic 验证失败时抛出异常。

    Args:
        config_path: config.yaml 的路径，None 时自动探测

    Returns:
        AppConfig 实例

    Raises:
        FileNotFoundError: 配置文件不存在
        pydantic.ValidationError: 配置字段值不合法
    """
    global _config, _config_path

    # P1-3: 加载 .env 文件（在 config.yaml 解析前）
    _load_dotenv()

    p = _resolve_path(config_path)

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


def load_config(config_path: str | None = None) -> AppConfig:
    """对外宽松接口：Pydantic 验证失败时尽量降级，不阻塞启动。

    策略：
    1. 优先严格验证（走 load_validated_config）
    2. 验证失败 → 尝试用 raw YAML dict 逐字段过滤后构造 AppConfig
    3. 还是失败 → 使用全默认 AppConfig 兜底

    永远返回一个可用的 AppConfig 实例，绝不抛异常。
    """
    global _config, _config_path

    # 策略 1：严格验证
    try:
        return load_validated_config(config_path)
    except Exception as e1:
        logger.warning(f"配置严格验证失败，尝试降级加载：{e1}")

        # 策略 2：逐字段过滤后构造
        try:
            p = _resolve_path(config_path)
            if not p.exists():
                logger.error(f"配置文件不存在，使用默认配置启动：{p}")
                _config = AppConfig()
                _config_path = p
                return _config

            _config_path = p
            with open(p, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}

            project_root = str(p.parent.resolve())
            # 逐 section 过滤：只保留 AppConfig 认识的字段
            valid_keys = set(AppConfig.model_fields.keys())
            filtered = {k: v for k, v in raw.items() if k in valid_keys}

            # 尝试构造
            try:
                _config = AppConfig.from_yaml(filtered, project_root=project_root)
            except Exception:
                # 更细粒度：逐个 section 尝试，失败的用默认值
                _config = _build_partial_config(raw, project_root)

            _apply_environment(_config)
            logger.warning(
                "配置降级加载完成，部分字段可能使用默认值。"
                "建议检查并重新保存 config.yaml。"
            )
            return _config
        except Exception as e2:
            logger.error(f"配置降级加载也失败，使用默认配置启动：{e2}")
            _config = AppConfig()
            return _config


def _build_partial_config(raw: dict, project_root: str) -> AppConfig:
    """逐 section 构造 AppConfig，失败的 section 用默认值。

    Args:
        raw: 原始 YAML dict
        project_root: 项目根目录

    Returns:
        AppConfig 实例，部分 section 可能用默认值
    """
    # 先用全默认值构造
    cfg = AppConfig()
    cfg.project_root = str(Path(project_root).resolve())

    # 逐个 section 尝试覆盖
    for field_name in AppConfig.model_fields:
        if field_name == "project_root":
            continue
        if field_name not in raw:
            continue
        try:
            field_value = raw[field_name]
            # 获取该 field 的模型类
            field_info = AppConfig.model_fields[field_name]
            model_cls = field_info.annotation
            if isinstance(field_value, dict) and model_cls and hasattr(model_cls, "model_validate"):
                validated = model_cls.model_validate(field_value)
                setattr(cfg, field_name, validated)
            elif not isinstance(field_value, dict):
                # 标量字段直接设置
                setattr(cfg, field_name, field_value)
        except Exception as e:
            logger.warning(f"配置 section '{field_name}' 加载失败，使用默认值：{e}")

    return cfg


def get_config() -> AppConfig:
    """获取全局配置单例，首次调用时自动加载"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


# ── P0-1: 配置写入原子化（来源：Seedvr2） ────────────────────


def save_config(config: AppConfig, config_path: str | None = None) -> None:
    """原子写入保存配置到 YAML 文件（来源：Seedvr2）。

    使用临时文件 + 原子替换策略避免写入过程中断导致配置文件损坏：
    1. 在目标目录创建隐藏临时文件（.config_*.tmp）
    2. 写入配置内容到临时文件
    3. 使用 os.replace 原子替换目标文件（同文件系统内是原子操作）
    4. 失败时安全清理临时文件

    Args:
        config: 更新后的 AppConfig
        config_path: 目标路径，None 时使用加载时的路径
    """
    global _config, _config_path
    p = Path(config_path) if config_path else (_config_path or get_project_root() / "config.yaml")
    p = p.resolve()

    config_dir = p.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    # 序列化为 YAML 字典（脱敏后不写回敏感字段）
    d = _serialize_for_yaml(config)

    # P0-1: 原子写入 — tempfile + os.replace
    fd, tmp_path = tempfile.mkstemp(
        dir=str(config_dir),
        prefix=".config_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(d, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, str(p))
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

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
    # P1-3: 使用 setdefault 而非直接赋值，保证优先级：
    # 用户 shell 显式 export > .env 文件中的值 > 代码默认值
    os.environ.setdefault("HF_HUB_OFFLINE", env.HF_HUB_OFFLINE)
    os.environ.setdefault("TRANSFORMERS_OFFLINE", env.TRANSFORMERS_OFFLINE)
    os.environ.setdefault("MODELSCOPE_OFFLINE", env.MODELSCOPE_OFFLINE)
    os.environ.setdefault("COMFYUI_DISABLE_UPDATE_CHECK", env.COMFYUI_DISABLE_UPDATE_CHECK)


def reload_config() -> AppConfig:
    """重新加载配置（热重载）"""
    global _config
    _config = load_config(str(_config_path)) if _config_path else load_config()
    return _config
