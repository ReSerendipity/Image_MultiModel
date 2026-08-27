“本文由 2026-08-27 家族治理 E3 从 AGENTS.md §4 移出，内容逐字保留”

# 测试约定详表（6 层测试分层等）

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
