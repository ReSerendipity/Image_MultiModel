"""
test_cron_backfill.py — 数据治理报告 P2-3：自实现 cron 补跑（misfire）

覆盖 _compute_cron_next_run 纯函数：
- 当日槽位未到 → (今日槽位, False)
- 当日槽位已过 → (明日槽位, True) —— 补跑判定依据
- 恰好等于槽位时刻 → 视为已过（立即执行，sleep 0）
- 通配符字段 → 维持旧行为，无补跑语义
"""

from __future__ import annotations

import datetime
from typing import Any

from integrated_app.app_server import _compute_cron_next_run


def _at(h: int, m: int) -> Any:
    return datetime.datetime(2026, 9, 5, h, m, 0, 0)


class TestComputeCronNextRun:
    def test_before_slot_same_day(self) -> None:
        nxt, missed = _compute_cron_next_run(_at(1, 0), "0", "3")
        assert nxt == _at(3, 0)
        assert missed is False

    def test_after_slot_missed_today(self) -> None:
        """跨 03:00 启动（如 11:55）→ 当日槽位已过，应判定补跑"""
        nxt, missed = _compute_cron_next_run(_at(11, 55), "0", "3")
        assert nxt == datetime.datetime(2026, 9, 6, 3, 0)
        assert missed is True

    def test_exactly_at_slot_counts_as_missed(self) -> None:
        """恰在槽位秒级边界 → 立即执行（sleep 0）语义一致"""
        nxt, missed = _compute_cron_next_run(_at(3, 0), "0", "3")
        assert nxt == datetime.datetime(2026, 9, 6, 3, 0)
        assert missed is True

    def test_wildcard_hour_no_backfill(self) -> None:
        nxt, missed = _compute_cron_next_run(_at(11, 55), "30", "*")
        assert missed is False
        assert nxt.minute == 30

    def test_wildcard_minute_no_backfill(self) -> None:
        nxt, missed = _compute_cron_next_run(_at(11, 55), "*", "3")
        assert missed is False
        assert nxt.hour == 3
