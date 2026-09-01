# 单机容量基线（P1-9）

> 生成命令：`python scripts/capacity_baseline.py [--runs 100] [--quick] [--latency-budget 30] [--out ...]`
> 结果产物：`perf/results/capacity_baseline.json`（生成物，不入库；`.gitignore` 已忽略 `perf/results/*.json`）
> 回归测试：`tests/observability/test_capacity_baseline.py`

## 1. 覆盖范围

报告要求覆盖「引擎 × 分辨率 × batch × LoRA × SeedVR2」五个维度，runner 的 profile 矩阵由两部分组成：

| 矩阵来源 | profile 命名 | 覆盖维度 |
|---|---|---|
| `build_matrix()` | `{256,512,1024}px_b{1,2}`（6 个） | 分辨率 × batch |
| `build_postprocess_matrix()` | `1024px_b1_seedvr2_on` / `1024px_b1_seedvr2_off` | SeedVR2 后处理开关 |
| `build_postprocess_matrix()` | `1024px_b1_lora1`（**仅当** `model/loras/` 下存在权重时自动加入） | LoRA |

- **引擎维度**：当前版本仅单一引擎 `z_image_turbo_native`（AGENTS.md §1），矩阵中所有 profile 固定该引擎。新增引擎时只需扩展 `build_matrix()` 的 `engine_name` 循环。
- **LoRA 维度**：`discover_lora_names()` 扫描 `model/loras/*.{safetensors,ckpt,pt,bin}`，无权重时自动跳过该 profile（避免基线因缺权重而误报失败）。

## 2. 采集指标

每个 profile 逐轮记录并在 `ProfileResult` 中聚合：

| 指标 | 字段 | 说明 |
|---|---|---|
| 完成 / 失败 / OOM 计数 | `completed` / `failed` / `oom` | 失败原因含 `oom` 时单独计入 `oom` |
| P50 / P95 / P99 端到端延迟 | `p50_s` / `p95_s` / `p99_s` | 从提交请求到任务终态的墙钟时间 |
| 吞吐 | `throughput_tps` | `completed / Σlatency` |
| 首预览时间 | `first_preview_avg_s` | 首次观测到 `progress >= 1` 的时间 |
| 落盘时间 | `persist_avg_s` | `completed_at - started_at` 均值 |
| 峰值显存 | `peak_vram_gb` | `torch.cuda.max_memory_allocated()`；**无 CUDA 时恒为 0.0**，报告会显式标记 `vram_measured: false` |

> ⚠️ 在 CI / CPU 环境（`IMM_FAKE_ENGINE=1`）下，除峰值显存外的指标均为 FakeEngine 的相对值，**只能用于回归对比，不能作为真实容量结论**。真实容量必须在目标 GPU 机型上复跑。

## 3. 容量公式

```
concurrency      = 1                       # 单 Worker 串行（AGENTS.md §3 硬约束 #4）
safe_queue_depth = floor(latency_budget_s / slowest_p95_s) * concurrency
expansion_trigger_depth = floor(safe_queue_depth * 0.85)   # 与分级过载 85% 档对齐
```

- `latency_budget_s` 默认 30s（`--latency-budget` 覆盖），对应「用户可容忍的最大排队等待」。
- 取**最慢** profile 的 P95（最保守），而非均值。
- 扩容触发点取 85%，与 `overload_policy.LIMIT_RATIO` 对齐，保证告警先于容量耗尽触发。

## 4. 最近一次基线结果（CI / FakeEngine，`--quick` 6 runs/profile）

| profile | completed | P50 | P95 | P99 | 吞吐 | OOM | 峰值显存 |
|---|---|---|---|---|---|---|---|
| 256px_b1 | 6/6 | 211ms | 245ms | 245ms | 5.09/s | 0 | 不可用 |
| 256px_b2 | 6/6 | 242ms | 256ms | 256ms | 4.13/s | 0 | 不可用 |
| 512px_b1 | 6/6 | 230ms | 248ms | 248ms | 4.74/s | 0 | 不可用 |
| 512px_b2 | 6/6 | 267ms | 306ms | 306ms | 3.72/s | 0 | 不可用 |
| 1024px_b1 | 6/6 | 234ms | 326ms | 326ms | 4.00/s | 0 | 不可用 |
| 1024px_b2 | 6/6 | 233ms | 295ms | 295ms | 4.27/s | 0 | 不可用 |
| 1024px_b1_seedvr2_on | 6/6 | 244ms | 416ms | 416ms | 3.73/s | 0 | 不可用 |
| 1024px_b1_seedvr2_off | 6/6 | 250ms | 261ms | 261ms | 4.02/s | 0 | 不可用 |

推导结论（`latency_budget_s = 30`）：

- 最慢 profile P95 = **416ms**（`1024px_b1_seedvr2_on`，SeedVR2 后处理是主要放大器）
- **最大安全队列深度 = 72**
- **扩容触发深度（85%）= 61**

## 5. 落地动作

1. `runtime.task_queue.maxsize` 应 ≤ 推导出的安全队列深度；当 P95 恶化导致深度下降时，需同步下调或水平扩容。
2. 每次发版前在目标 GPU 机型执行 `--runs 100` 完整基线，把结论回填本文件第 4 节。
3. 若 `peak_vram_gb` 逼近显卡总显存 × 0.9，触发 `docs/runbooks/gpu_oom.md` 的预防性动作（降 batch / 关 SeedVR2）。

## 6. 已知限制

- Windows + pytest 的 `tmp_path` / `tmp_path_factory` 在会话结束时清理 `pytest-current` 符号链接会抛 `PermissionError [WinError 5]`；本 runner 的测试改用 `tempfile.mkdtemp()` 自建目录规避。
- 单一 profile 内串行提交（等待上一任务终态再提交下一个），避免 runner 自身把队列填满导致 429/503 污染计数；对偶发的 429/503 会 sleep 0.5s 重试一次。
