# Image\_MultiModel AGENTS.md — AI 辅助开发指南

> 🧬 **自进化协议版本**：v1.3
> 📅 **最后更新日期**：2026-09-02
> 🎯 **对应项目版本**：v1.2.2（`config.yaml` 顶层 `version`；引擎 `license: Apache-2.0`）

***

## 0. 文档优先级（单一事实来源）

当以下文档相互矛盾时，**以此顺序为准**，并立即按铁律 #1 修正靠后者：

1. 代码与配置本身（`config.yaml` / `pyproject.toml` / `app/**` 源码 / `comfy_kernel/**`）
2. `docs/official_spec.md`（若本仓存在；当前本仓 `docs/` 仅有 `docs/repo-analysis/家族版本管理对照.md`，无 official\_spec）
3. `AGENTS.md`（本文件）
4. `README.md`
5. `CHANGELOG.md`

> 判据：**能被机器验证的事实永远优先于自然语言描述。**
>
> ⚠️ **特别声明（关于** **`comfy_kernel/AGENTS.md`）**：`comfy_kernel/` 是从 aki-v3 整体复制的 **vendored 上游 ComfyUI 源码**，其目录内自带一份 **ComfyUI 官方上游的** **`AGENTS.md`**（英文工程规范）。那**不是**本项目 `AGENTS.md`，且属禁区目录，**不得删除/移动/改写**（保留与上游 diff 的可追踪性）。它只约束「对 `comfy_kernel/**` 内核代码的改动」，本文件管整个 Image\_MultiModel 仓库；二者职责分工见 §3.2。

***

## ⚠️ 🤖 Agent 行为契约（自进化协议 · 必须严格遵守）

AI Agent 打开本文件后的**第一件事**是执行下面的「🧪 自进化自检清单」，并遵守以下 6 条铁律：

### 🔴 6 条自进化铁律

1. **🔄 同步规则（Synchronize First）**：如果发现项目实际情况（目录结构、依赖版本、技术栈、配置文件名、端口、引擎工作流等）与本文件描述 **不一致** → **立即更新本文件**，不要只改代码不改 AGENTS.md。这是最高优先级规则。
2. **📝 坑点累积（Gotchas Accumulation）**：每次修复 Bug / 踩坑后（哪怕很小），**必须** 追加一条到第 8 节「常见陷阱（Known Gotchas）」，写清：触发场景、现象/报错、正确做法、首次发现日期。
3. **📚 SOP 累积（SOP Accumulation）**：每次完成一个「本文件现有 SOP 没覆盖」的典型开发任务后，**必须** 整理成新 SOP 追加到第 9 节「典型 AI 开发场景 SOP」。
4. **✅ 自检流程（Self-Check on Startup）**：每次打开本文件准备工作前，**必须** 先跑下面的「🧪 自进化自检清单」，逐项核对，有任何一项不符先修正 AGENTS.md 再干活。
5. **🏷️ 版本递增（Version Increment）**：每次更新本文件内容后，**必须** 做三件事：① 顶部「自进化协议版本号」+0.1（小改）或 +1.0（大改/框架调整）；② 更新「最后更新日期」；③ 在末尾「📋 自进化修订记录表」追加一行。
6. **🔬 证据绑定（Evidence Binding）**：本文件中每出现一个**可执行文件路径**（脚本、配置、workflow、源码），它必须是**当时可验证存在**的。若想描述尚未实现的东西，必须显式加 `（计划，未实现）` 前缀。禁止把"CI 会阻断 X"写成一个 CI 里不存在的门禁。本仓**尚无** `scripts/check_spec_refs.py`（家族其它仓有），引用路径前请用文件系统手工核实。

### 🧪 自进化自检清单（每次启动工作前必跑）

- [ ] 顶层结构（`app/`、`app/integrated_app/`、`comfy_kernel/`、`workflows/`、`scripts/`、`tests/`）是否和 §3 模块边界 + 禁区表一致？

