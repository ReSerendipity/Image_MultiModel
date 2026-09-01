# Runbook 索引（运维应急响应）

> 评估 §9-P1-6 / §9-P0-4：每条 P0/P1 告警都必须链接到 Runbook。
> 告警引擎在 `app/integrated_app/observability/alerts.py` 中引用本目录。

| 告警名 | 严重度 | Runbook | 触发条件 |
|--------|--------|---------|----------|
| `ServiceUnhealthy` | critical | [service_startup.md](service_startup.md) | 健康检查连续失败 >=2 次 |
| `GpuVramLow` | critical | [gpu_oom.md](gpu_oom.md) | GPU 可用显存 <15% 持续 2min |
| `GenerationFailureRateHigh` | critical | [generation_failures.md](generation_failures.md) | 生成失败率 >5% 持续 5min |
| `QueueOverloaded` | warning | [queue_overload.md](queue_overload.md) | 队列填充率 >=85% 持续 5min |
| `DiskSpaceLow` | critical | [disk_full.md](disk_full.md) | 磁盘可用空间 <15% |

## 每套 Runbook 必备章节
症状 → 确认命令 → 影响判断 → 临时缓解 → 回滚/重启 → 数据保护 → 恢复验证 → 升级联系人。

## 关联文档
- 告警规则与阈值：[../ops/alert_rules.md](../ops/alert_rules.md)
- on-call 与升级：[../ops/oncall.md](../ops/oncall.md)
- post-mortem 模板：[../ops/post_mortem_template.md](../ops/post_mortem_template.md)
