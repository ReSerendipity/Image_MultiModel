"""
observability/http_metrics.py — HTTP 请求指标中间件

MLOps P0-2：统一记录 http_requests_total + http_request_duration_seconds。

路径归一化（关键）：URL 中的 task_id / UUID / 纯数字段会被折叠为 {id}，
避免把高基数字段当作 label 导致 Prometheus  cardinality 爆炸
（对应评估 §8 Monitoring blind spots / 标签风险）。
"""

from __future__ import annotations

import re
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .metrics import get_metrics

_ID_SEGMENT = re.compile(r"^([0-9a-f]{8,}|[0-9]+)$", re.IGNORECASE)
_SKIP_PREFIXES = ("/static", "/metrics", "/api/metrics", "/events", "/api/events", "/favicon.ico")


def normalize_path(path: str) -> str:
    """把动态路径段折叠为 {id}，保持 label 低基数。"""
    parts = path.split("/")
    out = []
    for p in parts:
        if p and _ID_SEGMENT.match(p):
            out.append("{id}")
        else:
            out.append(p)
    return "/".join(out) or "/"


class MetricsMiddleware:
    """Starlette 中间件：记录每个 HTTP 请求的计数与延迟。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "/")
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        route = normalize_path(path)
        start = time.monotonic()
        status = "500"

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message.get("type") == "http.response.start":
                status = str(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            m = get_metrics()
            m.http_requests_total.inc(1.0, method=method, route=route, status=status)
            m.http_request_duration_seconds.observe(duration, method=method, route=route)
