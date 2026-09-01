# Blue-Green 部署与一键回滚（P2-12）

> 评估依据：`OPS_STABILITY_ASSESSMENT_v2.0.0.md` §9-P2-12
> 实现：`docker-compose.bluegreen.yml` + `scripts/deploy/bluegreen.sh`
> 门禁联动：`scripts/post_deploy_smoke.py`（P2-11）+ `/api/alerts`（P0-4）+ 不可变 tag（P1-10）

## 1. 单 GPU 场景的 blue-green 变体

一块 GPU 无法同时常驻两份 Z-Image Turbo 9B 权重，因此不做「双活」，而是报告允许的
**最小实现**：

```
                    对外 :8288
active 槽 (imm-blue)  ┌─────────────┐   持续服务，promote 时才停（秒级窗口）
                      └─────────────┘
idle 槽 (imm-green)   内部 :8289    ── 新版本先在此起服 + 独立健康检查
```

## 2. deploy 流程（`bluegreen.sh deploy <tag>`）

| 步骤 | 动作 | 失败处理 |
|---|---|---|
| 0 | 拒绝可变 tag（`latest`/`dev`/... → 联动 P1-10） | 直接退出 |
| 1 | idle 槽起新版本（8289），**线上不受影响** | 停 idle，线上不变 |
| 2 | idle 健康检查 + **只读 smoke**（health/config/engines/metrics/sse，不提交生成任务避免显存竞争） | 停 idle，线上不变 |
| 3 | promote：记 `LAST_GOOD=旧tag` → 停 idle → 停 active → active 以新 tag 重启 | 健康失败 → **自动回滚** |
| 4 | 完整 smoke（含假生成任务） | 失败 → **自动回滚** |
| 5 | 观察窗口（默认 120s）：轮询 `/api/alerts`，出现 P1 firing（ServiceUnhealthy / GPUOOM / QueueOverload / GenerationFailuresHigh）即失败 | 失败 → **自动回滚** |
| 6 | 写入 HISTORY，promote 成功 | |

**晋级/回退条件**（报告 §9-P2-12）：错误率与生成成功率由完整 smoke 的假任务 + `GenerationFailuresHigh`
告警覆盖；OOM 由 `GPUOOM`/`gpu_oom_total` 覆盖；P99 超预算由 P2 `P99LatencyHigh` 告警在观察窗口中暴露
（P1 firing 为硬阻断）。

## 3. 一键回滚

```bash
bash scripts/deploy/bluegreen.sh rollback
# 内部：active 槽停止 → 以 LAST_GOOD 重启 → 健康检查（失败则提示按 runbook 人工介入）
```

- `LAST_GOOD` 只在每次 promote 前更新，连续回滚安全（回滚本身不覆盖 LAST_GOOD）；
- 自动回滚（步骤 3-5 失败时）与手工回滚走同一条 `do_rollback` 路径；
- `promote-only` 为紧急切流入口（跳过 idle 验证，要求立即人工跑 smoke）。

## 4. 状态文件

`.imm_bluegreen`（不入库；`IMM_BG_STATE` 覆盖路径）：

```
ACTIVE_SLOT=blue
BLUE_TAG=2.0.2
GREEN_TAG=2.0.1
LAST_GOOD=2.0.1
HISTORY=2026-09-01T05:00:00Z 2.0.2
...
```

`status` 子命令查看当前槽位、镜像、健康与历史。

## 5. 与 staging 流水线的关系

`deploy.yml → staging` job 在部署后强制跑 `post_deploy_smoke.py`，**smoke 失败即阻断**
`production` 晋级（GitHub environment 人工批准 + `needs: staging` 双门禁）；
`production` job 直接调用本脚本的 `deploy` 子命令完成 blue-green promote。

## 6. 演练记录要求

每次 staging/production promote 后，把 `smoke_report.json` 与 `bluegreen.sh status` 输出
归档到事故/发布记录（配合 P2-14 的 post-mortem 流程），满足验收清单
「至少完成一次 staging 部署、失败阻断和 rollback 演练」。

## 7. 已知限制

- 真实 promote 验证需要 Docker + GPU 环境；CI 当前对 compose YAML、脚本语法、
  状态机与参数校验做静态门禁，端到端演练需在 self-hosted runner 或有 GPU 的部署机执行；
- 秒级停服窗口是单 GPU 约束下的固有代价；若未来有多卡/多机，可切换为真正的双活
  blue-green（负载均衡器切流，无需停服）。
