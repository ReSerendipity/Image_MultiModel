# Image MultiModel · 测试体系完整性评估报告

| 项目 | 内容 |
|---|---|
| 报告版本 | v1.0 |
| 评估日期 | 2026-08-09 |
| 评估范围 | 项目根目录 + `tests/` 目录全部测试代码 + `bin/integrated_app/` 被测源码 |
| 评估方法 | 逐文件代码审查 + 配置文件检查 + 架构覆盖度分析 |
| 总体结论 | 专项测试设计扎实（安全/VRAM/恢复等 8 类覆盖良好），但 **CI/CD 完全缺失、覆盖率工具未配置、中间件/引擎/SSE 等核心模块零测试、E2E 空白**，距生产级测试体系仍有显著差距。 |

---

## 目录

1. [CI/CD 流水线](#1-cicd-流水线)
2. [单元测试框架与覆盖率](#2-单元测试框架与覆盖率)
3. [集成与 API 测试](#3-集成与-api-测试)
4. [E2E（端到端）测试](#4-e2e端到端测试)
5. [专项测试](#5-专项测试)
6. [测试盲区与薄弱环节汇总](#6-测试盲区与薄弱环节汇总)
7. [改进建议](#7-改进建议)
8. [附录：测试文件清单与覆盖矩阵](#8-附录测试文件清单与覆盖矩阵)

---

## 1. CI/CD 流水线

### 1.1 现状

| 检查项 | 结果 |
|---|---|
| `.github/workflows/` 目录 | ❌ 不存在 |
| `.gitlab-ci.yml` | ❌ 不存在 |
| `Jenkinsfile` | ❌ 不存在 |
| `Dockerfile` / `docker-compose.yml` | ❌ 不存在 |
| `Makefile` | ❌ 不存在 |
| `tox.ini` | ❌ 不存在 |
| Pre-commit hooks (`.pre-commit-config.yaml`) | ❌ 不存在 |
| 任何自动化构建/测试/部署脚本 | ❌ 不存在 |

### 1.2 评估

**CI/CD 流水线完全缺失。** 项目当前没有任何形式的自动化构建、测试或部署配置。所有测试均依赖开发者手动执行 `python -m pytest`，不存在：

- **自动触发机制**：推送代码、创建 PR 时无自动测试运行。
- **阶段划分**：无 lint → test → build → deploy 流程。
- **环境隔离**：无 CI 运行环境定义，测试在开发者本地环境执行，存在环境依赖泄漏风险（如 `config.yaml` 中硬编码的 `C:/Users/Doro/APP/ComfyUI-aki-v3/...` 路径）。
- **制品管理**：无测试报告、覆盖率报告的自动归档。
- **部署自动化**：无 Docker 镜像构建、无便携包自动打包流程。

### 1.3 风险

- 回归缺陷无法在合并前被拦截。
- 测试结果不可追溯（无历史记录）。
- 环境不一致导致的"本地通过、CI 失败"问题无法暴露。
- `AUDIT_REPORT_2.0.md` 提及的 113 测试全绿状态缺乏持续验证保障。

---

## 2. 单元测试框架与覆盖率

### 2.1 测试框架

| 检查项 | 结果 | 说明 |
|---|---|---|
| 测试框架 | ✅ pytest >= 7.0.0 | `requirements.txt` 第 27 行声明 |
| 异步测试支持 | ✅ pytest-asyncio >= 0.21.0 | `requirements.txt` 第 28 行声明 |
| `conftest.py` | ❌ 不存在 | 无共享 fixture、无 path 注入统一处理 |
| `pytest.ini` / `setup.cfg` / `pyproject.toml` | ❌ 均不存在 | 无 pytest 配置（asyncio_mode、testpaths、markers 等） |
| 测试标记 (markers) | ❌ 未定义 | 无 `@pytest.mark.slow` / `@pytest.mark.integration` 等分类 |
| 测试目录结构 | 🟡 扁平 | 11 个测试文件平铺在 `tests/` 下，无 `unit/` / `integration/` / `e2e/` 子目录分层 |

### 2.2 测试用例组织结构

当前共 **11 个测试文件**，约 **113 个测试用例**（依据 `AUDIT_REPORT_2.0.md` 记录）：

| 文件 | 测试类/函数数 | 组织方式 |
|---|---|---|
| `test_config.py` | 4 类 ~20 例 | 按功能分组：ConfigLoading / ResolveModelPath / ScanResourceFiles / PathGuard / HistoryDB |
| `test_workflow.py` | 3 类 ~18 例 | TestWorkflowLoading / TestPatcher / TestBatchChunk |
| `test_api_contract.py` | 7 函数 | 扁平函数式，module-scope fixture |
| `test_path_guard_attacks.py` | 1 类 18 例 | TestPathGuardAttacks，攻击类型编号注释 |
| `test_vram_estimation.py` | 1 类 10 例 | TestVRAMEstimation |
| `test_history_db_recovery.py` | 1 类 6 例 | TestHistoryDBRecovery |
| `test_i18n_coverage.py` | 1 类 5 例 | TestI18nCoverage |
| `test_task_queue_cancel.py` | 1 类 6 例 | TestTaskQueueCancel，`@pytest.mark.asyncio` |
| `test_batch_9999_split.py` | 1 类 8 例 | TestBatchSplit |
| `test_comfy_patcher_snapshot.py` | 1 类 5 方法 | TestPatcherSnapshot，`@pytest.mark.parametrize` |
| `test_watermark.py` | 4 函数 | 扁平函数式 |

**组织亮点**：
- 测试类按功能域划分，命名清晰（如 `TestPathGuardAttacks`、`TestHistoryDBRecovery`）。
- 每个文件头部有 docstring 说明对应的需求来源（`AUDIT_REPORT_2.0 Y2` / `MASTER_PLAN §x`）。
- `test_comfy_patcher_snapshot.py` 使用 `@pytest.mark.parametrize` 覆盖开关组合。

**组织问题**：
- 无 `conftest.py`，每个测试文件重复 `sys.path.insert(0, str(BIN_DIR))` 路径注入（11 个文件中 9 个存在此重复代码）。
- 无 `unit/` / `integration/` 分层，API 契约测试与纯函数单元测试混在同一目录。
- `test_config.py` 中的 `TestPathGuard` 和 `TestHistoryDB` 与 `test_path_guard_attacks.py`、`test_history_db_recovery.py` 功能重叠，职责边界模糊。

### 2.3 Mock 与依赖注入

| 检查项 | 结果 | 说明 |
|---|---|---|
| `unittest.mock` 使用 | ❌ 未使用 | 无 `Mock`、`MagicMock`、`patch` |
| `monkeypatch` 使用 | ❌ 未使用 | 无 pytest monkeypatch fixture |
| 内联 Mock 对象 | 🟡 少量使用 | `test_vram_estimation.py` 构造 `GPUInfo` mock dataclass；`test_task_queue_cancel.py` 定义 `mock_worker` 函数 |
| 外部服务 Mock | ❌ 缺失 | `ComfyClient`（HTTP+WS）、`ComfyEngine` 无任何 Mock 测试 |
| 数据库隔离 | ✅ `tmp_path` | `test_history_db_recovery.py` 和 `test_config.py` 使用 `tmp_path` fixture 创建临时 DB |
| `pytest.importorskip` | ✅ 1 处 | `test_watermark.py` 对 numpy 使用 |

**关键问题**：
- **Mock 策略严重不足**：项目核心依赖 ComfyUI 外部服务（`comfy/client.py` 148 行），但无任何 Mock/Stub 测试覆盖该客户端。`test_task_queue_cancel.py` 中的 `mock_worker` 是简单的同步函数模拟，未使用标准 Mock 框架，无法验证复杂的异步交互场景。
- **无依赖注入抽象**：`ComfyEngine` 直接实例化 `ComfyClient`（`engine.py` 第 74 行），未通过构造函数注入，导致测试时无法替换为 Mock 客户端。

### 2.4 覆盖率配置

| 检查项 | 结果 |
|---|---|
| `pytest-cov` 依赖 | ❌ 未声明 |
| `.coveragerc` 配置 | ❌ 不存在 |
| `pyproject.toml` [tool.coverage] | ❌ 不存在 |
| 覆盖率阈值 | ❌ 未设定 |
| 覆盖率报告生成 | ❌ 无 |
| `AUDIT_REPORT_2.0.md` 提及的目标 | "app_layer 覆盖率 ≥60%（M0/M1 目标）"——但无工具验证 |

**评估**：`AUDIT_REPORT_2.0.md` Y2 节明确要求 "app_layer 覆盖率 ≥60%"，但项目中既无 `pytest-cov` 依赖，也无任何覆盖率配置文件。该目标目前处于"有要求、无执行"状态。

---

## 3. 集成与 API 测试

### 3.1 现有 API 契约测试

`tests/test_api_contract.py` 使用 FastAPI `TestClient` 进行 HTTP 级别契约测试，共 7 个测试用例：

| 测试 | 覆盖端点 | 断言质量 |
|---|---|---|
| `test_health_ok` | `GET /api/health` | ✅ 验证 status==200 + JSON body status=="ok" |
| `test_config_ok` | `GET /api/config` | ✅ 验证 200 + "server" in body |
| `test_config_loras_ok` | `GET /api/config/loras` | ✅ 验证 200 + keys 集合 + count 一致性 |
| `test_list_endpoints_ok` | `GET /api/tasks, /api/presets, /api/outputs, /api/sse/events` | 🔴 **严重缺陷**（见下文） |
| `test_generate_valid_payload_not_422_or_500` | `POST /api/generate` | 🟡 验证状态码 in (200,400,409,503)，但未验证响应体结构 |
| `test_generate_invalid_payload_422` | `POST /api/generate` | ✅ 验证 Pydantic 422 |
| `test_presets_create_ok` | `POST /api/presets` | 🟡 验证 200，但未验证返回的 id 有效性 |

### 3.2 严重缺陷：虚假通过的 SSE 端点测试

`test_list_endpoints_ok` 测试 `/api/sse/events` 返回 200，但实际 SSE 端点注册路径为 **`/api/events`**（`system_routes.py` 第 72 行：`prefix="/api"` + `@router.get("/events")`）。测试通过的原因是 `app_server.py` 第 209-216 行的 **catch-all SPA fallback**：

```python
@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str):
    file = static_dir / full_path
    if file.exists() and file.is_file():
        return FileResponse(str(file))
    return FileResponse(str(static_dir / "index.html"))  # ← 所有未匹配路径返回 200 + index.html
```

`/api/sse/events` 不匹配任何已注册路由，被 catch-all 捕获后返回 `index.html`（HTTP 200），测试误判为通过。**这是一个 false positive：SSE 端点契约实际上未被验证。**

### 3.3 集成测试覆盖盲区

#### 3.3.1 中间件测试（完全缺失）

| 中间件 | 源文件行数 | 测试覆盖 | 问题 |
|---|---|---|---|
| `CSRFMiddleware` | `middleware/csrf.py` 54 行 | ❌ 零测试 | **且该中间件未在 `app_server.py` 中注册**（grep 确认无引用），属于死代码 |
| `RateLimitMiddleware` | `middleware/rate_limit.py` 83 行 | ❌ 零测试 | 已注册但无测试验证 429 限流行为、IP 维度计数、窗口过期 |
| `RequestIDMiddleware` | `middleware/request_id.py` 24 行 | ❌ 零测试 | 已注册但无测试验证 `X-Request-ID` 注入与回传 |

#### 3.3.2 路由测试覆盖矩阵

| 路由文件 | 端点 | 契约测试 | 深度集成测试 |
|---|---|---|---|
| `system_routes.py` | `GET /api/health` | ✅ | ❌ 未验证 GPU/引擎/队列状态字段完整性 |
| | `GET /api/events` (SSE) | 🔴 路径错误 | ❌ 无 SSE 事件流测试 |
| | `GET /api/gpu` | ❌ | ❌ |
| `config_routes.py` | `GET /api/config` | ✅ | ❌ 未验证脱敏字段（api_token/password） |
| | `GET /api/config/loras` | ✅ | ❌ |
| | `PUT /api/config` | ❌ | ❌ 完全未测试配置写回 + host 只读校验 |
| `generate_routes.py` | `POST /api/generate` | 🟡 | ❌ 未测试引擎不存在 404、batch>9999 400、VRAM 不足 400、队列满 503 |
| | `POST /api/generate/batch` | ❌ | ❌ 批量生成完全未测试 |
| | `GET /api/tasks/batch/{id}` | ❌ | ❌ |
| `task_routes.py` | `GET /api/tasks` | 🟡 仅 200 | ❌ 未测试筛选(status/engine/q/favorite)、分页 |
| | `GET /api/tasks/{id}` | ❌ | ❌ |
| | `POST /api/tasks/{id}/cancel` | ❌ | ❌ |
| | `POST /api/tasks/{id}/redraw` | ❌ | ❌ |
| | `DELETE /api/tasks` | ❌ | ❌ |
| `output_routes.py` | `GET /api/outputs` | 🟡 仅 200 | ❌ |
| | `GET /api/outputs/{file}` | ❌ | ❌ 未测试 PathGuard 集成（路径穿越攻击通过 API） |
| | `POST /api/outputs/{file}/fav` | ❌ | ❌ |
| `preset_routes.py` | `GET /api/presets` | 🟡 仅 200 | ❌ |
| | `POST /api/presets` | 🟡 仅 200 | ❌ |
| | `GET/PUT/DELETE /api/presets/{id}` | ❌ | ❌ |
| | `POST /api/presets/{id}/apply` | ❌ | ❌ |
| | `POST /api/presets/import` | ❌ | ❌ |
| | `GET /api/presets/export` | ❌ | ❌ |

#### 3.3.3 数据库操作测试

`test_config.py::TestHistoryDB` 和 `test_history_db_recovery.py` 对 `HistoryDB` 进行了较好的直接测试：

| 功能 | 测试覆盖 |
|---|---|
| `create_task` / `get_task` | ✅ |
| `list_tasks` 分页 | ✅ |
| `delete_tasks` 批量 | ✅ |
| `recover_stuck_tasks` | ✅ 6 例（含 WAL、FTS5、批量恢复） |
| 预设 CRUD | ✅ create + get + update + delete |
| `add_output` | ❌ |
| `list_outputs` | ❌ |
| `set_output_favorite` | ❌ |
| `set_favorite` (task) | ❌ |
| 并发写入 | ❌ |
| SQL 注入防护 | ❌ |

#### 3.3.4 外部服务交互测试

| 组件 | 行数 | 测试覆盖 |
|---|---|---|
| `comfy/client.py` (ComfyUI HTTP+WS 客户端) | 148 行 | ❌ 完全未测试 |
| `comfy/engine.py` (ComfyEngine 推理流程) | 230 行 | ❌ 完全未测试 |
| `comfy/workflow.py` (WorkflowManager) | 567 行 | ✅ 间接测试（通过 patch/snapshot 测试） |

**关键缺失**：`ComfyClient` 的 HTTP 请求（`/prompt`, `/interrupt`, `/history`, `/view`）和 WebSocket 消息处理无任何 Mock 测试。`ComfyEngine.infer_txt2img()` 的完整推理流程（patch → queue → WS 监听 → 输出获取）无集成测试。

---

## 4. E2E（端到端）测试

### 4.1 现状

| 检查项 | 结果 |
|---|---|
| Playwright | ❌ `requirements.txt` 第 31 行被注释（`# playwright>=1.40.0`），标注"M5 阶段" |
| Cypress | ❌ 不存在 |
| Selenium | ❌ 不存在 |
| E2E 测试目录 | ❌ 不存在 |
| `tests/e2e/` 或类似结构 | ❌ 不存在 |
| 前端页面自动化验证 | ❌ 不存在 |
| 截图比对 / 视觉回归 | ❌ 不存在 |
| UI 原型 (`prototypes/`) 验证机制 | ❌ 无自动化验证 |

### 4.2 评估

**E2E 测试体系完全空白。** 项目前端为单页应用（`bin/integrated_app/static/index.html`，约 10 万字节），`AUDIT_REPORT_2.0.md` F1-F10 详细列出了 10 个前端接线模块，但没有任何自动化验证：

- **无用户工作流验证**：生成 → 进度 → 取消 → 历史查看 → 重绘 等完整流程无 E2E 覆盖。
- **无前端-后端集成验证**：`AUDIT_REPORT_2.0.md` 提到 `fetch()` ≥10 和 `EventSource` = 1 的验收标准，但无自动化检查。
- **无原型比对验证**：`prototypes/` 目录包含 `figma-refactor/`（9 个 HTML 文件）和 `style-compare/`，但无自动化截图比对或 DOM 结构验证。
- **无跨浏览器测试**：无 BrowserStack / Sauce Labs 集成。

### 4.3 `MASTER_PLAN.md` 规划 vs 现实

`MASTER_PLAN.md` M5 阶段验收要求"Playwright E2E + 截图比对"，但当前项目处于 M0/M1 阶段，E2E 尚未启动。这在当前阶段可接受，但应提前规划。

---

## 5. 专项测试

### 5.1 安全防御测试

**文件**：`tests/test_path_guard_attacks.py` — **18 个测试用例**

| 攻击类型 | 覆盖 | 说明 |
|---|---|---|
| 简单路径穿越 `../` | ✅ | `test_double_dot` |
| 双重路径穿越 | ✅ | `test_double_double_dot` |
| Windows 绝对路径 | ✅ | `test_absolute_system_path`, `test_absolute_user_path` |
| Unix 绝对路径 | ✅ | `test_unix_absolute_path` |
| 空字节注入 | ✅ | `test_null_byte_injection` |
| URL 编码穿越 `%2e%2e` | ✅ | `test_url_encoded_traversal` |
| 混合斜杠 `\..\` | ✅ | `test_mixed_slashes` |
| 超长路径 | ✅ | `test_long_path` |
| 当前目录 + 穿越 `./../` | ✅ | `test_dot_dot_slash` |
| outputs 下穿越 | ✅ | `test_outputs_traversal` |
| data 下穿越 | ✅ | `test_data_traversal` |
| 符号链接模拟 | ✅ | `test_symlink_like_path` |
| Windows 保留设备名 `CON` | ✅ | `test_windows_reserved_name` |
| 正向验证（合法路径通过） | ✅ | 4 例：outputs/data/workflows + is_safe + safe_join |

**评价**：安全测试设计**优秀**，覆盖了 OWASP 路径穿越的主流攻击向量，且包含正向验证。

**缺失**：
- 未通过 API 层验证 PathGuard（`GET /api/outputs/{file}` 路径穿越攻击的端到端测试）。
- 未测试 CSRF 防护（中间件本身未注册）。
- 未测试 RateLimit 的 429 行为。
- 未测试 CORS 配置。
- 未测试 API Token 认证（`config.yaml` 中 `api_token.enabled: false`，但代码中无认证中间件）。

### 5.2 硬件资源估算测试

**文件**：`tests/test_vram_estimation.py` — **10 个测试用例**

| 测试维度 | 覆盖 |
|---|---|
| 基础估算（×1.5 系数） | ✅ `test_base_estimate`, `test_multisample_1_5_rule` |
| 分辨率因子 | ✅ `test_resolution_factor` |
| Batch 因子 | ✅ `test_batch_factor` |
| SeedVR2 额外开销 | ✅ `test_seedvr2_overhead` |
| FP8 回退 | ✅ `test_fp8_fallback` |
| 显存不足 | ✅ `test_vram_insufficient` |
| 显存充足 | ✅ `test_vram_sufficient` |
| 80% 阈值警告 | ✅ `test_vram_tight_warning` |
| Chunk 推荐 | ✅ `test_chunk_recommendation` |

**评价**：VRAM 估算测试**全面且边界覆盖良好**，使用 `GPUInfo` mock dataclass 模拟不同显存场景。

### 5.3 国际化覆盖测试

**文件**：`tests/test_i18n_coverage.py` — **5 个测试用例**

| 测试维度 | 覆盖 |
|---|---|
| 5 语言文件存在 | ✅ |
| 键集合 100% 一致 | ✅ |
| 无空值 | ✅ |
| zh-tw 繁体验证 | ✅ |
| 键数量 ≥ 40 | ✅ |

**评价**：locale JSON 文件一致性测试**完善**。

**缺失**：
- **`i18n.py` 的 `get_error_message()` 函数未被测试**：该函数包含模板变量格式化（`{name}`, `{detail}` 等）和 fallback 逻辑，但无任何测试用例。
- **`i18n.py` 的 `ERROR_MESSAGES` 字典只有 4 种语言**（zh/en/ja/ko），**缺少 zh-tw**，而 locale JSON 文件有 5 种。`get_error_message()` 的 `locale` 参数若传入 `"zh-tw"` 会 fallback 到 zh，此行为未被测试。
- `config.yaml` 的 `i18n.available_locales` 也只列了 4 种（zh/en/ja/ko），与实际 5 个 locale 文件不一致。

### 5.4 异常恢复测试

**文件**：`tests/test_history_db_recovery.py` — **6 个测试用例**

| 测试维度 | 覆盖 |
|---|---|
| 单任务卡死恢复 | ✅ `test_recover_stuck_processing_task` |
| 批量卡死恢复 | ✅ `test_recover_multiple_stuck_tasks` |
| 近期任务不恢复 | ✅ `test_no_recovery_for_recent_tasks` |
| 已完成任务不恢复 | ✅ `test_no_recovery_for_completed_tasks` |
| WAL 模式启用 | ✅ `test_wal_mode_enabled` |
| 恢复后 FTS5 可用 | ✅ `test_fts5_search_after_recovery` |

**评价**：崩溃恢复测试**设计优秀**，覆盖了两阶段恢复（cleanup → recover）、WAL 基础设施验证、FTS5 完整性验证。

### 5.5 其他专项测试

| 专项 | 文件 | 用例数 | 评价 |
|---|---|---|---|
| 水印 | `test_watermark.py` | 4 | ✅ 覆盖嵌入/提取 roundtrip、错误 payload、不可感知性、RGB 多通道。**缺失**：小图像容量不足异常、边界尺寸（恰好 8×8）、JPEG 压缩鲁棒性 |
| 任务队列取消 | `test_task_queue_cancel.py` | 6 | ✅ 覆盖 pending/processing/nonexistent 取消、队列满拒绝、回调触发、状态摘要。**缺失**：超时任务、failed 任务取消、并发提交 |
| Batch 9999 拆分 | `test_batch_9999_split.py` | 8 | ✅ 覆盖 9999/16/4 拆分、边界值(1/16/17)、全覆盖校验。**优秀**：`test_all_chunks_cover_full_batch` 使用笛卡尔积验证 |
| 工作流 Patcher 快照 | `test_comfy_patcher_snapshot.py` | 5 方法 | ✅ 4 大开关组合 + LoRA 强制 mode=0 + 结构完整性 + seed 持久性。使用 `@parametrize` |

---

## 6. 测试盲区与薄弱环节汇总

### 6.1 模块级覆盖矩阵

| 源文件 | 行数 | 测试覆盖 | 严重度 |
|---|---|---|---|
| `security/path_guard.py` | 144 | ✅ 充分（18 例） | — |
| `gpu_utils.py` | 208 | ✅ 充分（10 例） | — |
| `history_db.py` | 474 | 🟡 部分（CRUD + 恢复，缺 outputs） | 中 |
| `watermark.py` | 160 | ✅ 良好（4 例） | 低 |
| `task_queue.py` | 242 | 🟡 部分（取消，缺超时/重试/并发） | 中 |
| `engine_interface.py` | 235 | 🟡 间接（GenerationConfig 使用，Registry 未测） | 中 |
| `config.py` | 125 | 🟡 部分（load 测试，save/reload 未测） | 中 |
| `config_models.py` | — | 🟡 部分（路径解析测试，脱敏测试） | 低 |
| `comfy/workflow.py` | 567 | ✅ 良好（patch + batch + snapshot） | — |
| `comfy/client.py` | 148 | ❌ **零测试** | 🔴 高 |
| `comfy/engine.py` | 230 | ❌ **零测试** | 🔴 高 |
| `sse.py` | 111 | ❌ **零测试** | 🔴 高 |
| `model_manager.py` | 121 | ❌ **零测试** | 🔴 高 |
| `model_registry.py` | 92 | ❌ **零测试** | 🔴 高 |
| `middleware/csrf.py` | 54 | ❌ **零测试 + 未注册** | 🔴 高 |
| `middleware/rate_limit.py` | 83 | ❌ **零测试** | 🔴 高 |
| `middleware/request_id.py` | 24 | ❌ **零测试** | 中 |
| `i18n.py` | 167 | ❌ `get_error_message()` 未测试 | 中 |
| `app_server.py` | 241 | 🟡 间接（create_app 用于契约测试，lifespan 未独立测试） | 中 |
| 路由层 (6 文件) | ~600 | 🔴 严重不足（仅 7 契约测试，多数端点未覆盖） | 🔴 高 |

### 6.2 核心薄弱环节

1. **CI/CD 完全缺失**：无任何自动化测试执行机制。
2. **覆盖率工具未配置**：≥60% 目标无法验证，实际覆盖率未知。
3. **中间件层零测试**：CSRF（死代码）、RateLimit、RequestID 三个中间件均无测试。
4. **ComfyUI 交互层零测试**：`ComfyClient`（HTTP+WS）和 `ComfyEngine`（推理流程）完全未测试。
5. **SSE 事件总线零测试**：`SSEBus` 的 publish/subscribe/heartbeat 无测试。
6. **API 契约测试存在 false positive**：`/api/sse/events` 测试因 SPA fallback 虚假通过。
7. **路由覆盖严重不足**：6 个路由文件 ~30 个端点，仅 7 个有契约测试，深度集成测试几乎为零。
8. **E2E 完全空白**：无前端自动化测试。
9. **无 conftest.py**：路径注入重复 9 次，无共享 fixture。
10. **无 Mock 框架**：未使用 `unittest.mock` / `monkeypatch`，外部依赖无法隔离。

### 6.3 架构级问题

| 问题 | 影响 |
|---|---|
| `CSRFMiddleware` 已实现但未在 `app_server.py` 注册 | 安全防护存在代码但未生效，POST 接口无 CSRF 保护 |
| `i18n.py` ERROR_MESSAGES 缺 zh-tw | 后端错误消息在 zh-tw locale 下 fallback 到 zh，与前端 5 语言不一致 |
| `config.yaml` `i18n.available_locales` 只列 4 种 | 与实际 5 个 locale 文件不一致 |
| `app_server.py` catch-all 路由 | 所有未匹配路径返回 200 + index.html，可能导致 API 路径拼写错误被测试误判为通过 |

---

## 7. 改进建议

### 7.1 CI/CD 流水线（优先级：🔴 P0）

#### 7.1.1 引入 GitHub Actions

在 `.github/workflows/ci.yml` 中创建基础流水线：

```yaml
name: CI
on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt pytest-cov
      - run: python -m pytest --cov=bin/integrated_app --cov-report=xml --cov-report=term-missing
      - uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

#### 7.1.2 添加 pre-commit hooks

创建 `.pre-commit-config.yaml`：

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

#### 7.1.3 添加 Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m compileall -q bin tests
CMD ["python", "bin/clean_launch.py"]
```

### 7.2 覆盖率工具配置（优先级：🔴 P0）

#### 7.2.1 安装 pytest-cov

在 `requirements.txt` 测试区追加：

```
pytest-cov>=4.1.0
```

#### 7.2.2 创建 `pyproject.toml` 统一配置

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "security: marks tests as security tests",
]

[tool.coverage.run]
source = ["bin/integrated_app"]
omit = ["*/__init__.py", "*/locales/*", "*/static/*"]

[tool.coverage.report]
fail_under = 60
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
```

### 7.3 创建 conftest.py（优先级：🟡 P1）

在 `tests/conftest.py` 中统一路径注入和共享 fixture：

```python
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

@pytest.fixture
def project_root():
    return PROJECT_ROOT

@pytest.fixture
def tmp_db(tmp_path):
    from integrated_app.history_db import HistoryDB
    db = HistoryDB(tmp_path / "test.db")
    yield db
    db.close()

@pytest.fixture
def path_guard(project_root):
    from integrated_app.security.path_guard import PathGuard
    return PathGuard(
        allowed_base_dirs=["outputs/", "data/", "workflows/", "pretrained_models/"],
        project_root=str(project_root),
    )
```

### 7.4 中间件测试（优先级：🔴 P0）

新增 `tests/test_middleware.py`：

```python
# 测试要点：
# 1. RateLimitMiddleware: 发送 >limit 次请求 → 验证 429 + Retry-After header
# 2. RequestIDMiddleware: 验证 X-Request-ID 注入 + 回传
# 3. CSRFMiddleware: 先注册到 app，再测试 GET 发放 token + POST 无 token → 403
# 4. 修复 CSRFMiddleware 未注册问题（app_server.py add_middleware）
```

### 7.5 ComfyUI 交互层 Mock 测试（优先级：🔴 P0）

新增 `tests/test_comfy_client.py` 和 `tests/test_comfy_engine.py`：

```python
# 使用 unittest.mock.AsyncMock 或 aiohttp 测试工具：
from unittest.mock import AsyncMock, MagicMock, patch

# 测试要点：
# 1. ComfyClient.connect() → Mock aiohttp.ClientSession，验证 /system_stats 调用
# 2. ComfyClient.queue_prompt() → 验证 /prompt POST 请求体格式
# 3. ComfyClient.ws_recv() → 模拟 WS 消息（progress/executed/error）
# 4. ComfyEngine.infer_txt2img() → Mock ComfyClient + WorkflowManager，验证完整流程
# 5. ComfyEngine.cancel() → 验证 /interrupt 调用
# 6. ComfyEngine._fetch_outputs() → Mock history 响应，验证文件保存
```

**重构建议**：将 `ComfyEngine.__init__` 中的 `ComfyClient` 实例化改为构造函数注入，便于测试替换：

```python
# engine.py 修改前:
self._client = ComfyClient(...)  # 硬编码

# 修改后:
def __init__(self, ..., client: Optional[ComfyClient] = None):
    self._client = client  # 测试时注入 Mock
```

### 7.6 SSE 事件总线测试（优先级：🟡 P1）

新增 `tests/test_sse.py`：

```python
# 测试要点：
# 1. SSEBus.subscribe() → 验证返回 Queue + subscriber_count 增加
# 2. SSEBus.publish() → 验证所有订阅者收到消息 + SSE 格式正确
# 3. SSEBus.unsubscribe() → 验证订阅者移除
# 4. QueueFull 时丢弃旧消息逻辑
# 5. heartbeat 定时发送（使用 asyncio.sleep mock）
```

### 7.7 路由深度集成测试（优先级：🟡 P1）

扩展 `test_api_contract.py` 或新增 `tests/test_routes/`：

```python
# 优先补充：
# 1. PUT /api/config → 验证写回 + host 只读
# 2. POST /api/generate 引擎不存在 → 404
# 3. POST /api/generate batch>9999 → 400
# 4. POST /api/tasks/{id}/cancel → 验证状态变更
# 5. POST /api/tasks/{id}/redraw → 验证新任务创建
# 6. DELETE /api/tasks → 验证批量删除
# 7. GET /api/outputs/{file} 路径穿越 → 403（端到端安全测试）
# 8. POST /api/generate/batch → 验证 Grid 展开逻辑
# 9. Preset CRUD 全流程
# 10. 修复 /api/sse/events 测试路径 → /api/events
```

### 7.8 E2E 测试框架引入（优先级：🟢 P2，M5 阶段）

```python
# 1. 取消 requirements.txt 中 playwright 注释
# 2. 创建 tests/e2e/ 目录
# 3. 安装: pip install playwright && playwright install chromium
# 4. 创建 tests/e2e/conftest.py 配置 FastAPI TestServer fixture
# 5. 编写关键用户流 E2E：
#    - 首页加载 → 验证 UI 元素存在
#    - 生成流程 → 填写表单 → 提交 → SSE 进度 → 结果展示
#    - 历史查看 → 列表加载 → 详情 → 重绘
#    - 预设管理 → 创建 → 应用 → 删除
#    - 设置 → 修改 → 保存 → 刷新验证
# 6. 截图比对: 使用 playwright screenshot + pixelmatch
```

### 7.9 其他改进

| 改进项 | 优先级 | 说明 |
|---|---|---|
| 修复 CSRFMiddleware 未注册 | 🔴 P0 | `app_server.py` 中 `app.add_middleware(CSRFMiddleware)` |
| 修复 SSE 测试路径 | 🔴 P0 | `test_api_contract.py` 中 `/api/sse/events` → `/api/events` |
| 补充 `i18n.py` zh-tw 错误消息 | 🟡 P1 | `ERROR_MESSAGES` 字典添加 zh-tw 条目 |
| 修复 `config.yaml` available_locales | 🟡 P1 | 添加 `zh-tw` 到列表 |
| 引入 `unittest.mock` | 🟡 P1 | 替换内联 mock 为标准 Mock 框架 |
| 测试目录分层 | 🟢 P2 | `tests/unit/` + `tests/integration/` + `tests/e2e/` |
| 消除 `test_config.py` 与专项测试的重叠 | 🟢 P2 | 将 `TestPathGuard` / `TestHistoryDB` 迁移到对应专项文件 |
| 添加 `add_output` / `list_outputs` 测试 | 🟡 P1 | `HistoryDB` outputs 表 CRUD 完全覆盖 |
| 添加 `ModelManager` / `ModelRegistry` 测试 | 🟡 P1 | 引擎生命周期状态机验证 |
| 引入 ruff 代码检查 | 🟢 P2 | 替代 flake8 + isort + black |
| 添加 `scripts/verify_watermark.py` 测试 | 🟢 P2 | CLI 入口测试 |

---

## 8. 附录：测试文件清单与覆盖矩阵

### 8.1 测试文件清单

| # | 文件 | 用例数 | 类型 | 覆盖模块 |
|---|---|---|---|---|
| 1 | `test_config.py` | ~20 | 单元 | config, config_models, path_guard, history_db |
| 2 | `test_workflow.py` | ~18 | 单元 | comfy/workflow, gpu_utils, engine_interface |
| 3 | `test_api_contract.py` | 7 | 集成 | app_server, routes/* (浅层) |
| 4 | `test_path_guard_attacks.py` | 18 | 安全 | security/path_guard |
| 5 | `test_vram_estimation.py` | 10 | 单元 | gpu_utils |
| 6 | `test_history_db_recovery.py` | 6 | 异常恢复 | history_db |
| 7 | `test_i18n_coverage.py` | 5 | 国际化 | locales/*.json |
| 8 | `test_task_queue_cancel.py` | 6 | 单元 | task_queue |
| 9 | `test_batch_9999_split.py` | 8 | 单元 | comfy/workflow, gpu_utils |
| 10 | `test_comfy_patcher_snapshot.py` | 5 方法 | 单元 | comfy/workflow |
| 11 | `test_watermark.py` | 4 | 单元 | watermark |
| — | **合计** | **~113** | — | — |

### 8.2 未测试源文件清单

| # | 源文件 | 行数 | 风险评估 |
|---|---|---|---|
| 1 | `comfy/client.py` | 148 | 🔴 外部服务交互，高故障风险 |
| 2 | `comfy/engine.py` | 230 | 🔴 核心推理流程，高故障风险 |
| 3 | `sse.py` | 111 | 🔴 实时通信，高故障风险 |
| 4 | `middleware/csrf.py` | 54 | 🔴 安全组件（且未注册） |
| 5 | `middleware/rate_limit.py` | 83 | 🔴 安全组件 |
| 6 | `middleware/request_id.py` | 24 | 🟡 可观测性组件 |
| 7 | `model_manager.py` | 121 | 🔴 生命周期管理 |
| 8 | `model_registry.py` | 92 | 🟡 注册表桥接 |
| 9 | `i18n.py` (get_error_message) | 167 | 🟡 错误文案 |
| 10 | `config.py` (save/reload) | 125 | 🟡 配置写回 |
| 11 | `app_server.py` (lifespan) | 241 | 🟡 生命周期 |
| 12 | `scripts/verify_watermark.py` | 77 | 🟢 CLI 工具 |

### 8.3 测试体系成熟度评估

| 维度 | 成熟度 | 评分 | 说明 |
|---|---|---|---|
| CI/CD 流水线 | 无 | 0/5 | 完全缺失 |
| 单元测试框架 | 基础 | 2/5 | pytest 已用但无配置、无覆盖率、无 conftest |
| Mock 与依赖注入 | 薄弱 | 1/5 | 无标准 Mock 框架，外部依赖未隔离 |
| API 契约测试 | 初级 | 2/5 | 7 例浅层契约，存在 false positive |
| 路由集成测试 | 严重不足 | 1/5 | ~30 端点仅 7 个浅测 |
| 中间件测试 | 缺失 | 0/5 | 三个中间件零测试 |
| 外部服务测试 | 缺失 | 0/5 | ComfyClient/ComfyEngine 零测试 |
| E2E 测试 | 缺失 | 0/5 | 完全空白 |
| 安全测试 | 良好 | 4/5 | PathGuard 14 类攻击覆盖优秀 |
| VRAM 估算测试 | 良好 | 4/5 | 10 例覆盖全面 |
| 异常恢复测试 | 良好 | 4/5 | 6 例覆盖 WAL/FTS5/批量恢复 |
| 国际化测试 | 中等 | 3/5 | JSON 文件一致性良好，但函数未测 |
| 水印测试 | 良好 | 3.5/5 | 4 例覆盖核心场景 |
| 覆盖率管理 | 缺失 | 0/5 | 无工具、无配置、无阈值 |
| **综合** | **初级** | **1.8/5** | 专项测试有亮点，基础设施层严重缺失 |

---

*报告完毕。建议按 P0 → P1 → P2 优先级依次落实改进项，首要解决 CI/CD 缺失、覆盖率工具缺失、中间件/引擎/SSE 零测试三个核心问题。*
