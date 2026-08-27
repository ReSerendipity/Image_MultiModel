# Image MultiModel AGENTS.md — AI 辅助开发指南

> 🧬 **自进化协议版本**：v1.27  
> 📅 **最后更新日期**：2026-08-27  
> 🎯 **对应项目版本**：v1.4.0（Apache-2.0 开源协议）

---

## 0. 文档优先级（单一事实来源）

当以下文档相互矛盾时，**以此顺序为准**，并立即按铁律 #1 修正靠后者：

1. 代码与配置本身（`pyproject.toml` / `package.json` / `.pre-commit-config.yaml` / 源码）
2. `docs/official_spec.md`（若本仓存在；当前本仓无此文件）
3. `AGENTS.md`
4. `README.md` / `docs/**`
5. `CHANGELOG.md`

> 判据：**能被机器验证的事实永远优先于自然语言描述。**

---

## ⚠️ 🤖 Agent 行为契约（自进化协议 · 必须严格遵守）

AI Agent 打开本文件后的**第一件事**是执行下面的「🧪 自进化自检清单」，并遵守以下 5 条铁律：

### 🔴 6 条自进化铁律
1. **🔄 同步规则（Synchronize First）**：如果发现项目实际情况（目录结构、依赖版本、技术栈、配置文件名等）与本文件描述 **不一致** → **立即更新本文件**，不要只改代码不改 AGENTS.md。这是最高优先级的规则。
2. **📝 坑点累积（Gotchas Accumulation）**：每次修复 Bug / 踩坑后（哪怕是很小的坑），**必须** 追加一条到 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)（本地文档，未随仓库发布） 的 Known Gotchas 表，写清楚：触发场景、现象/报错、正确做法、首次发现日期。
3. **📚 SOP 累积（SOP Accumulation）**：每次完成一个「本文件现有 SOP 没覆盖」的典型开发任务后，**必须** 把步骤整理成新 SOP 追加到 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)（本地文档，未随仓库发布）。
4. **✅ 自检流程（Self-Check on Startup）**：每次打开本文件准备工作前，**必须** 先运行下面的「🧪 自进化自检清单」，逐项核对，有任何一项不符先修正 AGENTS.md 再干活。
5. **🏷️ 版本递增（Version Increment）**：每次更新本文件内容后，**必须** 做三件事：① 文件顶部「自进化协议版本号」+0.1（小改）或 +1.0（大改/框架调整）；② 更新「最后更新日期」；③ 在文件末尾「📋 自进化修订记录表」追加一行记录。
6. **🔬 证据绑定（Evidence Binding）**：本文件中每出现一个**可执行文件路径**（脚本、配置、workflow、源码），它必须是**当时可验证存在**的。引用前跑一次 `python scripts/check_spec_refs.py`；若确实想描述尚未实现的东西，必须显式加 `（计划，未实现）` 前缀。禁止把"CI 会阻断 X"写成一个 CI 里不存在的门禁。

### 🧪 自进化自检清单（每次启动工作前必跑）
- [ ] 目录结构（`app/integrated_app/`、`routes/`、`native/`、`middleware/`、`security/`、`tests/`）是否和第 3 节模块边界描述一致？
- [ ] 原生引擎（`z_image_turbo_native`，`backend: native`）的配置是否和 `config.yaml → models.engines` 实际条目一致？模型来源是否为 portable（`model/`，无外部链接）？
- [ ] 上次工作是否踩了新坑？如果是，是否已追加到 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)（本地文档，未随仓库发布） 的 Known Gotchas 表？
- [ ] 是否新增了路由文件？如果是，是否已确保文件内定义了 `router = APIRouter(...)` 变量（app_server.py 使用 `pkgutil.iter_modules` 自动发现，无需手动注册）？
- [ ] 新增的翻译 key 是否已完成 5 种语言 JSON 同步（见 [I18N_STANDARD.md](docs/project/I18N_STANDARD.md)（本地文档，未随仓库发布））？
- [ ] 上次更新是否正确递增了自进化协议版本号 + 追加了修订记录表？
- [ ] 版本号是否已同步：`config.yaml` / `app/integrated_app/__init__.py` / `CHANGELOG.md` 三处一致？
- [ ] 本文引用的 scripts/ configs/ workflows/ 路径是否全部真实存在？（跑 `python scripts/check_spec_refs.py`，要求退出码 0）
- [ ] §pre-commit 表格是否与 `.pre-commit-config.yaml` **双向**一致？（既无虚构钩子，也无漏记实际钩子）

---

## 1. 项目概览

> **Image MultiModel**：Z-Image Turbo 图像生成平台 — 基于 ComfyUI 工作流引擎，驱动唯一引擎 Z-Image Turbo 的统一 Web UI。  
> 核心特色：**单一 Z-Image Turbo 引擎**（`z_image_turbo_native`，进程内原生推理）+ VRAM 预检 + 批量任务队列 + SSE 实时进度 + DCT 频域水印溯源 + 安全加固体系 + 5 语言国际化  
> 开源协议：**Apache-2.0**  
> 技术栈：**Python 3.10+（推荐 3.12） + FastAPI + Uvicorn + Pydantic v2 + PyYAML + aiohttp + websockets + aiofiles + SQLite（WAL + FTS5） + 原生引擎（复用 comfy_kernel 源码）**  
> 代码入口：`app/clean_launch.py`（推荐，含配置预热 + 数据目录创建 + 健康检查）  
> 默认端口：**`http://127.0.0.1:8288`**（禁止 0.0.0.0 监听，见 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)（本地文档，未随仓库发布） Known Gotchas）  
> 模型来源：portable（`model/`，无外部链接，便携独立运行）  
> 依赖管理：`requirements.txt`（生产）+ `requirements-lock.txt`（锁定）+ `pyproject.toml`（工具配置）

---

## 2. 代码风格约定

### 2.1 Lint / 格式化 / 类型检查
| 工具 | 配置说明 | 关键规则 |
|------|---------|---------|
| **Ruff** | `pyproject.toml → [tool.ruff]` | `target-version = "py312"`，`line-length = 120` |
| Ruff select | `select = ["E", "F", "W", "I", "UP", "B", "SIM"]` | UP（Python 3.12 现代化语法）、B（flake8-bugbear）、SIM（flake8-simplify） |
| Ruff ignore（⚠️ 重要，不要擅自移除） | 见右侧详细说明 | **为什么有这些 ignore？每条都有理由**<br>`E501`：行长超 120 不强制报错（ruff format 已处理大部分场景）<br>`E402`：`app/clean_launch.py` 需要先 `sys.path.insert(0, app_dir)` 再 import integrated_app<br>`B008`：Pydantic `Field(default_factory=list/dict)` 场景大量使用可变默认值，框架官方推荐用法<br>`B017`：安全测试 `pytest.raises(Exception)` 泛匹配（攻击用例故意抓所有异常测回退）<br>`B905`：`zip()` 无 `strict` 参数（兼容旧代码）<br>`SIM102/SIM108/SIM105/SIM117`：三元表达式 / try-except 简化（可读性优先，不强制） |
| **Mypy** | `[tool.mypy] disallow_untyped_defs = false` | 渐进式策略：`config.py`、`config_models.py`、`history_db.py`、`watermark.py`、`security/path_guard.py` 开启严格类型；`comfy/`、`routes/` 因第三方 ComfyUI API 响应类型不确定放宽 |
| **命名规则** | 全局 | 类/异常 `PascalCase`，函数/方法/变量 `snake_case`，常量 `UPPER_SNAKE_CASE`，模块 `snake_case.py` |

