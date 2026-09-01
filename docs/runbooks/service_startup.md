# Runbook: 服务启动失败 / 健康检查失败（告警 `ServiceUnhealthy`）

> 关联告警：`ServiceUnhealthy`（critical，连续 health 失败 >=2 次）
> 关联指标：`health_unhealthy`（进程内计数）、`/api/health` 状态码

## 1. 症状（Symptom）
- `/api/alerts` 出现 `ServiceUnhealthy` 且 `firing=true`。
- `GET /api/health` 返回非 200，或返回体中 `status != ok`。
- 启动日志出现 `create_app` / `lifespan` 异常、导入错误、配置校验失败。
- CI 中 `startup-smoke` / `config-refs` job 失败。

## 2. 确认命令（Confirm）
```bash
# 健康检查
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8288/api/health
curl -s http://127.0.0.1:8288/api/health | python -m json.tool

# 配置字段引用完整性（P0-1 回归）
python scripts/check_config_refs.py

# 进程与端口
# Windows
netstat -ano | findstr :8288
# Linux
ss -ltnp | grep 8288

# 启动日志
tail -n 100 logs/*.log
```

## 3. 影响判断（Impact）
- 启动失败 = 全部流量不可用（单实例）。
- 健康检查失败可能是依赖（GPU 驱动 / 模型路径 / SQLite）不可用，或进程假死。
- 若 `config.runtime.idle_unload_minutes` 等字段缺失，会直接 `AttributeError` 导致启动失败（P0-1 已修复，由 `check_config_refs.py` 守护）。

## 4. 临时缓解（Mitigate）
1. 先用 `check_config_refs.py` 排除配置契约回归。
2. 确认 `model/`、`comfy_kernel/` 路径存在且权重完整（`ModelFormatConfig.verify_weights`）。
3. 确认 GPU 驱动可用：`nvidia-smi`。
4. 以假引擎快速验证应用层（非 GPU 问题）：
   ```bash
   IMM_FAKE_ENGINE=1 python app/clean_launch.py
   curl -s http://127.0.0.1:8288/api/health
   ```

## 5. 回滚 / 重启（Rollback / Restart）
- 优先回滚到 last-known-good 版本（见 P2-12 blue-green / 不可变镜像 tag P1-10）。
- 重启：
  ```bash
  # Windows
  start.bat
  # Linux
  ./start.sh
  ```
- 回滚后必须重跑 startup-smoke（boot → health → 假任务 → 关闭）。

## 6. 数据保护（Data Protection）
- 回滚**只**涉及应用代码/配置/镜像，不动 `outputs/`、`data/*.db`、`model/`。
- 回滚后校验 history DB 可查询（见 P2-13）。

## 7. 恢复验证（Verify）
- `GET /api/health` 稳定返回 200 且 `status=ok`。
- `/api/alerts` 中 `ServiceUnhealthy` 消失。
- startup-smoke 全绿；`/api/metrics/prometheus` 可抓取。

## 8. 升级联系人（Escalation）
- P1：通知值班（on-call）。
- P0（启动持续失败 >5min 影响线上）：升级服务 Owner，触发回滚决策。
- 每次启动失败事故写 post-mortem（`docs/ops/post_mortem_template.md`）。
