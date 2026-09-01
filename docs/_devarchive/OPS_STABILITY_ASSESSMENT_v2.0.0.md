# Image_MultiModel v2.0.0 运维稳定性体系深度完整性评估

> 评估对象：`C:\Users\Doro\Image_MultiModel`
>
> 评估日期：2026-08-31
>
> 评估口径：以当前工作树（包含未提交改动）为准，优先采信可执行代码、配置和 workflow；文档仅作为辅助证据。
>
> 重要版本纠偏：用户指定评估版本为 v2.0.0，但当前代码实际声明为 `config.yaml:1`、`app/integrated_app/__init__.py:7` 的 `1.4.0`。本报告沿用用户指定的评估标签 `v2.0.0`，但结论基于当前实际代码状态，不能视为已发布的 v2.0.0 构建验收。

---

## 1. 执行摘要

### 1.1 总体结论

**当前项目具备“单机推理服务可运行”的可靠性骨架，但尚未形成可承诺生产 SLA 的闭环运维体系。**

已经存在的基础能力包括：

- `docker-compose.yml:13` 的 `restart: unless-stopped`；
- `docker-compose.yml:55-61` 和 `Dockerfile:24-26` 的健康检查；
- `app/integrated_app/task_queue.py:50-59` 的单 Worker 串行 GPU 队列；
- 队列满时返回 503（`app/integrated_app/routes/generate_routes.py:273-276`）；
- 卡死任务恢复（`app/integrated_app/app_server.py:177-185`）；
- 批量 checkpoint 发现与续跑（`app/integrated_app/app_server.py:480-506`）；
- 请求 ID、轮转文件日志和异常堆栈留存（`app/integrated_app/app_server.py:103-145`、`middleware/request_id.py:25-50`）；
- 当前工作树新增的 GPU 采样、VRAM 泄漏判定和动态 batch 调度逻辑（`app/integrated_app/app_server.py:243-321`、`gpu_utils.py:350-422`）。

但关键闭环仍然缺失或不完整：

- 没有 Prometheus/OpenTelemetry `/metrics`、持久化指标查询 API 或告警通知通道；
- QPS、错误率、生成成功率、端到端生成延迟未形成统一指标；
- 没有正式 SLA/SLO、错误预算或可用性承诺；
- 没有生产 Runbook、on-call 轮值、升级路径、事故模板和 post-mortem 机制；
- 没有 GPU 自动扩缩容、水平高可用、蓝绿或金丝雀部署；
- 关键 CI job 大量 `continue-on-error: true`、`|| true`，并且 E2E/性能 job 被 `if: false` 禁用；
- 当前未提交的成本治理改动存在配置契约风险：`app_server.py:245` 直接访问 `config.runtime.idle_unload_minutes`，但当前 `RuntimeConfig` 未定义该字段，`config.yaml` 也没有该项；应在任何发布前先做启动 smoke test。

**发布建议：暂不建议以“具备完整运维稳定性体系”名义承诺 99.9% 级别 SLA。** 适合作为单 GPU、单实例、低并发或内部使用的推理服务；若要面向外部用户，需要优先补齐可观测性、SLO、应急响应和部署回滚闭环。

### 1.2 评分总览

本评分衡量的是“运维控制能力成熟度”，不是实测线上 MTTD/MTTR 或真实可用性。当前仓库没有长期生产时序数据，因此不能把代码能力等同于实际达标率。

| 指标 | 权重 | 得分 | 结论 |
|---|---:|---:|---|
| MTTD（平均发现时间能力） | 30 | **16** | 有健康检查、请求 ID、日志和 GPU/SSE 状态，但缺少统一 metrics、告警规则和通知闭环 |
| MTTR（平均恢复时间能力） | 30 | **15** | 有自动重启、队列恢复、checkpoint、引擎切换回滚；但无 Runbook/on-call，状态恢复和自动修复仍弱 |
| 可用性（Availability） | 40 | **19** | 单实例/单 GPU/单 Worker 有安全边界和反压，但无 HA、自动扩容、蓝绿/金丝雀、SLO 错误预算 |
| **总分** | **100** | **50** | **基础可运行，生产运维闭环不足；成熟度：中低** |

辅助按子体系评分（5 分制）：

