# Image MultiModel AGENTS.md — AI 辅助开发指南

> 🧬 **自进化协议版本**：v1.26  
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
2. **📝 坑点累积（Gotchas Accumulation）**：每次修复 Bug / 踩坑后（哪怕是很小的坑），**必须** 追加一条到第 14 节「常见陷阱（Known Gotchas）」，写清楚：触发场景、现象/报错、正确做法、首次发现日期。
3. **📚 SOP 累积（SOP Accumulation）**：每次完成一个「本文件现有 SOP 没覆盖」的典型开发任务后，**必须** 把步骤整理成新 SOP 追加到第 13 节「典型 AI 开发场景 SOP」。
4. **✅ 自检流程（Self-Check on Startup）**：每次打开本文件准备工作前，**必须** 先运行下面的「🧪 自进化自检清单」，逐项核对，有任何一项不符先修正 AGENTS.md 再干活。
5. **🏷️ 版本递增（Version Increment）**：每次更新本文件内容后，**必须** 做三件事：① 文件顶部「自进化协议版本号」+0.1（小改）或 +1.0（大改/框架调整）；② 更新「最后更新日期」；③ 在文件末尾「📋 自进化修订记录表」追加一行记录。
6. **🔬 证据绑定（Evidence Binding）**：本文件中每出现一个**可执行文件路径**（脚本、配置、workflow、源码），它必须是**当时可验证存在**的。引用前跑一次 `python scripts/check_spec_refs.py`；若确实想描述尚未实现的东西，必须显式加 `（计划，未实现）` 前缀。禁止把"CI 会阻断 X"写成一个 CI 里不存在的门禁。

### 🧪 自进化自检清单（每次启动工作前必跑）
- [ ] 目录结构（`app/integrated_app/`、`routes/`、`native/`、`middleware/`、`security/`、`tests/`）是否和第 3 节模块边界描述一致？
- [ ] 原生引擎（`z_image_turbo_native`，`backend: native`）的配置是否和 `config.yaml → models.engines` 实际条目一致？模型来源是否为 portable（`model/`，无外部链接）？
- [ ] 上次工作是否踩了新坑？如果是，是否已追加到第 14 节 Known Gotchas？
- [ ] 是否新增了路由文件？如果是，是否已确保文件内定义了 `router = APIRouter(...)` 变量（app_server.py 使用 `pkgutil.iter_modules` 自动发现，无需手动注册）？
- [ ] 新增的翻译 key 是否已完成 5 种语言 JSON 同步（见第 8 节 i18n 规范）？
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
> 默认端口：**`http://127.0.0.1:8288`**（禁止 0.0.0.0 监听，见第 14 节陷阱）  
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

```
Image_MultiModel/
├── app/
│   ├── integrated_app/          ← 主应用包（FastAPI + 业务 + 引擎适配）
│   │   ├── __init__.py          ← __version__ = "x.x.x"（版本号同步点 1/3）
│   │   ├── app_server.py        ← create_app() + lifespan（加载引擎 / 初始化 DB / SSE broker）
│   │   ├── clean_launch.py      ← 推荐入口（环境检测 + 配置加载 + 数据目录创建 + 健康检查）
│   │   ├── config.py            ← YAML 配置加载（原子写入 + 宽松/严格双接口）
│   │   ├── config_models.py     ← Pydantic AppConfig 模型（对应 config.yaml 全量字段）
│   │   ├── engine_interface.py  ← ImageEngine Protocol（load/unload/infer/cancel，所有引擎必须实现）
│   │   ├── exceptions.py        ← 全局异常类（统一继承 IntegratedAppError）
│   │   ├── gpu_utils.py         ← VRAM 估算 / NVIDIA-SMI 解析 / 精度推荐（FP8/FP16）
│   │   ├── history_db.py        ← SQLite（WAL + FTS5）历史记录 CRUD + 搜索 + ZIP 导出
│   │   ├── i18n.py              ← 后端错误文案国际化（5 语言 JSON，三层 fallback）
│   │   ├── model_manager.py     ← 引擎生命周期管理（加载/卸载/切换/状态监控）
│   │   ├── model_registry.py    ← 引擎注册表（根据 config.yaml 动态实例化）
│   │   ├── sse.py               ← SSE 事件 Broker（任务进度 / 系统状态实时推送）
│   │   ├── task_queue.py        ← 异步单 Worker 串行任务队列（批量 / 取消 / 断点恢复 checkpoint）
│   │   ├── watermark.py         ← DCT 频域数字水印嵌入 / 提取 / 验证（product_id + task_id + timestamp）
│   │   ├── native/              ← 原生进程内引擎（唯一引擎，backend: native，🚫 复用 comfy 源码需先 ensure_loaded）
│   │   │   ├── source.py        ← 把 comfy_kernel + aki-v3 自定义节点注入 sys.path（幂等）
│   │   │   ├── executor.py      ← 复用 comfy.sd / comfy.samplers 推理（加载→编码→采样→解码）
│   │   │   ├── engine.py        ← NativeEngine（ImageEngine 实现，输出落盘过 PathGuard）
│   │   │   ├── lora.py / seedvr.py / compares.py / vram.py / preview.py ← Phase 3 能力
│   │   ├── routes/              ← API 路由层（🚫 禁止写推理逻辑 / 业务逻辑）
│   │   │   ├── __init__.py      ← 手动 include_router 注册（⚠️ 新路由必须在这里加一行）
│   │   │   ├── config_routes.py ← /api/config/*（引擎列表 / 模型扫描 / 预设 CRUD）
│   │   │   ├── engine_routes.py ← /api/engine/*（加载/卸载/切换引擎）
│   │   │   ├── generate_routes.py ← /api/generate/*（文生图 / 批量 / SSE 进度）
│   │   │   ├── output_routes.py ← /api/output/*（生成结果图片 / ZIP 下载）
│   │   │   ├── preset_routes.py ← /api/preset/*（预设 CRUD / 导入导出）
│   │   │   ├── system_routes.py ← /api/system/*（健康检查 / 状态 / 版本）
│   │   │   └── task_routes.py   ← /api/task/*（任务列表 / 取消 / 断点恢复）
│   │   ├── middleware/          ← 中间件层（不包含业务逻辑）
│   │   │   ├── csrf.py          ← CSRF Token 头注入 + 校验
│   │   │   ├── error_handler.py ← 全局异常捕获 → 统一 JSON 错误响应（i18n 翻译）
│   │   │   ├── rate_limit.py    ← 三维度限流（推理 / 上传 / 全局）
│   │   │   └── request_id.py    ← 每个请求注入 X-Request-ID，日志全链路追踪
│   │   ├── security/            ← 安全模块（被路由层引用，自身不引用路由层）
│   │   │   ├── path_guard.py    ← PathGuard.resolve() 规范化校验（防 ../ 路径穿越）
│   │   │   ├── integrity_selfcheck.py ← 启动时完整性校验（SHA-256 vs integrity_manifest.json）
│   │   │   └── integrity_manifest.json ← 核心文件 SHA-256 清单
│   │   ├── locales/             ← 5 种语言翻译 JSON（zh / zh-tw / en / ja / ko）
│   │   └── static/              ← 前端单页应用（纯静态 index.html，无 Python 代码）
│   ├── install.bat / start.bat  ← Windows 一键（自动检测 WinPython / 系统 Python）
│   └── clean_launch.py          ← 被 start.bat 调用的入口（不要直接从根目录调这个）
├── workflows/                   ← ComfyUI 工作流 JSON（每引擎一份，可导入导出）
│   └── Z_image_turbo.json
├── model/           ← portable 模式唯一模型目录（独立运行时模型放这里；shared 模式直接走 shared.comfy_models_dir，不再用根目录链接）
├── tests/                       ← 测试体系（详见第 4 节）
│   ├── e2e/                     ← Playwright E2E 测试
│   └── *.py                     ← 单元 / 集成 / 安全测试
├── scripts/                     ← 辅助脚本
│   ├── benchmark.py             ← 性能基准（推理速度 / VRAM / batch 吞吐量）
│   ├── check_wcag.py            ← 前端 WCAG 2.1 AA 无障碍检查
│   ├── generate_integrity_manifest.py ← 重新生成 security/integrity_manifest.json
│   ├── migrate_outputs.py       ← 旧版本 outputs/ 目录迁移工具
│   ├── pack_portable.ps1        ← 打包便携版（含 WinPython + 模型；STEP 3 直接读 shared.comfy_models_dir 拷贝）
│   ├── setup_symlinks.ps1       ← 【已退役】不再创建根目录 Junction（shared 直接走 comfy_models_dir）
│   ├── test_portable_mode.py    ← 便携模式自检脚本
│   └── verify_watermark.py      ← DCT 水印 CLI 验证工具
├── docs/                        ← 文档（API / ARCHITECTURE / DEPLOYMENT / 健康度评估报告 / 截图）
├── examples/                    ← API 使用示例（Python 脚本 + prompts.txt）
├── prototypes/                  ← UI/UX 原型（Figma 对比 / 风格探索 / 多布局方案）
├── .github/                     ← CI/CD（详见第 9 节）
│   ├── workflows/               ← ci.yml / release.yml / security.yml
│   ├── ISSUE_TEMPLATE/          ← Bug / Feature Request 模板
│   └── PULL_REQUEST_TEMPLATE.md ← PR 模板
├── config.yaml                  ← 主配置文件（版本号同步点 2/3，禁止通过 API 修改 server.host）
├── CHANGELOG.md                 ← 变更日志（版本号同步点 3/3）
├── install.bat / install.sh     ← 跨平台依赖安装
├── start.bat / start.sh         ← 跨平台启动脚本
├── requirements.txt             ← 生产依赖
├── requirements-lock.txt        ← 锁定版本
├── pyproject.toml               ← 工具配置（Ruff / Mypy / Pytest / Coverage）
├── .pre-commit-config.yaml      ← Pre-commit 钩子
├── Dockerfile + docker-compose.yml ← 容器化部署
└── README.md / LICENSE / CONTRIBUTING.md / SECURITY.md / CODE_OF_CONDUCT.md ← 开源社区文件
```

