“本文由 2026-08-27 家族治理 E3 从 AGENTS.md §13 移出，内容逐字保留”

# 典型 AI 开发场景 SOP（照着做，少踩坑）

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