| 子体系 | 得分 | 评级 | 核心原因 |
|---|---:|---|---|
| 监控告警 | 2.0/5 | 部分具备 | 采样和日志已存在，但缺指标暴露、告警路由、持久化查询 |
| SLA/SLO | 0.5/5 | 基本缺失 | 只有零散 benchmark 阈值，没有承诺、分层 SLO 和错误预算 |
| 故障应急响应 | 1.0/5 | 基本缺失 | 未发现正式 Runbook、轮值、升级和 post-mortem 资产 |
| 容量与弹性 | 2.0/5 | 部分具备 | 单机 GPU 保护、队列上限、VRAM 预检存在；无自动扩缩容和完善负载分级 |
| 部署与回滚 | 1.5/5 | 初步具备 | 有引擎运行期失败回滚和 release workflow，但无应用部署、灰度和状态迁移回滚 |

---

## 2. 评估范围与证据边界

### 2.1 关键路径核验

| 用户指定路径 | 实际状态 | 评估结论 |
|---|---|---|
| `.github/workflows/ci.yml` | 存在 | 重点检查门禁、测试、性能/E2E 和失败处理 |
| `docker-compose.yml` | 存在 | 重点检查重启、健康检查、GPU、持久化和单点故障 |
| `monitor.py` | 未发现根目录同名文件 | 不能按该路径评估；实际监控脚本为 `scripts/perf_monitor.py` |
| `perf_monitor.py` | 存在于 `scripts/perf_monitor.py` | 重点检查采样对象、百分位数、输出和调度方式 |

辅助检查了：

- `Dockerfile`、`release.yml`、`release-please.yml`、`security.yml`、`pages-deploy.yml`；
- `app_server.py`、`task_queue.py`、`system_routes.py`、`generate_routes.py`、`engine_routes.py`、`sse.py`；
- `gpu_utils.py`、`cost_governance.py`、`config.yaml`、`config_models.py`；
- `tests/` 中的系统路由、队列取消、混沌、引擎回滚、VRAM 泄漏测试；
- `perf/monitoring_plan.md`、`docs/project/AI_DEV_SOPS.md` 和已有审计报告。

### 2.2 版本与工作树风险

当前工作树存在多处未提交修改，包括 CI、应用生命周期、成本治理、配置模型、测试和安全相关文件。因而本报告额外区分：

- **已存在控制**：当前代码可以直接观察到的能力；
- **未闭环控制**：代码或配置中有组件，但没有对外暴露、告警或验收闭环；
- **发布阻断候选**：当前工作树的改动可能导致启动/运行异常，须先验证。

---

## 3. 监控告警体系评估

### 3.1 Metrics collection coverage

#### QPS / 请求量

**结论：缺失统一 QPS 指标。**

- `RequestIDMiddleware` 只生成链路 ID，不计数请求量（`middleware/request_id.py:25-41`）。
- `RateLimitMiddleware` 维护每 IP 的滑动窗口计数，但这是限流状态，不是可查询的 QPS 指标（`middleware/rate_limit.py:33-46`）。
- 没有发现 Prometheus Counter、OpenTelemetry Meter、`/metrics` 路由或按 endpoint/method/status 聚合的请求统计。

影响：无法回答“当前 QPS、各 endpoint QPS、峰值 QPS、限流前后 QPS”这些基本运维问题。

#### 错误率 / 生成成功率

**结论：有任务状态落库，但没有形成实时错误率和成功率指标。**

- `TaskQueue` 会把任务置为 completed/failed/cancelled，并在 worker 异常时记录日志（`task_queue.py:189-217`）。
- `HistoryDB` 可保存任务错误和耗时，适合事后查询。
- `system_routes.py:49-69` 的 `/api/health` 只返回累计任务状态计数，不提供时间窗口成功率、按引擎错误率或按错误类型聚合。
- `cost_governance.py:249-288` 的成本聚合结构包含 completed/failed，但当前未发现对应的正式运维指标 API、告警路由或外部时序导出。

影响：无法对“生成成功率 SLO”做连续计算，不能区分用户参数错误、内容策略拒绝、队列满、OOM、模型加载失败和基础设施故障。

#### 延迟 / P99

**结论：只有手工 benchmark，缺少生产端到端延迟。**