- [ ] 单端口 **8288** 与 `config.yaml → server.port` 是否一致（有无改成其它端口）？

- [ ] 默认引擎 `z_image_turbo_native`（`config.yaml → models.default_engine`）的 `backend: native` 与 `comfy_source_dir: comfy_kernel` 是否仍一致？

- [ ] 是否修改了 `config.yaml` 结构或新增配置项？如果是，是否同步了 `app/integrated_app/config.py` / `config_models.py` 的 Pydantic 模型 + 本文件 §5？

- [ ] 是否新增了路由？如果是，是否定义了**模块级** **`router`** **变量**（`app_server.py` 用 `pkgutil` 自动发现，靠模块级 `router`，**不约束文件名后缀**）？

- [ ] 上次工作是否踩了新坑？如果是，是否已追加到第 8 节 Known Gotchas？

- [ ] 上次更新是否正确递增了自进化协议版本号 + 追加了修订记录表？

- [ ] 新增翻译 key 是否已完成 5 语言 JSON 词表同步（`app/integrated_app/locales/` 下 `zh` / `zh-tw` / `en` / `ja` / `ko`，见 §2.4）？

- [ ] §pre-commit 表格是否与 `.pre-commit-config.yaml` **双向**一致？（既无虚构钩子，也无漏记实际钩子）

***

## 1. 项目概览

> **Image\_MultiModel**：多引擎统一文生图（T2I）/ 图生图（I2I）后端服务 + 轻量 Web UI。
> 核心特色：**多引擎热插拔**（native 进程内 Comfy 内核 + diffusers 备用） + 统一 `/api` + 单 Worker 串行调度防 GPU OOM + 安全治理（路径守卫 / 内容过滤 / 权重校验 / 水印）+ 成本治理 / 可观测性。
> 开源协议：**Apache-2.0**（以根 `LICENSE` 为准；`config.yaml` 引擎 `license: Apache-2.0`）
> 技术栈：**Python 3.12+（pyproject** **`target-version = "py312"`）+ FastAPI + Uvicorn + Pydantic v2 + PyYAML + Torch（CUDA）+ Jinja2 + 5 语言 JSON i18n**，推理复用 `comfy_kernel` 内置 ComfyUI 内核。
> 代码入口：`app/clean_launch.py`（推荐；自动选 `.venv`/项目内 WinPython → 校验依赖 → 启动 uvicorn → 自动开浏览器）
> 后端入口：`app/integrated_app/app_server.py` 的 `create_app()` 工厂（模块级同时存在 `app = create_app()` 供 uvicorn 模块引用）
> 默认监听：**`http://127.0.0.1:8288`**（`config.yaml`；禁止 `0.0.0.0`，见 §8）
> 依赖管理：`pyproject.toml`（唯一声明源）+ `requirements.txt` / `requirements-lock.txt`
> 一键脚本：根 `install.bat` / `start.bat`（`app/` 下另有备用的 `app/install.bat` / `app/start.bat`；注意 `app/clean_launch.py` 为真实入口）

***

## 2. 代码风格 & 格式约定

### 2.1 工具配置（`pyproject.toml` 已统一配置）

| 工具                  | 配置位置 / 关键规则                                                                                                                                                                                                                                                 |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ruff**            | `[tool.ruff]`：`line-length=120`、`target-version="py312"`；`[tool.ruff.lint] select=["E","F","W","I","UP","B","SIM"]`，`ignore` 含 `E501/E402/B008/B017/B905/UP042/…`；`isort known-first-party=["integrated_app","app"]`（import 排序经 Ruff `I` 规则强制，**不要**另行手动重排） |
| **Mypy**            | `[tool.mypy]` 见 `pyproject.toml`（非 pre-commit 硬门禁的按实际配置为准）                                                                                                                                                                                                  |
| **Pytest/Coverage** | `[tool.pytest.ini_options]` `testpaths=["tests"]`、`asyncio_mode="auto"`、`--strict-markers`；markers = `slow / integration / security / e2e / smoke`                                                                                                          |

