# AGENTS.md — AI 辅助开发指南

本文档为 AI 编程助手（如 Codex / CatPaw / Cursor 等）提供 Image MultiModel 项目的开发规范和约束。AI 助手在修改代码前**必须**遵循以下规则。

---

## 代码风格

### Ruff 规则

- **行宽**：120 字符（`line-length = 120`）
- **目标版本**：Python 3.12（`target-version = "py312"`）
- **启用规则**：`E, F, W, I, UP, B, SIM`（pyflakes + pycodestyle + isort + pyupgrade + bugbear + simplify）
- **故意忽略的规则**（**不要**擅自移除这些 ignore）：
  - `E501`：行长超 120 不强制报错（ruff format 已处理大部分情况）
  - `E402`：模块级 import 顺序（项目中有 `sys.path.insert` 场景需要先加路径再 import）
  - `B008`：可变默认参数（Pydantic BaseModel 字段默认值场景需要）
  - `B017`：pytest `assertRaises(Exception)` 泛匹配（安全测试中有意使用）
  - `B905`：`zip()` 无 `strict` 参数（兼容旧代码）
  - `SIM102` / `SIM108` / `SIM105` / `SIM117`：三元表达式 / try-except 简化（可读性优先）

### 格式化

```bash
python -m ruff format bin tests        # 格式化
python -m ruff check --fix bin tests   # 自动修复
python -m ruff check bin tests         # 检查（CI 会跑）
```

### Import 顺序（isort）

```python
# 1. 标准库
import os
import sys
from pathlib import Path

# 2. 第三方
import pytest
from fastapi import FastAPI

# 3. 项目内部（known-first-party: integrated_app, bin）
from integrated_app.config import get_config
from integrated_app.routes import router
```

---

## 测试要求

### 覆盖率门槛

- **覆盖率不低于 75%**（`pyproject.toml` -> `[tool.coverage.report] fail_under = 75`）
- CI 会强制检查，低于 75% 的 PR 会被阻断

### 测试文件命名

- 单元测试：`tests/test_*.py`
- 集成测试：`tests/test_*.py`（使用 `@pytest.mark.integration`）
- 安全测试：`tests/test_*_attacks.py` / `tests/test_*_injection.py`（使用 `@pytest.mark.security`）
- E2E 测试：`tests/e2e/test_*.py`（使用 `@pytest.mark.e2e`）
- 属性测试：`tests/test_hypothesis.py`（使用 Hypothesis）

### 测试标记

```python
@pytest.mark.slow          # 慢测试
@pytest.mark.integration   # 集成测试（需要 ComfyUI 在线）
@pytest.mark.security      # 安全测试
@pytest.mark.e2e           # 端到端测试（需要浏览器）
@pytest.mark.smoke         # 冒烟测试（核心关键路径）
```

### 安全相关功能的测试要求

**新功能必须补 `test_` 测试。安全相关功能必须加攻击测试。**

例如：
- 新增文件操作路由 -> 补 PathGuard 路径穿越攻击测试（`tests/test_path_guard_attacks.py`）
- 新增数据库查询 -> 补 SQL 注入测试（`tests/test_sql_injection.py`）
- 新增 API 端点 -> 补契约测试（`tests/test_api_contract.py`）

### 运行测试

```bash
python -m pytest -q                                    # 全量测试
python -m pytest -m "not slow and not integration"     # 快速测试（排除慢/集成）
python -m pytest -m security                           # 仅安全测试
python -m pytest -m smoke                              # 仅冒烟测试
python -m pytest --cov=bin/integrated_app              # 覆盖率
python -m pytest tests/e2e -m e2e                      # E2E（需 Playwright）
```

---

## 模块边界

**严格分层，不允许跨层引用。**

### `comfy/` — ComfyUI 引擎层

- **只放** ComfyUI 相关逻辑：Client（HTTP/WS）、Engine（推理封装）、Workflow（参数注入/校验）、VRAM Scheduler
- **不能出现** FastAPI 代码（Request/Response/Router 等）
- **不能出现** SQLite 操作
- 可以引用：`config.py`、`engine_interface.py`

### `routes/` — API 路由层

