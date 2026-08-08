"""
middleware/csrf.py — CSRF 防护中间件

对应 MASTER_PLAN §4 / 附录 C1: CSRF (JSON fetch Token 头注入)
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF 防护中间件：
    - GET 请求发放 CSRF token（通过响应头 X-CSRF-Token）
    - POST/PUT/DELETE 请求需要携带 X-CSRF-Token 头
    """

    EXEMPT_METHODS = {"GET", "HEAD", "OPTIONS"}
    TOKEN_HEADER = "X-CSRF-Token"

    def __init__(self, app, cookie_name: str = "csrf_token") -> None:
        super().__init__(app)
        self.cookie_name = cookie_name

    async def dispatch(self, request: Request, call_next):
        # GET 请求：设置 token
        if request.method in self.EXEMPT_METHODS:
            response = await call_next(request)
            token = secrets.token_hex(16)
            response.set_cookie(
                self.cookie_name, token,
                httponly=True, samesite="lax", max_age=3600,
            )
            response.headers[self.TOKEN_HEADER] = token
            return response

        # 非 GET：验证 token
        token = request.headers.get(self.TOKEN_HEADER, "")
        cookie_token = request.cookies.get(self.cookie_name, "")

        if not token or token != cookie_token:
            return Response(
                content='{"detail": "CSRF token missing or invalid"}',
                status_code=403,
                media_type="application/json",
            )

        return await call_next(request)
