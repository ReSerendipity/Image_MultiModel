# Image_MultiModel v2.0.0 测试体系深度完整性评估

> 评估基准：基于仓库实际代码核查（非文档假设）。核查文件：`tests/`(54 个 `test_*` + `e2e/5`)、`scripts/benchmark.py`、`.github/workflows/ci.yml|security.yml`、`pyproject.toml`、`conftest.py`、`factories.py`。
> 评估日期：2026-08-31

---

## 0. 关键事实校正（与"前置条件"不符之处）

| 评估前置条件假设 | 实际情况 | 影响 |
|---|---|---|
| `tests/integration/` 目录 | **不存在**。集成测试散落为顶层 `tests/test_forward_path_api.py`、`test_forward_batch_and_cancel.py` 等 | 目录契约不一致，违反 AGENTS.md 铁律 #6（证据绑定） |
| `perf/benchmark.py` | **不存在**。性能基准在 `scripts/benchmark.py`，且是独立 `urllib` 脚本（非 pytest） | 命名/位置偏离文档，CI 中 `performance` job 为 `if: false` 已禁用 |
| E2E 在 CI 运行 | `e2e` job 为 `if: false`（"requires app startup which fails in CI"） | E2E 实际不在任何 CI 门禁中执行 |
| 覆盖率门槛 75% | `pyproject` 写 `fail_under = 75`，但 **CI 实际门槛 60%** 且测试命令带 `|| true`（失败不阻断） | 75% 红线从未真正生效，属文档与实现不一致 |

---

## 1. 测试金字塔分层评分

> 评分维度：覆盖面 / 真实性 / 可维护性 / CI 可重复性。满分 100。

### 1.1 单元测试（基座） —— 得分 76/100
**强项**
- 边界用例扎实：`test_path_guard_attacks.py` 17 个路径穿越向量（双点/绝对路径/空字节/URL 编码/混合斜杠/Windows 保留名/符号链接/跨平台归一化）+ 正向用例，覆盖度优秀。
- 属性测试到位：`test_hypothesis.py` 对 VRAM 估算、chunk 划分、水印 roundtrip/不可感知性做 Hypothesis 随机属性验证，边缘值覆盖好。
- 负向/错误路径充分：404/422/400、损坏权重 `WeightIntegrityError`、只读 DB `OperationalError` 等均有断言。
- Mock 适度：`test_native_security.py` 用 `patch("...ensure_loaded")` 屏蔽重型 comfy import，保持轻量，做法正确。

**弱项**
- `factories.py` 仅 2 个工厂（`GenerationConfigFactory`/`TaskFactory`），大量路由测试直接 `TestClient(create_app())` 拉起**全量 app** 而非纯单元 mock，偏重。
- `test_route_coverage.py::test_unload_engine` 用 `assert r.status_code in (200, 500)` —— 把已知 bug（factory 为 None 抛 TypeError）当"正常行为"放宽断言，掩盖缺陷而非回归其修复。
- 原生引擎/推理核心（`native/`、`comfy_kernel/`）在缺 torch 环境被 `conftest.py` 整体 `skip`，CI（ubuntu 无 GPU）下这部分覆盖实际为 0。

### 1.2 集成测试 —— 得分 54/100
**强项**
- DB CRUD 与并发：`test_history_db_*.py`、`test_concurrent_db.py` 验证 WAL 串行化、FTS5 并发搜索、事务回滚。
- LoRA 端到端：`test_forward_path_api.py`（取真实 `/api/config/loras` 首个文件）、`test_native_lora.py` 覆盖单层 LoRA 加载。

**弱项**
- **缺少 `tests/integration/` 包**，命名与文档不符。
- `test_forward_path_api.py` 要求本机 ComfyUI(8188) 在线，且项目已切 `backend: native`，纯原生部署下该链路**永远 skip**，真实性受限。
- 跨进程/跨服务集成（SSE 长连接、checkpoint 断点续跑跨进程）覆盖零散，无统一集成 fixtures。

### 1.3 E2E 测试 —— 得分 50/100（结构 70 / 执行 30）
**强项**
- POM 设计模式（`pages/home_page.py`）、条件等待替代固定 timeout、跨浏览器参数化（Chromium+Firefox 经 `BROWSER` 环境变量）—— 结构规范。
- 用户旅程拆分细致：页面加载→填表→进度条→输出→批量→预设→主题/语言切换→任务取消。