- `scripts/perf_monitor.py:17-57` 只请求 health endpoint 5 次，输出平均、最小和最大响应时间。
- `scripts/benchmark.py:65-98` 可计算 P50/P95/P99，但主要测试首页、history、health、config、loras、outputs 和 SSE；没有真实 `/api/generate` 提交到生成完成的端到端 P99。
- `scripts/benchmark.py:27` 只有 20 个样本，且当前为手工脚本，不是持续采集器。
- 项目已有 `task.created_at/started_at/completed_at` 等时间字段，但没有统一的 queue wait、model load、inference、post-process、first-preview 和 total duration 指标管道。

影响：无法判断真正的用户等待时间、GPU 队列等待时间和长尾生成耗时。

### 3.2 GPU / 队列 / 磁盘监控

当前工作树已经比单纯 SSE 方案前进了一步：

- `app_server.py:249-283` 每 2 秒读取 GPU 信息，写入 `MetricsStore`，发布 `gpu_status`，运行 `VRAMLeakMonitor`，并更新 `VRAMScheduler`。
- `gpu_utils.py:350-422` 提供可注入采样器、滑动窗口和单调增长判定，且有 `tests/test_vram_leak_monitor.py` 单元测试。
- `/api/health` 提供 GPU、内存、磁盘、引擎和队列摘要（`system_routes.py:42-135`）。

但这些能力仍未构成完整监控系统：

1. `MetricsStore` 是进程内 deque，不是跨重启持久化时序库；重启后历史指标丢失。
2. 没有 `/api/metrics` 或 Prometheus exposition endpoint，运维系统无法抓取。
3. `leak_detected` 只写入内存状态，没有告警通知、自动隔离、进程重启或事件工单。
4. `gpu_status` 通过 SSE 推送给前端，SSE 断开、浏览器关闭或进程重启均不能代替服务端监控。
5. 队列状态虽然通过 health/SSE 返回，但没有 queue depth 的时间序列、等待时长、拒绝数、年龄分布和阈值告警。
6. 磁盘仅在 health 请求时读取，未发现低磁盘阈值告警、输出目录容量趋势或写入失败预警。

### 3.3 告警阈值合理性

| 阈值/参数 | 当前配置或实现 | 评价 |
|---|---|---|
| 容器 healthcheck | 30s interval、10s timeout、3 retries、60s start period | **可作为存活检查，但不等于告警**；故障发现可能接近 90s，且没有外部通知 |
| 任务最大执行时间 | `config.yaml:213` 为 86400s | **过宽**。单任务可占住单 Worker 一天，MTTR 和队列恢复均会恶化；应按引擎/任务类型分层 |
| 队列容量 | `config.yaml:209` 为 100 | **仅容量上限，不是告警阈值**；缺少 70/85/95% 分级告警和队列年龄阈值 |
| VRAM 高/低水位 | `config.yaml:228-233` 为 90%/70%，但 `enabled: false` | **默认不生效**。配置看似有弹性策略，实际发布默认关闭，存在配置-实现认知差 |
| VRAM tight continue | `config.yaml:175` 为 true | 对降低拒绝率有帮助，但会把一部分风险转成 OOM/长延迟；生产建议必须配合 OOM 计数、熔断和降级策略 |
| 限流 | `global=600/min`, `infer=30/min`, `upload=10/min` | 属于请求保护，不是系统告警；无 429 率、限流命中率和异常 IP 趋势 |
| SSE | 30s heartbeat、1000 条队列 | 心跳可检测连接层存活，但没有连接数、丢事件率、重连率指标；队列满时会丢最旧事件（`sse.py:75-85`） |

### 3.4 日志结构与可搜索性

优点：

- `app_server.py:103-145` 配置控制台 + 轮转文件日志，50MB、5 份备份；
- 格式包含 timestamp、level、PID、TID、logger、filename、lineno、request_id；
- `error_handler.py:164-189` 对未处理异常记录完整服务端堆栈，并向客户端隐藏堆栈；
- Request ID 能贯穿请求日志和错误响应。

缺口：

- 日志是文本格式，不是 JSON/结构化事件；按 endpoint、status、task_id、engine、error_code、duration 的字段搜索成本较高。
- 任务 worker 日志包含 task_id，但没有统一 `event_name`、`duration_ms`、`queue_wait_ms`、`outcome` 字段。
- 未发现集中式日志采集、保留策略、脱敏验证、日志索引或告警查询规则。
- `rate_limit.py:52-79` 返回 429，但没有对应审计日志；限流攻击和误配难以追溯。
- `sse.py:79` 只记录队列满的 warning，没有丢事件计数和客户端维度信息。

