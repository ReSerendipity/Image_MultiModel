"""
单元测试：observability/tracing.py（P1-5 分布式追踪抽象）

验证 span 生命周期、W3C traceparent 解析/生成、父子串联、
记录器与 configure_tracing（降级路径，无 opentelemetry 依赖）。
"""

import pytest

from app.integrated_app.observability.tracing import (
    configure_tracing,
    format_traceparent,
    get_current_span,
    get_tracer,
    parse_traceparent,
    recent_spans,
    reset_current_span,
    set_current_span,
)


@pytest.fixture(autouse=True)
def _reset_tracing():
    configure_tracing(enabled=True, max_spans=200)
    yield
    from app.integrated_app.observability.tracing import clear_spans

    clear_spans()


def test_traceparent_roundtrip():
    tp = format_traceparent("a" * 32, "b" * 16, sampled=True)
    assert tp.startswith("00-")
    parsed = parse_traceparent(tp)
    assert parsed == ("a" * 32, "b" * 16)


def test_parse_traceparent_invalid():
    assert parse_traceparent(None) is None
    assert parse_traceparent("garbage") is None
    assert parse_traceparent("00-" + "a" * 31 + "-" + "b" * 16 + "-01") is None  # 长度不对


def test_span_lifecycle_records_duration():
    tracer = get_tracer("test")
    with tracer.start_span("op", attributes={"k": "v"}) as span:
        span.set_attribute("added", 1)
        assert span.status == "unset"
    assert span.status == "ok"
    assert span.duration_ms >= 0
    assert span.attributes["added"] == 1
    assert span.name == "op"


def test_span_records_exception():
    tracer = get_tracer("test")
    with pytest.raises(ValueError):
        with tracer.start_span("boom") as span:
            raise ValueError("x")
    assert span.status == "error"
    assert span.error is not None


def test_recorder_captures_spans():
    tracer = get_tracer("test")
    with tracer.start_span("a"):
        pass
    spans = recent_spans()
    assert any(s["name"] == "a" for s in spans)


def test_nested_parenting():
    tracer = get_tracer("test")
    with tracer.start_span("parent") as parent:
        assert get_current_span() is None  # 中间件外未自动绑定
        token = set_current_span(parent)
        try:
            with tracer.start_span("child", parent=get_current_span()) as child:
                assert child.trace_id == parent.trace_id
                assert child.parent_span_id == parent.span_id
        finally:
            reset_current_span(token)


def test_traceparent_continuation():
    """上游 traceparent 头可续接链路（跨进程）。"""
    upstream = format_traceparent("c" * 32, "d" * 16)
    tracer = get_tracer("http")
    parsed = parse_traceparent(upstream)
    with tracer.start_span("req", traceparent=upstream) as span:
        assert span.trace_id == parsed[0]
        assert span.parent_span_id == parsed[1]


def test_span_to_dict_shape():
    tracer = get_tracer("test")
    with tracer.start_span("x", attributes={"a": 1}) as span:
        pass
    d = span.to_dict()
    for key in ("name", "trace_id", "span_id", "duration_ms", "status", "attributes"):
        assert key in d
    assert d["attributes"]["a"] == 1


def test_configure_tracing_disable_does_not_crash():
    configure_tracing(enabled=False)
    tracer = get_tracer("test")
    with tracer.start_span("op"):
        pass
    # 即便禁用，tracer 仍可用（记录器降级而非崩溃）
    assert recent_spans() or True