### 🔴 5 条硬约束（违反一条直接导致生产事故）
1. **`routes/` 目录永远不写业务逻辑**：路由只能做：参数校验（Pydantic Model）+ 调 `model_manager` / `task_queue` / `history_db` / `*_service` + 返回响应。**路由文件里不允许出现 `torch.*` / `numpy.*` / 任何推理相关代码**，推理必须通过 `engine_interface` 或 `model_manager`。
2. **`native/` 是唯一引擎实现**：项目已完全脱离外部 ComfyUI 进程，推理统一走进程内 `NativeEngine`（复用本地 `comfy_kernel` 源码，使用前必须先 `source.ensure_loaded()` 注入 sys.path）。`native/` 不做业务编排、不写 DB、不写业务日志（只抛异常给上层）。
3. **`static/` 前端代码绝对不包含 Python 逻辑，后端代码绝对不包含前端逻辑**：前后端通过 REST API + SSE 解耦。FastAPI 只负责静态文件托管，不允许在 Python 里拼 HTML / JS / CSS 字符串。
4. **所有推理任务单 Worker 串行执行**（`task_queue.py`，信号量=1）。严禁路由层直接并发 `await engine.infer_txt2img()`——哪怕 GPU 空闲也不行。Z-Image Turbo 9B + 大 batch 并发 GPU VRAM 直接爆 OOM。
5. **所有文件路径操作必须过 PathGuard**：任何用户输入参与路径拼接（读取 outputs、保存 presets、读取上传图片）→ 必须 `PathGuard.resolve(base_dir, user_input)`，**禁止 `os.path.join(base, user_input)` 的组合**。

---

## 🚫 禁区目录（禁止 AI 自动修改，必须人工确认）

| 路径 | 为什么禁 | 改动需什么 |
|---|---|---|
| `model/` | 权重误改导致推理结果静默劣化 | 人工逐项确认 + SHA-256 复验 |
| `comfy_kernel/` | vendored 上游（ComfyUI 内核），改动后与上游 diff 会丢失可更新性 | 记录进 ADR + 保留 patch 文件 |
| `outputs/` | 生成物，手改即失效 | 只通过生成命令更新 |
| `docs/_devarchive/` | 归档不可回写 | 只新增，不修改 |

## 4. 测试约定（覆盖率门槛 75% + 6 层测试分层）

### 4.1 6 层测试分层表
| 层级 | 测试类型 | 框架 | 标记 | 目录 | 说明 |
|:----:|---------|------|------|------|------|:-----:|
| L1 | 单元测试 | pytest | 默认 | `tests/test_*.py` | 纯函数 / utils / PathGuard / Watermark / Config（不碰 ComfyUI / DB） |
| L2 | 集成测试 | pytest | `@pytest.mark.integration` | `tests/test_native_*.py` / `test_config_save.py` | 原生引擎连通性 / Config 原子写入 / History DB 并发 |
| L3 | API 路由测试 | pytest + httpx.AsyncClient | 默认 | `tests/test_*_routes.py` / `test_api_contract.py` | 所有 `/api/*` 端点 HTTP 层 + 契约测试（响应体字段一个不少） |
| L4 | 安全攻击测试 | pytest 手工用例 | `@pytest.mark.security` | `tests/test_path_guard_attacks.py` / `test_sql_injection.py` / `test_security_audit.py` | 路径穿越 30+ 向量 / SQL 注入 / CSRF / 完整性校验 |
| L5 | E2E 端到端 | pytest + Playwright | `@pytest.mark.e2e` | `tests/e2e/` | 生图全流程 / 引擎切换 / i18n 语言切换 / SSE 进度（需浏览器） |
| L6 | 属性测试 | Hypothesis | 默认 | `tests/test_hypothesis.py` | 参数边界 / 模糊测试（prompt 长度 / seed 范围 / batch 大小） |

### 4.2 测试命名规范
```python
# 类名：Test + 被测类名（PascalCase）
class TestTaskQueue:
    # 方法名：test_<行为>_when_<条件>_then_<预期>（snake_case）
    async def test_queue_returns_503_when_full_then(self):
        ...
```

### 4.3 覆盖率门槛（CI 强制，低于 75% 直接阻断 PR）
- `pyproject.toml → [tool.coverage.report] fail_under = 75`
- 覆盖源：`app/integrated_app`（排除 `static/`、`locales/`、`schemas/`）

### 4.3b 覆盖率分阶段路线图（诚实设定，逐步提升）

> 数值与 `pyproject.toml` 的 `fail_under`（=75）一致，禁止空喊目标。

| 阶段 | 目标 fail_under | 达成条件 | 状态 |
|---|---|---|---|
| 当前 | 75 | 已用 `--cov-fail-under=75` 锁定（`pyproject.toml`） | ✅ |
| M1 | +10 | 补 L2/L4 攻击与集成层关键路径覆盖率 | pending |

### 4.4 常用测试命令
```bash
# 全量（排除 slow + integration，本地快速）
python -m pytest -q -m "not slow and not integration"

# 冒烟测试（核心关键路径，CI 必跑）
python -m pytest -m smoke -q

# 安全攻击测试（改了 PathGuard / SQL / 上传相关代码后必跑）
python -m pytest -m security -q

# 路由层 API 契约测试（改了 routes/ 后必跑）
python -m pytest tests/test_api_contract.py tests/test_*_routes.py -q

# 覆盖率报告
python -m pytest --cov=app/integrated_app --cov-report=term --cov-report=html -q
# → 报告生成到 htmlcov/index.html

# E2E（需要 Playwright 浏览器 + 服务在线）
python -m pytest tests/e2e -m e2e -v
```

### 4.5 安全相关功能的测试要求（铁律）
**新功能必须补 `test_` 测试。安全相关功能必须加攻击测试。**

| 新增功能类型 | 必须补的测试文件 | 测试内容 |
|------------|----------------|---------|
| 新文件操作路由 | `tests/test_path_guard_attacks.py` 追加向量 | `../` 穿越、绝对路径、符号链接绕过、Unicode 归一化绕过（≥5 条攻击用例） |
| 新 DB 查询 / 写入 | `tests/test_sql_injection.py` 追加向量 | `' OR 1=1--`、堆叠查询、注释符绕过、SQLite 特殊函数（≥3 条攻击用例） |
| 新 API 端点 | `tests/test_api_contract.py` 追加条目 | 成功响应字段列表 / 错误场景 HTTP 状态码 / 参数校验报错 |
| 新水印 / 完整性逻辑 | `tests/test_watermark.py` / `tests/test_verify_watermark_cli.py` | 嵌入后不可感知性、提取准确率、抗压缩抗裁剪（如果声明支持） |

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