**监控子体系结论：2.0/5。**

---

## 4. SLA / SLO 定义评估

### 4.1 当前可识别的“隐含目标”

项目存在若干 benchmark 阈值，但它们不是正式 SLA/SLO：

- history 50 条：P95 ≤500ms（`scripts/benchmark.py:101-107`）；
- health：P95 ≤1000ms（`scripts/benchmark.py:110-116`）；
- config/loras/outputs：P95 ≤500ms（`scripts/benchmark.py:119-143`）；
- SSE gpu_status：≤5s（`scripts/benchmark.py:146-165`）；
- 取消时限：配置为 5s（`config.yaml:211`，并有队列测试）；
- 单任务最大超时：86400s（`config.yaml:213`）。

这些阈值没有：

- 统计窗口、排除项和分母定义；
- 生产数据源和持续计算方式；
- 目标未达标时的错误预算消耗；
- 责任人、通知渠道和修复时限；
- 版本/引擎/分辨率/批量大小分层。

### 4.2 三项核心指标打分

#### Generation success rate

**得分：0.5/5。**

有任务完成/失败状态和历史记录，但没有正式目标。例如，当前没有定义：

- 是否排除 4xx 用户错误、内容安全拒绝和主动取消；
- 队列满的 503 是否计入服务失败；
- 生成成功是“任务完成”还是“输出文件已成功写入并可读取”；
- 按日/周/月如何滚动计算。

#### P99 latency budget

**得分：1/5。**

有手工 P95/P99 benchmark，但不是生成链路预算。尤其缺少：

- 请求接收 → 排队完成；
- 排队等待；
- 模型加载；
- 首个预览事件；
- 最终图片落盘；
- API 返回/前端显示。

#### Availability commitment

**得分：0/5。**

没有发现可用性承诺、月度 uptime 计算、维护窗口、错误预算或服务等级分层。`restart: unless-stopped` 和 healthcheck 只能说明容器自愈/存活探测，不构成可用性承诺。

### 4.3 建议的第一版 SLO（建议值，不是当前项目事实）

在单 GPU、单实例定位下，不建议直接承诺 99.9%。可以先采用“内部/试运行”基线：

| SLO | 建议目标 | 分母/排除项 |
|---|---|---|
| API availability | 月度 ≥99.5% | `/api/health`、生成提交接口；维护窗口和明确的客户端 4xx 可单独排除 |
| Generation success rate | ≥98.0% | 排除用户主动取消、内容策略拒绝、明确参数 4xx；队列满 503 不排除 |
| Submit latency | P99 ≤1s | 不含实际推理时间；从网关收到请求到返回 task_id/明确拒绝 |
| Queue wait | P95 ≤30s、P99 ≤120s | 按引擎、分辨率、batch 分层；队列满直接拒绝单列 |
| End-to-end generation | 按 profile 定义 P95/P99 | 至少覆盖 1024×1024 batch=1、含/不含 SeedVR2 两个 profile |
| First progress/preview | P99 ≤5s | 从任务接受到首个有效 SSE task_status/preview |
| Cancellation | P95 ≤5s | 需要同时验证 GPU 释放和 Worker 可继续接单 |

---

## 5. 故障应急响应评估

### 5.1 Runbook 完整性

**结论：未发现正式生产 Runbook。**

`docs/project/AI_DEV_SOPS.md` 是 AI 开发和代码变更 SOP，不是运维故障手册；当前检索未发现成体系的：

- 服务启动失败排查；
- GPU OOM/显存泄漏；
- 队列堆积/队列满；
- 数据库锁/损坏/磁盘满；
- 输出目录爆满；
- 模型文件缺失/损坏；
- SSE 大面积断连；
- 版本回滚；
- 数据恢复和备份恢复。

已有代码日志能帮助专家排查，但不能保证值班人员在无上下文时快速恢复。

### 5.2 On-call rotation

**结论：未发现值班轮换表、服务负责人、升级路径或通知渠道。**

没有证据表明：

- 谁负责首响；
- P0/P1/P2 如何升级；
- 多久未确认需要升级到谁；
- GPU/应用/数据/安全问题分别由谁负责；
- 事故期间如何更新状态。

