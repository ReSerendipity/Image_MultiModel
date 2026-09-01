"""
middleware/tracing.py — 请求级根 span 中间件（架构评估 P1-5 / 反模式 #6）

在 ``RequestIDMiddleware`` 之后执行，为每个入站请求创建根 span，并把
既有 ``request_id`` 写入 span 属性；同时支持从 ``traceparent`` 头续接上游
链路（W3C Trace Context），并把本 span 的 ``traceparent`` 回写到响应头，
供下游/采集端延续调用链。

子 span（如生成编排、引擎推理）通过 ``observability.tracing`` 的
``get_current_span()`` 拿父 span，从而还原跨线程/跨进程的耗时分布。
"""

from __future__ import annotations

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..observability.tracing import (
    get_tracer,
    reset_current_span,
    set_current_span,
)

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求创建根 span，并贯通 request_id 与 traceparent。"""

    async def dispatch(self, request: Request, call_next):
        tracer = get_tracer("http")
        request_id = getattr(request.state, "request_id", None) or "-"
        traceparent_in = request.headers.get("traceparent")

        with tracer.start_span(
            name=f"{request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.path": request.url.path,
                "http.scheme": request.url.scheme,
                "request_id": request_id,
            },
            traceparent=traceparent_in,
        ) as span:
            # 进入 span 上下文（供嵌套子 span 取父），再执行业务
            token = set_current_span(span)
            request.state.trace_id = span.trace_id
            try:
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
                if response.status_code >= 500:
                    span.record_exception(RuntimeError(f"HTTP {response.status_code}"))
                else:
                    span.set_status_ok()
                response.headers["traceparent"] = span.traceparent
                response.headers["X-Trace-Id"] = span.trace_id
                return response
            except Exception as exc:  # noqa: BLE001 - 任何异常都记录进 span
                span.record_exception(exc)
                raise
            finally:
                reset_current_span(token)
