# Runbook: 队列堆积 / 队列满（告警 `QueueOverloaded`）

> 关联告警：`QueueOverloaded`（warning，队列填充率 >=85% 持续 5min）
> 关联指标：`queue_depth`、`queue_rejected_total`、`queue_oldest_age_seconds`

## 1. 症状（Symptom）
- `/api/alerts` 出现 `QueueOverloaded` 且 `firing=true`。
- `queue_depth` 接近 `runtime.task_queue.maxsize`（默认 100）。
- 生成请求返回 **503**（队列满拒绝），客户端收到 `Retry-After`。
- 任务端到端延迟 P95/P99 显著升高，`queue_oldest_age_seconds` 增大。

## 2. 确认命令（Confirm）
```bash
curl -s http://127.0.0.1:8288/api/metrics/prometheus | grep -E "^queue_(depth|rejected_total|oldest_age_seconds)"
curl -s http://127.0.0.1:8288/api/health | python -m json.tool   # 看 queue 段
# 拒绝计数按原因
curl -s http://127.0.0.1:8288/api/metrics/prometheus | grep "queue_rejected_total"
```

## 3. 影响判断（Impact）
- 单 Worker 串行队列：队列深 = 用户等待长，但**不会** OOM（与 GPU 解耦）。
- 85% 仅 warning；95% 起进入快速拒绝（返回 503 + Retry-After）；100% 全部拒绝。
- 若 oldest age 持续攀升，说明下游推理慢（GPU 慢 / 大 batch / 模型重载）。

## 4. 临时缓解（Mitigate）
按分级过载策略（评估 §9-P1-8）：
- **70%**：观察，准备限流；后台评估是否大 batch 拖慢。
- **85%（当前告警）**：限制低优先级 / 大 batch 任务；下调 `infer_per_minute`。
- **95%**：对新增提交快速拒绝并返回 `Retry-After`（已默认开启）。
- 客户端应实现指数退避，**禁止**服务端+客户端双重重试（雪崩风险）。
- 临时扩容：若有多实例能力，增加实例并前置负载均衡（当前为单实例定位）。

## 5. 回滚 / 重启（Rollback / Restart）
- 队列本身无需重启；优先通过限流与拒绝降压。
- 若需清空积压（会丢失未完成任务）：仅在确认可丢弃时重启服务，`TaskQueue` 会尝试从 checkpoint 恢复。

## 6. 数据保护（Data Protection）
- 拒绝的请求不会被持久化（不算失败率分母，符合 SLO 排除项）。
- 不要手动删除 `outputs/` 以“腾队列”；队列是内存结构，与落盘无关。

## 7. 恢复验证（Verify）
- `queue_depth` 回落到 <70%，`QueueOverloaded` 在 `/api/alerts` 中 resolved。
- 提交测试任务成功（非 503），`generation_completed_total` 增长。
- `queue_oldest_age_seconds` 回到正常区间（< 配置 cancel/超时量级）。

## 8. 升级联系人（Escalation）
- P2：值班观察，按 §4 分级处理。
- P1：若 95% 持续 >10min 或拒绝率异常高，升级到服务 Owner。
- 事后复盘容量基线是否偏低（见 P1-9 容量基线 runner）。