### 5.3 Post-mortem culture

**结论：未发现固定 post-mortem 模板、事故编号、行动项跟踪或复盘指标。**

项目有 Known Gotchas 和工程审计记录，但它们偏向开发经验积累，不等于生产事故复盘闭环。建议至少固定记录：影响时间线、检测方式、根因、触发条件、为什么未提前发现、临时缓解、永久修复、责任人和截止日期。

### 5.4 已有恢复能力与局限

| 能力 | 现状 | 局限 |
|---|---|---|
| 进程自愈 | Compose restart | 只解决进程退出；不能解决逻辑卡死、输出损坏或错误配置 |
| 卡死任务恢复 | `recover_stuck_tasks()` | 需要验证恢复判定、幂等性、重复执行和 DB 异常场景 |
| 批量断点续跑 | `TaskCheckpoint` | 只恢复 checkpoint 中的剩余数量；需要验证输出去重、状态一致性和跨版本兼容 |
| 取消 | 队列设置 cancel_requested + 引擎 cancel | 取消与历史 DB 状态存在路由先写、worker 后写的竞态空间 |
| 引擎切换回滚 | 当前代码有 best-effort rollback | 先卸载旧引擎再加载新引擎；回滚失败时仍可能进入无可用引擎状态 |
| 自动卸载 | 当前工作树有 idle unload loop | `app_server.py:315` 在运行事件循环内调用 `run_until_complete`，该路径会触发运行时错误并被捕获，自动卸载实际可能不生效 |

**故障响应子体系结论：1.0/5。**

---

## 6. 容量规划与弹性评估

### 6.1 GPU 资源自动扩缩容

**结论：未实现。**

- `docker-compose.yml:15-22` 只预留 1 个 NVIDIA GPU；
- `config.yaml:284-287` 只配置 device_ids 和 CPU fallback；
- `server.workers=1`（`config.yaml:7`），并且项目 Known Gotchas 明确多 Worker 会重复加载模型；
- 没有 GPU 池、节点注册、调度器、水平扩容、缩容冷却和跨实例负载均衡。

`VRAMScheduler` 是**单进程 batch 上限调节**，不是 GPU 自动扩缩容。

### 6.2 Queue depth threshold alerts

**结论：有队列容量和拒绝，但没有阈值告警。**

- `asyncio.Queue(maxsize=100)` 提供硬上限（`task_queue.py:67`）；
- 队列满时 `put_nowait` 返回 False，并由生成路由返回 503（`task_queue.py:104-119`、`generate_routes.py:273-276`）；
- `/api/health` 返回累计 pending/processing 数量；
- 未发现 70%、85%、95% 水位告警、队列等待时间告警、老任务告警或自动限流降级。

### 6.3 Load shedding strategies

已经存在的保护：

- 推理限流（`RateLimitMiddleware`）；
- 队列满时快速拒绝 503；
- VRAM 预检和 batch chunk 推荐；
- 单 Worker 串行化，避免并发 GPU OOM；
- `VRAMScheduler` 可在启用后钳制 batch 上限。

不足：

- 没有按租户/优先级/任务类型的分级队列；
- 没有 deadline-aware shedding，所有任务都可能进入同一队列；
- 没有在 GPU 高水位时暂停低优先级任务、关闭预览、降分辨率或切换 CPU/低精度的完整策略；
- 没有统一的过载响应码语义、Retry-After 估算和客户端退避建议；
- `config.yaml:217-221` 声明 batch retry 参数，但 `task_queue.py` 只描述自动重试，未看到对应的重试循环实现，存在“配置存在但行为未兑现”的风险。

### 6.4 容量模型缺口

缺少以下基线数据：

- 单 GPU 按模型/分辨率/batch/LoRA/SeedVR2 的吞吐；
- 最大稳定并发和队列服务率；
- 启动加载时长、模型切换时长；
- 每任务 GPU·秒、峰值显存和显存回收时长；
- 输出/缩略图/上传缓存的增长率；
- DB 在 5 万记录、并发读写和磁盘逼近满时的行为。

**容量与弹性子体系结论：2.0/5。**

---

## 7. 部署与回滚机制评估

### 7.1 CI/CD 现状

`.github/workflows/ci.yml` 有较完整的 job 目录，但门禁可信度不足：

