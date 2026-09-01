# staging 部署与 post-deploy smoke（P2-11）

> 评估依据：`OPS_STABILITY_ASSESSMENT_v2.0.0.md` §9-P2-11
> 检查脚本：`scripts/post_deploy_smoke.py`
> CI 门禁：`ci.yml → post-deploy-smoke`（每次 push 演练）+ `deploy.yml → staging`（发布后真部署）
> 单元测试：`tests/release/test_post_deploy_smoke.py`

## 1. 目的

发布/晋级前自动验证部署后的服务真的可用，**smoke 失败即阻断晋级，不允许仅打印日志**。

## 2. 六项检查

| # | 检查 | 端点 | 判定标准 |
|---|---|---|---|
| 1 | health | `GET /api/health` | 200 且 `status ∈ {ok, healthy, degraded}` |
| 2 | config | `GET /api/config` | 200 且 `runtime.task_queue.maxsize > 0` |
| 3 | engines | `GET /api/engine/engines` | 列表包含 `z_image_turbo_native` |
| 4 | generation | `POST /api/generate` → 轮询 `GET /api/tasks/{id}` | 假任务在超时内 completed |
| 5 | queue_protection | `GET /api/metrics/prometheus` | 暴露 `queue_depth` 与 `queue_rejected_total`（P1-8 保护已装载） |
| 6 | sse | `GET /api/events` | 建流成功且收到首块字节 |

CSRF：脚本预热时从 `/api/health` 响应头取 `X-CSRF-Token`，并以「头 + 同名 cookie」双重提交方式访问 POST 端点（与 `middleware/csrf.py` 的双重提交校验匹配）。

## 3. 用法

```bash
# 对已部署环境跑全量检查
python scripts/post_deploy_smoke.py --base-url http://staging:8288 --timeout 15 --output smoke_report.json

# 只跑读路径（快速探活）
python scripts/post_deploy_smoke.py --base-url http://staging:8288 --checks health,config,engines

# 失败时 exit code = 1（CI / 部署脚本据此阻断晋级）
python scripts/post_deploy_smoke.py --base-url http://staging:8288 || { echo "SMOKE FAILED — 停止晋级"; exit 1; }
```

## 4. 晋级流水线（deploy.yml）

```
release.yml（打 tag → 构建不可变镜像 → SBOM）
        │ workflow_run
        ▼
deploy.yml:staging（部署 staging → post_deploy_smoke 门禁 → 通过才标记 active slot）
        │ needs: staging（smoke 失败时 job 已红，无法进入）
        ▼
deploy.yml:production（人工批准 + blue-green promote + 观察窗口 + 自动回退，见 P2-12）
```

要点：

- `smoke` 步骤**没有** `continue-on-error`，失败即 job 失败；
- 「标记 active slot」步骤仅在 `steps.smoke.outcome == 'success'` 时执行，失败版本永远不会接管流量；
- 显式增加 `Block promotion on smoke failure` 步骤，输出可操作的失败摘要；
- `smoke_report.json` 以 artifact 形式保留，供复盘。

## 5. 无 staging secrets 时的演练模式

未配置 `STAGING_HOST/USER/SSH_KEY` 时，`deploy.yml` 与 `ci.yml` 的 post-deploy-smoke 会在
runner 本机 `docker compose up`（或 uvicorn + `IMM_FAKE_ENGINE=1`）起服务，跑同一份
`post_deploy_smoke.py`，再拆服务。**门禁逻辑与真实环境完全一致**，只是被测服务是本机演练实例。

## 6. 验收对照（§9-P2-11）

- [x] 部署后自动检查 health / config / engine list / 假生成任务 / 队列满保护 / SSE；
- [x] smoke 失败自动停止晋级（exit 1 + job 红 + slot 不切换 + production needs 不满足）；
- [x] 每项检查有独立单测（16 项，含失败路径与退出码断言）；
- [x] 已在真实 uvicorn + fake engine 上端到端验证（6 项全过，用时 ~3s）。
