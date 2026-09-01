# On-call 值班制度（P2-14）

> 评估依据：`OPS_STABILITY_ASSESSMENT_v2.0.0.md` §5 故障应急响应、§9-P2-14、验收清单。
> 告警定义见 [alert_rules.md](alert_rules.md)；处置手册见 [../runbooks/](../runbooks/README.md)。

## 1. 事故分级

| 级别 | 定义 | 例子 | 首响目标 | 解决目标 |
|---|---|---|---|---|
| **P0 / critical** | 服务不可用或核心功能瘫痪 | ServiceUnhealthy、GpuVramLow、DiskSpaceLow、全量生成失败 | **5 分钟**（工作时间）/ 15 分钟（夜间） | 1 小时 |
| **P1 / high** | 核心功能显著劣化，未完全中断 | GenerationFailureRateHigh、promote 后观察窗口失败已自动回滚 | 15 分钟 | 4 小时 |
| **P2 / medium** | 局部劣化或风险预警 | QueueOverloaded（warning）、P99 超 SLO 预算、429 率上升 | 1 小时（工作时间） | 下一工作日 |
| **P3 / low** | 无用户感知，计划内处理 | 备份失败但旧备份可用、文档过期 | 无 | 排期处理 |

> severity 与级别的映射：`alerts.py` 的 `critical` → P0/P1（服务是否还能出图为界）、
> `warning` → P2。`/api/alerts` 的 `severity` 字段为准。

## 2. 值班职责与轮值

- **Primary**：接收全部 P0/P1/P2 通知，执行 runbook，15 分钟无进展必须升级；
- **Secondary（备份）**：Primary 30 分钟无响应自动接管；负责事后复盘主持；
- 轮值周期：一周；交接时同步「观察中的风险项清单」（未关闭 post-mortem action + pending 告警）。

## 3. 升级路径

```
监控 firing 通知（日志 notifier → 接入 IM/电话后替换）
  → Primary（首响目标见上表）
    → P0 或 15 分钟无进展 → Tech Lead
      → 1 小时未缓解 / 数据损坏风险 → 服务 Owner（决策：回滚/停服/恢复演练）
```

**决策权矩阵**：

| 动作 | 谁能执行 |
|---|---|
| `bluegreen.sh rollback` | Primary 即可（一键、低风险、有 LAST_GOOD 兜底） |
| 重启服务 / 清磁盘 / cancel 积压任务 | Primary（按 runbook） |
| `orphans --prune-db`（数据清理） | Tech Lead 批准 + 先 backup |
| 停服发布 hotfix / schema 迁移回滚 | 服务 Owner |

## 4. 首响检查单（前 3 分钟）

1. `curl -s http://127.0.0.1:8288/api/alerts` → 哪个规则 firing？value 多少？
2. 沿 `runbook` 字段打开对应 runbook，按「确认命令」章节执行；
3. 判断影响面：全量 or 部分？（`GET /api/health` queue 计数 + `generation_health` 分母）；
4. **能回滚先回滚**：最近有 promote → `bash scripts/deploy/bluegreen.sh rollback`
   （回滚不丢数据，见 state_backup.md §6）；不能回滚才进入排障；
5. 每 15 分钟在事故频道同步一次状态（无进展也要发）。

## 5. 通知渠道现状与目标

- **现状**：notifier 写入应用日志（firing 前缀 `[ALERT][CRITICAL]` / `[ALERT][WARNING]`，
  恢复前缀 `[ALERT-RESOLVED]`），由部署机日志转发（docker logs → 集中日志）；
- **最小可用**：cron 每 5 分钟 `curl /api/alerts` 检查 `firing_count>0` 即发 IM webhook；
- **目标**：接入 Prometheus Alertmanager / 企业 IM 机器人，恢复通知闭环。
  接入前，日志关键字 `[ALERT]`（firing）/ `[ALERT-RESOLVED]`（恢复）就是告警接口，不得改文案。

## 6. 演练要求（满足验收清单）

每季度至少一次故障演练，GPU OOM、显存泄漏、DB 锁、磁盘满、SSE 丢事件场景轮着做
（对应 runbook 覆盖），记录：触发 → 首响耗时 → 缓解耗时 → 恢复验证结果，
演练发现的问题开 issue 跟踪。演练即测试：把故障注入过程写成脚本放
`scripts/drills/`（计划，未实现——首次演练时沉淀）。

## 7. 与 post-mortem 的衔接

P0/P1 事故解决后 **5 个工作日内** 必须产出 post-mortem（模板见
[post_mortem_template.md](post_mortem_template.md)）；行动项进 issue 看板，
每次版本发布前由 Release Owner 检查「未关闭的高风险 action」（见 §9-P2-14 验收）。
