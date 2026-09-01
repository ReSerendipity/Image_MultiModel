"""
observability/metrics.py — 零依赖 Prometheus 风格指标原语

MLOps P0-2（运维稳定性评估）：统一可抓取指标入口。

设计约束（对应评估 §8 Monitoring blind spots / 标签高基风险）：
- 不引入 prometheus_client 外部依赖，避免污染 requirements；
- 指标标签仅允许低基数字段（route/method/status/engine/error_code），
  禁止 task_id / prompt 等高基数字段直接作为 label；
- Counter / Gauge / Histogram 均为进程内聚合，render() 输出标准 exposition 文本，
  供 ``/api/metrics`` 直接返回。

所有指标经由 ``get_metrics()`` 单例注册，跨模块共享。
"""

from __future__ import annotations

import threading
from collections.abc import Iterable

# 默认直方图桶（秒）：覆盖 5ms ~ 120s 的生成链路典型区间
_DEFAULT_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0,
    2.5, 5.0, 10.0, 30.0, 60.0, 120.0,
)


def _escape_label_value(value: str) -> str:
    """转义 Prometheus label value 中的特殊字符。"""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _bucket_str(boundary: float) -> str:
    return "+Inf" if boundary == float("inf") else repr(boundary)


class _Base:
    """指标基类：统一标签键校验与序列键计算。

    子类（Counter / Gauge / Histogram）均实现 ``render()``；此处声明基类接口，
    使 ``MetricsRegistry._metrics: list[_Base]`` 上的 ``render()`` 调用类型合法。
    """

    def render(self) -> list[str]:
        """渲染为 Prometheus 文本行（由子类实现）。"""
        raise NotImplementedError

    def __init__(self, name: str, description: str, labelnames: Iterable[str] = ()) -> None:
        self.name = name
        self.description = description
        self.labelnames = tuple(labelnames)
        if not self.name or not self.name.replace("_", "").isalnum():
            raise ValueError(f"invalid metric name: {name!r}")

    def _key(self, labels: dict[str, str]) -> tuple[str, ...]:
        return tuple(str(labels.get(label, "")) for label in self.labelnames)

    def _label_text(self, key: tuple[str, ...]) -> str:
        if not self.labelnames:
            return ""
        parts = [
            f'{label}="{_escape_label_value(v)}"'
            for label, v in zip(self.labelnames, key)
        ]
        return "{" + ",".join(parts) + "}"


class Counter(_Base):
    """单调递增计数器（进程内）。"""

    def __init__(self, name: str, description: str, labelnames: Iterable[str] = ()) -> None:
        super().__init__(name, description, labelnames)
        self._series: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        if amount < 0:
            raise ValueError("counter increment must be >= 0")
        k = self._key(labels)
        with self._lock:
            self._series[k] = self._series.get(k, 0.0) + amount

    def value(self, **labels: str) -> float:
        return self._series.get(self._key(labels), 0.0)

    def total(self) -> float:
        """所有 label 组合计数的总和。"""
        return sum(self._series.values())

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} counter",
        ]
        for k, v in sorted(self._series.items()):
            lines.append(f"{self.name}{self._label_text(k)} {v:g}")
        return lines


class Gauge(_Base):
    """可增可减的瞬时量（queue_depth / disk_free_bytes 等）。"""

    def __init__(self, name: str, description: str, labelnames: Iterable[str] = ()) -> None:
        super().__init__(name, description, labelnames)
        self._series: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, **labels: str) -> None:
        k = self._key(labels)
        with self._lock:
            self._series[k] = float(value)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        k = self._key(labels)
        with self._lock:
            self._series[k] = self._series.get(k, 0.0) + amount

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        self.inc(-amount, **labels)

    def value(self, **labels: str) -> float:
        return self._series.get(self._key(labels), 0.0)

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} gauge",
        ]
        for k, v in sorted(self._series.items()):
            lines.append(f"{self.name}{self._label_text(k)} {v:g}")
        return lines


