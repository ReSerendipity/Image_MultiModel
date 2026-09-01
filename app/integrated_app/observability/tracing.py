"""
observability/tracing.py — 分布式追踪抽象（架构评估 P1-5 / 反模式 #6）

现状与取舍：
- 项目已有 ``RequestIDMiddleware`` 提供请求关联，但缺少 span 级别的
  调用链贯通，跨线程（executor）与跨进程（SSE/worker）无法还原耗时分布。
- 本项目定位为离线自包含部署，OpenTelemetry **非硬依赖**。故本模块实现
  依赖无关的追踪抽象：
  * 未安装 opentelemetry → 降级为进程内 span 记录（零依赖、零开销可关）
  * 已安装并配置 → 自动接入 OTEL TracerProvider，双写本地与 OTEL
- 支持 W3C ``traceparent`` 的解析与生成，保证未来接入上游网关/采集端时
  链路可跨进程续接。

用法::

    from integrated_app.observability.tracing import get_tracer
    with get_tracer("generate").start_span("submit_txt2img", {"engine": name}) as span:
        ...
        span.set_attribute("task_id", task_id)
"""

from __future__ import annotations

import contextvars
import logging
import os
import random
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# ── W3C traceparent 版本 ────────────────────────────────────────
_TRACEPARENT_VERSION = "00"


def _new_trace_id() -> str:
    """生成 32 位十六进制 trace id。"""
    return f"{random.getrandbits(128):032x}"


def _new_span_id() -> str:
    """生成 16 位十六进制 span id。"""
    return f"{random.getrandbits(64):016x}"


def format_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """按 W3C Trace Context 规范序列化 ``traceparent`` 头。"""
    flags = "01" if sampled else "00"
    return f"{_TRACEPARENT_VERSION}-{trace_id}-{span_id}-{flags}"


def parse_traceparent(header: str | None) -> tuple[str, str] | None:
    """解析 ``traceparent`` 头，返回 ``(trace_id, parent_span_id)``。

    非法/缺失一律返回 None（调用方据此开启新链路）。
    """
    if not header:
        return None
    try:
        parts = header.strip().split("-")
        if len(parts) != 4:
            return None
        _ver, trace_id, span_id, _flags = parts
        if len(trace_id) != 32 or len(span_id) != 16:
            return None
        int(trace_id, 16)
        int(span_id, 16)
        return trace_id, span_id
    except Exception:  # noqa: BLE001 - 头部非法即忽略
        return None


# ── Span ───────────────────────────────────────────────────────
@dataclass
class Span:
    """一个调用链片段。"""

    name: str
    trace_id: str = field(default_factory=_new_trace_id)
    span_id: str = field(default_factory=_new_span_id)
    parent_span_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "unset"  # unset | ok | error
    error: str | None = None
    _tracer: Any = None
    _otel_span: Any = None

    # ── 生命周期 ──────────────────────────────────────────────
    def __enter__(self) -> Span:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None:
            self.record_exception(exc)
        self.finish()
        return False  # 不吞异常

    def finish(self) -> None:
        """结束 span 并回写记录器。"""
        if self.end_time is None:
            self.end_time = time.time()
        if self.status == "unset":
            self.status = "ok"
        if self._tracer is not None:
            self._tracer._record(self)
        if self._otel_span is not None:
            try:
                self._otel_span.end()
            except Exception:  # noqa: BLE001 - OTEL 异常不影响业务
                pass

    # ── 属性 / 事件 ──────────────────────────────────────────
    def set_attribute(self, key: str, value: Any) -> None:
        """写入 span 属性（同时写入 OTEL span，若存在）。"""
        self.attributes[key] = value
        if self._otel_span is not None:
            try:
                self._otel_span.set_attribute(key, value)
            except Exception:  # noqa: BLE001
                pass

    def set_attributes(self, attrs: dict[str, Any]) -> None:
        for k, v in (attrs or {}).items():
            self.set_attribute(k, v)

    def record_exception(self, exc: BaseException) -> None:
        """记录异常并置 error 状态。"""
        self.status = "error"
        self.error = f"{type(exc).__name__}: {exc}"
        self.attributes["error.type"] = type(exc).__name__
        if self._otel_span is not None:
            try:
                self._otel_span.record_exception(exc)
            except Exception:  # noqa: BLE001
                pass

    def set_status_ok(self) -> None:
        self.status = "ok"

    # ── 序列化 ────────────────────────────────────────────────
    @property
    def duration_ms(self) -> float:
        end = self.end_time if self.end_time is not None else time.time()
        return round((end - self.start_time) * 1000.0, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "attributes": self.attributes,
        }

    @property
    def traceparent(self) -> str:
        return format_traceparent(self.trace_id, self.span_id)


# ── 记录器（进程内，有界）──────────────────────────────────────
class SpanRecorder:
    """有界 span 环形缓冲，供调试端点与测试断言消费。"""

    def __init__(self, max_spans: int = 1000) -> None:
        self._max = max(1, int(max_spans))
        self._spans: deque[Span] = deque(maxlen=self._max)

    def add(self, span: Span) -> None:
        self._spans.append(span)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return [s.to_dict() for s in list(self._spans)[-limit:]]

    def clear(self) -> None:
        self._spans.clear()

    def __len__(self) -> int:
        return len(self._spans)