- `lint`、`mypy`、`sast`、`frontend-smoke` 使用 `continue-on-error: true`（例如 `ci.yml:23`、`38-43`、`120-124`、`172-177`）；
- Mypy 命令自身使用 `|| true`（`ci.yml:59-64`）；
- pip-audit 使用 `|| true`（`ci.yml:136-140`）；
- frontend 安装、模板渲染、前端 smoke 多处 `|| true`（`ci.yml:185-200`）；
- E2E 和 performance job 明确 `if: false`（`ci.yml:202-243`），关键运行态验证不会执行；
- coverage gate 在找不到 `coverage.xml` 时直接 warning 并退出 0（`ci.yml:102-106`）；
- `security.yml` 的多个 job 也设置 `continue-on-error: true`，与“高危 CVE 阻断 CI”的注释不一致。

这会造成典型反模式：流水线绿色不代表 lint、类型、安全、前端、E2E 和性能真正通过。

### 7.2 Blue-green / Canary

**结论：未实现。**

- 未发现应用部署到 staging/production 的 workflow；
- `release.yml` 主要创建 GitHub Release，并在 `release.yml:51-55` 明确跳过 Windows portable package 构建；
- `pages-deploy.yml` 只部署 demo 到 GitHub Pages，不是推理服务部署；
- 未发现 blue-green、canary、流量比例、shadow traffic、自动回滚或部署后 smoke gate。

### 7.3 Quick rollback trigger

当前只有两类局部回滚语义：

1. **引擎运行期切换回滚**：`engine_routes.py:29-99` 在新引擎加载失败时尝试重新加载旧引擎；对应 `tests/test_engine_switch_rollback.py` 有单测。
2. **Git/Release 人工回退可能性**：发布产物进入 GitHub Release，但没有服务编排侧的版本选择、健康门禁和一键回退。

未定义以下触发条件：

- 错误率连续多少分钟超过阈值；
- P99 延迟超过预算多久；
- OOM/显存泄漏多少次触发回退；
- 输出质量回归失败如何阻止发布；
- 哪个版本作为 last-known-good；
- 谁拥有回滚批准权。

### 7.4 Rollback state preservation

当前有 SQLite `data/history.db`、`data`、`outputs`、`logs` volume 持久化（`docker-compose.yml:36-49`），这是正向设计。但仍有风险：

- 没有 DB schema migration/rollback 策略和备份校验；
- 没有在发布前执行数据兼容性检查；
- `outputs` 与 history DB 的文件路径一致性、孤儿输出和重复输出缺少回滚验收；
- Compose 使用 `image-multimodel:latest`（`docker-compose.yml:11`），不利于精确定位和快速回退；
- 模型与 `comfy_kernel` 通过运行时挂载提供，应用代码、内核、工作流和模型版本不能作为一个不可变 artifact 一起回退；
- `docker-compose.yml:41` 挂载 `./workflows`，但当前项目结构快照中没有根目录 `workflows` 的早期说明一致性证据，发布前应做挂载路径完整性检查。

**部署与回滚子体系结论：1.5/5。**

---

## 8. 反模式识别

| 反模式 | 结论 | 证据与影响 | 严重度 |
|---|---|---|---|
| Alert fatigue | **部分命中** | 当前未发现大量告警规则，因此“误报过多”尚未形成；但 `logger.warning` 既承载可恢复降级又承载潜在故障，且没有去重/抑制/升级策略，未来接入告警后很容易把日志噪声直接转成告警风暴 | 中 |
| Missing runbook / stale docs | **命中** | 未发现正式生产 Runbook、on-call、post-mortem；`perf/monitoring_plan.md` 仍描述手动执行、只测基础 API，且示例入口与当前结构存在漂移 | 高 |
| Manual deployments without automation | **命中** | Release workflow 只创建 Release，portable package 明确跳过；未发现推理服务 staging/prod 部署、部署后验证和自动回退 | 高 |
| Single point of failure | **强命中** | 单实例、单 GPU、单 Worker、进程内 SSE、进程内指标 Store、SQLite 本地 DB；任一主机/GPU/进程故障都会影响完整推理能力 | 严重 |
| Monitoring blind spots | **强命中** | `/api/generate` 完整推理链、错误率、QPS、队列年龄、OOM、输出落盘失败、数据库异常、SSE 丢事件均缺少可抓取指标 | 严重 |
| Green CI illusion | **强命中** | 多 job `continue-on-error`、`|| true`，E2E/performance `if:false`，coverage 文件缺失可跳过门禁 | 严重 |
| Configuration-control mismatch | **命中** | 当前工作树的 `idle_unload_minutes` 被生命周期代码读取但未在 `RuntimeConfig`/`config.yaml` 中定义；VRAM scheduler 有配置但默认关闭；retry 配置与实际执行逻辑不一致 | 严重 |
| In-memory observability loss | **命中** | `MetricsStore` 进程内环形缓冲，重启即丢失；不能支持跨重启趋势、故障前回溯和长期容量规划 | 高 |
| False rollback confidence | **部分命中** | 引擎切换回滚是局部 best-effort，不能替代应用版本回滚；回滚失败后没有自动隔离、告警和安全状态 | 高 |

