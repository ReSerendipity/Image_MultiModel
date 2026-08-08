"""
middleware/rate_limit.py — 速率限制中间件

对应 MASTER_PLAN §4: RateLimit
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    简单的内存速率限制（每 IP）。
    生产环境可替换为 Redis 后端。
    """

    def __init__(
        self,
        app,
        global_per_minute: int = 600,
        infer_per_minute: int = 30,
        upload_per_minute: int = 10,
    ) -> None:
        super().__init__(app)
        self.global_limit = global_per_minute
        self.infer_limit = infer_per_minute
        self.upload_limit = upload_per_minute
        self._global_hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._infer_hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._upload_hits: Dict[str, Deque[float]] = defaultdict(deque)

    def _check_rate(self, hits: Dict[str, Deque[float]], ip: str, limit: int) -> bool:
        now = time.time()
        window = 60.0
        # 清理过期
        while hits[ip] and hits[ip][0] < now - window:
            hits[ip].popleft()
        if len(hits[ip]) >= limit:
            return False
        hits[ip].append(now)
        return True

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # 全局限制
        if not self._check_rate(self._global_hits, client_ip, self.global_limit):
            return Response(
                content='{"detail": "Rate limit exceeded (global)"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        # 推理接口限制
        path = request.url.path
        if "/api/generate" in path and request.method == "POST":
            if not self._check_rate(self._infer_hits, client_ip, self.infer_limit):
                return Response(
                    content='{"detail": "Rate limit exceeded (infer)"}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": "60"},
                )

        # 上传接口限制
        if "/api/upload" in path and request.method == "POST":
            if not self._check_rate(self._upload_hits, client_ip, self.upload_limit):
                return Response(
                    content='{"detail": "Rate limit exceeded (upload)"}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": "60"},
                )

        return await call_next(request)
