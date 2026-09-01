"""
middleware/auth.py — API 认证中间件（HTTP Basic + Bearer Token）

对应安全评估 C-01：``config.yaml`` 声明了 ``security.basic_auth`` 与
``security.api_token`` 两项控制，但全仓无任何运行时代码消费它们——属于典型的
"配置幻觉"（Phantom Control）。本模块补齐这两项控制的实现。

设计要点：
- **默认关闭**（两项 ``enabled`` 均为 ``false``），保持本地单机零配置的既有体验；
  任一启用后，未通过认证的请求返回 ``401`` + ``WWW-Authenticate``。
- 口令校验支持两种哈希格式，**无需新增依赖**：
  * bcrypt（``$2a$`` / ``$2b$`` / ``$2y$`` 前缀）—— 需可选依赖 ``bcrypt``，缺失时自动跳过
  * PBKDF2-HMAC-SHA256（``pbkdf2_sha256$...``）—— 标准库 ``hashlib`` 实现，**推荐**
- Token 比对统一使用 ``secrets.compare_digest``（恒定时间，防时序侧信道）。
- 豁免路径仅限探活、静态资源与 OpenAPI 文档，业务 ``/api/*`` 一律受保护。

口令哈希生成（运维用）::

    python -c "from app.integrated_app.middleware.auth import hash_password_pbkdf2; \\
        print(hash_password_pbkdf2('your-password'))"
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import secrets
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# bcrypt 哈希前缀（可选依赖，缺失时该格式一律校验失败）
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")
# PBKDF2 格式: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
_PBKDF2_PREFIX = "pbkdf2_sha256$"
_PBKDF2_ITERATIONS = 480_000
_PBKDF2_SALT_BYTES = 16

# 认证失败响应体
_UNAUTHORIZED_BODY = '{"detail": "Unauthorized"}'


# ── 口令哈希 ──────────────────────────────────────────────────
def hash_password_pbkdf2(
    plain: str,
    iterations: int = _PBKDF2_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    """生成 PBKDF2-HMAC-SHA256 口令哈希串（供生成 config.yaml 配置用）。

    Args:
        plain: 明文口令。
        iterations: 迭代次数（默认 480000，OWASP 推荐量级）。
        salt: 盐值；为空时随机生成 16 字节。

    Returns:
        str: ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`` 格式哈希串。
    """
    salt_bytes = salt if salt is not None else secrets.token_bytes(_PBKDF2_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt_bytes, iterations)
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{base64.b64encode(salt_bytes).decode('ascii')}$"
        f"{base64.b64encode(dk).decode('ascii')}"
    )


def _verify_pbkdf2(plain: str, hashed: str) -> bool:
    """校验 PBKDF2 格式哈希串。"""
    parts = hashed.split("$")
    if len(parts) != 4:
        return False
    try:
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2], validate=True)
        expected = base64.b64decode(parts[3], validate=True)
    except (ValueError, binascii.Error):
        return False
    if iterations <= 0 or not salt or not expected:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def _verify_bcrypt(plain: str, hashed: str) -> bool:
    """校验 bcrypt 格式哈希串；``bcrypt`` 未安装时返回 False（不抛异常）。"""
    try:
        import bcrypt  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "[AUTH] 配置了 bcrypt 口令哈希，但 bcrypt 包未安装，无法校验。"
            " 请安装 bcrypt，或改用 pbkdf2_sha256$ 格式哈希。"
        )
        return False
    try:
        return bool(bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8")))
    except (ValueError, TypeError):
        return False


def verify_password(plain: str, stored_hash: str) -> bool:
    """按哈希串前缀分派到对应的校验实现。

    Args:
        plain: 明文口令。
        stored_hash: 配置中的哈希串（bcrypt 或 pbkdf2_sha256 格式）。

    Returns:
        bool: 校验通过为 True；格式不支持或哈希为空时为 False。
    """
    if not plain or not stored_hash:
        return False
    if stored_hash.startswith(_BCRYPT_PREFIXES):
        return _verify_bcrypt(plain, stored_hash)
    if stored_hash.startswith(_PBKDF2_PREFIX):
        return _verify_pbkdf2(plain, stored_hash)
    logger.warning("[AUTH] 不支持的口令哈希格式（应以 $2b$ 或 pbkdf2_sha256$ 开头）")
    return False


# ── Token ─────────────────────────────────────────────────────
def verify_token(presented: str, allowed: list[str]) -> bool:
    """恒定时间比对 Bearer Token。

    Args:
        presented: 客户端提交的 token。
        allowed: 配置中登记的合法 token 列表。

    Returns:
        bool: 命中任一合法 token 为 True。
    """
    if not presented or not allowed:
        return False
    for candidate in allowed:
        if not isinstance(candidate, str):
            continue
        if secrets.compare_digest(presented, candidate):
            return True
    return False


# ── 中间件 ────────────────────────────────────────────────────
class AuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic / Bearer Token 认证中间件（默认关闭）。

    两项控制均关闭时直接放行，不改变任何既有行为。
    任一启用后，除豁免路径外的请求必须携带有效凭据。

    豁免路径设计原则：仅放行**不构成信息泄露且前端必需**的端点——
    探活（/api/health）、首页、静态资源、OpenAPI 文档。
    SSE 事件流（/api/events）**不豁免**，因为它是真实数据通道。
    """

    EXEMPT_PATHS = frozenset({
        "/",
        "/api/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    })
    EXEMPT_PREFIXES = ("/static/", "/docs", "/redoc")

    def __init__(self, app, config: Any = None) -> None:
        super().__init__(app)
        self._config = config

    def _get_security_config(self) -> Any | None:
        """惰性获取安全配置（构造时未传入则回退全局单例）。"""
        if self._config is not None:
            return getattr(self._config, "security", None)
        try:
            from ..config import get_config

            cfg = get_config()
            return getattr(cfg, "security", None) if cfg is not None else None
        except Exception:  # noqa: BLE001 - 配置不可用时按"未启用"处理
            return None

    def _is_exempt(self, path: str) -> bool:
        return path in self.EXEMPT_PATHS or path.startswith(self.EXEMPT_PREFIXES)

    @staticmethod
    def _unauthorized(kind: str) -> Response:
        scheme = "Bearer" if kind == "bearer" else "Basic"
        realm = 'Basic realm="Image MultiModel"' if scheme == "Basic" else "Bearer"
        return Response(
            content=_UNAUTHORIZED_BODY,
            status_code=401,
            media_type="application/json",
            headers={"WWW-Authenticate": realm},
        )

    async def dispatch(self, request: Request, call_next):
        sec = self._get_security_config()
        if sec is None:
            return await call_next(request)

        basic = getattr(sec, "basic_auth", None)
        token_cfg = getattr(sec, "api_token", None)
        basic_enabled = bool(getattr(basic, "enabled", False))
        token_enabled = bool(getattr(token_cfg, "enabled", False))

        # 两个都关闭 → 完全放行（保持向后兼容）
        if not basic_enabled and not token_enabled:
            return await call_next(request)

        if self._is_exempt(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        # Bearer Token 优先（无状态、可轮换，推荐用于程序化调用）
        if token_enabled:
            presented = ""
            if auth_header.lower().startswith("bearer "):
                presented = auth_header[7:].strip()
            elif not presented:
                presented = request.headers.get("X-API-Token", "").strip()
            if verify_token(presented, list(getattr(token_cfg, "tokens", []) or [])):
                return await call_next(request)

        # HTTP Basic（浏览器/运维场景）
        if basic_enabled:
            username_ok = False
            password_ok = False
            if auth_header.lower().startswith("basic "):
                try:
                    decoded = base64.b64decode(auth_header[6:].strip()).decode("utf-8")
                    user, _, pwd = decoded.partition(":")
                    username_ok = secrets.compare_digest(
                        user, str(getattr(basic, "username", "") or "")
                    )
                    if username_ok:
                        password_ok = verify_password(
                            pwd, str(getattr(basic, "password_bcrypt_hash", "") or "")
                        )
                except (ValueError, binascii.Error, UnicodeDecodeError):
                    username_ok = password_ok = False
            if username_ok and password_ok:
                return await call_next(request)

        logger.warning(
            "[AUTH] 401 未授权访问: path=%s method=%s client=%s",
            request.url.path,
            request.method,
            request.client.host if request.client else "unknown",
        )
        return self._unauthorized("bearer" if token_enabled else "basic")


__all__ = [
    "AuthMiddleware",
    "hash_password_pbkdf2",
    "verify_password",
    "verify_token",
]
