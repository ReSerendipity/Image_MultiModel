# 指标字典（metrics_dictionary.md）

> 对应数据治理评估报告 §3.6 / §4.8 / §4.12。统一所有业务指标的计算口径，防止漂移与同名不同义。
> 实时指标见 `observability/metrics.py`（Prometheus 格式）；历史回顾指标由 `metrics_quality.compute_quality_metrics()` 从 `history_db` 聚合。

## 指标定义

| 指标 | 计算逻辑 | 数据来源 | 口径说明 |
|------|---------|----------|----------|
| `total_attempts` | `COUNT(*)` FROM tasks | history_db | 全部任务提交（含失败/取消） |
| `successful_generations` | `COUNT(*) WHERE status='completed'` | history_db | 完成且落盘的任务（**不含** failed/cancelled） |
| `failed_generations` | `COUNT(*) WHERE status='failed'` | history_db | 推理失败（带 `error_code` 聚类） |
| `cancelled_generations` | `COUNT(*) WHERE status='cancelled'` | history_db | 用户取消 |
| `success_rate` | `successful / total` | history_db | **仅计 completed**；前端计数若含 failed 则与之天然不同，属正常差异，需注明 |
| `avg_generation_time_s` | `AVG(processing_time_s) WHERE completed AND >0` | history_db | 均值；分位数（p50/p95/p99）待 `observability` 直方图补充 |
| `lora_usage_frequency` | 按 `tasks.lora_checksums[].name` 计数 | history_db | 多 LoRA 叠加分别计次 |
| `generation_*_total` | Prometheus Counter（submitted/accepted/rejected/started/completed/failed/cancelled） | observability/metrics | 实时计数，命名与 history_db status 对齐 |
| `generation_duration_seconds` | Prometheus Histogram | observability/metrics | 实时生成时长分布 |
| `gpu_memory_used_bytes` / `gpu_memory_total_bytes` | Prometheus Gauge（来自 `gpu_utils`） | observability/metrics | VRAM 实时占用（峰值回溯需历史采样） |
| `gpu_oom_total` | Prometheus Counter | observability/metrics | OOM 事件数 |

## 统一枚举

```
GenerationStatus = { pending, processing, completed, failed, cancelled, interrupted }
```

- `successful_generations` = `completed` 且输出文件存在、size>0
- `total_attempts` = 所有 submission（无论结果）

## 同名不同义澄清（反模式 #4.2）

- 「总生成量」≠「成功生成量」。Dashboard 若直接 `COUNT(tasks)` 会与「成功量」永远不一致，需在标签上显式区分。
- 前端实时计数（Prometheus Counter）与历史回顾计数（history_db 聚合）允许存在时间差（Counter 含进行中任务），不一致属正常。

## 变更流程

任何指标口径变更必须：① 更新本文件；② 同步修改 `metrics_quality.py`；③ 通知相关方。禁止在单点硬编码改口径。
