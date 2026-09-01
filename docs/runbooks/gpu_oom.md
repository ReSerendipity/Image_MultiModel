# Runbook: GPU OOM / 显存泄漏（告警 `GpuVramLow`）

> 关联告警：`GpuVramLow`（critical，GPU 可用显存 <15% 持续 2min）
> 关联指标：`gpu_memory_used_bytes`、`gpu_oom_total`、`sse_events_dropped_total`

## 1. 症状（Symptom）
- 告警面板 / `/api/alerts` 出现 `GpuVramLow` 且 `firing=true`。
- `/api/metrics/prometheus` 中 `gpu_memory_used_bytes` 接近 `gpu_memory_total_bytes`。
- 生成任务开始返回 `vram_insufficient`（4xx）或直接被引擎层 OOM 终止。
- 日志出现 CUDA out of memory / allocator 相关错误。

## 2. 确认命令（Confirm）
```bash
# 实时显存占用
nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu \
  --format=csv

# 抓取指标快照
curl -s http://127.0.0.1:8288/api/metrics/prometheus | grep -E "gpu_memory_(used|total)_bytes"
curl -s http://127.0.0.1:8288/api/alerts | python -m json.tool

# 当前队列与进行中任务
curl -s http://127.0.0.1:8288/api/health | python -m json.tool
```

## 3. 影响判断（Impact）
- **单 GPU 单实例**：OOM 会直接杀死当前推理，导致进行中任务失败并计入失败率。
- 若 `vram_scheduler.enabled=true`，高水位会触发降 batch / 限流，吞吐下降但一般不致命。
- 若持续 OOM 且未隔离，会反复触发 `GenerationFailureRateHigh`，进入告警风暴。

## 4. 临时缓解（Mitigate）
1. 立即降低并发入口：临时下调 `config.yaml → runtime.task_queue.maxsize` 与限流 `infer_per_minute`（需重启生效，见第 5 节）。
2. 启用 VRAM 调度（若未启用）：`runtime.vram_scheduler.enabled=true`，`vram_high_watermark_pct=90`。
3. 手动释放常驻权重（不会中断已 accepted 任务）：
   - 通过运维接口或重启空闲卸载守护：`runtime.idle_unload_minutes` 设较小值（如 5），等待 `IdleUnloadManager` 触发。
4. 若大 batch / 高分辨率是主因，引导用户降 batch_size 或分辨率。

## 5. 回滚 / 重启（Rollback / Restart）
```bash
# 优雅重启（保存 outputs / history，不丢数据）
# Windows
start.bat
# Linux
./start.sh

# 重启后确认健康
curl -s http://127.0.0.1:8288/api/health | grep -q '"status":"ok"' && echo "HEALTHY"
```
- 重启前确认无正在写入的 checkpoint；重启会触发 `TaskQueue` 恢复未完成任务（checkpoint 机制）。
- 模型权重为 portable（`model/`），重启不会变更权重；如怀疑权重损坏，先跑 `ModelFormatConfig.verify_weights` 校验。

## 6. 数据保护（Data Protection）
- **不要**删除 `outputs/`、`data/*.db`、`model/`。
- 重启前备份 history DB：`cp data/history.db data/history.db.bak-$(date +%s)`（见 P2-13 备份治理）。
- OOM 不应影响已落盘图片；恢复后核对 outputs 与 history 记录一致性。

## 7. 恢复验证（Verify）
- `GpuVramLow` 在 `/api/alerts` 中消失（或转为 pending/resolved）。
- `gpu_memory_used_bytes` 回落到 <85% 水位以下。
- 提交一个假引擎/小图生成任务成功完成，且 `generation_completed_total` 增长。
- 连续 10 分钟无新 OOM 日志。

## 8. 升级联系人（Escalation）
- P1：通知值班（on-call，见 `docs/ops/oncall.md`）。
- P0（OOM 持续 >15min 且生成成功率跌破 98%）：升级到服务 Owner + 基础设施。
- 事后必须填写 post-mortem（`docs/ops/post_mortem_template.md`）。