# ── Tracer ─────────────────────────────────────────────────────
class Tracer:
    """进程内 tracer；可选双写 OpenTelemetry。"""

    def __init__(self, name: str, recorder: SpanRecorder, otel_tracer: Any = None) -> None:
        self._name = name
        self._recorder = recorder
        self._otel_tracer = otel_tracer

    @property
    def name(self) -> str:
        return self._name

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        parent: Span | None = None,
        traceparent: str | None = None,
    ) -> Iterator[Span]:
        """开启一个 span（上下文管理器，退出自动 finish）。

        Args:
            name: span 名称（建议 ``模块.操作``）。
            attributes: 初始属性。
            parent: 父 span（进程内嵌套）；与 ``traceparent`` 二选一。
            traceparent: 上游传入的 W3C 头，用于跨进程续接链路。
        """
        trace_id = _new_trace_id()
        parent_span_id = None
        if parent is not None:
            trace_id = parent.trace_id
            parent_span_id = parent.span_id
        elif traceparent:
            parsed = parse_traceparent(traceparent)
            if parsed:
                trace_id, parent_span_id = parsed

        span = Span(name=name, trace_id=trace_id, parent_span_id=parent_span_id, _tracer=self)
        span.set_attributes(attributes or {})

        if self._otel_tracer is not None:
            span._otel_span = self._safe_otel_start(name, span)

        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            span.finish()

    def _safe_otel_start(self, name: str, span: Span) -> Any:
        """尽力开启 OTEL span；不可用时静默返回 None。"""
        try:
            return self._otel_tracer.start_span(name)
        except Exception as e:  # noqa: BLE001 - OTEL 不可用不影响业务
            logger.debug("OTEL span start failed (%s): %s", name, e)
            return None

    def _record(self, span: Span) -> None:
        self._recorder.add(span)


# ── 当前 span（跨层父子串联用）─────────────────────────────────
_current_span: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "current_span", default=None
)


def set_current_span(span: Span | None) -> Any:
    """设置当前上下文的 span，返回用于 reset 的 token。"""
    return _current_span.set(span)


def reset_current_span(token: Any) -> None:
    """恢复当前上下文的 span。"""
    try:
        _current_span.reset(token)
    except (ValueError, LookupError):  # pragma: no cover - 上下文边界
        pass


def get_current_span() -> Span | None:
    """获取当前上下文的 span（用于嵌套子 span 的 parent）。"""
    return _current_span.get()


# ── 全局装配 ───────────────────────────────────────────────────
_recorder = SpanRecorder()
_tracers: dict[str, Tracer] = {}
_ENABLED: bool = True
_OTEL_TRACER: Any = None
_OTEL_BOOTSTRAPPED = False


def _bootstrap_otel() -> Any:
    """尝试装载 OpenTelemetry；不可用返回 None（仅尝试一次）。"""
    global _OTEL_BOOTSTRAPPED
    if _OTEL_BOOTSTRAPPED:
        return _OTEL_TRACER
    _OTEL_BOOTSTRAPPED = True
    try:
        from opentelemetry import trace as otel_trace  # type: ignore

        provider = otel_trace.get_tracer_provider()
        logger.info("OpenTelemetry detected, tracing will be exported as configured")
        return provider.get_tracer("integrated_app")
    except Exception:  # noqa: BLE001 - OTEL 未安装是预期内的降级路径
        logger.debug("OpenTelemetry not available, using in-process tracing only")
        return None


def configure_tracing(enabled: bool | None = None, max_spans: int = 1000) -> None:
    """按环境变量/参数配置追踪。

    环境变量：
        ``IMM_TRACING_DISABLED=1`` → 关闭（start_span 退化为零开销 no-op）
        ``IMM_TRACING_MAX_SPANS``  → 环形缓冲容量
    """
    global _ENABLED, _recorder, _OTEL_TRACER
    if enabled is None:
        enabled = os.environ.get("IMM_TRACING_DISABLED", "") != "1"
    _ENABLED = bool(enabled)
    _recorder = SpanRecorder(max_spans=int(os.environ.get("IMM_TRACING_MAX_SPANS", max_spans)))
    _OTEL_TRACER = _bootstrap_otel() if _ENABLED else None
    # 失效已缓存的 tracer，使其重新绑定到新记录器，避免跨配置读取旧 buffer
    _tracers.clear()
    logger.info("Tracing configured: enabled=%s max_spans=%s otel=%s", _ENABLED, max_spans, _OTEL_TRACER is not None)


def get_tracer(name: str = "integrated_app") -> Tracer:
    """获取（或惰性创建）指定名称的 tracer。"""
    tracer = _tracers.get(name)
    if tracer is None:
        if not _OTEL_BOOTSTRAPPED:
            configure_tracing()
        tracer = Tracer(name, _recorder, _OTEL_TRACER)
        _tracers[name] = tracer
    return tracer


def get_recorder() -> SpanRecorder:
    """获取全局 span 记录器（供调试端点/测试消费）。"""
    return _recorder


def recent_spans(limit: int = 100) -> list[dict[str, Any]]:
    """返回最近的 span 列表（调试与测试用）。"""
    return _recorder.recent(limit)


def clear_spans() -> None:
    """清空 span 缓冲（测试隔离用）。"""
    _recorder.clear()


def is_enabled() -> bool:
    return _ENABLED


__all__ = [
    "Span",
    "SpanRecorder",
    "Tracer",
    "clear_spans",
    "configure_tracing",
    "format_traceparent",
    "get_recorder",
    "get_tracer",
    "is_enabled",
    "parse_traceparent",
    "recent_spans",
]