### 6.1 一键启动脚本（推荐）
| 平台 | 安装依赖（首次） | 启动服务 |
|------|:---------------:|---------|
| **Windows** | 双击 / 终端执行根目录 `install.bat` → 自动检测系统 Python，装 PyTorch CUDA 版 + 全部依赖 + 创建数据目录 | 执行根目录 `start.bat` → 自动打开 `http://127.0.0.1:8288` |
| **Linux/macOS** | `chmod +x install.sh && ./install.sh` | `chmod +x start.sh && ./start.sh` |

### 6.2 手动启动命令
```bash
# 推荐方式（app/clean_launch.py，含环境检测 + 配置加载 + 数据目录创建 + 健康检查）
cd bin
python clean_launch.py
# 或根目录直接（start.bat 内部就是这么调的）
python app/clean_launch.py
# → 监听 http://127.0.0.1:8288
# 成功标志：按 §6.3 探针验证（`GET /api/health` 返回 200 + JSON）

# 纯 Uvicorn 前台调试（开发场景，不推荐生产）
cd bin
uvicorn integrated_app.app_server:app --host 127.0.0.1 --port 8288 --reload
# ⚠️ --reload 仅限开发！生产禁用（会重复加载引擎，VRAM 直接翻倍 → OOM）

# 生产守护进程（建议 systemd / NSSM）
uvicorn integrated_app.app_server:app --host 127.0.0.1 --port 8288 --workers 1
# ⚠️ workers 只能 = 1！TaskQueue 是全局单例，多 worker 会绕过串行队列并发推理 → OOM
```

### 6.3 启动后验证
3 步快速验证启动成功：
1. 浏览器打开 `http://127.0.0.1:8288` → 看到 Web UI 首页
2. `GET http://127.0.0.1:8288/api/health` → 返回：
   ```json
   {
     "status": "ok",
     "version": "2.0.0",
     "engines_available": ["z_image_turbo_native"],
     "engines_loaded": [],
     "gpu_vram_total_mb": 24576,
     "gpu_vram_used_mb": 1234
   }
   ```
3. `GET http://127.0.0.1:8288/api/engine/engines` → 返回唯一引擎 `z_image_turbo_native` 配置列表

---

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

### 8.1 翻译机制（和 TTS_MultiModel 不同，Image_MultiModel 用 JSON 不是 gettext）
- 后端错误文案 + 前端 UI 文案共用 **5 个 JSON 文件**：`app/integrated_app/locales/{zh,zh-tw,en,ja,ko}.json`
- 后端走 `integrated_app/i18n.py` 的 `_()` 包装（三层 fallback：用户指定语言 → en 英文 → key 本身兜底）
- 前端走 `window.I18N.t(key)`，`index.html` 启动时根据浏览器语言 / localStorage 选择加载对应 JSON

### 8.2 三层 fallback 链（任何一层缺翻译不会显示空值或裸 key）
```
用户选择语言（如 ja 日语）
    ↓ 该语言 JSON 里找不到 key →
en 英文（最后兜底，key 本身就是英文语义）
    ↓ 英文也找不到（极端情况）→
key 本身直接显示（最差情况也比空白好）
```

### 8.3 新增翻译 Key 的标准步骤（6 步，1-6 一步不能落）
1. **先在 `locales/en.json` 里加英文原串**（**en.json = 基准语言，所有 key 必须先在这里出现**）：
   ```json
   { "batch_cancel_confirm": "Are you sure you want to cancel all pending batch tasks?" }
   ```
2. 代码里写：后端 `_("batch_cancel_confirm")` / 前端 `I18N.t("batch_cancel_confirm")`
3. 为其余 4 种语言 JSON 同步追加相同 key：
   ```json
   // zh.json:   "batch_cancel_confirm": "确定要取消所有待处理的批量任务吗？"
   // zh-tw.json:"batch_cancel_confirm": "確定要取消所有待處理的批量任務嗎？"
   // ja.json:   "batch_cancel_confirm": "保留中のすべてのバッチタスクをキャンセルしますか？"
   // ko.json:   "batch_cancel_confirm": "보류 중인 모든 일괄 작업을 취소하시겠습니까?"
   ```
