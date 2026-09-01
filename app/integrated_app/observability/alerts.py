"""
observability/alerts.py — 告警评估引擎（MLOps P0-4）

把"日志 warning"升级为可执行告警：基于指标快照周期评估规则，支持
for（持续时长）、去重（同一告警不重复通知）、恢复判定，且每条告警都
链接到对应 Runbook（消除反模式 Missing runbook / Alert fatigue）。

注意：本模块只做「评估 + 状态机 + 通知去重」，不绑定具体通知通道；
通知通道通过 ``set_notifier`` 注入（默认仅记录结构化日志，避免误报风暴）。
真实 Alertmanager / 企业微信 / 邮件推送由部署侧配 channel。

阈值（来自评估 §9-P0-4）：
- 服务不健康（>=2 次连续 health 失败）：critical，立即
- 生成失败率 >5% 持续 5min：critical
- 队列填充 >=85% 持续 5min：warning
- GPU 可用显存 <15% 持续 2min：critical
- 磁盘可用 <15%：critical
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """一条处于 firing/pending 状态的告警。"""

    name: str
    severity: str  # critical | warning
    message: str
    runbook: str
    for_s: float
    since_ts: float
    firing: bool  # 是否已满足 for 时长（正式 firing）
    value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity,
            "message": self.message,
            "runbook": self.runbook,
            "for_s": self.for_s,
            "since_ts": self.since_ts,
            "firing": self.firing,
            "value": self.value,
        }


# runbook 链接（相对仓库 docs/runbooks）
_RUNBOOK = {
    "service_startup": "docs/runbooks/service_startup.md",
    "gpu_oom": "docs/runbooks/gpu_oom.md",
    "queue_overload": "docs/runbooks/queue_overload.md",
    "disk_full": "docs/runbooks/disk_full.md",
    "generation_failures": "docs/runbooks/generation_failures.md",
}


class AlertEngine:
    """无 GPU 依赖的告警状态机。"""

    def __init__(self, notifier: Callable[[Alert], None] | None = None) -> None:
        self._notifier = notifier or self._default_notifier
        self._first_seen: dict[str, float] = {}  # alert name -> 首次触发 ts
        self._notified: set[str] = set()  # 已通知（去重）
        self._lock = threading.Lock()

    @staticmethod
    def _default_notifier(alert: Alert) -> None:
        logger.warning(
            "[ALERT][%s] %s — %s (runbook: %s)",
            alert.severity.upper(), alert.name, alert.message, alert.runbook,
        )

    def set_notifier(self, notifier: Callable[[Alert], None]) -> None:
        self._notifier = notifier

    def _make_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "ServiceUnhealthy",
                "severity": "critical",
                "runbook": _RUNBOOK["service_startup"],
                "for_s": 0.0,
                "check": lambda s: bool(s.get("health_unhealthy")),
                "message": lambda s: "服务健康检查连续失败（>=2 次），可能进程/依赖异常",
                "value": lambda s: 1.0,
            },
            {
                "name": "GenerationFailureRateHigh",
                "severity": "critical",
                "runbook": _RUNBOOK["generation_failures"],
                "for_s": 300.0,
                "check": lambda s: float(s.get("generation_failure_rate", 0.0)) > 0.05,
                "message": lambda s: (
                    f"生成失败率 {float(s.get('generation_failure_rate', 0.0)) * 100:.1f}% "
                    f"超过 5% 阈值（持续 5min）"
                ),
                "value": lambda s: float(s.get("generation_failure_rate", 0.0)),
            },
            {
                "name": "QueueOverloaded",
                "severity": "warning",
                "runbook": _RUNBOOK["queue_overload"],
                "for_s": 300.0,
                "check": lambda s: float(s.get("queue_fill_ratio", 0.0)) >= 0.85,
                "message": lambda s: (
                    f"队列填充率 {float(s.get('queue_fill_ratio', 0.0)) * 100:.0f}% "
                    f">= 85%（持续 5min）"
                ),
                "value": lambda s: float(s.get("queue_fill_ratio", 0.0)),
            },
            {
                "name": "GpuVramLow",
                "severity": "critical",
                "runbook": _RUNBOOK["gpu_oom"],
                "for_s": 120.0,
                "check": lambda s: (
                    s.get("gpu_free_pct") is not None
                    and float(s["gpu_free_pct"]) < 15.0
                ),
                "message": lambda s: (
                    f"GPU 可用显存 {float(s.get('gpu_free_pct', 0.0)):.1f}% < 15%（持续 2min）"
                ),
                "value": lambda s: float(s.get("gpu_free_pct", 0.0)),
            },
            {
                "name": "DiskSpaceLow",
                "severity": "critical",
                "runbook": _RUNBOOK["disk_full"],
                "check": lambda s: (
                    s.get("disk_free_pct") is not None
                    and float(s["disk_free_pct"]) < 15.0
                ),
                "for_s": 0.0,
                "message": lambda s: (
                    f"磁盘可用空间 {float(s.get('disk_free_pct', 0.0)):.1f}% < 15%"
                ),
                "value": lambda s: float(s.get("disk_free_pct", 0.0)),
            },
        ]

    def evaluate(self, snapshot: dict[str, Any]) -> list[Alert]:
        """基于快照评估所有规则，返回当前活跃告警（含 pending）。

        副作用：对状态从非 firing 变为 firing 的告警调用 notifier（去重）。
        """
        now = float(snapshot.get("now", time.time()))
        active: list[Alert] = []
        with self._lock:
            for rule in self._make_rules():
                try:
                    firing_now = bool(rule["check"](snapshot))
                except Exception as e:  # noqa: BLE001
                    logger.debug("alert rule %s check failed: %s", rule["name"], e)
                    firing_now = False

                if not firing_now:
                    # 恢复：清理首触发时间，并补发一次恢复通知（仅对已通知过的）
                    self._first_seen.pop(rule["name"], None)
                    if rule["name"] in self._notified:
                        self._notified.discard(rule["name"])
                        logger.info("[ALERT-RESOLVED] %s", rule["name"])
                    continue

                first = self._first_seen.setdefault(rule["name"], now)
                elapsed = now - first
                is_firing = elapsed >= rule["for_s"]
                alert = Alert(
                    name=rule["name"],
                    severity=rule["severity"],
                    message=rule["message"](snapshot),
                    runbook=rule["runbook"],
                    for_s=rule["for_s"],
                    since_ts=first,
                    firing=is_firing,
                    value=rule["value"](snapshot),
                )
                active.append(alert)
                if is_firing and rule["name"] not in self._notified:
                    self._notified.add(rule["name"])
                    try:
                        self._notifier(alert)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("alert notifier failed: %s", e)
        return active

    def reset(self) -> None:
        with self._lock:
            self._first_seen.clear()
            self._notified.clear()


# ── 健康检查连续失败追踪（供 ServiceUnhealthy 规则） ──────────────
_health_lock = threading.Lock()
_health_failures = 0
_HEALTH_UNHEALTHY_THRESHOLD = 2


def record_health_success() -> None:
    global _health_failures
    with _health_lock:
        _health_failures = 0


def record_health_failure() -> None:
    global _health_failures
    with _health_lock:
        _health_failures += 1


def health_unhealthy() -> bool:
    """连续 health 失败达到阈值即视为不健康。"""
    with _health_lock:
        return _health_failures >= _HEALTH_UNHEALTHY_THRESHOLD


def _reset_health() -> None:
    global _health_failures
    with _health_lock:
        _health_failures = 0


_alert_singleton: AlertEngine | None = None
_alert_lock = threading.Lock()


def get_alert_engine() -> AlertEngine:
    global _alert_singleton
    if _alert_singleton is None:
        with _alert_lock:
            if _alert_singleton is None:
                _alert_singleton = AlertEngine()
    return _alert_singleton


def reset_alert_engine() -> None:
    global _alert_singleton
    with _alert_lock:
        _alert_singleton = None