class Histogram(_Base):
    """直方图（端到端延迟 / 队列等待）。

    进程内保留有限样本（每 label 组合上限 1024）用于近似分位数，
    同时维护标准 Prometheus bucket 累计计数 + sum + count。
    """

    def __init__(
        self,
        name: str,
        description: str,
        labelnames: Iterable[str] = (),
        buckets: Iterable[float] = _DEFAULT_BUCKETS,
    ) -> None:
        super().__init__(name, description, labelnames)
        self._buckets = list(buckets) + [float("inf")]
        self._counts: dict[tuple[tuple[str, ...], int], int] = {}
        self._sum: dict[tuple[str, ...], float] = {}
        self._samples: dict[tuple[str, ...], list[float]] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, **labels: str) -> None:
        k = self._key(labels)
        with self._lock:
            self._sum[k] = self._sum.get(k, 0.0) + value
            for i, b in enumerate(self._buckets):
                if value <= b:
                    self._counts[(k, i)] = self._counts.get((k, i), 0) + 1
                    break
            samples = self._samples.setdefault(k, [])
            samples.append(value)
            if len(samples) > 1024:
                samples.pop(0)

    def _quantile(self, samples: list[float], q: float) -> float:
        if not samples:
            return 0.0
        s = sorted(samples)
        idx = max(0, min(len(s) - 1, int(q * (len(s) - 1))))
        return s[idx]

    def render(self) -> list[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            sum_snapshot = dict(self._sum)
            samples_snapshot = {k: list(v) for k, v in self._samples.items()}
            # 计算每个 label 组合的累计 bucket
            cumulative: dict[tuple[str, ...], list[int]] = {}
            for (k, i), c in self._counts.items():
                cum = cumulative.setdefault(k, [0] * len(self._buckets))
                cum[i] += c
            for k, cum in cumulative.items():
                lt = self._label_text(k)
                running = 0
                for i, b in enumerate(self._buckets):
                    running += cum[i]
                    lines.append(f'{self.name}_bucket{lt},le="{_bucket_str(b)}" {running:g}')
                total = sum(cum)
                lines.append(f"{self.name}_sum{lt} {sum_snapshot.get(k, 0.0):g}")
                lines.append(f"{self.name}_count{lt} {total:g}")
            # 近似分位数（可选，便于看板直接读取 P50/P95/P99）
            for q, suffix in ((0.5, "p50"), (0.95, "p95"), (0.99, "p99")):
                for k, samples in samples_snapshot.items():
                    if not samples:
                        continue
                    lt = self._label_text(k)
                    lines.append(
                        f"{self.name}_{suffix}{lt} {self._quantile(samples, q):g}"
                    )
        return lines


class MetricsRegistry:
    """指标注册表——聚合所有 Counter/Gauge/Histogram 并渲染 exposition。"""

    def __init__(self) -> None:
        self._metrics: list[_Base] = []

        # ── HTTP ──
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests by method, route and status.",
            labelnames=("method", "route", "status"),
        )
        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds by method and route.",
            labelnames=("method", "route"),
        )

        # ── 生成链路生命周期 ──
        self.generation_submitted_total = Counter(
            "generation_submitted_total",
            "Generation tasks submitted (accepted by validation) by engine.",
            labelnames=("engine",),
        )
        self.generation_accepted_total = Counter(
            "generation_accepted_total",
            "Generation tasks accepted into the queue by engine.",
            labelnames=("engine",),
        )
        self.generation_rejected_total = Counter(
            "generation_rejected_total",
            "Generation submissions rejected before queueing by error_code.",
            labelnames=("error_code",),
        )
        self.generation_started_total = Counter(
            "generation_started_total",
            "Generation tasks started by the worker by engine.",
            labelnames=("engine",),
        )
        self.generation_first_progress_total = Counter(
            "generation_first_progress_total",
            "Generation tasks that emitted their first progress event by engine.",
            labelnames=("engine",),
        )
        self.generation_first_preview_total = Counter(
            "generation_first_preview_total",
            "Generation tasks that emitted their first preview by engine.",
            labelnames=("engine",),
        )
        self.generation_completed_total = Counter(
            "generation_completed_total",
            "Generation tasks completed successfully by engine.",
            labelnames=("engine",),
        )
        self.generation_failed_total = Counter(
            "generation_failed_total",
            "Generation tasks failed by engine and error_code.",
            labelnames=("engine", "error_code"),
        )
        self.generation_cancelled_total = Counter(
            "generation_cancelled_total",
            "Generation tasks cancelled by engine.",
            labelnames=("engine",),
        )

        # ── 生成延迟（monotonic clock 分段） ──
        self.generation_duration_seconds = Histogram(
            "generation_duration_seconds",
            "End-to-end generation duration in seconds (submit -> completed).",
            labelnames=("engine",),
        )
        self.generation_queue_wait_seconds = Histogram(
            "generation_queue_wait_seconds",
            "Time a task waited in the queue before processing started.",
            labelnames=("engine",),
        )
        self.generation_inference_seconds = Histogram(
            "generation_inference_seconds",
            "Inference (model load + txt2img) duration in seconds.",
            labelnames=("engine",),
        )

        # ── 队列 ──
        self.queue_depth = Gauge(
            "queue_depth",
            "Current number of tasks waiting in the queue.",
        )
        self.queue_processing = Gauge(
            "queue_processing",
            "Current number of tasks being processed.",
        )
        self.queue_oldest_age_seconds = Gauge(
            "queue_oldest_age_seconds",
            "Age in seconds of the oldest pending task.",
        )
        self.queue_rejected_total = Counter(
            "queue_rejected_total",
            "Tasks rejected at submission because the queue was full.",
            labelnames=("reason",),
        )

        # ── GPU ──
        self.gpu_memory_used_bytes = Gauge(
            "gpu_memory_used_bytes",
            "GPU VRAM currently used in bytes.",
        )
        self.gpu_memory_total_bytes = Gauge(
            "gpu_memory_total_bytes",
            "GPU VRAM total in bytes.",
        )
        self.gpu_oom_total = Counter(
            "gpu_oom_total",
            "Count of GPU out-of-memory events detected during inference.",
        )

        # ── SSE ──
        self.sse_connected = Gauge(
            "sse_connected",
            "Current number of connected SSE clients.",
        )
        self.sse_events_dropped_total = Gauge(
            "sse_events_dropped_total",
            "Cumulative SSE events dropped due to subscriber queue overflow.",
        )

        # ── 磁盘 ──
        self.disk_free_bytes = Gauge(
            "disk_free_bytes",
            "Free disk space in bytes on the data volume root.",
        )
        self.disk_total_bytes = Gauge(
            "disk_total_bytes",
            "Total disk space in bytes on the data volume root.",
        )

        self._register_all()

    def _register_all(self) -> None:
        for attr in (
            "http_requests_total", "http_request_duration_seconds",
            "generation_submitted_total", "generation_accepted_total",
            "generation_rejected_total", "generation_started_total",
            "generation_first_progress_total", "generation_first_preview_total",
            "generation_completed_total", "generation_failed_total",
            "generation_cancelled_total", "generation_duration_seconds",
            "generation_queue_wait_seconds", "generation_inference_seconds",
            "queue_depth", "queue_processing", "queue_oldest_age_seconds",
            "queue_rejected_total", "gpu_memory_used_bytes", "gpu_memory_total_bytes",
            "gpu_oom_total", "sse_connected", "sse_events_dropped_total",
            "disk_free_bytes", "disk_total_bytes",
        ):
            self._metrics.append(getattr(self, attr))

    def render(self) -> str:
        """渲染为 Prometheus text exposition 格式。"""
        out: list[str] = []
        for m in self._metrics:
            out.extend(m.render())
        return "\n".join(out) + "\n"


_metrics_singleton: MetricsRegistry | None = None
_metrics_lock = threading.Lock()


def get_metrics() -> MetricsRegistry:
    """获取进程级指标注册表单例。"""
    global _metrics_singleton
    if _metrics_singleton is None:
        with _metrics_lock:
            if _metrics_singleton is None:
                _metrics_singleton = MetricsRegistry()
    return _metrics_singleton


def reset_metrics() -> None:
    """测试用：清空单例（避免跨测试串扰）。"""
    global _metrics_singleton
    with _metrics_lock:
        _metrics_singleton = None