### 2.2 命名规则

- 类/异常 `PascalCase`；函数/方法/变量 `snake_case`；常量 `UPPER_SNAKE_CASE`；模块 `snake_case.py`

- public 函数加 Google 风格 docstring（Args / Returns / Raises）

- 路由文件**不许**出现 `torch.*` / 推理逻辑；只做参数校验 + 调 `services/` / 能力模块 + 返回

### 2.3 分层约束（硬）

- `app/integrated_app/routes/`：只做 HTTP 组装；业务在 `services/`、`native/`、`model_*` 等能力层

- FastAPI 路由靠模块级 `router` 自动注册（`pkgutil` 递归发现），新增路由**必定义** `router = APIRouter(...)`

- 领域层/服务层禁止 import FastAPI；错误统一走 `exceptions.py`

- 外部资源（权重/模型）必须离线可用；不新增运行时联网请求路径

### 2.4 i18n

- 词表：`app/integrated_app/locales/` 下 5 个 JSON——`zh.json` / `zh-tw.json` / `en.json` / `ja.json` / `ko.json`

- 新增翻译 key 必须**同时**补齐 5 份（改完需重启服务生效；Jinja 模板 `auto_reload` 可能即时生效，排查"改了没反应"先分清改的是词表还是模板）

***

## 3. 模块边界 & 禁区目录（🚫 跨层引用严格禁止）

### 3.1 目录地图（可验证存在，2026-09-02 核对）

```
Image_MultiModel/
├── app/
│   ├── clean_launch.py          ← 推荐入口（.venv/WinPython 选择、依赖校验、启动 uvicorn、开浏览器）
│   └── integrated_app/          ← 应用主体
│       ├── app_server.py        ← FastAPI create_app() + pkgutil 路由自动发现 + 静态/模板挂载
│       ├── config.py config_models.py ← 配置加载（读根 config.yaml）+ Pydantic 模型
│       ├── spec.py              ← 领域公式/规格契约层
│       ├── engine_interface.py  ← ImageEngine Protocol + InMemoryEngineRegistry + GenerationConfig（22 项）
│       ├── model_manager.py model_registry.py model_compat.py model_card.py   ← 权重定位/加载/显存/兼容/模型卡片
│       ├── generation_service.py seedvr2_service.py task_queue.py checkpoint.py ← 生成编排/队列/断点
│       ├── lineage.py  cost_governance.py  overload_policy.py  workflow_governance.py workflow_schema.py
│       ├── watermark.py watermark_gpu.py  metrics_quality.py  quality_metrics.py  prompt_expander.py
│       ├── cache.py history_db.py i18n.py sse.py mcp_server.py gpu_utils.py exceptions.py
│       ├── native/              ← 进程内 Comfy 内核推理引擎（engine/executor/diffusers_engine/seedvr/
│       │                          preview/compares/lora/output_pipeline/vram/source）
│       ├── comfy/
│       │   └── schemas/workflow_schema.json
│       ├── routes/              ← /api/* 路由（config/engine/generate/governance/metrics/output/
│       │                          preprocess/preset/prompt/safety/system/task）
│       ├── services/            ← 生成/SeedVR2 业务服务
│       ├── security/            ← content_filter/path_guard/magic_check/upload_limits/weight_integrity/
│       │                          integrity_selfcheck + integrity_manifest.json/kernel_baseline
│       ├── middleware/          ← auth/csrf/rate_limit/error_handler/request_id/security_headers/tracing
│       ├── observability/       ← alerts/generation_metrics/http_metrics/metrics/tracing
│       ├── preprocessors/       ← canny/midas/openpose
│       ├── templates/           ← base.html / index.html（Jinja2）
│       ├── static/              ← css / js（seed.css / app.js）
│       ├── locales/             ← zh/zh-tw/en/ja/ko 五语言 JSON
│       └── testing/fake_engine.py
├── comfy_kernel/                ← 🚫 禁区：vendored 上游 ComfyUI（含它自己的 AGENTS.md，见 §0 声明）
├── workflows/                   ← 用户自放 ComfyUI 工作流的参考目录（已被 `.gitignore` 排除）；
│                                    引擎推理**由代码构建**（native），`config.yaml → engines.<key>.workflow_file`
│                                    一律置空；`app/clean_launch.py` 启动时若无此目录会自动重建空目录
├── scripts/                     ← setup_symlinks.ps1 / generate_integrity_manifest.py / init_watermark_key.py /
│                                  verify_watermark.py / pack_portable.ps1 / benchmark.py / check_config_refs.py 等
├── tests/                       ← 扁平 + e2e/integration/observability/release/smoke/frontend
├── demo/  release/              ← 演示页 / 发布元数据（build_metadata.json、sbom.json）
├── config.yaml  pyproject.toml  requirements*.txt  .pre-commit-config.yaml  start.bat  install.bat
├── README.md  CHANGELOG.md  SECURITY.md  CODE_OF_CONDUCT.md  LOCAL_RULES.md  AGENTS.md
```