### 2.2 Import 顺序（Ruff `isort` 强制执行，known-first-party = integrated_app, app）
```python
# 1. Stdlib（import sys / os / asyncio / typing / json）
# 2. Third-party（import fastapi / pydantic / yaml / aiohttp / numpy / PIL）
# 3. Local project（from integrated_app.config import get_config / from integrated_app.native.engine import NativeEngine）
```

### 2.3 格式化 / Lint 命令
```bash
python -m ruff format bin tests        # 格式化
python -m ruff check --fix bin tests   # 自动修复可修复问题
python -m ruff check bin tests         # 检查（CI 会跑，阻断 PR）
python -m mypy app/integrated_app      # 类型检查
```

### 2.4 Docstring
- public 类 / 函数用 **Google 风格** docstring：
  ```python
  async def infer_txt2img(self, params: Txt2ImgParams) -> list[Image.Image]:
      """文生图推理（调用 ComfyUI 工作流）。

      Args:
          params: 文生图参数（prompt / negative_prompt / steps / cfg / width / height / seed / batch）

      Returns:
          list[PIL.Image.Image]: 生成的图像列表，长度 = params.batch_size

      Raises:
          EngineNotLoadedError: 引擎未加载（需要先调用 load()）
          WorkflowValidationError: 工作流 JSON 节点 ID 与 Schema YAML 不匹配
          VramEstimateExceededError: VRAM 预估超过 GPU 可用显存 ×1.5 安全系数
      """
  ```

---

## 3. 模块边界 & 5 条硬约束（🚫 绝对不能违反）

> 📂 完整目录树（各模块文件职责 / 修改注意事项）已移入 [MODULE_MAP.md](docs/project/MODULE_MAP.md)（本地文档，未随仓库发布）。
> 本节保留 5 条硬约束原文。
### 🔴 5 条硬约束（违反一条直接导致生产事故）
1. **`routes/` 目录永远不写业务逻辑**：路由只能做：参数校验（Pydantic Model）+ 调 `model_manager` / `task_queue` / `history_db` / `*_service` + 返回响应。**路由文件里不允许出现 `torch.*` / `numpy.*` / 任何推理相关代码**，推理必须通过 `engine_interface` 或 `model_manager`。
2. **`native/` 是唯一引擎实现**：项目已完全脱离外部 ComfyUI 进程，推理统一走进程内 `NativeEngine`（复用本地 `comfy_kernel` 源码，使用前必须先 `source.ensure_loaded()` 注入 sys.path）。`native/` 不做业务编排、不写 DB、不写业务日志（只抛异常给上层）。
3. **`static/` 前端代码绝对不包含 Python 逻辑，后端代码绝对不包含前端逻辑**：前后端通过 REST API + SSE 解耦。FastAPI 只负责静态文件托管，不允许在 Python 里拼 HTML / JS / CSS 字符串。
4. **所有推理任务单 Worker 串行执行**（`task_queue.py`，信号量=1）。严禁路由层直接并发 `await engine.infer_txt2img()`——哪怕 GPU 空闲也不行。Z-Image Turbo 9B + 大 batch 并发 GPU VRAM 直接爆 OOM。
5. **所有文件路径操作必须过 PathGuard**：任何用户输入参与路径拼接（读取 outputs、保存 presets、读取上传图片）→ 必须 `PathGuard.resolve(base_dir, user_input)`，**禁止 `os.path.join(base, user_input)` 的组合**。
## 🚫 禁区目录（禁止 AI 自动修改，必须人工确认）

| 路径 | 为什么禁 | 改动需什么 |
|---|---|---|
| `model/` | 权重误改导致推理结果静默劣化 | 人工逐项确认 + SHA-256 复验 |
| `comfy_kernel/` | vendored 上游（ComfyUI 内核），改动后与上游 diff 会丢失可更新性 | 记录进 ADR + 保留 patch 文件 |
| `outputs/` | 生成物，手改即失效 | 只通过生成命令更新 |
| `docs/_devarchive/` | 归档不可回写 | 只新增，不修改 |

## 4. 测试约定（覆盖率门槛 75% + 6 层测试分层）


> 📂 6 层测试分层表 / 命名规范 / 覆盖率路线图 / 测试命令 / 安全测试要求已移入 [TEST_LAYERS.md](docs/project/TEST_LAYERS.md)（本地文档，未随仓库发布）。
> 门槛：`pyproject.toml → [tool.coverage.report] fail_under = 75`（CI 强制，低于 75% 直接阻断 PR）。
---

## 5. 依赖管理
| 文件 | 作用 | 更新频率 |
|------|------|---------|
| `requirements.txt` | 生产依赖（FastAPI / Uvicorn / Pydantic / aiohttp / websockets / Pillow / numpy / scipy / PyYAML 等） | 加新依赖时更新 |
| `requirements-lock.txt` | 完整锁定版本（含传递依赖） | 每次改 requirements 后 `python scripts/generate_lock.py` 生成（如果还没这个脚本就 `pip freeze > requirements-lock.txt`） |
| `pyproject.toml` | 工具配置（Ruff / Mypy / Pytest / Coverage） | 改工具参数时更新 |

> ⚠️ **注意**：PyTorch 不在 requirements.txt 里，由 `install.bat` / `install.sh` 根据 CUDA 版本单独安装（--index-url https://download.pytorch.org/whl/cu132 或 cu124，具体看环境）。

---

## 6. 构建 / 启动命令
> 📂 一键启动 / 手动启动 / 启动后验证详表已移入 [BUILD_COMMANDS.md](docs/project/BUILD_COMMANDS.md)（本地文档，未随仓库发布）。
> 常用：`python app/clean_launch.py`（推荐入口，监听 http://127.0.0.1:8288）。
## 7. 依赖注入 & 单例注册表清单

> 所有跨层访问必须通过 FastAPI Depends 或对应的 Registry 单例，**禁止直接从模块 import 全局变量实例**。

| 单例 | 获取方式（Depends / get_xxx()） | 作用域 |
|------|--------------------------------|--------|
| `config: AppConfig` | `Depends(get_config)`（integrated_app.config） | app 生命周期全局单例，启动时加载一次 |
| `model_manager: ModelManager` | `Depends(get_model_manager)`（integrated_app.model_manager） | lifespan 启动时实例化，负责引擎加载/卸载/切换 |
| `task_queue: TaskQueue` | `Depends(get_task_queue)`（integrated_app.task_queue） | 全局单例，信号量=1 保证串行推理 |
| `history_db: HistoryDB` | `Depends(get_history_db)`（integrated_app.history_db） | 全局单例 SQLite 连接池（WAL 模式） |
| `sse_broker: SSEBroker` | `Depends(get_sse_broker)`（integrated_app.sse） | 全局单例，SSE 事件发布订阅 |
| `path_guard: PathGuard` | `Depends(get_path_guard)`（integrated_app.security.path_guard） | 全局单例，所有路径操作必过 |

> 测试中替换单例：`app.dependency_overrides[get_config] = lambda: MockAppConfig(...)`

