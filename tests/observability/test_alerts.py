"""
tests/observability/test_alerts.py — 告警评估引擎单元测试

MLOps P0-4：验证 for 时长、去重、恢复判定、健康连续失败追踪，以及 runbook 链接。
无 GPU / 应用依赖。
"""

from __future__ import annotations

import time

from app.integrated_app.observability import alerts as alerts_mod
from app.integrated_app.observability.alerts import AlertEngine, get_alert_engine, reset_alert_engine


def _engine() -> AlertEngine:
    reset_alert_engine()
    return get_alert_engine()


def test_disk_low_fires_immediately():
    eng = _engine()
    alerts = eng.evaluate({"disk_free_pct": 5.0, "now": time.time()})
    names = [a.name for a in alerts]
    assert "DiskSpaceLow" in names
    assert all(a.firing for a in alerts if a.name == "DiskSpaceLow")


def test_queue_overload_requires_for_duration():
    eng = _engine()
    now = time.time()
    # 第一次：触发但 for=300s 未到，不应 firing
    a1 = eng.evaluate({"queue_fill_ratio": 0.95, "now": now})
    q1 = [a for a in a1 if a.name == "QueueOverloaded"][0]
    assert q1.firing is False
    # 超过 for 时长后 firing
    a2 = eng.evaluate({"queue_fill_ratio": 0.95, "now": now + 301})
    q2 = [a for a in a2 if a.name == "QueueOverloaded"][0]
    assert q2.firing is True


def test_alert_recovery_clears_state():
    eng = _engine()
    now = time.time()
    eng.evaluate({"queue_fill_ratio": 0.95, "now": now})
    eng.evaluate({"queue_fill_ratio": 0.95, "now": now + 301})
    assert any(a.firing for a in eng.evaluate({"queue_fill_ratio": 0.95, "now": now + 302}))
    # 恢复：填充率下降
    cleared = eng.evaluate({"queue_fill_ratio": 0.3, "now": now + 303})
    assert not any(a.name == "QueueOverloaded" for a in cleared)


def test_notifier_dedup_called_once():
    eng = _engine()
    calls = []
    eng.set_notifier(lambda a: calls.append(a.name))
    now = time.time()
    eng.evaluate({"disk_free_pct": 3.0, "now": now})
    eng.evaluate({"disk_free_pct": 3.0, "now": now + 1})
    # 同一条告警 firing 后只通知一次
    assert calls.count("DiskSpaceLow") == 1


def test_generation_failure_rate_rule():
    eng = _engine()
    now = time.time()
    # 失败率 > 5% 持续 5min
    alerts = eng.evaluate({"generation_failure_rate": 0.2, "now": now + 400})
    assert "GenerationFailureRateHigh" in [a.name for a in alerts]


def test_health_unhealthy_after_threshold():
    alerts_mod._reset_health()
    alerts_mod.record_health_failure()
    assert alerts_mod.health_unhealthy() is False
    alerts_mod.record_health_failure()
    assert alerts_mod.health_unhealthy() is True
    alerts_mod.record_health_success()
    assert alerts_mod.health_unhealthy() is False


def test_all_rules_have_runbook_links():
    eng = AlertEngine()
    # 触发每一条规则，确认都有 runbook
    snapshot = {
        "health_unhealthy": True,
        "generation_failure_rate": 0.5,
        "queue_fill_ratio": 0.95,
        "gpu_free_pct": 5.0,
        "disk_free_pct": 5.0,
        "now": time.time(),
    }
    alerts = eng.evaluate(snapshot)
    assert len(alerts) >= 5
    for a in alerts:
        assert a.runbook.startswith("docs/runbooks/"), a.runbook