> 注意：本仓 `docs/` 目前仅有 `docs/repo-analysis/`（家族对照报告）；后续新增文档按 §10 规则归位。

### 3.2 comfy\_kernel 分工（本仓库特有，务必遵守）

- `comfy_kernel/` 是 **vendored 上游 ComfyUI**，其 `comfy_kernel/AGENTS.md` 是 **ComfyUI 官方工程规范**，与本文件角色不同：

  - 改 `comfy_kernel/**` 内核代码 → 遵循 `comfy_kernel/AGENTS.md`（上游纪律）

  - 改整个仓库其它部分 → 遵循本文件（项目纪律）

- `config.yaml → models.engines.<engine>.comfy_source_dir: comfy_kernel` 指明推理内核来源；引擎权重经 `config.yaml` 的 `mount_map` + `symlink_strategy: junction`，由 `scripts/setup_symlinks.ps1` 管理（同卷零冗余）。

### 🚫 禁区目录（禁止 AI 自动修改，必须人工确认）

| 路径                                                                         | 为什么禁                                    | 改动需什么                                                 |
| -------------------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------- |
| `comfy_kernel/`                                                            | vendored 上游（ComfyUI），改动后与上游 diff 丢失可更新性 | 记录进 ADR + 保留 patch 文件；人工确认                            |
| `pretrained_models/`（`config.yaml` portable `internal_models_dir`）`model/` | 权重误改导致推理静默劣化                            | 人工逐项确认 + SHA-256 复验（走 `security/weight_integrity.py`） |
| `app/integrated_app/security/`                                             | 安全边界模块                                  | 默认禁止自动修改；用户显式授权时可动                                    |
| `release/`、`demo/assets/`                                                  | 发布元数据/演示产物                              | 只通过构建/生成命令更新                                          |
| `backups/`                                                                 | 归档                                      | 只新增，不修改                                               |

***

## 4. 启动命令

### 4.1 一键启动（推荐）

- **Windows**：双击根 `start.bat` → 调用 `app/clean_launch.py` → 自动打开 `http://127.0.0.1:8288`

- 首次环境：根 `install.bat` 或 `install.sh`（安装 CUDA 版 torch + 剩余依赖）

### 4.2 手动启动（调试）

```bash
# 方式 A（推荐，含环境自检 + 自动开浏览器）
python app/clean_launch.py

# 方式 B（纯 Uvicorn 前台调试，含 --reload，仅限开发）
python -m uvicorn app.integrated_app.app_server:app --host 127.0.0.1 --port 8288 --reload
# ⚠️ --reload 生产禁用；--workers 只能 = 1（串行信号量是进程内字典，多 worker 各自放行 1 并发 → OOM）
```

### 4.3 启动后验证

- 打开 `http://127.0.0.1:8288` 能看到 Web UI；`/api/system/...` 健康端点返回 `{"status":"ok",...}` 即成功（具体端点见 `app/integrated_app/routes/system_routes.py`）。