**弱项（含反模式命中）**
- **反模式 #1（依赖真实 GPU）**：`test_fill_form_and_submit`/`test_progress_bar_appears`/`test_output_appears` 真实点击 `#genBtn` → 命中 `/api/generate` → 触发**实时 GPU 推理**。无 GPU 或 VRAM 不足时大量 `pytest.skip`，CI 必 flaky/超时。
- **反模式 #6（视觉回归缺失）**：截图存到 `tmp_path`/`tmp_path_factory.mktemp`（**临时目录，运行即弃**），无基线目录、无像素比对。`capture-screenshots.js` 仅手动生成到 `tests/screenshots/`，但无任何测试与之比对 → 视觉回归**实际不存在**。
- `norecursedirs = ["tests/e2e"]` + CI `if: false` → E2E 既不被默认 pytest 收集，也不进 CI，价值未兑现。

### 1.4 性能测试 —— 得分 30/100
**现状（仅 `scripts/benchmark.py`）**
- 覆盖：首页 gzip ≤50KB、`/api/health|/config|/loras|/outputs` 延迟 P50/P95/P99、SSE 事件 ≤5s。
- **缺口（对照需求）**：
  - ❌ 生成延迟 p50/p95/p99：只测端点延迟，**未测 `/api/generate` 完整推理管线**耗时。
  - ❌ 并发吞吐：无任何并发压测（无 locust/k6/asyncio 并发请求）。
  - ❌ 显存/GPU profiling：仅 `gpu_utils` 的 VRAM *估算* 单测，无真实 `nvidia-smi`/显存曲线采集。
  - ❌ **反模式 #5（无趋势追踪）**：结果仅 `print` 到 stdout，不落库/不存 CI artifact，无法跨版本比对趋势。
  - ❌ CI `performance` job `if: false` 禁用。

### 1.5 安全测试 —— 得分 70/100
**强项**
- 路径穿越：17 向量全拒（见 1.1）。
- SQL 注入：`test_sql_injection.py` 覆盖。
- 权重完整性：safetensors/pickle（CWE-502）`fail_closed`/`fail_open` 双路径（`test_native_security.py`）。
- 内容安全：`test_content_filter.py`（CLIP NSFW）+ `test_auth_middleware.py`（鉴权/CSRF）。
- `security.yml` 含 CodeQL / Trivy / pip-audit / secret-scan，外部扫描完备。

**弱项（需求缺口）**
- ❌ **提示词注入（需求 #2）**：无"jailbreak / 指令覆盖"类测试。`content_filter` 测的是 NSFW 而非 prompt injection，概念混淆。
- ❌ **文件上传校验绕过（需求 #3）**：全仓 `upload|multipart` 无对应测试。图片上传接口（若存在）未测 MIME/扩展名/路径注入绕过。
- 部分安全测试 `continue-on-error: true`（CodeQL/Trivy），高危问题不阻断合并。

### 1.6 混沌工程 —— 得分 75/100
**强项（`test_chaos_engineering.py`）**
- GPU OOM 降级：FP8 回退 / 完全不足 `can_run=False` / batch chunk 自动缩小 / 无 GPU 回 CPU 不崩。
- SQLite 磁盘满：只读 DB、mock `OperationalError`、事务回滚后数据完好。
- 并发竞争：5×3 线程并发写无丢失、并发更新最终一致、FTS5 写时搜索不脏读。
- 崩溃恢复：checkpoint 断点续跑、stuck `processing`→`interrupted`、FTS5 索引存活。

**弱项**
- ⚠️ 模块 docstring 声明"网络超时降级：aiohttp 请求超时不阻塞主线程"，但**实际无对应 test class** —— 声明与实现不符（铁律 #6）。
- ❌ 资源耗尽仅覆盖 GPU VRAM，**无 CPU/内存/句柄耗尽**场景。

---

## 2. 反模式命中总表