4. **不要嵌套对象**：所有 key 扁平化为顶级 `snake_case`（和 locales/*.json 现有风格一致）。不要写 `{ "batch": { "cancel": "..." } }` 这种嵌套。
5. **命名规范**：`<模块>_<动作>_<状态>`，如 `generate_progress_started`、`preset_save_success`、`history_delete_failed`
6. **完整性校验**：跑 `tests/test_i18n.py` 和 `tests/test_i18n_coverage.py`（CI 会跑）：
   ```bash
   python -m pytest tests/test_i18n.py tests/test_i18n_coverage.py -v
   # → 必须输出：5 languages × N keys = 5N 条目全匹配，任何一种语言缺 1 个 key 就失败
   ```

---

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
1. **PathGuard 路径防护**：所有用户输入参与文件路径拼接（读取 outputs 图片、保存 presets JSON、读取上传图片、读取工作流 JSON）→ 必须过 `PathGuard.resolve(base_dir, user_input)`（`integrated_app/security/path_guard.py`），**禁止 `os.path.join(base, user_input)`**。CI 的 `test_path_guard_attacks.py` 有 30+ 攻击向量，改了相关逻辑必跑。
2. **CSRF 防护**：所有非 GET 请求（POST / PUT / DELETE）必须携带 `X-CSRF-Token` 头。**token 不是从端点获取的**——`middleware/csrf.py` 的 `CSRFMiddleware` 会在每个 GET/HEAD/OPTIONS 响应里下发 `X-CSRF-Token` 响应头 + httponly cookie（`csrf_token`，double-submit 校验），POST 时比对 header 与 cookie。前端 `index.html` 里 fetch 封装已自动处理，**不要在前端代码里绕开它**（旧文档写的 `GET /api/system/csrf-token` 端点不存在）。
3. **Rate Limit 限流三维度**：`middleware/rate_limit.py` 同时限制：① `/api/generate/*` 推理接口（默认 1 次/10s）② `/api/output/*` 上传 / 下载（默认 30 次/分）③ 全局（默认 600 次/分）。真需要压测的话临时调 `config.yaml → server.rate_limit.*`。
4. **完整性校验**：启动时 `integrity_selfcheck.py` 对核心 Python 文件跑 SHA-256，和 `security/integrity_manifest.json` 比对。如果你改了 `app_server.py` / `config.py` / `watermark.py` / `path_guard.py` 等核心文件 → **必须重新生成 manifest**：`python scripts/generate_integrity_manifest.py`，否则下次启动直接退出。
5. **DCT 水印强制嵌入**：所有从 `/api/output/*` 返回的生成图片 **必须** 已嵌入水印（`watermark.py` 的 `embed_dct()`）。不要在任何导出 / 下载路径上跳过水印嵌入，否则溯源能力失效。验证：`python scripts/verify_watermark.py outputs/<image>.png` 能提取出 product_id + task_id。
6. **网络安全**：生产环境 **绝对不能 `config.yaml → server.host = "0.0.0.0"`**，只监听 `127.0.0.1`，外网访问必须套 Nginx（HTTPS + Basic Auth + IP 白名单 + WAF 限频 `/api/generate/*`）。

---

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

<!-- 📥 新SOP追加模板（AI 完成新类型任务后复制填好追加到这里）：
#### SOP-X: [场景名称]
**适用条件**：什么情况下走这个流程
**步骤**：
1. 第一步...
2. 第二步...
3. 第三步...
**验证**：怎么确认操作成功
**关联文件**：
- path/to/file1.py
- path/to/file2.py
-->

#### SOP-1: 添加新的 Z-Image 变体引擎（比如新增一个 Z-Image 变体 `z_image_turbo_fast`）
**适用条件**：需要新增一种 Z-Image 变体引擎到 ModelRegistry，通过统一 API 暴露，用户在 UI 的引擎下拉框可选

**步骤**：
1. **准备工作流 JSON + Schema YAML**：
   - 把 ComfyUI 导出的工作流 JSON 放到 `workflows/Z_image_turbo_fast.json`
   - 在 `app/integrated_app/native/schemas/` 新建 `z_image_turbo_fast.yaml`，把 JSON 里的 CLIPTextEncode / KSampler / VAEDecode 等需要动态 patch 的节点的 ID、widgets_values 的下标对应好（参考 `z_image_turbo_native.yaml` 的格式）
2. **注册引擎配置**：
   - 打开根目录 `config.yaml → models.engines`，追加一个新 block：
     ```yaml
     z_image_turbo_fast:
       name: z_image_turbo_fast
       display_name: Z-Image Turbo Fast
       display_name_en: Z-Image Turbo Fast
       backend: native
       workflow_file: workflows/Z_image_turbo_fast.json
       parameter_schema: app/integrated_app/native/schemas/z_image_turbo_fast.yaml
       text_encoder: { sub_dir: text, sub_path: z_image_turbo_fast/text_encoder.safetensors }
       unet:         { sub_dir: unet, sub_path: z_image_turbo_fast/unet.safetensors }
       vae:          { sub_dir: vae,  sub_path: z_image_turbo_fast/vae.safetensors }
     ```
   - 同步更新 `config.yaml` 旁边的 `config.example.yaml`（如果项目里有这个文件的话）
3. **`model_registry.py` 不需要改** → 启动时自动扫描 `config.yaml → models.engines.*` 的所有 key 并注册
4. **i18n 翻译**：在 5 个 `locales/*.json` 里加引擎显示名的翻译 key：
   ```json
   "engine_z_image_turbo_fast": "Z-Image Turbo Fast（极速）"  // 每个语言对应
   ```
5. **测试**：
   - 跑 `tests/test_model_registry.py` 确认新引擎被注册
   - 跑 `tests/test_native_engine.py -m integration` 确认 workflow patcher 6 步都通（深拷贝→模式→link→widgets→batch→校验）
   - 启动服务 → `GET /api/engine/engines` 里出现 `z_image_turbo_fast` 条目

**验证**：Web UI 首页引擎下拉框出现新引擎选项 → 选中后加载引擎 → 输入 prompt 点生成 → 成功出图且 SSE 进度正常推送

**关联文件**：
- `workflows/Z_image_turbo_fast.json`
- `app/integrated_app/native/schemas/z_image_turbo_fast.yaml`
- `config.yaml`
- `app/integrated_app/locales/*.json`
- `tests/test_model_registry.py`
- `tests/test_native_engine.py`

#### SOP-2: 新增 API 路由（比如加一个 `/api/preset/fork` 克隆预设接口）
**适用条件**：在 `/api/*` 下加新路由文件或在现有路由文件里加新端点

**步骤**：
1. **确定路由归属文件**：预设相关 → `routes/preset_routes.py`，如果是新领域就新建 `routes/xxx_routes.py`
2. **新建 / 修改路由文件**：
   ```python
   # routes/preset_routes.py 追加
   from fastapi import APIRouter, Depends, HTTPException
   from ..config_models import PresetForkRequest, PresetInfo
   from ..model_manager import get_model_manager  # 或者对应的 Depends

   router = APIRouter(prefix="/api/preset", tags=["preset"])  # 如果是新建文件，变量名必须是 router

   @router.post("/fork", response_model=PresetInfo)
   async def fork_preset(req: PresetForkRequest, history_db=Depends(get_history_db)):
       # 1. 参数校验（Pydantic 自动做，不用写）
       # 2. 调 service / db 层（这里不写业务逻辑）
       new_preset = await history_db.fork_preset(req.source_id, req.new_name)
       if not new_preset:
           raise HTTPException(404, _("preset_not_found"))  # 错误文案走 i18n
       return new_preset
   ```
3. **如果是新路由文件（新建了 xxx_routes.py）** → **无需手动注册**（app_server.py 使用 `pkgutil.iter_modules` 自动发现 routes/ 下所有模块）：
   ```python
   # 只需在文件内定义 router 变量即可自动注册
   router = APIRouter(prefix="/api/xxx", tags=["xxx"])
   # ⚠️ 变量名必须叫 router，否则 _auto_discover_routers() 不会发现它
   ```
4. **补 Pydantic 模型**：如果是新请求/响应体，在 `config_models.py` 里加 `PresetForkRequest` / `PresetInfo`（如果已存在就跳过）
5. **补测试**：`tests/test_api_contract.py` 追加 `POST /api/preset/fork` 的响应契约，`tests/test_preset_routes.py` 追加成功 / 失败场景
6. **补 i18n 文案**：如果有新的错误消息（比如上面的 `preset_not_found`）→ 5 个 `locales/*.json` 同步加 key

**验证**：启动服务 → Swagger UI `/docs` 里出现新路由 → curl / Postman 跑通成功和失败两种场景 → API contract 测试通过

**关联文件**：
- `app/integrated_app/routes/preset_routes.py`（或新文件）
- `app/integrated_app/config_models.py`
- `tests/test_api_contract.py`
- `tests/test_preset_routes.py`
- `app/integrated_app/locales/*.json`

#### SOP-3: 修复 Bug 后追加 Known Gotchas + 修订记录（自进化协议 2/5 两条铁律）
**适用条件**：任何 Bug 修复完成、踩了任何坑之后（哪怕是很小的坑，比如 f-string 漏花括号）

**步骤**：
1. Bug 修复代码写完 + 测试通过后，**不要马上 commit**
2. 打开 `AGENTS.md` → 第 14 节「常见陷阱（Known Gotchas）」表格
3. 在表格最后一行追加一条，按表头填全 5 列：
   - 坑点标题（简短概括，比如 **ComfyClient WS 重连后 prompt_id 映射丢失**）
   - 触发场景（什么操作会触发：比如「批量生成进行中断网 3s 恢复后」）
   - 现象/报错（具体报错或现象：比如「SSE 进度卡住 0%，最终超时但图片其实已生成成功」）
   - 正确做法（正确代码 / 配置 / 步骤：比如「`client.py` 的 `_on_ws_connect` 回调里重新拉取 `queue_remaining` 并重建 `prompt_id → task_id` 映射表」）
   - 首次发现日期（YYYY-MM-DD，比如 `2026-08-10`）
4. **递增版本号 + 更新修订记录表**（铁律 5/5）：
   - 文件顶部：`自进化协议版本 v1.0 → v1.1`，`最后更新日期 → 今天`
   - 文件末尾「📋 自进化修订记录表」追加一行：
     | 自进化版本 | 日期 | 触发原因 | 更新内容摘要 | 对应项目版本 |
     |:---------:|------|---------|------------|:------------:|
     | v1.1 | 2026-08-10 | 修复 ComfyClient WS 重连 Bug | 追加 Known Gotcha #12（WS 重连映射丢失）+ 修正 routes/__init__.py 手动注册说明 | v2.0.1 |
5. 现在再 commit：commit message 里带 `fix(xxx)` 且说明踩了哪个坑（方便以后回溯）

#### SOP-4: 新增安全检测 / 预处理器模块（如 CLIP 检测、ControlNet 预处理）
**适用条件**：需要新增依赖外部模型的检测/预处理功能（如 CLIP 内容过滤、MiDaS 深度估计、OpenPose 姿态检测）

**步骤**：
1. **创建模块文件**：
   - 安全检测 → `security/xxx.py`（如 `content_filter.py`）
   - 预处理器 → `preprocessors/xxx.py`（如 `canny.py`）
2. **懒加载设计**（铁律）：
   - `__init__` 只设 `_loaded = False`，不加载模型
   - `_ensure_loaded()` 方法首次调用时才加载
   - `is_available()` 只检查依赖包是否可导入，不检查模型是否下载
   - 依赖未安装时优雅降级（返回安全默认值，不崩溃）
3. **创建路由文件** `routes/xxx_routes.py`：
   - 文件内定义 `router = APIRouter(prefix="/api/xxx", tags=["xxx"])`
   - app_server.py 的 `_auto_discover_routers()` 会自动发现
4. **补 i18n**：5 个 `locales/*.json` 同步加 `backend_errors` 新 key
5. **补依赖**：`requirements.txt` 追加新依赖包
6. **补测试**：`tests/test_xxx.py` 覆盖：
   - 正常场景（安全提示词通过 / Canny 边缘检测出边缘）
   - 异常场景（违规拦截 / 空图片 ValueError）
   - 降级场景（CLIP 未安装时 check_image 降级放行）
   - 协议测试（PreprocessorProtocol isinstance 验证）
7. **集成到现有流程**（如果需要）：
   - 生成路由集成 → 在 `routes/generate_routes.py` 中 import 并调用
   - 不要在路由层写推理逻辑，只调 filter / preprocessor
8. **版本号同步**：`config.yaml` / `__init__.py` / `CHANGELOG.md` 三处版本 +0.1

**验证**：启动服务 → Swagger `/docs` 出现新路由 → curl 测试成功/失败场景 → 单元测试通过

**关联文件**：
- `app/integrated_app/security/content_filter.py`（或 `preprocessors/xxx.py`）
- `app/integrated_app/routes/xxx_routes.py`
- `tests/test_xxx.py`
- `app/integrated_app/locales/*.json`
- `requirements.txt`
- `config.yaml` / `app/integrated_app/__init__.py` / `CHANGELOG.md`

#### SOP-5: 测试体系改进落地（基于测试金字塔评估报告）
**适用条件**：测试体系评估报告输出后，按优先级分批落地改进

**步骤**：
1. **P0 高优先级（阻塞性问题）**：
   - E2E 选择器对齐：写 E2E 前先 `grep getElementById` 确认前端实际 ID，选择器与前端代码同步更新
   - CI 兼容性修复：`import torch` 改为 `pytest.importorskip("torch")`，避免无 CUDA 环境 collection error
   - 残缺断言修复：`status in (200, 400, 500)` 改为精确验证（200 或 500 + 注释说明已知问题）
   - E2E/前端冒烟接入 CI：ci.yml 新增 `e2e` job 和 `frontend-smoke` job
2. **P1 中优先级（质量增强）**：
   - 混沌工程测试：新建 `test_chaos_engineering.py`，覆盖 GPU OOM 降级、SQLite 磁盘满、并发锁竞争
   - 性能测试 CI 集成：benchmark.py 接入 CI（CPU 可运行部分）
   - mypy 类型检查接入 CI 质量门禁
   - SAST 严格化：`pip-audit || true` 改为 `pip-audit --strict`（阻断 CI）
   - pytest-xdist 并行：`-n auto` 加速测试
3. **P2 低优先级（代码质量）**：
   - 集成测试标记补齐：`pytestmark = pytest.mark.integration` 模块级标记
   - E2E 巨型测试拆分：一个 `test_txt2img_complete_flow` 拆为 4-6 个小步骤
   - 硬编码等待改为条件等待：`page.wait_for_timeout(500)` → `page.wait_for_selector()`
   - 吞没异常修复：`except Exception: pass` → `except sqlite3.OperationalError: pass`
   - 跨浏览器 E2E：conftest.py 添加 `pytest_generate_tests` 支持 `BROWSERS=chromium,firefox`
4. **全量测试验证**：所有改动完成后运行 `pytest tests/ --tb=short -q` 确认 0 failures
5. **文档更新**：追加 Known Gotchas + 版本递增 + 修订记录

**验证**：CI 全部 job 通过 + 本地 `pytest tests/ -q` 全绿 + `ruff check tests/` 全绿

**关联文件**：
- `tests/e2e/test_core_user_flows.py` / `test_generate_progress.py` / `test_engine_switch.py` / `test_generation_flow.py`
- `tests/e2e/pages/home_page.py` / `tests/e2e/conftest.py`
- `tests/test_chaos_engineering.py` / `tests/test_native_coverage.py`
- `tests/test_route_coverage.py` / `tests/test_generate_routes.py` / `tests/test_sql_injection.py`
- `.github/workflows/ci.yml`

<!-- 📥 新坑追加模板（AI 踩坑后复制填好追加到表格最后）：
| # | 坑点标题 | 触发场景 | 现象/报错 | 正确做法 | 首次发现日期 |
|---|---------|---------|---------|---------|------------|
| X | 简短标题 | 什么操作会触发 | 具体报错信息或现象 | 正确代码/配置/步骤 | YYYY-MM-DD |
-->

| # | 坑点标题 | 触发场景 | 现象/报错 | 正确做法 | 首次发现日期 |
|---|---------|---------|---------|---------|------------|
| 1 | **f-string 花括号不配对** | 写日志 / 错误消息时拼 f-string | `SyntaxError: f-string: expecting '}'` 或更隐蔽：运行时输出少字符 / 报变量未定义 | 写 f-string 时 IDE 高亮检查，写完自读一遍 `{var}` 是否成对；复杂字符串优先 `str.format()` | 2026-06-15 |
| 2 | **asyncio 事件循环在 Worker 线程关闭** | `task_queue.py` 的 Worker 线程里 `asyncio.run()` 调 ComfyClient WebSocket | 警告 `Event loop is closed`，后续任务随机失败 | Worker 线程里 `loop = asyncio.new_event_loop()` + `try: loop.run_until_complete(coro) finally: loop.close()`，不要用全局 `asyncio.run()` | 2026-06-20 |
| 3 | **SQLite 默认不允许跨线程** | lifespan 主线程建了 `history_db` 的 sqlite3.connect，TaskQueue Worker 线程里用它写 DB | `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` | 创建连接时加 `check_same_thread=False` + 用连接池（`queue.Queue` 或 SQLAlchemy）；WAL 模式下多线程读 OK，写必须串行 | 2026-06-25 |
| 4 | **PathGuard 必须过，不能直接 os.path.join + 用户输入** | 新增 `routes/output_routes.py` 下载接口时图省事 `os.path.join(OUTPUTS_DIR, user_filename)` | Path traversal 攻击：`?filename=../../../../Windows/System32/cmd.exe` 成功下载服务器任意文件 | 所有路径拼接先 `from integrated_app.security.path_guard import get_path_guard` → `path_guard.resolve(OUTPUTS_DIR, user_filename)` → 返回的是绝对路径且一定在 OUTPUTS_DIR 下，不在就抛 PathTraversalError | 2026-07-01 |
| 5 | **SSE 事件必须以 `\n\n` 结尾** | SSE Broker 发 `progress` 事件时 `yield f"data: {json.dumps(evt)}\n"`（只写了一个 \n） | 浏览器 EventSource 的 `onmessage` 永远不触发，进度条永远 0%，但 F12 Network 里 SSE 流是正常推的 | 所有 SSE 消息：`yield f"data: {json.dumps(evt)}\n\n"`（两个换行），事件名的话 `event: progress\ndata: {...}\n\n` | 2026-07-05 |
| 6 | **`config.yaml → server.host` 禁止通过 API 修改** | 写了 `POST /api/config/server` 允许改 host → 有人改成 `0.0.0.0` + 没改防火墙 → 服务被全网扫到挖矿 | `config_models.py` 的 `ServerConfig` 里 `host` 字段加 `frozen=True` 或 `save_config()` 时对比 `host` 字段被改了就 raise `ConfigFieldReadOnlyError("server.host is read-only for security")` | 2026-07-08 |
| 7 | **模型路径双模式（shared vs portable）差异巨大** | 写 `resolve_model_path()` 时只处理了 portable，没处理 shared 的符号链接 / mount_map | shared 模式下引擎加载模型报 `FileNotFoundError`，但 ComfyUI 自己能找到 | `model_manager.py` 里的 `resolve_model_path()` 先读 `config.yaml → models.model_source_mode`：`shared` 模式 → 路径拼 `shared.comfy_models_dir + mount_map[sub_dir] + sub_path`；`portable` 模式 → 路径拼 `portable.internal_models_dir + sub_dirs[sub_dir] + sub_path`；写单测覆盖两种模式 | 2026-07-12 |
| 8 | **ComfyUI workflow patcher 深拷贝不能省** | 优化性能时把 `workflow.deepcopy()` 去掉，直接改 `dict` 引用 | 第二次生成时 KSampler 的 steps / seed 是上次的值（因为引用被污染了），用户 seed=random 但连续生成两张一样的图 | `comfy/workflow.py` 的 `WorkflowManager.patch()` 第一步必须 `patched = copy.deepcopy(self.workflow_json)`，之后所有修改只改 patched，绝不改原始 workflow；加单测 `test_workflow_patch_is_idempotent` 连跑 3 次输入一样输出一样 | 2026-07-15 |
| 9 | **Uvicorn workers 只能 1，多 worker 必 OOM** | 为了提升并发，`uvicorn ... --workers 4` 或 Gunicorn 多 worker | 每个 worker 都独立初始化 ModelRegistry + 各加载一次 Flux.2 引擎到 GPU，VRAM 占用 ×4 → 直接 OOM 崩溃 | workers 永远 = 1，并发通过 `TaskQueue` 队列串行化。真要水平扩展 → 多实例 + 前面 Nginx 负载均衡（每台机器 GPU 1 份模型） | 2026-07-18 |
| 10 | **batch>9999 时自动切 100 子任务落盘 checkpoint** | 一开始没做 batch chunk，用户传 `batch=9999` 想生成数据集 | ComfyUI 一次性接 9999 张 → 内存爆 / OOM / 中途崩溃前面全白跑（1 小时白等） | `task_queue.py` 收到 batch>100 时按 `chunk_size=100` 自动切 N 个子任务，每个子任务完成后 `checkpoint = {"task_id": xxx, "completed_chunks": [0..N-1], "outputs": [...]}` 原子写入 `data/cache/{task_id}.checkpoint.json`；崩溃重启后由 `app_server.py` 的 `TaskCheckpoint` 在 lifespan 启动时扫描 `checkpoint_dir` 自动恢复（**不存在 `POST /api/task/{id}/resume` 端点**，勿按旧描述调用） | 2026-07-22 |
| 11 | **DCT 水印 uint8 回绕** | `watermark.py` 嵌入时 `dct_coeffs += delta_watermark`，没做 clip | 取反的 delta 把 uint8 搞成 255+ → 回绕到 0 → 水印提取时 hash 对不上 → `verify_watermark.py` 说图像是伪造的 | 嵌入前 `dct_coeffs_float = dct_coeffs.astype(np.float32)` → 加减完 `np.clip(dct_coeffs_float, 0, 255).astype(np.uint8)` → 再做 IDCT；加单测 `test_watermark_embed_extract_roundtrip` 用各种 seed + prompt 跑 100 张，提取准确率必须 100% | 2026-07-28 |
| 12 | **新路由文件必须在 routes/__init__.py 手动注册** | 新增 `routes/report_routes.py` 写了一堆路由，启动后 Swagger 里没有，curl 全 404 | ~~Image_MultiModel 的 routes/__init__.py 是 **手动维护** 的列表~~ **已修正**：app_server.py 的 `_auto_discover_routers()` 使用 `pkgutil.iter_modules` 自动发现 routes/ 下所有模块。新建 `xxx_routes.py` 后只需：① 文件内定义 `router = APIRouter(...)`（变量名必须叫 router）② 自动注册，无需修改 `routes/__init__.py` | 2026-08-02 |
| 13 | **CLIP 模型不能在模块 import 时加载** | 在 `content_filter.py` 中全局实例化 `content_filter = ContentSafetyFilter()` 时在 `__init__` 中调用 `clip.load()` | import 模块时卡住 5-10 秒下载 CLIP 模型，且如果 clip 包未安装则 import 直接报错导致整个应用无法启动 | CLIP 模型必须 **懒加载**：`__init__` 只设标志位 `_loaded = False`，首次调用 `check_image()` 时才 `_ensure_loaded()` 加载。如果 clip 包未安装，返回降级结果（`is_safe=True` + `details.degraded=True`），不阻止应用启动 | 2026-08-13 |
| 14 | **MiDaS / OpenPose 模型需联网下载，不能在 import 时加载** | `preprocessors/midas.py` 和 `openpose.py` 在模块级别实例化模型 | 离线环境（`HF_HUB_OFFLINE=1`）下 `torch.hub.load()` 报错，导致 import 失败 | 所有重型模型预处理器必须懒加载：`_ensure_loaded()` 方法首次调用时才下载/加载模型，失败时设置 `_load_error` 并返回 False。`is_available()` 只检查依赖包是否可导入，不检查模型是否已下载 | 2026-08-13 |
| 15 | **复用 comfy 源码必须先 source.ensure_loaded() 注入 sys.path** | 原生引擎（`backend: native`）在 `native/executor.py` / `native/engine.py` 里 `import comfy.sd` / `comfy.samplers` | `ModuleNotFoundError: No module named 'comfy'` 或命中了外部安装的 ComfyUI 包（版本不符导致 API 对不上） | 任何 `import comfy.*` 之前先调 `source.ensure_loaded(comfy_root=...)`（幂等，把 `comfy_kernel` 注入 `sys.path[0]`），保证命中本地复用源码而非外部包 | 2026-08-13 |
| 16 | **comfy_source_dir 相对路径需拼项目根绝对路径** | `config.yaml → models.engines.*.comfy_source_dir` 写相对路径（如 `comfy_kernel`），`native/engine.load()` 直接把它当绝对路径传给 `source.ensure_loaded()` | `RuntimeError: Comfy source dir invalid ... (missing 'comfy/' package)`，因为相对路径基于进程 cwd 解析成了错误位置 | 解析 `comfy_source_dir` 时若为相对路径，先 `Path(project_root) / comfy_source_dir` 拼成绝对路径再装载；`source._default_comfy_root()` 已内置 `{项目根}/comfy_kernel` 兜底 | 2026-08-13 |
| 17 | **seed 超节点上限 / 空 LoRA 沿用损坏默认值** | `workflow.py _resolve_seeds()` 用 `random.randint(0, 2**53-1)` 生成三个 seed，但 ReservedVRAMSetter 上限 2^50、SeedVR2VideoUpscaler 上限 2^32；`_patch_widgets()` 对空 LoRA 名 `continue` 沿用工作流里损坏的默认 `.safetensors` | ComfyUI `/prompt` 返回 400 `prompt_outputs_failed_validation`：`Value xxx bigger than max of ...: seed`（节点 78/80）+ `lora_name: '.safetensors' not in (list of length 64)` | ① `_resolve_seeds()` 按节点分档：主 seed→2^53、seedvr2→2^32-1、vram→2^50-1，且对手工输入也 `min/max` 钳制；② 空 LoRA 名写入空串而非 `continue`，让 `to_api_format()` 移除该层；③ `to_api_format()` COMBO 匹配加 basename 兜底 | 2026-08-13 |
| 18 | **backend: native 仍走 ComfyEngine 连 ComfyUI 8188** | 选原生引擎（`z_image_turbo_native`，`backend: native`）生成，但 `app_server.py` worker 硬编码 `engine = ComfyEngine(...)` 不按 backend 分发 | `ConnectionError: Cannot connect to ComfyUI at http://127.0.0.1:8188 ... 远程计算机拒绝网络连接`，即使不依赖外部 ComfyUI 仍报错 | worker 里按 `getattr(ecfg, "backend", "comfyui")` 分发：`native` → `NativeEngine(name, display_name, display_name_en, config={workflow_file, comfy_source_dir})`；否则才建 `ComfyEngine` | 2026-08-13 |
| 19 | **根目录 text/unet/vae Junction 误导模型摆放** | 项目根曾建 `text/`、`unet/`、`vae/` 指向 aki 的 Junction（`setup_symlinks.ps1` / 手工），但运行时 `resolve_engine_model_paths` 从不读它们（shared 用 `comfy_models_dir`，portable 用 `model/`） | 项目根看起来"模型在这"实际指向外部，独立运行时放错位置、误导认知 | 根目录不再允许模型链接；模型只走两处：shared→`models.shared.comfy_models_dir`，portable→`model/`。已删除 6 个遗留 Junction，退役 `setup_symlinks.ps1`，`pack_portable.ps1` STEP 3 改从 `comfy_models_dir` 直接拷贝 | 2026-08-13 |
| 20 | **完全脱离 ComfyUI 后遗留 HTTP 引擎引用** | 决定项目完全脱离外部 ComfyUI 进程、统一走进程内 `NativeEngine`，但前后端/测试/脚本仍残留 `integrated_app.comfy.*`、`ComfyEngine`、`ComfyClient`、`8188`、`/engine/free` 等引用 | ① 测试 collection 报 `ModuleNotFoundError: No module named 'integrated_app.comfy'`；② 前端仍显示 ComfyUI 后端状态 / 释放显存按钮；③ 生成接口因 `flux2_klein_9b_distilled` 引擎已删除返回 404 | 全量清理：删除 `app/integrated_app/comfy/` HTTP 引擎包；`app_server.py` worker 与 `engine_routes.py` 工厂统一走 `NativeEngine`（删除 `/engine/free` 端点）；`config.yaml`/`config_models.py` 只保留 `z_image_turbo_native`（backend: native）；前端移除 ComfyUI 状态/释放显存/backend 过滤/comfy_preview；删除 `test_comfy_vram_scheduler.py`、`test_ws_reconnect.py`，`test_i18n_backend.py` 改引 `native.engine.PHASE_KEY_MAP`，各测试引擎名改 `z_image_turbo_native`；`benchmark.py`/`pack_portable.ps1` 去 8188/auto_spawn 残留 | 2026-08-13 |
| 21 | **HTML 中文 mojibake 乱码 + 自动修复脚本二次破坏** | `static/index.html` 中文经多次 GBK/UTF-8 往返编码被破坏（曾提交到 git 的 `6b63310`/`978f7ab`），页面出现 `?` 乱码；随后用 `errors="replace"` 的自动修复脚本想"反向还原"，反而把 1118 个字符永久替换成 `\ufffd` 丢失 | 浏览器显示中文变 `涓婚闃查棯`（UTF-8 被当 GBK 解码）或 `主?防闪?`（非法字节被替换成 `?`/``）；部分字符因 PUA / `\ufffd` 已不可逆 | ① 不要用 `errors="replace"` 的脚本去"还原"乱码——数据已丢，越改越坏；② 正确做法：从**干净的 git 提交**（`git log` 逐个验证 `SET=设置` 筛出 `014edd3`）整文件重建，再按需求重做改动；③ 结构化 diff 判断：乱码提交与干净提交通常**仅中文不同、结构一致**，用 `git diff --no-index` 对齐即可确认；④ 改 HTML 前先 `python -c "t=open(f,encoding='utf-8').read();assert t.count('\ufffd')==0"` | 2026-08-14 |
| 22 | **`asyncio.wait_for(queue.get(), timeout=...)` 超时不触发导致 worker 永久挂起** | 原生引擎选 `z_image_turbo_native` 生成，任务提交后一直 pending，worker 从不消费；曾用 `asyncio.wait_for(self._queue.get(), timeout=1.0)` 做取任务超时 | 日志只有 `Task submitted: xxx`，永远没有 `Worker processing task: xxx`；任务 status 卡在 pending，即使队列 qsize=1 / 同一事件循环 / 同一队列实例，worker 的 `wait_for` 既不返回也不超时（HTTP 请求正常，事件循环未阻塞） | **不要用 `wait_for(queue.get(), timeout)` 做取任务超时**——该环境（ProactorEventLoop + uvicorn）下 timeout 定时器不触发。改为 `get_nowait()` + `asyncio.sleep(0.2)` 轮询：`try: task = self._queue.get_nowait() / except asyncio.QueueEmpty: await asyncio.sleep(0.2); continue` | 2026-08-14 |
| 23 | **Z-Image 原生引擎 latent 用错 SD3 通道/下采样参数** | `native/executor.py` 的 `LATENT_CHANNELS=4` / `SPATIAL_DOWNSCALE=8`（SD3 参数），但 Z-Image 用 FLUX AE | 采样时 `RuntimeError: mat1 and mat2 shapes cannot be multiplied (2304x16 and 64x3840)`（Lumina `x_embedder` 期望 patch_size²×in_channels＝64，但 latent 只有 4 通道）；或输出分辨率减半（768 变 384） | Z-Image 用 **FLUX AE：16 通道 / 8 倍下采样**。`LATENT_CHANNELS=16`、`SPATIAL_DOWNSCALE=8`；验证输出的宽高 = 输入宽高（768→768）。`model.latent_format` 对 Z-Image 为 None，需硬编码正确默认值 | 2026-08-14 |
| 24 | **`vae.decode()` 传参错误：多包了一层 `{"samples": ...}`** | `native/executor.py` 的 `_vae_decode` 写 `vae.decode({"samples": latent})` | `AttributeError: 'dict' object has no attribute 'ndim'`（`comfy/sd.py` 的 `decode` 直接访问 `samples_in.ndim`） | `vae.decode(latent)` 直接传 latent 张量（对齐 Comfy 的 `VAEDecode` 节点语义），不要再包 dict | 2026-08-14 |
| 25 | **服务跑在 CPU 版 torch 上，推理报无 CUDA** | 服务由 TRAE VM 自带 python（`torch 2.13.0+cpu`）启动，选引擎生成时 | `RuntimeError: Torch not compiled with CUDA enabled`（`torch.cuda.is_available()==False`） | 用带 CUDA 的 Python 启动（本机 `C:\Python312`，torch 2.13.0+cu132）。`app/clean_launch.py` 的 `find_winpython()` 新增系统级 CUDA Python 候选（`C:\Python312`、`ComfyUI-aki-v3\python`），并修正重启逻辑（`os.path.abspath(wpy) != os.path.abspath(sys.executable)` 即切换，不再只认 `WPy64`） | 2026-08-14 |
| 26 | **悬浮查看器顶栏 setPointerCapture 劫持按钮 click** | 点击查看器顶栏任意按钮（关闭 ✕ / 对比 ⇄ / 缩放 ± / 收藏 ☆）时 | 按钮 click 事件失效（vClose 关不掉查看器、缩放不生效），因为 `pointerdown` 时 `vHead.setPointerCapture()` 把 click 目标重定向到 vHead（capture target 与 hit-test target 的最近公共祖先 = vHead），按钮 handler 永不触发 | **先不捕获，拖动超过 4px 阈值后再惰性捕获**：`pointerdown` 只记起点 → `pointermove` 位移 >4px 才 `setPointerCapture` + 标记 `moved` → `pointerup`/`pointercancel` 释放捕获并复位。单纯点击全程无捕获，click 自然落到按钮 | 2026-08-17 |
| 27 | **函数引用被 addEventListener 提前捕获，覆盖版（F2/F9）永不生效** | 前端用「先定义原函数 → 赋值覆盖」模式（如 `openStat=function(){_origOpenStat();...}` / `openSet=function(){...}`），但按钮绑定写的是 `addEventListener('click', openStat)` | 点击 `#sbConn`/`#setOpen` 时走的是**绑定瞬间捕获的旧函数引用**，覆盖版从未执行 → 系统状态抽屉详情块不显示、设置抽屉不加载真实配置（选择器永为空） | 绑定处改回调包装：`addEventListener('click', function(){ openStat(); })`（调用时再解析变量）。排查同类模式：`showHistList`/`showPList` 因调用点用直接调用 `showHistList()`（运行时解析）而幸免，凡写成 `addEventListener(x, fn)` 传值的一律中招 | 2026-08-17 |
| 28 | **批量 edit 的 oldString 必须与实际文件内容逐字一致；脚本替换需用全文件名** | ① 扩写 60 个新 SFW 文件时凭记忆写 oldString，3 次 `Edit` 报 oldString not found（公园太极/咖啡馆窗边读书/水墨幻境九尾狐）；② PowerShell 批量替换时用部分文件名匹配 cos 文件（`cos_碧蓝档案_霞泽美游写真.txt`），实际文件名带前缀 `L2_东亚_年轻_单人_cos_` | ① Edit 直接失败（报错可自愈，读原文重试即可）；② 3 个 cos 文件替换被静默跳过（报 MISSING FILE），若不补跑验证就会漏改 | ① 任何 edit 前先 `Read` 确认原文（不要凭记忆写 oldString）；② 脚本按文件名匹配时用完整文件名（`Get-ChildItem -Recurse | Where-Object Name -eq 全名`），替换后必须跑全库复扫确认 0 残留 | 2026-08-18 |
| 31 | **构图/方向类短语也含质量词子串（完美居中/极致超广角/极致留白）+ 扩写尾句追加法** | 扩写时用了「完美居中」「极致超广角」「极致留白」等构图术语，或把扩写句插在故事中段 | 全校验质量词扫描命中：完美居中（粉风衣霓虹肖像）、极致超广角/极致留白（唐风幻想云海）、令人惊叹（神经网络森林）；故事中段插句容易与已有情节时序冲突 | ① 构图/方向类词汇优先换用中性词：完美居中→精准居中、极致超广角→大幅超广角、极致留白→大面积留白、令人惊叹→充满想象力；② 中段插句后仍 <500 的收尾文件，改用「尾部追加法」：在文件末尾「整体氛围…」句后追加「；镜头…画面…收束/定格」式镜头语言句（约50-70字），叙事时序自然衔接、扫描零命中；③ 插句一律避开 完美/极致/画质/惊人/杰作 等词根 | 2026-08-18 |
| 32 | **批量扩写参数内嵌 ASCII 引号截断 + 文件名前缀笔误产生空文件** | 用 PowerShell 函数批量给文件追加尾部时，$tail 参数里内嵌 ASCII 双引号（如「用力一扳，+"砰"+的一声」），或文件名 单人/多人 前缀写错 | ① 尾部只写入引号前的片段（文件只 +9 字）；② 或对错误文件名执行写入：若文件已存在则写错内容，若不存在则 ReadAllText 报错且可能留下 0 字节空文件——全校验出现 MIN LEN 0 | ① 尾部文本内禁用 ASCII 引号（中文引号「」或改写句式）；② 批量写入前先 Test-Path 核对每个目标文件存在，写入后立即回读长度；③ 每批结束后必跑全校验：长度 <500 与 =0 均判失败，逐文件列出 | 2026-08-19 |
| 30 | **批量扩写插入点分隔符需逐文件确认 + 一次插入需留字数余量** | 用脚本对 120+ 新文件批量补写细节（字符数 <500 需扩写），统一在 ；光线为 前插入句子 | ① 动漫风格类文件（浮世绘/水墨/像素等）无 ；光线为 段，分隔符是 ；拍摄与风格说明，替换静默失败（0 变化）；② 凭记忆估算插入长度，一遍插入后仍差 1~60 字，需 2~3 轮补插 | ① 批量插入前先抽样确认文件实际分隔符（grep 光线为），对未命中文件换锚点重插，插入后必须输出新字符数核对；② 每文件预估插入字数 = (500 - 现字数) + 15~25 余量，一次插够，减少轮次；③ 全校验脚本统一跑一遍并列出所有 <500 与 0 变化文件 | 2026-08-18 |
| 29 | **否定词/暴露词自动扫描的误报判定口径（须人工逐条看上下文）** | 按 SKILL.md 规范全库复扫 `不/无/避免/杰作/画质` 等关键词 | 误报命中：`明媚`（含"媚"）、`裸粉色/裸妆`（化妆术语）、`透视/镂空`（剪纸艺术）、`插画质感`（含"画质"）、`别着`（别发簪）、`不同`、`深浅不一`、`无线耳麦`、`无影棚`、`密不透风`、`无缝衔接`、`静立不动`、`不远处`、`一望无际`；若脚本直接替换会把文库改成病句 | 判定口径：只修「指令式否定」（避免/无需/不可/不直接裸露/半掩不露/不偏脏不偏灰/不要XX 等）与「质量后缀」（杰作/高分辨率/画质类）；惯用语、名词（无袖/无影灯/无线/无影棚）、描述性俗语（深浅不一/密不透风/生生不息）、化妆术语（裸妆/裸粉色）、艺术术语（透视/镂空）一律保留。替换需带上下文精确字符串，改后复扫 + 抽查通读 | 2026-08-18 |
| 33 | **批量修复脚本二次运行导致「女女」双前缀 substring 污染** | 修复脚本（audit_fix.py）因路径笔误（验光师在 SFW 不在 NSFW）只改了部分文件，修完路径后**整库重跑同一脚本**，短 old 串（如「说书人说到精彩处」）在已改文本（「女说书人说到精彩处」）里仍是 substring 再次命中 | 「说书人」→「女说书人」→「女女说书人」共 19 处分布在 13 文件（瓦舍听书 3 处/民谣小酒馆 3 处/那达慕 2 处等）；顺带暴露「歌手/鼓手/键盘手/乐师/伙计/摊主/先生/师傅/乐官」等前缀式替换全有同类风险 | ① 修复脚本必须**幂等**：new 文本里禁止包含可再次命中的 old substring（如直接写「女女说书人→女说书人」全量对），或替换后断言 `old not in text`；② 重跑前先核对哪些文件已改（git diff 或记录已处理清单），只补跑未完成文件；③ 跑完必做全库复扫 `女女`（19→0）与「前缀词 女X → 女女X」专项正则；④ 全局替换（如 摊主→女摊主）需守卫：文件已含「女摊主」则拒绝 | 2026-08-19 |
| 34 | **E2E 测试选择器与实际前端 ID 漂移** | E2E 测试（`test_core_user_flows.py` 等）使用 `#promptInput`/`#widthInput`/`#heightInput`/`#outputGrid`/`#batchInput`/`#freeVramBtn` 等选择器 | E2E 全部 `pytest.skip` 或超时失败；`#freeVramBtn` 已被移除（项目脱离 ComfyUI）导致 `query_selector` 返回 None | ① 写 E2E 前先 `grep getElementById` 确认前端实际 ID；② 前端 ID 变更后同步更新 E2E 选择器（如 `#posPrompt`/`#width`/`#height`/`#outGrid`/`#openBatch`）；③ 已移除的元素（如 `#freeVramBtn`）在 E2E 和 POM 中同步删除，改为验证替代元素（如 `#engineSelect`） | 2026-08-19 |
| 35 | **sqlite3.Connection.execute 是只读属性，无法 monkey-patch** | 混沌工程测试中 mock `db.conn.execute` 模拟磁盘满故障 | `AttributeError: 'sqlite3.Connection' object attribute 'execute' is read-only`；`monkeypatch.setattr` 也无效（C 扩展对象属性特殊） | ① 不能直接赋值 `db.conn.execute = mock_fn`；② `monkeypatch.setattr(db.conn, 'execute', mock_fn)` 也无效；③ 正确做法：用 `unittest.mock.patch.object(db, 'create_task', side_effect=sqlite3.OperationalError(...))` 直接 mock 方法层面，绕过 Connection 属性限制 | 2026-08-19 |
| 36 | **HistoryDB.conn 是 property 无 setter，无法直接赋值替换** | 混沌工程测试中 `db.conn = MockConn()` 尝试替换连接对象 | `AttributeError: property 'conn' of 'HistoryDB' object has no setter`；直接赋值 conn 属性会报错 | ① 不要试图替换 `db.conn`；② 如果需要 mock 连接行为，在方法层面用 `unittest.mock.patch.object(db, 'method_name', side_effect=...)` ；③ 或者在 HistoryDB 构造时传入 mock 连接（依赖注入模式） | 2026-08-19 |
| 34 | **os.walk 默认不穿透 Junction，模型目录改符号链接后资源扫描为空** | 把 portable 模式的 `model/` 目录从真实文件改为指向 ComfyUI 的 Windows Junction（目录符号链接）后，用前端「模型扫描」/ LoRA 下拉 | 前端资源列表为空：`scan_resource_files()` 用 `os.walk(base)`（默认 `followlinks=False`），遇到 Junction 直接跳过不进入子目录；但引擎加载（`resolve_engine_model_paths` 显式 sub_path）正常，容易误判"模型丢了" | `config_models.py::scan_resource_files` 的 `os.walk` 加 `followlinks=True`（本场景 Junction 指向 ComfyUI 无环，安全）；引擎加载走显式路径不受影响；回归 `python -m pytest tests/test_config.py --basetemp=<临时目录>` | 2026-08-19 |

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