- `config.yaml → models.auto_load_default_engine: false`，默认引擎不会自动加载，需在 UI/接口选择后加载。

***

## 5. 配置与环境变量

- 唯一权威配置源：根 **`config.yaml`**（顶层键：`version / server / models / inference / ...`），由 `app/integrated_app/config.py` 加载。

- **环境变量覆盖**：

  - `app/clean_launch.py` 提供 `IMM_EXTRA_PYTHON_DIRS`（显式指定额外 Python 目录；禁硬编码外部绝对解释器路径，防劫持）

  - 离线相关：`HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` / `MODELSCOPE_OFFLINE` / `COMFYUI_DISABLE_UPDATE_CHECK`（`config.py` `_apply_environment` 用 `setdefault` 注入，显式系统变量 > `.env` > 代码默认值）

- **引擎规格**：引擎声明在 `config.yaml → models.engines.<key>`（如 `z_image_turbo_native`：`backend: native`、`comfy_source_dir: comfy_kernel`、`text_encoder/unet/vae` 子路径、`vram_gb`、`default_precision`、`supported_features`）。新增引擎须**同时**在此登记；引擎推理由代码构建，`workflow_file` 保持置空（勿虚构 JSON 路径）。

- 端口/监听：`server.port`（8288）、`server.host`（127.0.0.1）、`server.workers`（1）、`server.ssl`。

***

## 6. 测试约定

- **覆盖率门禁（真实生效）**：`pyproject.toml → [tool.coverage.report] fail_under = 65`（≥65% 才通过；`source = ["app/integrated_app"]`，omit `*/__init__.py / locales / static / schemas`）。未达标主要集中 GPU 依赖模块（`native/`、`seedvr2_service`、`preprocessors`），CI 无 GPU 时相关用例整体 skip。

- **命令**：

  - 全量单测 + 覆盖率：`pytest tests/ --cov=app/integrated_app --cov-report=term-missing --cov-fail-under=65 -q`

  - 冒烟：`pytest tests/smoke/`（`test_startup_smoke.py`）

  - 集成：`tests/integration/`（`test_fake_generation_flow.py` 等，`testing/fake_engine.py` 提供 mock 引擎）

  - E2E：`tests/e2e/`（Playwright，`.github` 触发方式与本地运行见 `tests/e2e`，需服务已监听 8288）

- **命名**：类 `Test<被测类>`；方法 `test_<场景>_<期望>_<条件>`；**严禁** **`assert True`** **凑覆盖率**。

- 目录：`tests/` 扁平为主，另含 `e2e/` `integration/` `observability/` `release/` `smoke/` `frontend/`；`tests/package.json` 管理前端测试依赖。

***

## 7. Git 提交规范 & CI

### 7.1 Conventional Commits

```
<type>(<scope>): <subject>
```

Type：`feat` / `fix` / `docs` / `refactor` / `perf` / `test` / `chore` / `ci` / `security`
Scope 建议：`native` / `engine` / `routes` / `security` / `i18n` / `observability` / `ci`

### 7.2 Pre-commit（`.pre-commit-config.yaml` 实际钩子，双向一致，勿臆造）

| 钩子                        | 作用                         |
| ------------------------- | -------------------------- |
| `ruff`（--fix）             | lint + 自动修可修问题             |
| `ruff-format`             | 代码格式化                      |
| `trailing-whitespace`     | 去行尾空白                      |
| `end-of-file-fixer`       | 保证文件以换行结尾                  |
| `check-yaml`              | YAML 语法（含 `config.yaml`）   |
| `check-added-large-files` | 拦误加大文件                     |
| `check-merge-conflict`    | 检查遗留冲突标记                   |
| `debug-statements`        | 拦未清理的 `breakpoint()`/`pdb` |

> 注：本仓 pre-commit **没有** mypy / check-i18n-coverage 钩子；不要在本表写入不存在的钩子。

