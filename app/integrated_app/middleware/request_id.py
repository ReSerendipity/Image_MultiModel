"""
middleware/request_id.py — 请求 ID 注入中间件

为每个入站 HTTP 请求分配唯一 ID，并注入 Python logging 上下文，
使整条请求链路的日志都能自动携带 request_id（用于 ELK/EFK 聚合与链路追踪）。
"""

from __future__ import annotations

import contextvars
import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    """获取当前上下文关联的 request_id。"""
    return _request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求注入唯一 ID（用于日志追踪）"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        token = _request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            try:
                _request_id_var.reset(token)
            except (ValueError, LookupError):
                pass


class RequestIDLogFilter(logging.Filter):
    """日志过滤器，将当前 request_id 注入每条 LogRecord。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = _request_id_var.get("-")
        return True