---
## 8. i18n 多语言规范（5 种语言：简中 / 繁中 / 英 / 日 / 韩）
> 📂 翻译机制 / 三层 fallback 链 / 新增 key 6 步流程已移入 [I18N_STANDARD.md](docs/project/I18N_STANDARD.md)（本地文档，未随仓库发布）。
## 9. Git 提交规范 & 发布流程 & CI

### 9.1 Conventional Commits
```
<type>(<scope>): <subject>

<body>

<footer>
```
Type：`feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `chore` / `ci` / `security`  
Scope 建议：`comfy` / `routes` / `queue` / `history` / `i18n` / `watermark` / `security` / `workflow/z-turbo`

示例：
```
feat(workflow/z-turbo): VRAM 预检自动切 FP8 精度 + batch chunk 100 张落盘 checkpoint
fix(watermark): 修复 DCT 嵌入 uint8 回绕导致的水印提取失败
test(security): 新增 PathGuard 路径穿越攻击测试 30 例
ci: 增加 E2E Playwright 截图对比 job
```

### 9.2 版本号同步修改清单（🚨 发版时 3 个文件 3 处一起改，漏一个 API /health 版本号对不上）
| # | 文件路径 | 要改的字段 | 示例（2.0.0 → 2.1.0） |
|---|---------|-----------|---------------------|
| 1 | **`config.yaml`（根）** | 顶部第一行 `version:` | `version: 2.0.0` → `version: 2.1.0` |
| 2 | **`app/integrated_app/__init__.py`** | `__version__` | `__version__ = "2.0.0"` → `__version__ = "2.1.0"` |
| 3 | **`CHANGELOG.md`（根）** | 标题格式 `## [x.x.x] - YYYY-MM-DD` | `## [2.0.0] - 2026-08-10` → 在上面新增 `## [2.1.0] - 2026-08-17` |

> ⚠️ 为什么 3 处都要？`/api/system/health` 返回的 version 从 `__init__.py` 读，配置保存时 YAML 里的 version 用于数据迁移判断，CHANGELOG 用于 GitHub Release 自动生成说明。

### 9.3 CI Workflow（`.github/workflows/` 三个核心）
| Workflow | 触发时机 | 关键步骤 |
|----------|---------|---------|
| **ci.yml** | 每个 PR / push 到 main | Ruff lint + format 检查 → Mypy 类型检查 → pytest 单元/路由/安全 + 覆盖率（fail_under=75%）→ i18n 完整性校验 |
| **release.yml** | tag `v*.*.*` 推送 | 构建 Docker 镜像 → 打包便携版（WinPython + 依赖）→ 创建 GitHub Release → 上传构建产物 |
| **security.yml** | 每周定时 / PR 改了 security/ | CodeQL 代码扫描 → PathGuard 全量攻击向量回归 → Integrity manifest 校验 → 依赖漏洞扫描（pip-audit） |

---
## 10. Pre-commit 钩子（提交前自动跑的检查）