### 7.3 CI（⚠️ 本仓无 `.github/` 目录，无 GitHub Actions CI）

- **实测（2026-09-02）：本仓整个** **`.github/`** **目录都不存在**，故没有任何 `.github/workflows/*.yml`。质量门禁以**本地**为准：

  - `precheck.ps1`（push 前预检；`-Full` 含测试与覆盖率门禁）

  - `.pre-commit-config.yaml` 钩子（§7.2）

  - 覆盖率门禁 `pyproject.toml → [tool.coverage.report] fail_under = 65`

- 不要臆写"quality-gate / security-assertions"等 CI job 名称（v1.0 曾误写，v1.1 已纠正）。

- `demo/README.md` 提到的 `pages-deploy.yml` 在本仓并不存在（历史参考），勿据此断言存在 CI。

- 若未来引入 CI，需在 `.github/workflows/` 落地后再更新本节（证据绑定）。

***

## 8. 常见陷阱（Known Gotchas）

> 历史踩坑记录尚未系统建表；**自本协议生效起，每次踩坑按铁律 #2 追加到下表尾部。**

| # | 坑点标题                                     | 触发场景                                                        | 现象/报错                      | 正确做法                                                                       | 首次发现日期                                   |
| - | ---------------------------------------- | ----------------------------------------------------------- | -------------------------- | -------------------------------------------------------------------------- | ---------------------------------------- |
| 1 | **裸跑** **`0.0.0.0`** **/ 硬编码外部解释器路径**    | 把监听改成 `0.0.0.0`，或在 `clean_launch.py` 写死其它项目/系统的绝对 Python 路径 | 安全审计红线；路径劫持风险              | 只监听 `127.0.0.1`；解释器只走 `.venv`/项目内 `WPy64-*`/`IMM_EXTRA_PYTHON_DIRS`（§3、§4） | 2026-09-02（来源：`clean_launch.py` 注释 M-05） |
| 2 | **`comfy_kernel`** **被误当成项目 AGENTS 改/删** | 看到 `comfy_kernel/AGENTS.md` 以为是本项目文件                        | 破坏 vendored 上游 diff，丢失可更新性 | 原位保留；改内核走上游规范，改仓库走本文件（§0 声明）                                               | 2026-09-02                               |
| 3 | （待填）                                     | <br />                                                      | <br />                     | <br />                                                                     | <br />                                   |

***

## 9. 典型 AI 开发场景 SOP（照着做，少踩坑）

#### SOP-1: 新增一个 `/api` 子路由

1. 在 `app/integrated_app/routes/` 新建 `xxx_routes.py`，定义 `router = APIRouter(prefix="/xxx", tags=["xxx"])`。
2. **无需手动** **`include_router`**：`app_server.py` 用 `pkgutil` 自动发现模块级 `router` 并注册（约束是模块级 `router` 变量，**不看文件名后缀**）。新增后确认能被 `create_app()` 发现。
3. 需要写库走 `history_db.py` / `cache.py`；需要生成业务走 `services/generation_service.py` + `task_queue.py`；需要推理参数走 `engine_interface.py` / `spec.py`。
4. 在 `tests/` 补 pytest；`/api/system/...` 健康端点确认不影响既有路由。
5. 按 §5 核对是否需新增 `config.yaml` 配置或环境变量。

#### SOP-2: 新增/修改一个引擎

1. 在 `config.yaml → models.engines.<key>` 登记引擎（backend、`comfy_source_dir`、`text_encoder/unet/vae` 子路径、vram/precision、`supported_features`）。
2. 引擎推理**由代码构建**（native/backend + `comfy_kernel`），`config.yaml → engines.<key>.workflow_file` **保持置空**（治理 `workflow_governance.py` 对空值直接跳过校验）；不要虚构指向不存在 JSON 的路径（铁律 #6）。
3. 若引擎依赖新权重，走 `security/weight_integrity.py` 的 SHA-256 校验链路 + `scripts/setup_symlinks.ps1` 挂载。
4. 加/改后端实现（`app/integrated_app/native/` 或 `diffusers_engine.py`），并补 `tests/` 用例；覆盖走 GPU 的模块在 CI 无 GPU 时会被 skip，勿因此漏写 mock 覆盖。