- **只做**：参数校验（Pydantic Model）-> 调用服务层 -> 返回响应
- **不能写** 推理逻辑 / 业务逻辑（应委托给 `task_queue` / `model_manager` / `history_db` 等）
- **不能直接** 操作 ComfyUI Client（应通过 `engine_interface` 或 `model_manager`）
- 可以引用：所有服务层模块

### `middleware/` — 中间件层

- CSRF / RateLimit / RequestID / ErrorHandler
- 不包含业务逻辑

### `security/` — 安全模块

- PathGuard（路径防护）、Integrity（完整性校验）、Watermark（水印）
- 被路由层和其他服务层引用，自身不引用路由层

### `static/` — 前端

- 单页应用（`index.html`），纯静态文件
- 通过 `fetch()` 调用 REST API，通过 `EventSource` 订阅 SSE
- 前端不包含 Python 代码，后端不包含前端逻辑（除 FastAPI 静态文件托管配置）

---

## MASTER_PLAN 配合

### 新功能开发流程

1. **先更新 `MASTER_PLAN.md`** 中对应里程碑的验收标准
2. **再写代码**，代码实现严格对齐 MASTER_PLAN 中的契约定义
3. **补测试**，测试覆盖 MASTER_PLAN 验收要点
4. **更新 `CHANGELOG.md`**，记录变更
5. **提交**，提交信息使用 Conventional Commits 格式

### 里程碑对应

| 里程碑 | 模块 | 关键文件 |
|--------|------|----------|
| M0 | 骨架 + 配置 | `app_server.py` / `config.py` / `config_models.py` |
| M1 | ComfyUI 适配 | `comfy/client.py` / `comfy/engine.py` / `comfy/workflow.py` |
| M2 | 文生图工作台 | `task_queue.py` / `model_manager.py` / `gpu_utils.py` / `routes/generate_routes.py` |
| M4 | 批量 + 历史 | `routes/task_routes.py` / `history_db.py` / `routes/output_routes.py` |
| M5 | UI/UX | `static/index.html` / `locales/*.json` |
| M6 | 性能 + 安全 | `security/` / `scripts/benchmark.py` / `Dockerfile` |

---

## 提交规范

### Conventional Commits

```
<type>(<scope>): <description>

类型:
  feat     新功能
  fix      修复 Bug
  docs     文档变更
  test     测试相关
  chore    构建/工具/依赖
  refactor 重构（不改变功能）
  perf     性能优化
  security 安全修复
```

示例：
```
feat(M2): 添加 LoRA 下拉资源扫描端点 GET /api/config/loras
fix(watermark): 修复 DCT 嵌入 uint8 回绕问题
docs(api): 补充 examples/ 示例脚本
test(security): 新增 PathGuard 路径穿越攻击测试 14 例
```

### Pre-commit 钩子

项目配置了 `.pre-commit-config.yaml`，提交前自动运行：
- ruff check + format
- trailing-whitespace
- end-of-file-fixer
- check-yaml
- check-added-large-files
- check-merge-conflict
- debug-statements

```bash
# 安装 pre-commit
pip install pre-commit
pre-commit install

# 手动运行
pre-commit run --all-files
```

---

## 常见陷阱

1. **f-string 花括号**：之前出过 `f"...: e}"` 缺左花括号的 Bug，写 f-string 时注意 `{var}` 配对
2. **asyncio 事件循环**：Worker 线程中使用 `asyncio.run()` 时注意 `Event loop is closed` 警告，用 try/finally 包裹
3. **SQLite 线程安全**：`sqlite3` 默认不允许跨线程使用，如需跨线程加 `check_same_thread=False` 或使用连接池
4. **PathGuard**：所有文件路径操作必须经过 `PathGuard.resolve()` 校验，不允许直接拼接用户输入的路径
5. **SSE 长连接**：SSE 事件必须以 `\n\n` 结尾，否则浏览器不会触发 `onmessage`
6. **Config host 只读**：`config.yaml` 中的 `server.host` 不允许通过 API 修改，安全考虑
7. **模型路径双模式**：`shared` 模式模型路径指向 ComfyUI 目录，`portable` 模式指向项目内 `pretrained_models/`，修改时注意 `resolve_model_path()` 的行为差异
