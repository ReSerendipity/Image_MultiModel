"""security/auth_bootstrap.py — 最小 api_token 鉴权的 off-by-default bootstrap

对应 2026-09-04 安全评估 M3：回环绑定 + 鉴权默认全关 + ``/api/config`` PUT
等状态变更端点无保护，构成本地提权面（本机任意进程/浏览器内恶意 JS 可静默
改配置、卸载引擎）。本模块提供**可选**的自动化收敛：

- **off-by-default**：``security.api_token.bootstrap: false``（默认）时完全不
  改变既有行为，本地零配置体验不变；
- ``bootstrap: true`` 且 ``enabled: false`` 时，首次启动生成 256-bit token
  并持久化到 ``<project_root>/.api_token``（gitignore，不回写 config.yaml，
  避免注释丢失 gotcha）；已存在则复用，保证 token 跨重启稳定；
- 运行时置 ``enabled=True`` + ``tokens=[token]``，AuthMiddleware 立即生效；
- 运维读取 ``.api_token`` 配置客户端；关闭增强 = 删文件 + bootstrap 置 false。
"""

from __future__ import annotations

import logging
import secrets
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_FILE_NAME = ".api_token"


def _token_file(project_root: str | Path) -> Path:
    return Path(project_root) / TOKEN_FILE_NAME


def _persist_token(path: Path, token: str) -> None:
    path.write_text(token + "\n", encoding="utf-8")
    try:
        # POSIX 收紧权限；Windows 无此语义，忽略失败
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # noqa: BLE001 - Windows / 只读挂载下 chmod 可能失败
        pass


def ensure_api_token(config) -> str | None:
    """按 bootstrap 策略启用最小 api_token 鉴权。

    Args:
        config: AppConfig（全局单例；本函数会就地修改其 security.api_token）。

    Returns:
        生效的 token；未触发 bootstrap 时返回 None。
        返回值仅供调用方记录日志使用，**不得写入任何持久化存储**。
    """
    token_cfg = getattr(getattr(config, "security", None), "api_token", None)
    if token_cfg is None:
        return None
    if not bool(getattr(token_cfg, "bootstrap", False)):
        return None  # off-by-default：未开启则不改变任何行为
    if bool(getattr(token_cfg, "enabled", False)):
        return None  # 已显式启用鉴权，尊重现有配置

    token_file = _token_file(getattr(config, "project_root", "."))
    if token_file.exists() and token_file.read_text(encoding="utf-8").strip():
        token = token_file.read_text(encoding="utf-8").strip()
        source = "复用已有"
    else:
        token = secrets.token_urlsafe(32)
        _persist_token(token_file, token)
        source = "新生成"

    # 运行时启用（AuthMiddleware 每请求读取 get_config()，立即生效）
    token_cfg.enabled = True
    token_cfg.tokens = [token]
    logger.warning(
        "[AUTH-BOOTSTRAP] api_token 鉴权已启用（%s token：%s）。"
        "客户端请求需携带 Authorization: Bearer <token> 或 X-API-Token 头；"
        "如需关闭，删除 %s 并将 security.api_token.bootstrap 置 false。",
        source,
        token_file,
        token_file,
    )
    return token


__all__ = ["ensure_api_token", "TOKEN_FILE_NAME"]