#### SOP-3: 增加一处翻译文案

1. 在代码/模板用 key 调用 `t()`（或模板过滤器）。
2. **同时**补齐 `app/integrated_app/locales/` 下 5 份 JSON（`zh`/`zh-tw`/`en`/`ja`/`ko`）的同一个 key。
3. 改完重启服务验证；缺失 key 按 §8.2 回退逻辑处理（勿用会产生真值空串的反模式）。

***

## 📋 自进化修订记录表（AGENTS.md 进化史）

| 自进化版本 | 日期         | 触发原因                                                            | 更新内容摘要                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | 对应项目版本 | 已校验 |
| :---: | ---------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----: | :-: |
|  v1.0 | 2026-09-02 | 家族规范对齐：为 Image\_MultiModel 补充桶级 AGENTS.md（此前仅有 LOCAL\_RULES.md） | 建立自进化协议（6 铁律 + 自检清单）；§0 明确 comfy\_kernel/AGENTS.md = 上游文件、非本项目 AGENTS；项目概览（多引擎 native/diffusers、单端口 8288、词网 `comfy_kernel`）；模块地图（app/integrated\_app 各子包）；禁区表（comfy\_kernel/安全/权重/发布）；启动命令；配置与环境变量；测试约定（fail\_under=65）；Git/CI/Pre-commit 钩子双向一致表；Known Gotchas 起步（端口/解释器、comfy\_kernel 误改 2 条）；SOP-1\~3；归档规范；家族远程同步/push 预检/CI 流程铁律。**所有引用路径均经文件系统核实**（本仓无 docs/ 目录，无 check\_spec\_refs.py，故不引用）                                                                                                                                                                     | v1.2.2 |  —  |
|  v1.1 | 2026-09-02 | 铁律 #1 事实同步：engine `workflow_file` 置空 + 修正 v1.0 臆造 CI 表述         | ① 用户删除 `workflows/` 参考 JSON（`flux1_dev_fp8.json` / `flux2_klein_9b.json` / `Z_image_turbo.json` 均不在磁盘），`config.yaml` 的 `z_image_turbo_native.workflow_file` **置空**（引擎推理由代码/native 构建，治理 `workflow_governance.py` 对空值直接跳过）；同步 `tests/test_config.py` 断言为 `workflow_file == ""`；② **修正 v1.0 臆造**：实测本仓**整个** **`.github/`** **目录不存在、无 GitHub Actions CI**，§7.3 重写为"无 CI，门禁以 precheck.ps1 + pre-commit + fail\_under=65 为准"，并撤销对 quality-gate/security-assertions/pages-deploy.yml 的错误断言；③ §3.1 `workflows/` 行、SOP-2、§5 统一改为"引擎推理由代码构建，`workflow_file` 保持置空（勿虚构 JSON 路径）" | v1.2.2 |  —  |
|  v1.2 | 2026-09-02 | 铁律 #1 同步：`docs/` 已建立，修正"无 docs/"表述                              | t1 产出跨仓版本台账落在 `docs/repo-analysis/`，导致 §0/§3.1/§10 的"本仓无 docs/ 目录"表述失效；已改为"docs/ 仅有 docs/repo-analysis/"，并保留归档规则。另登记待核实：`config.yaml` 中 `security.integrity_selfcheck.manifest_file` 与 `i18n.locale_dir` 仍指向 `bin/integrated_app/...`（旧目录名，实际为 `app/integrated_app/...`），归入 t9 核验                                                                                                                                                                                                                                                                                     | v1.2.2 |  —  |
|  v1.3 | 2026-09-02 | 落地开放项 #1/#2：版本统一 1.2.2 + 补配置引用门禁脚本                              | ① `tests/test_config.py` 版本断言由 2.0.0 改为 1.2.2（对齐 config.yaml，用户裁决）；② 新增 `scripts/check_config_refs.py`（AST 解析配置模型 + 代码引用扫描 + security「声明即消费」对账），`tests/test_config_refs_gate.py` 三例转为通过（25 passed）；§3.1 scripts 列表登记新脚本                                                                                                                                                                                                                                                                                                                                               | v1.2.2 |  —  |

