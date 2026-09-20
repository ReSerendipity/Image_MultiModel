# AGENT_CONSTRAINTS.md — 面向自动化协作的公开硬约束（最小集）

> 本文件是仓库**公开、可入库**的工程硬约束子集，供代码注释 / 配置 / CI 直接引用。
> 更完整的 AI 协作规范（自进化协议、SOP 流程、坑点累积集等）以本地 `AGENTS.md` 与
> `docs/agents/` 为载体，**仅本地保留、未随仓库发布**；本文件只下沉其中
> **可被机器验证、且跟踪代码已依赖**的最小约束集，避免跟踪代码引用未入库文档而断链。
>
> 每条约束都标注**仓库内可解析的事实来源**（配置文件 / 源码 / CI）。当本文件描述与
> 代码 / 配置冲突时，以代码为准并回改本文件——「能被机器验证的事实永远优先于自然语言」。

## C-1 监听地址：仅绑回环，禁 `0.0.0.0`

- 服务默认只监听 `127.0.0.1:8288`；**禁止**绑定 `0.0.0.0` 等全接口对外暴露。
- 强制点（机器可验证）：
  - `app/integrated_app/config_models.py` host 校验器：`allowed = {"127.0.0.1", "localhost", "::1"}`，非法值直接 `raise ValueError`。
  - `config.yaml`：`server.host: 127.0.0.1` / `server.port: 8288`。
  - `docker-compose.yml`：`ports: "127.0.0.1:8288:8288"`。
- 远程访问须经反向代理转发，不得为图方便改绑地址。

## C-2 路由层不写业务 / 推理逻辑（分层硬约束）

- `app/integrated_app/routes/` 下的路由模块**只做 HTTP 组装**：参数校验 → 调用
  `services/` / `native/` / `model_*` 等能力层 → 返回响应。
- 路由文件中**禁止**出现 `torch.*` 或直接推理逻辑。
- 依赖本约束的代码：
  - `app/integrated_app/routes/metrics_routes.py`（只做指标读取 / 渲染 / 告警评估）
  - `app/integrated_app/security/weight_integrity.py`（只做文件级校验，不触碰推理）

## C-3 禁区目录（默认禁止自动修改，须人工确认）

| 路径 | 为什么禁 | 改动需什么 |
| --- | --- | --- |
| `comfy_kernel/` | vendored 上游 ComfyUI 源码（保持可与上游 diff 追踪） | 记录进 ADR + 保留 patch；人工确认 |
| `pretrained_models/`（portable `internal_models_dir`）、`model/` | 权重误改导致推理静默劣化 | 人工逐项确认 + SHA-256 复验 |
| `app/integrated_app/security/` | 安全边界模块 | 默认禁止自动修改；用户显式授权时可动 |
| `release/`、`demo/assets/` | 发布元数据 / 演示产物 | 只通过构建 / 生成命令更新 |
| `backups/` | 归档 | 只新增，不修改 |

> `comfy_kernel/` 目录自带一份 ComfyUI **官方上游**的 `AGENTS.md`（英文工程规范），
> 它只约束对 `comfy_kernel/**` 内核代码的改动，与本仓规范职责分工不同；该文件属禁区，
> 不得删除 / 移动 / 改写（保留与上游 diff 的可追踪性）。

## C-4 覆盖率门禁：`fail_under = 65`

- 覆盖率红线为 **65%**，机器可验证来源：`pyproject.toml` 的 `[tool.coverage.*] fail_under = 65`；
  CI 的 Coverage Gate 与此同步（见 `.github/workflows/ci.yml`）。
- 本地快检 `scripts/check_local.py` **不含**覆盖率（数值跨平台有差异，以 CI 为准）。

## C-5 单 Worker 串行调度防 GPU OOM

- 推理调度采用**单 Worker 串行**，避免并发任务同时占显存导致 OOM。
- 强制点：`config.yaml` 的 `server.workers: 1` 与任务队列 `worker_mode: single_serial`。

---

> **维护约定**：当被代码 / 配置引用的硬约束新增或变更时，先改事实来源（config / 源码 / CI），
> 再同步本文件；更细粒度的操作性规范（SOP 步骤、坑点复现等）仍写回本地 `docs/agents/`（未随仓库发布），
> 不要从跟踪代码里直接引用那些未入库的路径。
