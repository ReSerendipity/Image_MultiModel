"""
middleware/rate_limit.py — 速率限制中间件

对应 MASTER_PLAN §4: RateLimit
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# 每个类别最多保留的客户端桶数量（LRU 淘汰，防内存随独立 IP 数无限增长）
_MAX_BUCKETS = 10_000
_WINDOW = 60.0


class _BoundedHits:
    """有界（LRU）命中计数器：超过上限时淘汰最久未使用的客户端桶。"""

    def __init__(self, max_buckets: int = _MAX_BUCKETS) -> None:
        self.max_buckets = max_buckets
        self._data: OrderedDict[str, deque[float]] = OrderedDict()

    def get(self, ip: str) -> deque[float] | None:
        return self._data.get(ip)

    def record(self, ip: str, now: float) -> deque[float]:
        dq = self._data.get(ip)
        if dq is None:
            if len(self._data) >= self.max_buckets:
                self._data.popitem(last=False)  # 淘汰最久未使用
            dq = deque()
            self._data[ip] = dq
        else:
            self._data.move_to_end(ip)
        dq.append(now)
        return dq


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    简单的内存速率限制（每真实客户端 IP）。

    - 代理识别（L-03）：优先采用 X-Forwarded-For / X-Real-IP 取真实客户端
      IP（取最左/原始客户端），避免反向代理后所有请求共享同一桶导致误杀或漏限。
    - LRU 有界桶（L-03）：各维度桶数上限 _MAX_BUCKETS，超出淘汰最久未用，防止内存膨胀。
    生产环境可替换为 Redis 后端。
    """

    def __init__(
        self,
        app,
        global_per_minute: int = 600,
        infer_per_minute: int = 30,
        upload_per_minute: int = 10,
        trusted_proxies: bool = True,
    ) -> None:
        super().__init__(app)
        self.global_limit = global_per_minute
        self.infer_limit = infer_per_minute
        self.upload_limit = upload_per_minute
        self.trusted_proxies = trusted_proxies
        self._global_hits = _BoundedHits()
        self._infer_hits = _BoundedHits()
        self._upload_hits = _BoundedHits()

    @staticmethod
    def _client_ip(request: Request, trusted_proxies: bool = True) -> str:
        """解析真实客户端 IP（代理识别）。

        仅当信任前置代理时才采纳 X-Forwarded-For / X-Real-IP 的首个（原始）
        客户端地址；否则直接使用 TCP 对端地址，防止客户端伪造请求头绕过限流。
        """
        if trusted_proxies:
            xff = request.headers.get("X-Forwarded-For")
            if xff:
                # 取最左（原始客户端）；后续为各级代理，忽略
                return xff.split(",")[0].strip()
            xri = request.headers.get("X-Real-IP")
            if xri:
                return xri.strip()
        return request.client.host if request.client else "unknown"

    def _check_rate(self, hits: _BoundedHits, ip: str, limit: int) -> bool:
        now = time.time()
        dq = hits.get(ip)
        if dq is not None:
            while dq and dq[0] < now - _WINDOW:
                dq.popleft()
        if dq is not None and len(dq) >= limit:
            return False
        hits.record(ip, now)
        return True

    async def dispatch(self, request: Request, call_next):
        client_ip = self._client_ip(request, self.trusted_proxies)

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
