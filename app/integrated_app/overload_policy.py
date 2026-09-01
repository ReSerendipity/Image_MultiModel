"""
overload_policy.py — 队列分级过载策略（MLOps P1-8）

评估 §9-P1-8：将队列从「硬上限→503」升级为分级过载响应：
- 70%：warning（仅观察，记录指标，不拒绝）
- 85%：限制低优先级 / 大 batch（大 batch 快速拒绝 + Retry-After）
- 95%：快速拒绝（429 + Retry-After）
- 100%：明确 503（队列满）

设计为无副作用的纯函数，便于单测（见 tests/observability/test_overload_policy.py）。

返回结构：
    OverloadDecision(
        action="proceed" | "reject_503" | "reject_429",
        status=200 | 503 | 429,
        reason="ok" | "queue_full" | "queue_95" | "queue_85_large_batch",
        retry_after_s=int,        # 仅在拒绝时 > 0
        tier=0|1|2|3|4,
        message=str,
    )
"""

from __future__ import annotations

from dataclasses import dataclass

# 分级阈值（填充率，0~1）
WARN_RATIO = 0.70
LIMIT_RATIO = 0.85
REJECT_RATIO = 0.95

# 视为「大 batch」的阈值（> 该值视为可被 85% 档限流）
LARGE_BATCH_THRESHOLD = 4

# 默认 Retry-After（秒）：基于典型单图推理时长估算
RETRY_AFTER_S = 10


@dataclass
class OverloadDecision:
    action: str
    status: int
    reason: str
    retry_after_s: int
    tier: int
    message: str


def evaluate_overload(
    fill_ratio: float,
    batch_size: int = 1,
    *,
    maxsize: int = 100,
) -> OverloadDecision:
    """根据队列填充率与请求 profile 决定过载动作。

    Args:
        fill_ratio: 当前队列填充率 = queue_size / maxsize（0~1，>=1 视为满）。
        batch_size: 请求 batch 大小（用于 85% 档的大 batch 限流）。
        maxsize: 队列上限（仅用于说明，不直接参与判定）。

    Returns:
        OverloadDecision。
    """
    if fill_ratio >= 1.0 or maxsize <= 0 and fill_ratio >= 1.0:
        return OverloadDecision(
            action="reject_503",
            status=503,
            reason="queue_full",
            retry_after_s=RETRY_AFTER_S,
            tier=4,
            message="队列已满，请稍后重试（Retry-After 已给出建议间隔）",
        )

    if fill_ratio >= REJECT_RATIO:
        return OverloadDecision(
            action="reject_429",
            status=429,
            reason="queue_95",
            retry_after_s=RETRY_AFTER_S,
            tier=3,
            message="队列接近满载（>=95%），快速拒绝请按 Retry-After 退避",
        )

    if fill_ratio >= LIMIT_RATIO:
        # 85% 档：仅限流大 batch（视为低优先级 / 重负载）
        if batch_size > LARGE_BATCH_THRESHOLD:
            return OverloadDecision(
                action="reject_429",
                status=429,
                reason="queue_85_large_batch",
                retry_after_s=RETRY_AFTER_S,
                tier=2,
                message="队列水位较高（>=85%），大 batch 任务暂缓，请降低 batch_size 或稍后重试",
            )
        # 小 batch 仍放行，但计入 warning 观察
        return OverloadDecision(
            action="proceed",
            status=200,
            reason="ok_warning",
            retry_after_s=0,
            tier=1,
            message="队列水位偏高（>=85%），持续观察",
        )

    if fill_ratio >= WARN_RATIO:
        # 70% 档：仅 warning，正常放行
        return OverloadDecision(
            action="proceed",
            status=200,
            reason="ok_warning",
            retry_after_s=0,
            tier=1,
            message="队列水位偏高（>=70%），持续观察",
        )

    return OverloadDecision(
        action="proceed",
        status=200,
        reason="ok",
        retry_after_s=0,
        tier=0,
        message="队列正常",
    )


def fill_ratio_of(queue_size: int, maxsize: int) -> float:
    """计算填充率（防御除零）。"""
    if maxsize <= 0:
        return 1.0
    return min(1.0, queue_size / maxsize)
