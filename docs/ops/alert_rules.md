# 告警规则与阈值（P2-14）

> 与 `app/integrated_app/observability/alerts.py` 逐条对齐（代码为单一事实来源，
> 修改阈值必须同步本文件）。评估依据：§4 监控告警体系、§9-P0-4。

## 规则总览

| # | 规则 | severity | 触发条件 | for 持续 | 恢复判定 | Runbook |
|---|---|---|---|---|---|---|
| 1 | ServiceUnhealthy | critical | 健康检查连续失败 ≥2 次 | 立即 | 健康检查成功即 `[ALERT-RESOLVED]` | docs/runbooks/service_startup.md |
| 2 | GenerationFailureRateHigh | critical | 生成失败率 > 5% | 300s | 失败率 ≤5% | docs/runbooks/generation_failures.md |
| 3 | QueueOverloaded | warning | 队列填充率 ≥ 85% | 300s | 填充率 < 85% | docs/runbooks/queue_overload.md |
| 4 | GpuVramLow | critical | GPU 可用显存 < 15% | 120s | ≥15% | docs/runbooks/gpu_oom.md |
| 5 | DiskSpaceLow | critical | 磁盘可用 < 15% | 立即 | ≥15% | docs/runbooks/disk_full.md |

## 阈值依据

- **5% 失败率 / 5min**：单任务偶发失败可容忍；持续 5 分钟 >5% 说明系统性故障
  （模型损坏、依赖异常），而非用户 prompt 触发（内容安全拒绝计入 rejected，不计失败率）。
- **85% 队列 / 5min**：与 P1-8 分级过载 85% 档（LIMIT_RATIO）对齐 —— 服务端开始
  拒大 batch 的同时发出告警，值班有 ~15% 余量时间介入；100% 时已有 429/503。
- **15% 显存 / 2min**：低于此水位下一个 1024px b2 任务大概率 OOM；2min 避开瞬时毛刺。
- **15% 磁盘 / 立即**：输出落盘是硬失败条件，且磁盘不会自愈，不等待。

## 告警生命周期（去重疲劳，评估反模式 #1）

1. `for_s`：条件须**持续**满足才转正式 firing（pending 期间只在 `/api/alerts` 可见，不通知）；
2. **去重**：`_notified` set 保证同一规则 firing 期间只通知一次；
3. **恢复通知**：条件消失记 `[ALERT-RESOLVED]` 并出 `_notified`，下次再触发会重新通知；
4. 每条告警自带 `runbook` 链接 + `value`（当前观测值）+ `since_ts`，值班无需盲查。

## 查看方式

```bash
curl -s http://127.0.0.1:8288/api/alerts | python -m json.tool
# alerts[].{name,severity,message,runbook,firing,value,since_ts}
# firing_count / snapshot（各信号当前值）/ generation_health（分母明细）
```

Prometheus 抓取端：`GET /api/metrics/prometheus`（指标与 SLO 定义见 [slo.md](slo.md)）。

## 变更流程

调整阈值属于运维契约变更：改 `alerts.py` → 跑 `tests/observability/test_alerts.py` →
同步本文件 → 若影响晋级门禁同步 `scripts/deploy/bluegreen.sh` 观察窗口清单 →
PR 附容量基线依据（引用 docs/ops/capacity_baseline.md）。