| # | 反模式 | 命中 | 证据 |
|---|---|---|---|
| 1 | 测试依赖真实 GPU → CI 慢/flaky | **命中** | `test_core_user_flows.py` 真实点击 `#genBtn` 触发实时推理；E2E 在无 GPU 下大量 skip |
| 2 | 硬编码绝对路径破坏跨平台 | 基本规避 | `conftest.py`/`benchmark.py` 均用 `PROJECT_ROOT` 相对解析；path_guard 已处理跨平台分隔符 |
| 3 | 测试用例间共享全局状态 | **部分命中** | 路由测试 `TestClient(create_app())` 模块级作用域 + 单例注册表共享；`conftest._ENGINE_OK` 导入期全局判定 |
| 4 | 无负向测试 | **基本规避** | 404/422/400、攻击向量、损坏权重均有负向断言（反而偏多） |
| 5 | 性能基线无趋势追踪 | **命中** | `benchmark.py` 仅 print，无落库/artifact/历史比对 |
| 6 | 视觉回归截图过期 | **命中（更糟：无基线）** | 截图存临时目录即弃；`capture-screenshots.js` 无比对环节 |

---

## 3. 改进优先级排序

### P0（阻断级，立即修）
1. **修复覆盖率门禁失效**：CI `|| true` 移除使测试失败可阻断；将实际门槛对齐文档 `fail_under=75`（当前 CI 仅 60%）。否则 75% 红线形同虚设。
2. **E2E 去 GPU 化**：为生成流程注入"假引擎"（fixture 替换 `model_manager`/推理后端），使 prompt→进度→输出旅程在无 GPU 下可跑；仅保留 1 条真实推理冒烟（标记 `@pytest.mark.slow` 手动跑）。直接消除反模式 #1。
3. **补齐目录契约**：新建 `tests/integration/` 包，将 `test_forward_path_api*` 等归入；或更新 AGENTS.md 声明"集成测试位于 `tests/` 顶层"。消除铁律 #6 证据绑定违规。

### P1（高价值）
4. **真实视觉回归**：用 `capture-screenshots.js` 生成基线并提交 `tests/screenshots/baseline/`；新增 Playwright `to_have_screenshot()` 像素比对 job（CI 启用，阈值可配）。消除反模式 #6。
5. **补齐安全缺口**：新增 `test_prompt_injection.py`（指令覆盖/分隔符注入/角色劫持）与 `test_upload_validation.py`（MIME/扩展名/路径注入绕过）。
6. **性能测试升级**：`scripts/benchmark.py` 增加（a）`/api/generate` 完整管线 p50/p95/p99（走假引擎保证可复现）；（b）asyncio 并发吞吐；（c）显存采样。结果写 JSON 并上传 Codecov/artifact 做趋势比对（消反模式 #5）。迁移到 `perf/` 或 `tests/perf/` 并接入 pytest。

### P2（健壮性）
7. **实现"网络超时"混沌用例**（当前仅 docstring 声明）；补充 CPU/内存资源耗尽场景。
8. **消除全局状态**：路由测试改为函数级 `TestClient` + `dependency_overrides` 清理；避免模块级共享单例导致的相互污染（反模式 #3）。
9. **收紧弱断言**：修复 `test_unload_engine` 的 `in (200,500)`，要么修根因（factory 为 None）要么加回归断言正确行为。

### P3（完善度）
10. **扩展 factories**：`factories.py` 仅 2 个工厂，补充 DB 行 / 预设 / 历史记录等工厂，减少路由测试样板。
11. **`security.yml` 关键扫描去 `continue-on-error`**：CodeQL/Trivy 高危项应阻断合并（当前宽松）。

---

## 4. 总结

测试体系**广度可观**（54 单元 + 5 E2E + 混沌 + 属性 + 安全扫描链），**结构性亮点明确**（POM、路径攻击 17 向量、混沌 OOM/崩溃恢复、Hypothesis）。但存在三类系统性短板：

1. **可执行性落差**：75% 覆盖率红线、`tests/integration/`、`perf/benchmark.py`、E2E/性能 CI job 均"文档声明 ≠ 实际运行"（铁律 #6 多处违反）。
2. **E2E/性能未脱离硬件**：真实 GPU 推理 + 无趋势追踪的基准，导致这两层在 CI 不可复现、无历史可比。
3. **安全语义缺口**：路径/SQL/权重扎实，但 prompt-injection 与 upload-bypass 两大攻击面零覆盖。

按金字塔健康度：**单元(76) > 混沌(75) > 安全(70) > 集成(54) > E2E(50) > 性能(30)**。优先级应**先补 P0 的执行/契约失效，再做 P1 的 E2E 去 GPU 化与视觉回归/安全/性能补洞**。