`.pre-commit-config.yaml` 配置了 8 个钩子，每个 commit 前自动执行：
| 钩子 | 作用 |
|------|------|
| `ruff` | 自动 fix 简单 lint 问题 + import 排序 |
| `ruff-format` | 自动格式化（确保和 Ruff lint 配置一致） |
| `trailing-whitespace` | 去除行尾空格 |
| `end-of-file-fixer` | 确保文件末尾有空行 |
| `check-yaml` | YAML 语法检查（config.yaml / workflows/*.yml 都靠它） |
| `check-added-large-files` | 防止误提交 >5MB 的大文件（模型权重 / 图片不要提交） |
| `check-merge-conflict` | 检查有没有遗留 `<<<<<<< HEAD` 冲突标记 |
| `debug-statements` | 防止把 `breakpoint()` / `import pdb` 提交上去 |

### 安装（首次 clone 后必执行一次）
```bash
pip install pre-commit
pre-commit install      # 安装到 .git/hooks/pre-commit
# 可选：手动跑一遍所有钩子（确认环境 OK）
pre-commit run -a
```

---
## 11. 安全注意事项
> 📂 安全注意事项全文（6 条）已移入 [SECURITY_NOTES.md](docs/project/SECURITY_NOTES.md)（本地文档，未随仓库发布）。
## 12. MASTER_PLAN 配合规则

### 12.1 新功能开发流程（5 步，一步不能落）
1. **先更新 `MASTER_PLAN.md`** 中对应里程碑的验收标准（如果里程碑完成度已经是 100%，就在下面追加新里程碑）
2. **再写代码**，代码实现严格对齐 MASTER_PLAN 中的契约定义（M0→骨架 / M1→ComfyUI 适配 / M2→文生图工作台 / M4→批量+历史 / M5→UI/UX / M6→性能+安全）
3. **补测试**，测试覆盖 MASTER_PLAN 验收要点的每一条
4. **更新 `CHANGELOG.md`**，在 `## [Unreleased]` 下分类记录（Added / Changed / Fixed / Security）
5. **提交**，提交信息使用 Conventional Commits 格式（第 9.1 节）

### 12.2 里程碑 → 模块对应表
| 里程碑 | 模块 | 关键文件 |
|--------|------|----------|
| M0 | 骨架 + 配置 | `app_server.py` / `config.py` / `config_models.py` |
| M1 | ComfyUI 适配（**计划，未实现**） | ~~`comfy/client.py` / `comfy/engine.py` / `comfy/workflow.py` / `comfy/vram_scheduler.py`~~ — 项目跳过 HTTP ComfyUI 引擎，v1.6 已彻底脱离外部 ComfyUI 进程；该能力由 M7 原生引擎承接。勿再按此列路径找代码 |
| M2 | 文生图工作台 | `task_queue.py` / `model_manager.py` / `gpu_utils.py` / `routes/generate_routes.py` |
| M4 | 批量 + 历史 | `routes/task_routes.py` / `history_db.py` / `routes/output_routes.py` / `routes/preset_routes.py` |
| M5 | UI/UX | `app/integrated_app/templates/index.html` / `app/integrated_app/static/`（前端资源）/ `app/integrated_app/locales/*.json`（根目录无 `static/`，勿引用 `static/index.html`） |
| M6 | 性能 + 安全 | `security/` / `scripts/benchmark.py` / `middleware/` / `Dockerfile` |
| M7 | 原生引擎 | `native/`（source / executor / engine / lora / seedvr / compares / vram / preview）/ `config.yaml`（backend: native）|

---
## 13. 典型 AI 开发场景 SOP（照着做，少踩坑）
> 📂 完整内容（SOP-1~SOP-5 + Known Gotchas 表）已移入 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)（本地文档，未随仓库发布）。
> 新 SOP / 新坑一律追加到该文件（铁律 #2/#3）。
---

> **⚠️ 2026-08-27 合并账目**：本节此前存在**两张完全重复**的「自进化修订记录表」。
> 上方一张仅含 v1.0–v1.8（与本表前 8 行逐字一致），系早期维护时误复制产生。
> 按铁律 #3「累积不删除」原则：重复内容不丢失，统一以本节为**唯一权威修订表**，
> 上方重复表已删除；表内 v1.15–v1.19 为后续追加时插序（位于 v1.14 与 v1.20 之间）、
> 以及两个 v1.24 行（分别对应「测试体系改进」与「portable 模型目录迁移」），
> 均保持追加位序不予重排（历史只增不改）。
## 📋 自进化修订记录表（AGENTS.md 进化史）

| 自进化版本 | 日期 | 触发原因 | 更新内容摘要 | 对应项目版本 | 已校验 |
|:---------:|------|---------|------------|:------------:|:-----:|
| v1.0 | 2026-08-10 | 初始建立自进化协议（项目健康度评估报告建议补齐） | 从 Image_MultiModel 项目健康度评估报告建议补齐：建立自进化协议（5 条铁律 + 7 项自检清单）+ 完整目录树 + 5 条硬约束 + 启动命令章节（一键脚本 + 手动 + 3 步验证）+ i18n 多语言规范章节（JSON 5 语言 6 步流程 + test_i18n_coverage.py 校验）+ 版本号同步清单（3 个文件 3 处：config.yaml / __init__.py / CHANGELOG.md）+ CI 3 个 Workflow 说明 + 安全注意事项 6 条（PathGuard / CSRF / RateLimit / Integrity / Watermark / 网络）+ 集中化 12 条 Known Gotchas 表格 + 3 条 SOP（新增引擎 / 新增路由 / Bug 修复后追坑追修订） | v2.0.0  | — |
| v1.1 | 2026-08-13 | 实施全功能实施指南 P0 三项任务（CLIP 安全检测 / 提示词扩展 / ControlNet 预处理器） | 新增模块：`security/content_filter.py` / `prompt_expander.py` / `preprocessors/`（canny + midas + openpose）；新增路由：`safety_routes.py` / `prompt_routes.py` / `preprocess_routes.py`；修正 Gotcha #12（routes 自动发现，非手动注册）；新增 Gotcha #13（CLIP 懒加载）+ #14（MiDaS/OpenPose 懒加载）；新增 SOP-4（新增安全/预处理器模块）；i18n 新增 9 个 key 5 语同步；版本号 1.0.0 → 1.1.0 三处同步 | v1.1.0  | — |
| v1.2 | 2026-08-13 | 原生进程内引擎（M7）+ 双后端模式改造 | 新增模块边界：`native/` 包（source / executor / engine / lora / seedvr / compares / vram / preview）；更新自检清单与第 3 节目录树；里程碑对应表追加 M7；新增 Gotcha #15（复用 comfy 源码需 ensure_loaded 注入 sys.path）+ #16（comfy_source_dir 相对路径需拼项目根绝对路径）；新增安全测试 `tests/test_native_security.py`；版本号 1.1.0 → 1.2.0 三处同步 | v1.2.0  | — |
| v1.3 | 2026-08-13 | 修复 ComfyUI /prompt 400 校验失败（seed 超上限 + 空 LoRA 沿用损坏默认值） | 新增 Gotcha #17（seed 超节点上限 / 空 LoRA 沿用损坏默认值）；修复 `workflow.py`：`_resolve_seeds()` 按节点分档钳制 seed（主 2^53 / seedvr2 2^32-1 / vram 2^50-1）+ 对手工输入 min/max 钳制；空 LoRA 名写入空串使 `to_api_format()` 移除该层；`to_api_format()` COMBO 匹配加 basename 兜底；前端 L1/L6 LoRA 默认改「— 禁用 —」；`tests/test_workflow.py` 18 用例全过 | v1.2.0  | — |
| v1.4 | 2026-08-13 | 修复原生引擎仍连 ComfyUI、LoRA 默认坏值 | 新增 Gotcha #18（backend: native 仍走 ComfyEngine 连 ComfyUI 8188）；修复 `app_server.py` worker 按 `ecfg.backend` 分发引擎（native → NativeEngine，否则 ComfyEngine）；修复 `app_server.py` 原生引擎不传 `on_chunk_done`（NativeEngine 不支持）碰 TypeError；实现 Gotcha #16：`native/engine.py` 相对 `comfy_source_dir` 拼 `cfg.project_root` 为绝对路径；`tests/test_workflow.py` 18 用例 + `tests/test_native_*` 40 用例全过；`NativeEngine.load()` 实测 OK | v1.2.0  | — |
| v1.5 | 2026-08-13 | 清理根目录遗留 Junction，统一模型摆放，规划彻底脱离 ComfyUI | 新增 Gotcha #19（根目录 text/unet/vae Junction 误导模型摆放）；删除根目录 6 个遗留 Junction；模型摆放统一为 shared→`comfy_models_dir` / portable→`model/`；退役 `setup_symlinks.ps1`；`pack_portable.ps1` STEP 3 改从 `comfy_models_dir` 直接拷贝；新增 `docs/COMFYUI-INDEPENDENCE-PLAN.md`（彻底脱离 ComfyUI + 复用源码独立成项目规划） | v1.2.0  | — |
| v1.6 | 2026-08-13 | 彻底删除 comfy/ HTTP 引擎包，项目完全脱离外部 ComfyUI 进程 | 新增 Gotcha #20（完全脱离 ComfyUI 后遗留 HTTP 引擎引用）；删除 `app/integrated_app/comfy/`（client/engine/workflow/vram_scheduler/schemas）；`app_server.py` worker 与 `engine_routes.py` 引擎工厂统一走 `NativeEngine`（删除 `/engine/free` 端点）；`config.yaml`/`config_models.py` 只保留 `z_image_turbo_native`（backend: native）；前端移除 ComfyUI 状态/释放显存/backend 过滤/comfy_preview；删除 `test_comfy_vram_scheduler.py`、`test_ws_reconnect.py`，`test_i18n_backend.py` 改引 `native.engine.PHASE_KEY_MAP`，各测试引擎名改 `z_image_turbo_native`；`benchmark.py`/`pack_portable.ps1` 去 8188/auto_spawn 残留；同步第 2.2 节 import 示例、第 3 节目录树、硬约束 #1/#2 为 native 语义 | v1.2.0  | — |
| v1.7 | 2026-08-14 | 修复 `index.html` 中文 mojibake 乱码 + 彻底清理前端 ComfyUI 残留 | 新增 Gotcha #21（HTML 中文 mojibake + 自动修复脚本二次破坏）；从干净 git 提交 `014edd3` 整文件重建 `static/index.html`（0 乱码）；前端彻底脱离 ComfyUI：移除 `freeVramBtn`/`/engine/free`、ComfyUI 后端状态面板、`CONN: LOCAL:8188`、关于面板「统一驱动 ComfyUI」副标题；引擎引用统一为 `z_image_turbo_native`；顶部图标按钮加文字标签（主题/颜色/字体/关于/设置/模型/语言）；删除会二次破坏编码的 `scripts/fix_encoding_ui.py` | v1.2.1  | — |
| v1.8 | 2026-08-14 | 修复原生引擎无法出图（worker 挂起 + latent 参数错 + VAE 传参 + CPU torch），切 portable 模型来源 + 用 FP8 unet | 新增 Gotcha #22（`asyncio.wait_for(queue.get(), timeout)` 超时不触发导致 worker 永久挂起 → 改 `get_nowait()`+`sleep` 轮询）+ #23（Z-Image latent 应为 16 通道/8 倍下采样，误用 SD3 的 4 通道导致 shape 错/分辨率减半）+ #24（`vae.decode()` 直接传张量，勿包 `{"samples":...}`）+ #25（服务须用 CUDA Python `C:\Python312`，`torch 2.13.0+cu132`，勿用 TRAE VM CPU 版 torch）；`config.yaml → model_source_mode` 改 `portable`（模型入 `model/`，无外部链接，便携独立运行）；unet 改用 FP8（`zimageTurboNSFWByStable_2602NSFWFP8.safetensors`），`default_precision=fp8`；`clean_launch.py` 新增系统级 CUDA Python 候选 + 修正重启逻辑；补装 `einops`/`torchsde`/`comfy-aimdo`/`comfy-kitchen`；实测 768×768 出图 ~30s；版本号 1.2.0 → 1.2.2 三处同步 | v1.2.2  | — |
| **v1.9** | **2026-08-17** | **M8: diffusers 原生引擎迁移 + TTS_MultiModel 架构对齐** | **新增** `diffusers_engine.py`（ZImageDiffusersEngine，Apache-2.0，eliminate GPL-3.0）+ `DiffusersEngineConfig` + `InMemoryEngineRegistry`（TTS 风格，懒导入+RLock）+ `create_engine_instance()` 工厂方法（backend 分发）；**修改** `config.yaml` default_engine=z_image_turbo_diffusers；**新增** phase_loading_model / phase_encoding / phase_decoding / phase_postprocessing i18n 5 语同步；**版本** 1.2.2 → 1.3.0 三处同步 | **v1.3.0**  | — |
| **v1.10** | **2026-08-17** | **M9: 三项性能/功能改进** | **新增** `watermark_gpu.py`（cupy 批量 DCT 加速）+ `services/seedvr2_service.py`（SeedVR2 懒加载管理器）+ `_generate_ese_compare()` 双图对比；**修改** `watermark.py` 入口自动检测 cupy + `diffusers_engine.py` 集成 SeedVR2/EsEs + `app.js` renderImg() 更换静态"BEFORE"为真实双图对比 + `seed.css` 新增 `.v-img.split-view` 样式；**同步** version 1.3.0→1.4.0 三处 + `requirements.txt` 追加可选 `cupy-cuda12x`；**测试** 480 passed, 0 failures | **v1.4.0**  | — |
| **v1.11** | **2026-08-17** | **M10: 前端走查修复（E2E 验证驱动）** | **新增** Gotcha #26（查看器顶栏 setPointerCapture 劫持按钮 click → 4px 阈值惰性捕获）+ #27（addEventListener 捕获旧函数引用致 F2/F9 覆盖版失效 → 回调包装）；**修复** `index.html`：批量/状态抽屉 `?`→`✕`、批量警告框/提交按钮 `?`→`⚠`/`▶`、负向提示词清空/复制按钮补 id、查看器下载/重绘按钮补 id、SeedVR2「待接入」→「已接入」、Eses/SeedVR2 过时文案更新、重复注释清理；**修复** `app.js`：负向提示词清空/复制接线、查看器下载/重绘接线、系统状态抽屉详情块 `.drawer-body`→`.ov-body` + openStat/openSet 绑定改回调包装（真实配置/状态终于加载）、prompt 渲染 4 处 XSS 转义（escHtml）、队列取消按钮改 id 选择器、删除失效 mock 行监听；**验证** Playwright 15 项交互检查全过 + 无控制台错误；E2E 8 项失败系既有环境问题（conftest 硬编码 8288 无服务 / Google Fonts 外链不可达致 goto load 超时 / 旧 UI data-i18n='sub' 选择器漂移），与本次改动无关 | v1.4.0  | — |
| **v1.12** | **2026-08-17** | **AGENTS.md 自检通过（例行版本递增）** | 运行自进化自检清单逐项核对：目录结构（app/integrated_app + routes/native/middleware/security/tests）与第 3 节一致；唯一引擎 `z_image_turbo_native`（backend: native）与 config.yaml → models.engines 一致；Known Gotchas 已至 #27；路由 auto_register 命名规范未违反；i18n 5 语言 key 同步；版本号三处同步确认一致（config.yaml / __init__.py / CHANGELOG 均 v1.4.0）、端口 8288 与入口 `app/clean_launch.py` 一致。仅例行递增自进化版本 v1.11 → v1.12，无文档内容修正 | v1.4.0  | — |
| **v1.13** | **2026-08-17** | **目录重命名 bin→app** | **修改** 项目主程序目录 `bin/` → `app/`：入口 `bin/clean_launch.py` → `app/clean_launch.py`、`bin/integrated_app` → `app/integrated_app`、`bin/start.bat` → `app/start.bat`、`bin/install.bat` → `app/install.bat`；**同步** start.bat / start.sh / install.bat / install.sh、pyproject.toml（coverage `source` / `mypy_path` / `known-first-party`）、.github workflows（ci.yml 等）、config.yaml（cert/key/manifest_file/locale_dir 路径）、Dockerfile / docker-compose.yml / README.md / .gitignore / perf_monitor.py、tests/ 与 scripts/ 全部 import 与路径引用为 app；start.sh 的 venv `/usr/bin/...`、`node_modules\.bin\`、npm `"bin"` 字段等非项目 bin 引用保持不变 | v1.4.0  | — |
| **v1.14** | **2026-08-17** | **目录重命名 pretrained_models→model** | **修改** 模型目录 `pretrained_models/` → `model/`：**同步** config.yaml（`internal_models_dir: model` + security.allowed_base_dirs `- model/`）、config_models.py（`internal_models_dir` 默认值 / allowed_base_dirs default_factory / docstring `./model/`）、`native/seedvr.py`（`_DEFAULT_MODELS_DIR` + 注释）、`native/diffusers_engine.py` 注释、`services/seedvr2_service.py` 全部路径字符串、scripts/setup_symlinks.ps1 + pack_portable.ps1、.env.example 注释、.gitignore（model/README.txt + 5 行权重忽略 + !model/.gitkeep）、docker-compose.yml（`./model:/app/model:ro`）、install.bat / install.sh（mkdir）、tests/（test_config / test_path_guard_attacks / test_security_audit / test_native_coverage）、README.md / AGENTS.md；`internal_models_dir` 键名保持不变 | v1.4.0  | — |
| **v1.19** | **2026-08-19** | **SFW 七夕主题专栏：新建 `prompt/SFW/七夕/` 子目录 + 29 个七夕提示词** | 按用户需求（人文向优先）新建七夕专栏子目录（命名格式与 SFW 主目录一致，`人种_年龄_人数_题材.txt`），29 个文件覆盖：①神话星辰4（银河织女星许愿/鹊桥灯影夜游/葡萄架听鹊语/月下拜织女）；②乞巧民俗5（庭院乞巧会/凤仙花染红甲/巧果煎炸/晒书晒衣/摩睺罗泥人铺）；③古风宫苑4（唐宫乞巧楼/月下互赠香囊/水畔放河灯/绣坊绣比翼）；④神话传说深化3（月下结拜金兰/剪纸鹊桥相会/庙会戏台演鹊桥会）；⑤地方民俗4（广府拜七姐/岭南取七夕水/喜蛛应巧/兰夜绘星图）；⑥古风人文3（灯谜会提灯猜谜/月老祠求红线/老绣娘讲牛郎织女）；⑦现代人文传承4（闺蜜互赠巧果礼盒/老字号巧果铺赶工/社区巧果非遗课堂/文创市集乞巧体验摊）；⑧岁时温情2（老夫妻摇扇忆当年/独倚窗阑遥望双星）；牛郎织女传说全女性化处理（只做星象/鹊桥/葡萄架意象）；避让既有题材（星空露营/烛光晚餐/夜市小吃街/石桥观荷/织布机/糖画/皮影/评书等）与 NSFW 七夕两篇（穿针乞巧/鹊桥许愿）差异化；全校验全绿：29 文件全部 ≥500 字符（MIN 504）、质量词 0、否定词 0、暴露词 0、无重名（SFW 内部+SFW/NSFW 交叉）、无 U+FFFD、无半角标点、ASCII 引号 0 残留；README.md 补充七夕专栏说明 | v1.4.0  | — |
| **v1.20** | **2026-08-19** | **SFW/NSFW 全库男性角色清除（POV 全女性化）+ 修复脚本二次运行污染** | 按用户 POV 规则（画面中不允许出现男性角色）全库扫描 1571 文件：①修复真男性角色：验光师（顾客→女顾客×9）、镖局启程（总镖头/伙计/托镖商人→女）、船夫×5 文件（乌镇/尼罗河/威尼斯/浮世绘/曲江游春→船娘）、农夫（土楼→农妇）、明清当铺朝奉（蓄须中年人→盘发中年妇人）、养老院/乒乓球/美术馆/布达拉宫等老人→老妇人、端午鼓手/乐队鼓手/键盘手→女X、教坊乐官/编钟/昆曲/弗拉明戈乐师→女X、瓦舍/老茶馆说书人→女说书人、各摊主/掌柜/店主→女X、cos 瞬教鞭先生→执教鞭女老师、cos 宵宫烟花店老板→老板娘、cos 朝颜花绘圣诞老人装→圣诞主题衣裙、马术训练病句"一名的东亚的"→"一位东亚的"等；②修复 audit_fix.py 二次运行 substring 污染：新增 Gotcha #33（女女双前缀 19 处/13 文件全清 0）；③全校验全绿：女女 0、真男性词 0（仅老板娘/女摊主/女说书人/动物胡须/主角自称等豁免）、SFW 全部 ≥500 字符（MIN 501）、无 U+FFFD、无半角标点、无相邻重复 | v1.4.0  | — |
| **v1.18** | **2026-08-19** | **SFW 种类优先扩展（第三轮）：+126 新文件（38 新种类），SFW 320→446** | 按用户方向扩展：①中国古代朝代30（先秦秦汉4/魏晋3/大唐5/宋4/明4/明清市井3/武侠4/古建3）；②各类社会人士30（司法4/金融3/传媒3/教育科研4/交通物流4/基层4/文体幕后4/生活服务4）；③外国古今26（古希腊3/罗马3/埃及3/中世纪3/文艺复兴2/日本3/朝鲜3/丝路2/美洲2/现代异国4）；④神话传说4+少数民族5（少数民族统一 东亚_ 前缀+特征词强化：那达慕盛装/火把节银饰长裙/葡萄架歌舞/风雨桥芦笙/高原经幡）；⑤补充29（节令3/戏曲3/雅戏3/老行当4/水乡3/非遗3/异国3/晒秋2/神话2/茶百戏1/太空2）；避让 NSFW 已有题材（胡旋舞→教坊乐舞、银行柜员→理财顾问等）；新增 Gotcha #32（扩写参数 ASCII 引号截断+文件名前缀笔误致空文件）；全校验全绿：446 文件全部 ≥500 字符（MIN 500）、质量词 0（仅旧文件 艺术术语/艺术理念 保留）、否定词 0（仅 要不要/舍不得 惯用语）、暴露词 0（仅 雾气/材质/乳香 保留）、无重名（SFW 内部+SFW/NSFW 交叉）、无 U+FFFD、ASCII 引号已清除 | v1.4.0  | — |
| **v1.17** | **2026-08-18** | **SFW 种类优先扩展（第二轮）：+98 新文件（25 新种类），SFW 222→320** | 新增 25 个新种类共 98 文件：职业日常6/书香阅读5/文博展览5/户外露营5/亲子时光5/银发生活5/校园时光5/夜生活5/茶酒咖啡4/市井小吃4/甜品烘焙4/花卉园艺4/水域湖泊4/山川徒步4/冰雪运动3/健身塑形3/潮玩手办3/游戏娱乐3/美妆护肤3/绘画设计3/音乐创作3/婚礼纪念3/寺庙祈福3/观鸟自然3/艺术空间3；人物以东亚为主+少量欧美（鸡尾酒调酒师/法式甜点/健身房自由重量/红酒品鉴会），多人双人约 26 个；新增 Gotcha #31（构图类短语含质量词子串：完美居中/极致超广角→精准居中/大幅超广角，扩写尾部追加法在「整体氛围」句后接镜头语言句零命中）；修复旧文件 3 处（完美居中/令人惊叹/极致超广角/极致留白）；全校验全绿：320 文件全部 ≥500 字符、质量词 0（仅 儿童画/麦当劳「不完美」艺术理念与 木版画质感/插画质感 术语保留）、指令式否定 0（仅 舍不得/要不要 惯用语）、SFW 暴露词 0（仅 雾气/纱料/化妆术语 保留）、无重名（SFW 内部 + SFW/NSFW 交叉均 0）、无 U+FFFD | v1.4.0  | — |
| **v1.16** | **2026-08-18** | **SFW 种类优先扩展：+125 新文件（22 新种类）** | 新增 Gotcha #30（批量扩写插入点分隔符需逐文件确认：动漫风格文件用 ；拍摄与风格说明 无 ；光线为 段，替换会静默失败；一次插入需留字数余量，预估 =(500-现字数)+15~25）；新增 125 个 SFW 文件覆盖 22 个新种类：民俗非遗10/音乐8/舞蹈5/竞技运动8/田园农业6/海洋5/城市人文5/手工艺5/舞台演出5/游乐4/季节气象8/餐饮6/服饰5/动物新种8/琴棋书画5/科技3/医护2/交通3/民宿酒店2/摄影3/动漫新风格8（浮世绘/像素/折纸/水墨/蜡笔/玻璃画/霓虹赛博/蒸汽朋克）/双人多题材6；人物以东亚为主+少量欧美/其他（芭蕾/街舞/冲浪/音乐节/薰衣草/霓虹赛博/蒸汽朋克），多人12 个；全部 ≥500 字符、0 否定句式、0 质量后缀、0 SFW 暴露词；全库 545 文件（SFW 222 + NSFW 323）复核：修复 5 处旧文件残留（完美的小星球效果/完美的弧线/毫不裸露/毫不露肤/没有任何肢体交缠）；全校验 6 项全绿（字符数/质量后缀/指令式否定/SFW 暴露词/重名/U+FFFD）| v1.4.0  | — |
| **v1.15** | **2026-08-18** | **SKILL.md 规范全库复查（SFW+NSFW 969 文件）+ SFW 补充 60 文件** | 新增 Gotcha #28（批量 edit oldString 必须逐字一致 / 脚本替换需全文件名）+ #29（否定词/暴露词扫描误报判定口径：只修指令式否定与质量后缀，惯用语/化妆术语/艺术术语保留）；SKILL.md 复查修复：质量后缀（杰作×6、高分辨率×6、画质×11）+ 指令式否定（避免/无需/不可×3、不偏脏不偏灰、不复杂不厚重、不僵硬不摆拍、不进也不出、不重叠不相贴不缠绕、不惊不怖、不过度紧绷、不喧宾夺主、不见生硬线条、不直接裸露×18、半掩不露×5、掩不住×3、不得不露面、放不开、无多余陈设、无任何多余陈设、均不佩戴、够不到、无法言说、毫无表情、而不俗艳、而不失雅致）+ 全部改正向描述；60 个新 SFW 文件全部 ≥500 字符 | v1.4.0  | — |
| **v1.21** | **2026-08-19** | **NSFW L5 新增 5 条：男友 POV 口交 ×3 + 肛塞自插 + 观影自慰** | 新建 5 个 L5 文件（`prompt/NSFW/` 根目录）：①车内俯身口交POV（深夜江边车内，副驾跪坐俯身，镜头即男友视线，画外男声喘息锚点）；②卧室跪姿口交POV（床沿地毯跪坐，目光穿画面与观众相接）；③卧室反向跨坐口交POV（男友仰躺视线，丰臀正对镜头，臀沟特写）；④浴室镜前肛塞自插（扶台弯腰，T形硅胶肛塞+白浊浓稠润滑液，镜面雾气倒影）；⑤卧室观影自慰（靠床头看片，改**手指**自慰不用跳蛋，屏幕光晕明暗交替）。全部 G 罩杯丰腴身形（用户两轮放大 E→G）＋出图调优：口交动作改「正埋下头＋樱唇被阴茎撑开绷紧＋唇瓣包覆/箍住柱身＋深喉没入口中＋下缘虚化」确保正在口交而非将要口交；乳房增大不再只靠罩杯数字，改用实感描述（沉甸甸垂坠/乳沟深邃/一手根本无法掌握/乳肉晃动）；链状配饰与纹身全数移除（银链腰链/珍珠项链/锁骨链/银脚链/桃心吊坠/银链吊坠/玫瑰刺青→仅耳钉/发夹，避免模型在画面下缘渲染金属链）；肛塞文件强化「臀部正中肛口/塞体没入臀缝/大半没入肛门内」位置词＋嘴部改「紧抿着唇/鼻间轻哼」防塞错位到嘴边；人物要素全项（明确成年/身高/面容≥2/发色+发型/妆造/肌肤/服装配饰/神态/姿势）+ 单主语"她" + 全角标点 + 体液白浊浓稠 + 行文顺序合规 + POV 无完整男性角色；全校验通过：5 文件全部 ≥500 字符（MIN 584）、词频≤3、无 U+FFFD、无半角标点、无相邻重复、无链状配饰与纹身残留 | v1.4.0  | — |
| **v1.22** | **2026-08-19** | **L5 出图迭代：蕾丝胸罩托举、口交含入口中、肛塞趴伏撅臀 + 全 11 个 L5 文件乳房统一放大** | ①口交动作强化「正埋下头＋阴茎大半已含入口中＋樱唇被撑开绷紧＋柱身在她唇间缓缓进出＋深喉几乎整根没入口腔＋画面下缘虚化」，解决"嘴边未含入"；②5 篇新文件胸部改穿**蕾丝半杯胸罩**（车内黑/跪姿白/反向跨坐黑/肛塞湿透浅紫/观影粉），「托着沉甸甸的巨乳＋乳肉几乎溢出杯口」增强托举沉甸感；③肛塞场景由"侧身扶洗手台"改为「双肘撑浴缸边缘、上身与地面平行、臀部高高撅起正对镜头」，肛塞抵肛门推入过程直白化；④**全部 11 个 L5 文件**乳房统一放大为「G罩杯尺寸惊人的巨乳沉甸甸垂在胸前/乳沟深邃/一手根本无法掌握/乳肉丰盈饱满」（闺蜜双人两角同规格，罩杯数字+实感描述并用）；⑤清除全部链状配饰与纹身（细银链/银链腰链/锁骨链/玫瑰刺青→仅耳钉/发夹）；顺带修复旧文件词频超限（假阳具口交口水4→3、浴室花洒柱身4→3）并强化假阳具口交"大半已含入口中"；全校验全绿：11 文件全部 ≥500 字符（MIN 591）、词频≤3、无链饰/纹身/U+FFFD/半角标点残留 | v1.4.0  | — |
| **v1.23** | **2026-08-19** | **L5 扩展 23 个新文件（8 方向）：乳交3/口交变体3/道具新玩法4/自慰场景5/骑乘POV1/双人3/情趣感官2/户外半公开2** | 新增 23 个 L5 文件（`prompt/NSFW/` 根目录）：**A 乳交系列**3（卧姿乳交POV俯视/乳交颜射乳沟/乳交转口交）；**B 口交变体**3（书房桌下口交POV/卧室站姿口交POV/深喉特写85mm大头）；**C 道具新玩法**4（阴蒂吸吮器/拉珠渐进入肛/震动棒G点前壁/乳夹+跳蛋）；**D 自慰场景**5（浴缸泡泡浴/商场试衣间半公开/酒店落地窗夜景/清晨赖床/客厅沙发）；**E POV女上位**1（正面骑乘，结合处柱身出入局部锚点）；**F 双人**3（双女六九互舔/共享震动棒/乳贴乳互摸）；**G 情趣感官**2（丝绸眼罩跳蛋感官剥夺+画外音引导/丝带轻缚双手自愿）；**H 户外半公开**2（夜公园长椅/车内副驾跳蛋手指并用）；统一沿用 G 罩杯巨乳实感+蕾丝半杯胸罩+无纹身无链饰（仅耳钉/发夹/非金属道具：硅胶乳夹/丝绸眼罩/丝带）+ 白浊浓稠体液 + 词频≤3 + 口交类含入口中写法；新文件全 ≥500 字符（MIN 527）；全校验 34 个 L5 文件全绿（含顺带修复晨光跳蛋旧文件"把她把"笔误与阴蒂×4） | v1.4.0  | — |
| **v1.24** | **2026-08-19** | **测试体系改进全量落地（基于测试金字塔评估报告）** | **P0**：E2E 选择器对齐实际前端 ID（`#posPrompt`/`#width`/`#height`/`#outGrid`/`#openBatch`，移除已废弃 `#freeVramBtn`）+ E2E 巨型测试拆分为 7 个小步骤 + 硬编码 `wait_for_timeout` 改为条件 `wait_for_selector` + `test_native_coverage.py` 的 `import torch` 改为 `pytest.importorskip` + `test_route_coverage.py` 残缺断言精确化 + `test_generate_routes.py` 的 503 测试改用 `unittest.mock.patch` + ci.yml 新增 `e2e`/`frontend-smoke`/`mypy`/`performance` 4 个 job；**P1**：新建 `test_chaos_engineering.py`（12 用例：GPU OOM 降级 4 + SQLite 磁盘满 3 + 并发锁竞争 3 + 崩溃恢复 2）+ ci.yml `sast` job 移除 `|| true` 改为 `--strict` + ci.yml `test` job 添加 `-n auto` 并行；**P2**：4 个集成测试文件补加 `pytestmark = pytest.mark.integration` + `test_sql_injection.py` 的 `except Exception` 改为 `except sqlite3.OperationalError` + E2E conftest.py 添加 `pytest_generate_tests` 跨浏览器支持；新增 Gotcha #34（E2E 选择器漂移）+ #35（sqlite3.Connection.execute 只读）+ #36（HistoryDB.conn property 无 setter）；新增 SOP-5（测试体系改进落地）；全量测试 218+ passed 0 failed | v1.4.0  | — |
| **v1.24** | **2026-08-19** | **portable 模型目录迁移 ComfyUI + Junction 复用（零冗余）** | 将 `model/` 下 FLUX.1-dev-fp8×4 / FLUX.2-klein-9b-fp8×5 / Z-image-bf16×1 / Z-image_turbo-bf16×2 / t5xxl / qwen3-8b / qwen3-4b / ae vae / flux2-vae 共 17 个模型（~132.7GB）逐目录移动至 ComfyUI `models/{unet,text_encoders,vae}`，原路径建立 9 个 Junction 指向 ComfyUI（两侧共用、无磁盘冗余）；新增 `model/README.md` 说明链接结构与维护规范；新增 Gotcha #34（os.walk 默认不穿透 Junction → `scan_resource_files` 加 `followlinks=True`）；`tests/test_config.py` 22 passed | v1.4.0  | — |
| **v1.25** | **2026-08-27** | **家族规范完整性审计（Phase A · T4）：文档↔文件系统/代码对账修正** | ① 删除两张完全重复的「自进化修订记录表」中的第一张（v1.0–v1.8 逐字重复），合并账目见修订表正上方注记；② 里程碑表 M1 行标注「计划，未实现」——项目已彻底脱离外部 ComfyUI 进程（v1.6），旧关键文件列的 HTTP 引擎文件均不存在，勿按旧路径找代码；③ M5 行关键文件由不存在的根 `static/index.html` 改为实际路径 `app/integrated_app/templates/index.html` 与 `app/integrated_app/static/`；④ README 两处文档链接重定向至实际子目录（`docs/project/` 与 `docs/plans/`）。**以上改动均为更正与事实不符的引用，未新增任何未实现的承诺** | v1.4.0  | — |

| v1.26 | 2026-08-27 | **家族规范完整性审计（Phase B · B4）：自进化协议打补丁（第 6 条铁律 + 修订表已校验列）** | ① 新增第 6 条铁律「证据绑定（Evidence Binding）」：可执行路径必须当时可验证存在、未实现项须显式标注、禁止虚构 CI 门禁；② 自检清单追加两项：路径真实存在校验（跑 `python scripts/check_spec_refs.py`）与 pre-commit 双向一致校验；③ 修订记录表增加「已校验」列，历史行统一填 `—`（未校验），新条目须填 `✓ (check_spec_refs)` 或 `✗`；④ 本仓新增 `scripts/check_spec_refs.py` 家族审计 wrapper 与 `.github/workflows/docs-consistency.yml`（本地/含审计器环境强校验，纯 CI 环境找不到审计器时降级跳过保持绿）。本行即首个填写「已校验」的条目 | v1.4.0| ✓ (check_spec_refs) |
| v1.27 | 2026-08-27 | **家族规范治理 Phase C/D/E 落地（一致性·补齐·账本）** | C1 SECURITY.md 单一位置；C2 合规文档统一命名；C0 未入库 docs 链接标注；D1 §0 仲裁节；D2 docs/adr/ 架构决策记录；D3 FILEMAP+同步脚本；D4 禁区章节；D5 .github 治理层补齐；D6 许可证台账（comfy_kernel + 节点矩阵）；D8 安全审计报告；D9 覆盖率路线图（75）；E3 AGENTS 体量拆分 99.1KB→47.8KB；E4 迁移报告。以上各项均只更正与事实不符的表述，未新增任何未实现的承诺 | v1.4.0 | ✓ (check_spec_refs) |

<!-- 🔄 下次更新 AGENTS.md 时，在上面表格末尾追加新一行，不要删除历史记录 -->


## 路线图落地新增模块（2026-08-18，未提交）
- app/integrated_app/mcp_server.py — MCP Server（移植自 TTS_MultiModel）
- app/integrated_app/spec.py — 领域公式契约层（含 validate_output_size）
- scripts/render_pages.py + tests/frontend/smoke.js — 前端冒烟测试
- tests/test_mcp_server.py、tests/test_spec.py

## 📂 文件归档与放置规范（重要：新增文件必须遵守）

> 本仓库目录已于 2026-08-23 系统整理（见 `docs/整理记录_20260823.md`（本地文档，未随仓库发布））。后续任何新增/生成文件，**先判断类型再放置**，不要随意丢在仓库根目录或其他位置。

**docs/ 分类（项目文档）**
- `docs/project/`：需求(PRD)、架构、API、技术选型、设计上下文
- `docs/plans/`：实施计划、路线图、指南(Guide)、待办(TASKS)
- `docs/reports/`：评估/审计/安全/测试/优化报告、Lessons
- `docs/repo-analysis/`：仓库学习报告（命名 `{仓库名}_技术学习报告.md`）
- `docs/_devarchive/`：历史/一次性开发产物、交接方案、旧版本文档（**归档而非删除**）

**根目录只允许放置**
- 标准仓库文件：README、LICENSE、CONTRIBUTING、CODE_OF_CONDUCT、CHANGELOG、AGENTS、SECURITY
- 构建与配置：build/gradle、pyproject.toml、config.yaml、requirements*.txt、Dockerfile、docker-compose.yml、.gitignore、.env(.example)、.editorconfig、启动脚本(start/install)
- 明确被 build/CI 或文档要求从根目录运行的工具

**禁止事项（防止回归混乱）**
- ❌ 一次性调试脚本/截图/日志/草稿 → 放 `scripts/` 或 `docs/_devarchive/`，绝不堆在根目录
- ❌ 文档散落到 tests/perf/launcher/model 等业务目录 → 归入 `docs/` 对应分类
- ❌ 移动/删除 gitignored 运行时产物（`.watermark_key`、`.coverage`、`perf/monitoring_plan.md`）
- ❌ 删除旧版本文档 → 需要留档移入 `docs/_devarchive/`

> 本仓库特别说明：内置组件 `comfy_kernel/` 自带文档随组件保留，不归入 `docs/`。
> 新增文件前若不确定归属，先询问，不要自作主张放置。

---

## 远程同步铁律（Remote Sync Rule）

> 2026-08-27 家族治理补充：防止 AI 直写远程后本地/远程分叉。

1. **禁止静默直写远程**：任何通过 GitHub API / 网页端直接修改远程 main 的操作（CI 工作流、依赖配置、分支、PR 等），执行前必须向用户说明，执行后必须检查本地与远程差异。
2. **操作远程后必须同步**：直写远程导致本地落后时，必须提醒用户执行 `git pull`，或经用户同意后代为同步；禁止留下分叉状态。
3. **禁止动未提交改动**：用户本地存在未提交修改时，不得擅自 commit / push / stash / checkout 覆盖，必须先征得用户同意。
4. **优先走本地流程**：代码与配置修改默认在本地完成、经用户确认后 push；确需直写远程时，按第 2 条补同步。
