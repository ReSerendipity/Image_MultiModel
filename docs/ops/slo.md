# SLO 定义与错误预算（正式版）

> 评估依据：`OPS_STABILITY_ASSESSMENT_v2.0.0.md` §4.3（建议值）+ §10 验收清单
> 「SLO、分母、排除项、错误预算和告警阈值已文档化」。
> 所有指标均可从 `GET /api/metrics/prometheus` 直接计算（P0-3 交付），不依赖手工读 SQLite。
> 告警阈值联动规则见 [alert_rules.md](alert_rules.md)。

## 1. 服务定位与承诺级别

单 GPU、单实例、单 Worker 串行推理服务。**不对外承诺 99.9% SLA**；
本文件为「内部/试运行」基线（报告原话），连续 2 个月达标后方可讨论对外承诺。

- 统计窗口：自然月滚动（latency 类）+ 30 天滚动（availability）；
- 维护窗口：每周二 04:00–05:00 UTC（发布/演练时段），从 availability 分母扣除；
- 计算频率：每日由 cron 汇总一次，写入 ops 看板（计划，未实现——当前人工周会核对）。

## 2. SLO 表

| # | SLO | 目标 | 计算式（PromQL 风格） | 分母/排除项 |
|---|---|---|---|---|
| S1 | API availability | 月度 ≥ 99.5% | `1 - avg_over_time(up[30d])` 反向，或 `http_requests_total{status=~"5.."} / http_requests_total` 的失败分钟占比 | 维护窗口扣除；纯 4xx 客户端错误不算不可用；**503 队列满算不可用**（容量也是可用性） |
| S2 | Generation success rate | ≥ 98.0% | `generation_completed_total / (generation_completed_total + generation_failed_total)` | 排除 `generation_cancelled_total`（用户主动取消）与 `generation_rejected_total{reason="content_policy"}`（内容策略）；**不排除**队列拒绝/503（计入服务侧失败）；失败按 error_code 分类，参数 4xx 在提交端拦截不入分母 |
| S3 | Submit latency | P99 ≤ 1s | `histogram_quantile(0.99, http_request_duration_seconds{route="/api/generate"})` | 从收到请求到返回 task_id/明确拒绝；不含推理时间 |
| S4 | Queue wait | P95 ≤ 30s，P99 ≤ 120s | `histogram_quantile(0.95, generation_queue_wait_seconds)` | 按引擎/分辨率/batch 分层看（label: engine；分辨率经 payload 关联暂在容量报告层做）；队列满直接拒绝单列为 S1 |
| S5 | E2E generation | 按 profile 定义 | `histogram_quantile(0.95/0.99, generation_duration_seconds)` | profile 基线值来自 `docs/ops/capacity_baseline.md`，每次有 GPU 全量基线（--runs 100）后更新：当前 1024px b1 P95 预算 **真实 GPU 待测**（fake 引擎数据仅回归用） |
| S6 | First preview | P99 ≤ 5s | `generation_first_preview_total / generation_started_total` 的到达时间分布（事件时间戳差） | 从任务 started 到首个有效 preview SSE 事件 |
| S7 | Cancellation | P95 ≤ 5s | cancel 调用 → status=cancelled 的时延（task 事件日志聚合） | 必须同时验证 GPU 释放与 Worker 可继续接单（runbook 演练口径） |

## 3. 错误预算

| SLO | 目标 | 月度错误预算 | 预算耗尽后果 |
|---|---|---|---|
| S1 99.5% | ≥99.5% | ≤ 3.65 h/月 不可用 | 冻结功能发布，只做稳定性工作；下月首个发布需 Tech Lead 批准 |
| S2 98% | ≥98% | ≤ 2% 任务失败 | 同上，且必须产出 post-mortem（P0/P1 级流程） |
| S4 队列等待 | P95≤30s | 连续 5min>30s 的分钟数 ≤ 432/月（2%） | 触发容量评审：对照 capacity_baseline.md 调整 maxsize 或扩容 |

- 预算消耗 >50% 时：当周禁止高风险变更（模型升级、依赖大版本）；
- 预算剩余为负：只允许回滚与修复类变更。

## 4. 与告警的映射（SLO → alert rule）

| SLO | 守护告警 | 阈值联动 |
|---|---|---|
| S1 | ServiceUnhealthy | 健康检查连续失败 ≥2 次即 critical |
| S2 | GenerationFailureRateHigh | >5%/5min ≈ 预算 2% 的实时哨兵 |
| S4/S1 | QueueOverloaded | ≥85%/5min，先于 100% 拒绝触发 |
| S5 | （观察）GpuVramLow + P99 手工周报 | 真实 GPU 基线建立后加 P99LatencyHigh |
| — | DiskSpaceLow | S1 的前置保护（磁盘满是必然故障） |

## 5. 变更记录

| 日期 | 变更 | 依据 |
|---|---|---|
| 2026-09-01 | 首次正式化：采纳报告 §4.3 全部建议值；补齐分母/排除项/错误预算/告警映射 | OPS_STABILITY_ASSESSMENT §4.3、§9-P0-3、§10 |

> ⚠️ 本文件生效的前提是 S5 的真实 GPU 基线：当前容量基线（perf 环境）只能证明
> **测量链路正确**，显存与延迟绝对值需在目标机型复跑 `capacity_baseline.py --runs 100` 后回填。