---

## 9. P0/P1 改进建议

### P0：发布阻断与可观测性基线

1. **先修启动契约并跑真实启动 smoke**
   - 解决 `app_server.py:245` 对未定义 `config.runtime.idle_unload_minutes` 的直接访问；
   - 统一 `config.yaml`、`config_models.py`、生命周期代码的字段契约；
   - 启动、`GET /api/health`、提交一个假引擎任务、关闭服务各做一次自动化验证；
   - 将“配置字段引用完整性”加入 CI。

2. **建立统一 metrics 入口**
   - 暴露 `/metrics` 或 OpenTelemetry exporter；
   - 至少提供：`http_requests_total`、`http_request_duration_seconds`、`generation_submitted_total`、`generation_completed_total`、`generation_failed_total`、`generation_duration_seconds`、`queue_depth`、`queue_rejected_total`、`queue_oldest_age_seconds`、`gpu_memory_used_bytes`、`gpu_oom_total`、`sse_connected`、`sse_events_dropped_total`、`disk_free_bytes`；
   - 指标标签限制为 route/template、method、status、engine、error_code，禁止 prompt/task_id 等高基数字段直接作为 label。

3. **定义并实现生成成功率与端到端延迟**
   - 记录 submitted、accepted、started、first_progress、first_preview、completed/failed/cancelled；
   - 统一 error_code 分类；
   - 生成 pipeline 用 monotonic clock 记录 queue wait、load、inference、postprocess、persist、total；
   - 每个 SLO 都能从指标直接计算，不能依赖手工读取 SQLite。

4. **把告警从“日志 warning”升级为可执行告警**
   - P1：health failed 2 次、生成失败率 >5% 持续 5 分钟、队列 >85% 持续 5 分钟、GPU free VRAM <15% 持续 2 分钟、磁盘可用 <15%；
   - P2：P99 超预算、SSE 丢事件、429 率异常、任务年龄过长；
   - 加去重、for、group_by、silence 和恢复通知；
   - 每条告警必须链接到 Runbook。

5. **收紧 CI 门禁**
   - 删除质量关键 job 的 `continue-on-error: true`；
   - 删除 `|| true`，需要允许失败时必须显式记录并将 job 标红或转为非门禁信息 job；
   - E2E/performance 不应长期 `if:false`，至少用假引擎/CPU profile 接入；
   - coverage 文件不存在应失败；
   - release job 必须依赖 CI 全部必需检查通过。

### P1：故障恢复与生产容量

6. **建立四套最小 Runbook**
   - GPU OOM/显存泄漏；
   - 队列堆积/队列满；
   - 服务启动失败/健康检查失败；
   - 数据库/磁盘/输出目录异常。

   每套至少包含：症状、确认命令、影响判断、临时缓解、回滚/重启、数据保护、恢复验证、升级联系人。

7. **修正自动卸载实现并加入回归测试**
   - 在异步生命周期中直接 `await mm.unload_engine(...)`，不要在运行事件循环里调用 `run_until_complete`；
   - 推理开始/结束调用 `mark_activity()`；
   - 验证卸载后下一任务可以安全重载模型，且不会破坏 active registry。

8. **将队列容量策略从硬上限升级为分级过载策略**
   - 70%：warning；85%：限制低优先级/大 batch；95%：快速拒绝并返回 Retry-After；100%：明确 503；
   - 记录 queue oldest age、拒绝数和各 profile 服务率；
   - 明确重试策略，避免客户端和服务端双重重试造成雪崩。

