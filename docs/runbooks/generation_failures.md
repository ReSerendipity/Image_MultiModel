# Runbook: 生成失败率过高（告警 `GenerationFailureRateHigh`）

> 关联告警：`GenerationFailureRateHigh`（critical，生成失败率 >5% 持续 5min）
> 关联指标：`generation_failed_total`、`generation_completed_total`、
>           `generation_duration_seconds`、`queue_rejected_total`
> 错误分类（`classify_generation_error`）：oom / timeout / cancel /
>           content_filter / weight_integrity / model_load / inference_error

## 1. 症状（Symptom）
- `/api/alerts` 出现 `GenerationFailureRateHigh` 且 `firing=true`。
- `generation_failed_total` 增长率明显高于 `generation_completed_total`。
- 用户侧大量任务进入 `failed` 状态（非 `cancelled` / 非 4xx 拒绝）。

## 2. 确认命令（Confirm）
```bash
curl -s http://127.0.0.1:8288/api/metrics/prometheus | grep -E "generation_(failed|completed|submitted)_total"
# 错误分类分布（若 expose 了 error_code 维度）
curl -s http://127.0.0.1:8288/api/metrics/prometheus | grep "generation_failed_total"
# 单任务详情
curl -s http://127.0.0.1:8288/api/tasks/<task_id> | python -m json.tool
# 应用日志中的错误分类
grep -E "classify_generation_error|weight_integrity|model_load" logs/*.log | tail -n 50
```

## 3. 影响判断（Impact）
- 失败率 >5% 持续 = SLO（Generation success rate ≥98%）被破坏风险。
- 区分失败来源：
  - `oom` / `weight_integrity` / `model_load` → 基础设施/权重问题（见 gpu_oom / service_startup）。
  - `timeout` → 任务超时配置过宽或下游慢（见 queue_overload）。
  - `content_filter` → 内容策略拒绝（**不计入** SLO 失败分母）。
  - `cancel` → 用户主动取消（**不计入** 失败分母）。

## 4. 临时缓解（Mitigate）
1. 先按 error_code 聚类，定位主因（优先 `oom`/`model_load`/`weight_integrity`）。
2. `oom` → 参照 `gpu_oom.md` 降压。
3. `model_load` / `weight_integrity` → 校验 `model/` 权重（SHA256 manifest，`ModelFormatConfig.verify_weights`），必要时回滚到 last-known-good 权重。
4. `timeout` → 收紧 `runtime.task_queue.max_timeout_s`（默认过宽 86400s）或降负载。

## 5. 回滚 / 重启（Rollback / Restart）
- 权重问题：回滚镜像/权重到 last-known-good（P1-10 不可变 artifact + P2-12 回滚）。
- 应用问题：回滚应用版本并重启（见 `service_startup.md`）。

## 6. 数据保护（Data Protection）
- 失败任务不落盘，无数据丢失风险。
- 权重回滚前备份 `model/` 与相关 manifest。

## 7. 恢复验证（Verify）
- `GenerationFailureRateHigh` 在 `/api/alerts` 中 resolved。
- 失败率回落到 <5%，连续 5min 稳定。
- 提交测试任务成功完成，`generation_completed_total` 增长。
- 各类 error_code 计数回归基线。

## 8. 升级联系人（Escalation）
- P1：值班定位主因并执行缓解。
- P0（失败率 >20% 或影响外部用户）：升级服务 Owner + 基础设施，触发回滚。
- 写 post-mortem（`docs/ops/post_mortem_template.md`）。