<!-- 🔄 下次更新 AGENTS.md 时，在上面表格末尾追加新一行，不要删除历史记录 -->

***

## 📂 文件归档与放置规范（重要：新增文件必须遵守）

> 本仓 `docs/` 自 2026-09-02 起建立，当前含 `docs/repo-analysis/`（跨仓版本管理对照等）。后续新增文档归属见下方分类，先判断类型再放置。

**根目录允许放置**

- 标准仓库文件：README、LICENSE、CHANGELOG、AGENTS、SECURITY、CODE\_OF\_CONDUCT、LOCAL\_RULES

- 构建与配置：config.yaml、pyproject.toml、requirements\*.txt、.pre-commit-config.yaml、.env.example、Dockerfile、docker-compose.yml、启动/安装脚本（start/install .bat/.sh）、precheck.ps1

- 明确被 build/CI/文档要求从根目录运行的工具

**禁止事项（防止回归混乱）**

- ❌ 一次性调试脚本/截图/日志/草稿 → 放 `scripts/` 或归档目录，绝不堆在根目录

- ❌ 临时/生成产物堆在根目录（`.venv`、`node_modules`、`__pycache__`、`outputs/` 等已有 `.gitignore` 管理）

- ❌ 移动/删除 gitignored 运行时产物

- ❌ 删除旧版本文档 → 需要留档移入归档目录

- 新增文件前若不确定归属，先询问，不要自作主张放置。

***

## 远程同步铁律（Remote Sync Rule）

1. **禁止静默直写远程**：任何通过 GitHub API / 网页端直接修改远程 main 的操作（CI 工作流、依赖配置、分支、PR 等），执行前必须向用户说明，执行后必须检查本地与远程差异。
2. **操作远程后必须同步**：直写远程导致本地落后时，必须提醒用户 `git pull`，或经用户同意后代为同步；禁止留下分叉状态。
3. **禁止动未提交改动**：用户本地存在未提交修改时，不得擅自 commit / push / stash / checkout 覆盖，必须先征得用户同意。
4. **优先走本地流程**：代码与配置修改默认在本地完成、经用户确认后 push；确需直写远程时按第 2 条补同步。

## push 前预检铁律

- 提交并推送前必须通过本地预检：直接 `git push`（pre-push hook 自动执行 precheck.ps1），或手动 `powershell -File precheck.ps1` 全绿后推送。

- 预检失败时**修复代码**，而不是跳过检查；`--no-verify` 仅限用户明确要求时使用。

- 改动业务代码后需跑一次 `-Full`（含测试与覆盖率门禁）再推送。

- 预检脚本与 hook 均为本地文件（不入库），勿删除。

## CI 流程铁律

1. **推送闭环**：push ≠ 完成。push 后必须用 `gh run list` / `gh run watch` 盯 CI 到终态并回报结果；红了**当场自己修**（刚推送的上下文最全），跑不完或修不动立即回报而不是留到明天。
2. **修复交接**：CI 红时先读 `FIX_LOG.md`（若存在）；动手修必须追加一行：**失败签名（关键报错行）→ 假设 → 动作 → 结果**。同一失败签名第二次出现，禁止再试同方向，必须读完整失败日志或 revert 换策略。同一仓库同一时刻只允许一个修复者。
3. **红灯止损**：main 红后限时 30-60 分钟拿不出明确根因 → `git revert` 回到 last green，恢复 main 绿色后再从容修（配合 `FIX_LOG.md`）。**revert 是止损，不是失败。**