9. **完成单机容量基线**
   - 每个引擎、分辨率、batch、LoRA、SeedVR2 profile 运行至少 100 次；
   - 记录吞吐、P50/P95/P99、峰值显存、OOM、首预览时间和落盘时间；
   - 用容量公式确定最大安全队列深度和扩容触发点。

10. **使用不可变版本 artifact**
    - Compose 镜像从 `latest` 改为 Git SHA/语义版本 tag；
    - 镜像、代码、workflow、comfy_kernel、模型 manifest 形成可追溯版本；
    - 发布前生成 SBOM、镜像 digest 和配置快照。

### P2：高可用和部署治理

11. **增加 staging + post-deploy smoke**
    - 部署后自动检查 health、config、engine list、假生成任务、队列满保护和 SSE；
    - smoke 失败自动停止晋级，不允许仅打印日志。

12. **实现 blue-green 或最小 canary**
    - 单 GPU 场景至少做“旧容器保持服务 + 新容器独立健康检查 + 人工/自动切流”；
    - 以错误率、P99、OOM 和生成成功率作为晋级/回退条件；
    - 明确 last-known-good 版本和一键 rollback 命令。

13. **状态与备份治理**
    - history DB 做定期备份、完整性校验和恢复演练；
    - 明确 schema migration 向前/向后兼容；
    - 回滚后验证 history DB、outputs、checkpoints 的一致性；
    - 对输出文件和 DB 记录建立孤儿检测。

14. **建立 on-call 和 post-mortem 制度**
    - 明确 P0/P1/P2、首响目标、升级时限和负责人；
    - 每次 P0/P1 事故必须有复盘；
    - 将复盘行动项纳入 issue/看板，并在版本发布前检查未关闭的高风险项。

---

## 10. 建议验收清单

完成 P0/P1 后，建议以以下条件作为“可进入受控生产”的门槛：

- [ ] 代码启动成功，所有配置字段引用可由自动检查证明存在；
- [ ] `/metrics` 可被抓取，至少覆盖 QPS、错误率、生成成功率、端到端延迟、队列、GPU、磁盘、SSE；
- [ ] 生产环境有至少 7 天指标留存和可视化；
- [ ] P95/P99 采用端到端生成数据，而不是只测 health/config；
- [ ] SLO、分母、排除项、错误预算和告警阈值已文档化；
- [ ] 每条 P0/P1 告警都有 Runbook 链接和负责人；
- [ ] CI 中质量关键 job 不再被 `continue-on-error` 或 `|| true` 吞掉；
- [ ] E2E/CPU 假引擎性能测试至少在 PR 或 nightly 中运行；
- [ ] 队列 85%/95%/100% 的行为和告警已有自动化测试；
- [ ] GPU OOM、显存泄漏、DB 锁、磁盘满、SSE 丢事件均有故障演练记录；
- [ ] 发布使用不可变镜像 tag/digest；
- [ ] 至少完成一次 staging 部署、失败阻断和 rollback 演练；
- [ ] history DB、outputs、checkpoints 回滚后仍能查询、下载和续跑；
- [ ] 已建立 on-call 轮值和 P0/P1 post-mortem 流程。

---

## 11. 最终判定

### 当前状态

**判定：Conditional / 有条件可用。**

- 作为单机、单 GPU、内部或低并发推理应用：具备一定稳定性基础；
- 作为对外承诺 SLA 的生产平台：不通过；
- 作为 v2.0.0 运维成熟度验收：不通过，主要阻塞项是可观测性、SLO、应急响应、部署自动化和高可用缺失；
- 当前工作树中成本治理改动还存在启动契约和自动卸载实现风险，必须在任何性能/稳定性结论前先修复并跑启动验证。

### 优先级排序

1. **P0：修复当前工作树的启动契约风险；补 `/metrics`、生成链路指标和告警；收紧 CI。**
2. **P1：补 Runbook/on-call/post-mortem；完成队列/VRAM/磁盘过载保护和容量基线。**
3. **P2：不可变 artifact、staging smoke、blue-green/canary、DB/输出回滚演练。**

在上述 P0/P1 完成前，项目更准确的描述应是：

> **“带有健康检查、队列反压、任务恢复和基础 GPU 监控的单机图像生成服务”，而不是“已建立完整生产级运维稳定性体系的平台”。**
