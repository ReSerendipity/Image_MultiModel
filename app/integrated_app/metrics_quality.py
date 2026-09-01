"""
metrics_quality.py — 业务指标统一聚合（数据治理 §3.6 / 长期-指标单一来源）

提供从 ``HistoryDB`` 派生业务指标的**唯一聚合入口**，避免各模块各自重算导致口径漂移
（反模式 #4.12）。与 ``observability/metrics.py``（Prometheus 实时计数器）互补：
此处面向「历史回顾 / 报表」视角，从数据库聚合成功率、平均生成时长、LoRA 使用频次等。

指标口径（统一术语，呼应 metrics_dictionary.md）：
- successful_generations = status='completed' 且 processing_time_s>0 的任务
- total_attempts        = tasks 表全部记录
- success_rate          = successful / total
- lora_usage_frequency  = 按 tasks.lora_checksums 中各 LoRA 名计数（多 LoRA 叠加分别计次）
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def compute_quality_metrics(history_db: Any) -> dict[str, Any]:
    """从 history_db 聚合业务指标。

    Args:
        history_db: ``HistoryDB`` 实例。

    Returns:
        指标字典（见模块 docstring 口径定义）。
    """
    conn = history_db.conn
    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0]
    cancelled = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='cancelled'").fetchone()[0]
    avg_dur = conn.execute(
        "SELECT AVG(processing_time_s) FROM tasks WHERE status='completed' AND processing_time_s > 0"
    ).fetchone()[0]

    lora_usage: dict[str, int] = {}
    rows = conn.execute(
        "SELECT lora_checksums FROM tasks WHERE lora_checksums IS NOT NULL AND lora_checksums != '[]'"
    ).fetchall()
    for (blob,) in rows:
        try:
            for rec in json.loads(blob):
                n = rec.get("name")
                if n:
                    lora_usage[n] = lora_usage.get(n, 0) + 1
        except Exception:  # noqa: BLE001 - 单条脏数据不影响整体聚合
            continue

    success_rate = (completed / total) if total else 0.0
    return {
        "total_attempts": total,
        "successful_generations": completed,
        "failed_generations": failed,
        "cancelled_generations": cancelled,
        "success_rate": success_rate,
        "avg_generation_time_s": float(avg_dur) if avg_dur is not None else 0.0,
        "lora_usage_frequency": lora_usage,
    }
