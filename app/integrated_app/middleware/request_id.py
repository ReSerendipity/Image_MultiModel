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


def set_request_id(request_id: str):
    """把 request_id 绑定到当前线程/协程上下文，返回 reset 用的 token。

    供非 HTTP 入口（如 task_queue 的 worker 线程）复用提交侧的 request_id，
    使「HTTP 提交 → worker 执行」整条链路日志携带同一个 ``req=`` 关联键。
    """
    return _request_id_var.set(request_id or "")


def reset_request_id(token) -> None:
    """还原 :func:`set_request_id` 设置的上下文（容忍跨上下文 reset 失败）。"""
    try:
        _request_id_var.reset(token)
    except (ValueError, LookupError):
        pass


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
            reset_request_id(token)


class RequestIDLogFilter(logging.Filter):
    """日志过滤器，将当前 request_id 注入每条 LogRecord。

    取值优先级：LogRecord 已有属性 > 当前上下文 ContextVar > worker 线程
    在飞任务元数据回退（task_queue 的 worker 线程不跑中间件，ContextVar
    通常为空；即便 worker_func 已显式绑定，这里也兜底，保证跨线程边界
    的 ``req=`` 关联键不丢）。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            rid = _request_id_var.get()
            if not rid:
                try:
                    from ..task_queue import TaskStatus, get_task_queue

                    tq = get_task_queue()
                    cur = tq.current_task if tq is not None else None
                    if cur is not None and cur.status == TaskStatus.PROCESSING:
                        rid = getattr(cur, "request_id", "")
                except Exception:  # noqa: BLE001 - 回退读取失败不应阻断日志
                    rid = ""
            record.request_id = rid or "-"
        return True
