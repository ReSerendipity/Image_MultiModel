"""
test_storage_quota_alert.py — 数据治理报告 P1-5：outputs 配额逼近告警

覆盖：
- dir_size_gb：目录体积统计 / 不存在目录
- evaluate_storage_quota_proximity：超 80% 触发 / 未超不触发 / 预算 0 关闭 /
  删除量字段落进 alert（budget_gb 注入，避免真实配置耦合与巨型测试文件）
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from integrated_app.cost_governance import dir_size_gb, evaluate_storage_quota_proximity


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="quota_test_"))


def _mk_outputs(root: Path, n_files: int, size_bytes: int = 1024) -> Path:
    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        (out / f"img_{i}.png").write_bytes(b"\0" * size_bytes)
    return out


def test_dir_size_gb_counts_recursive() -> None:
    d = _tmp()
    _mk_outputs(d, 10, size_bytes=1024)
    (d / "outputs" / "sub").mkdir()
    (d / "outputs" / "sub" / "x.png").write_bytes(b"\0" * 1024)
    got = dir_size_gb(d / "outputs")
    assert got > 0
    assert abs(got - (11 * 1024) / (1024**3)) < 1e-9


def test_dir_size_gb_missing_dir_is_zero() -> None:
    assert dir_size_gb(_tmp() / "nope") == 0.0


def test_quota_alert_triggers_over_80pct() -> None:
    root = _tmp()
    _mk_outputs(root, 900, size_bytes=1024)  # ≈0.00088GB
    # 预算 0.001GB → 80% 阈值 0.0008GB，0.00088 超过
    alert = evaluate_storage_quota_proximity(root, deleted_tasks=0, budget_gb=0.001)
    assert alert is not None
    assert alert["dimension"] == "storage_gb_quota_proximity"
    assert alert["level"] == "warning"
    assert alert["deleted_tasks"] == 0
    assert alert["used_gb"] > alert["threshold_gb"]


def test_quota_alert_silent_under_threshold() -> None:
    root = _tmp()
    _mk_outputs(root, 10, size_bytes=1024)  # 极小
    assert evaluate_storage_quota_proximity(root, deleted_tasks=0, budget_gb=1.0) is None


def test_quota_alert_disabled_when_budget_zero() -> None:
    root = _tmp()
    _mk_outputs(root, 2000, size_bytes=1024)
    assert evaluate_storage_quota_proximity(root, deleted_tasks=0, budget_gb=0.0) is None


def test_quota_alert_includes_deleted_count() -> None:
    root = _tmp()
    _mk_outputs(root, 900, size_bytes=1024)
    alert = evaluate_storage_quota_proximity(root, deleted_tasks=5, budget_gb=0.001)
    assert alert is not None
    assert alert["deleted_tasks"] == 5
