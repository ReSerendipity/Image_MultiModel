# Image MultiModel · 剩余任务清单报告

| 项目 | 内容 |
|---|---|
| 版本 | v1.0（剩余任务全量清单） |
| 日期 | 2026-08-09 |
| 执行依据 | `MASTER_PLAN.md`（§9 路线图）+ `PRD.md`（验收矩阵）+ `AUDIT_REPORT_2.0.md` |
| 当前基线 | 244 测试全绿、覆盖率 81.21%；真实 ComfyUI（RTX 5070 Ti 12GB + ComfyUI 0.31.1）上前向链路已验证 |

---

## 0. 状态快照（完成 / 剩余）

| 里程碑 | 状态 | 说明 |
|---|---|---|
| 阶段 0 + M0 | ✅ 完成 | 骨架、配置、单页托管、config/health/SSE、契约测试 |
| M1 | ✅ 完成 | ComfyUI 适配层、Patcher + UI→API 转换（子图展开/bypass 重连/伪控件过滤/COMBO 归一化）、Schema、Mock 测试 |
| M2 核心 | ✅ 完成 | 最小链路 + 全套（SeedVR2 2048+Eses+VRAM）+ LoRA 单层 真实出图；`tests/test_forward_path_api.py` 5/5 |
| M2 收尾 | 🟡 剩余 8 项 | 见 §1（取消/batch 分块/5 语/LoRA 6 层/引擎加载切换/SSE 事件/进度阶段/显存弹窗） |
| M4 | 🟡 待做 | 批量端到端、断点续跑、历史完整 CRUD、图库收藏/下载、缩略图（见 §2） |
| M5 | 🟡 待做 | 主题防闪烁、WCAG AA、StatusBar、系统状态抽屉、i18n 后端文案、Playwright E2E（见 §3） |
| M6 | 🟡 部分 | watermark 模块已建**未接入管线**、scripts 已建**未真机验证**；性能基准/安全审计/Docker/lock 待做（见 §4） |
| 工程收尾 | 🟡 待做 | 输出命名规范、SSE 事件补全、临时文件清理（见 §5） |

---

## 1. M2 收尾（P0，真实环境验收剩余项）

> 前置：ComfyUI 运行中（127.0.0.1:8188），参考 `tests/test_forward_path_api.py` 的写法补用例。

### 1.1 取消链路端到端 <5s（P0，PRD I-12）
- **现状**：`POST /api/tasks/{id}/cancel` → `TaskQueue.cancel` → 置 `cancel_requested`；Worker 的 `prog` 回调里检测后调 `engine.cancel()`（→ `/interrupt`）。代码链路存在，**未在真实环境验证耗时**。
- **位置**：`bin/integrated_app/task_queue.py`（cancel）、`app_server.py`（worker prog）、`comfy/engine.py`（cancel）。
- **做法**：新增 `tests/test_forward_path_api.py::test_cancel_under_5s`：提交 batch_size=8（分块慢任务）→ 1s 后 cancel → 断言任务 `cancelled` 且总耗时 <5s；用 nvidia-smi 前后对比显存回落。
- **验收**：`python -m pytest tests/test_forward_path_api.py::test_cancel_under_5s -v` 通过；ComfyUI `/interrupt` 生效。

### 1.2 batch 分块（P0，PRD 4.3.2 第 5 步 / I-5 降级版）
- **现状**：`_patch_batch_chunk` 在 UI 层拆分（chunk≤16，开超分≤4），9999 拆分逻辑有 Mock 测试（`test_batch_9999_split.py`）；**真实 ComfyUI 上未验证多 chunk 连续提交与结果合并**。
- **位置**：`comfy/workflow.py::_patch_batch_chunk`、`comfy/engine.py::infer_txt2img`。
- **做法**：真实测试 batch_size=32（无超分，2×chunk16）与 batch_size=9（开超分，3×chunk4）；断言多张输出全部落盘、`output_count` 正确；**9999 全量**留到 4090 级环境（PRD I-5）。
- **验收**：新增 `test_forward_batch_chunk`，输出文件数 = batch_size。

### 1.3 断点续跑 checkpoint（P0，PRD 2.7.2）
- **现状**：**未实现**。batch>500 应每 100 张落盘 checkpoint（应用崩溃可续）。
- **位置**：新增 `bin/integrated_app/tasks/checkpoint.py`（或并入 task_queue）；config `runtime` 段加 `checkpoint_every: 100`。
- **做法**：Worker 每完成 100 张写 `data/checkpoints/{task_id}.json`（已完成的 prompt×seed 组合 + 剩余队列）；启动时 `history_db.recover_stuck_tasks` 后扫描 checkpoint 恢复未完成任务。
- **验收**：Mock 测试（中断后重启 → 补齐剩余，seed 不重复）+ `test_history_db_recovery` 扩展。

### 1.4 LoRA 6 层全开/全关对比（P0，PRD I-6）
- **现状**：单层已通；**6 层全开**（默认权重 1.0/0.7/0.5/0.4/0.3/0.2）与全关未对比验证；6 层文件名均需真实存在（`/api/config/loras` 核对）。
- **做法**：真实测试同 seed 生成 全开 vs 全关 两张，断言两张 hash 不同、均 completed；把默认 6 层文件名与扫描结果匹配，缺失层自动回退 `— 禁用 —`（前端已实现回退逻辑，需验证提示）。
- **验收**：`test_forward_lora_stack_all`；`generation_config` 完整记录 6 层。

### 1.5 引擎加载 / 切换 API（P1，PRD 2.3.3 + I-15）
- **现状**：**无引擎加载/切换端点**（`system_routes` 无 `POST /api/engine/load`）；Worker 每次任务内建引擎（`engine.load()` 每次连接+拉 object_info），切换引擎在 UI 侧无真实联动；ModelManager/Registry 有代码但未接路由。
- **位置**：新增 `routes/engine_routes.py`（或并入 system）：`POST /api/engine/load {engine_name}`（生成器进度 → SSE `model_status`）、`POST /api/engine/unload`、`GET /api/engines`（registry 元数据 + 加载状态）。
- **做法**：复用 `model_manager.py`（A3 三阶段切换/回滚）；前端模型菜单（`engMenu`）点击 → load → 状态灯。
- **验收**：`POST /api/engine/load` 返回引擎状态；SSE 收到 `model_status:loaded`；切换失败回滚不崩溃。

### 1.6 SSE 事件补全（P1，PRD 2.9.1）
- **现状**：只发布 `task_status` + `heartbeat`；前端已监听 `gpu_status`（目标元素 `sb-gpu` 已修）但**后端不发布**；`comfy_preview` / `queue_status` / `model_status` 未发。
- **位置**：`app_server.py` lifespan + `routes/system/sse`。
- **做法**：① 每 2s 发布 `gpu_status`（`gpu_utils.get_gpu_info` → free/total/util）；② 队列变化发布 `queue_status`（task_queue 回调）；③ 引擎加载发布 `model_status`（配合 1.5）；④ 可选 `comfy_preview`（WS 预览图 b64，量大，P2）。
- **验收**：前端系统状态抽屉 GPU 数值随 SSE 刷新（接 3.3）。

### 1.7 进度阶段文案对齐（P1，PRD 2.9.2）
- **现状**：引擎 progress 阶段为英文（`Sampling x/y`、`Executing node N`、`Completed`）；前端期望中文阶段（排队中/采样中/超分中/对比拼接/保存入库）。
- **做法**：`engine._handle_msg` 输出 i18n 阶段键（如 `phase_sampling`），前端字典映射 5 语；未知阶段显示旋转指示器。
- **验收**：SSE `task_status.phase` 为键而非裸英文；前端 5 语渲染正确。

### 1.8 显存预检弹窗（P2，PRD B4）
- **现状**：预检放行开关已加（`allow_tight`）；前端未展示 `warning`/`estimated_vram_gb`（后端已返回）。
- **做法**：`startGenReal` 收到 `warning` 时在阶段文案/弹窗提示"显存紧张，将依赖低显存模式，可能较慢"。
- **验收**：开 SeedVR2 时前端可见提示。

---

## 2. M4 批量 + 历史 + 素材库（P0 前两项 / P1 其余）

### 2.1 批量接口端到端（P0，PRD 2.7 / I-11）
- **现状**：`POST /api/generate/batch`（`BatchGenerateRequest`：prompts 列表 + prompt_file + grid_dimensions 6 维）代码存在，**未真实联调**；前端批量底抽屉有 `api/generate/batch` 引用但未完整验证。
- **位置**：`routes/generate_routes.py::batch`；前端 `static/index.html` 批量段。
- **做法**：真实测试 2 条 prompt × batch=2（SeedVR2 off）→ 4 张输出；Grid 2 维（steps×cfg）数量预测与实出一致；前端批量抽屉提交 + 批次进度（`GET /api/tasks/batch/{id}`）。
- **验收**：`test_forward_batch_small`；失败单条不阻塞整批 + 重试。

### 2.2 历史完整 CRUD（P1，PRD 2.8）
- **现状**：`list_tasks`（分页/筛选参数已有）+ `get_task` + `delete_tasks` + `set_favorite` 存在；**搜索（q 关键字）实现程度未验证**、批量导出 ZIP / 批量标签 / 保留策略清理（天数/GB 双阈值）未实现。
- **位置**：`routes/task_routes.py`、`history_db.py`。
- **做法**：补 `q` 全文搜索（SQLite FTS5 或 LIKE 兜底）；`GET /api/tasks/export?ids=` 打包 ZIP（original/upscaled/compare 可分别选）；`POST /api/tasks/tags` 批量加标签；清理任务（`keep_days`/`max_gb` 扫描 outputs + DB 删除，`config.output.history.cleanup_cron`）。
- **验收**：1000 条历史分页 <500ms；导出 ZIP 结构正确；清理只删超期数据。

### 2.3 历史详情 / 重绘 / 存预设（P1，PRD 2.8.2）
- **现状**：redraw 端点已有；前端历史详情子视图展示字段较少（engine/status/prompt/时间/尺寸）。
- **做法**：详情展示 generation_config 22 项（8 基础 + LoRA 6 层 + SeedVR2 + Eses + VRAM + 输出）；「保存为预设」按钮（调 `POST /api/presets`）；「重绘」已接。
- **验收**：详情 22 项与提交一致；重绘像素级一致（同 seed）。

### 2.4 图库：收藏 / 下载 / 筛选（P1，PRD 2.8.2）
- **现状**：`GET /api/outputs`（type/fav/page）存在；前端收藏按钮、`set_output_favorite` 未接；下载走 `/api/outputs/{file}/download`（有）但前端预览用 `/api/outputs/{path}` 直链。
- **做法**：前端图库卡片接收藏（调 `set_output_favorite`）、下载（新窗口 `/api/outputs/{file}/download`）、筛选 chips（type/fav 已渲染）。
- **验收**：收藏后 `?fav=true` 过滤正确；下载文件完整。

### 2.5 缩略图生成（P2，PRD 2.8.1）
- **现状**：DB 有 `thumbnail` 字段，worker 直接传 `outputs[0]` 全图路径，**未生成 512 缩略图**；`config.output.save_thumbnail: true` 未生效。
- **做法**：`engine._fetch_outputs` 保存后用 Pillow 生成 `{file}_thumb.png`（最长边 512）写入 `data/cache/thumbs/`；`add_output`/`update_task_status` 填缩略图路径。
- **验收**：`data/cache/thumbs/` 出现缩略图；图库列表加载明显变快。

---

## 3. M5 UI/UX + 设置 + 可访问性

### 3.1 主题防闪烁 + 明暗切换（P1，PRD 附录 E2）
- **现状**：前端主题切换 localStorage 已做（`localStorage` ×7）；`<head>` 防闪烁脚本未加（现在是运行时 JS 切换）。
- **做法**：`static/index.html` `<head>` 首行插入同步脚本（读 `localStorage['theme']` → 设置 `data-theme`，默认跟随系统）。
- **验收**：刷新无闪烁；明暗切换样式不崩（对照原型）。

### 3.2 WCAG AA 对比度（P1，PRD 3.4）
- **现状**：原型视觉（浅灰/薰衣草紫）未做对比度审计；`wcag-contrast-test.js` 未接入。
- **做法**：写 `tests/wcag-contrast-test.js`（Playwright 截各 Tab → 遍历文本元素算对比度 ≥4.5:1/3:1）；修正不合格色值（薰衣草紫按钮白字、浅灰提示文字等）。
- **验收**：报告 CSV 全绿。

### 3.3 系统状态抽屉真实化（P1，PRD 2.10）
- **现状**：抽屉内 GPU/内存/磁盘/引擎/后端为静态值；`GET /api/health` 已有真实数据。
- **做法**：进入抽屉拉 `GET /api/health`（含 GPU 信息、队列、引擎列表）；接 SSE `gpu_status` 每 2s 刷新（配合 1.6）；磁盘用 `shutil.disk_usage` 后端化。
- **验收**：数值随真实环境变化。

### 3.4 设置抽屉全量读写（P1，PRD 2.11）
- **现状**：`GET/PUT /api/config` 已接（设置抽屉进入加载、保存写回）；但**表单控件与 config 字段映射不全**（心跳/自动拉起/负载均衡/保留策略等未绑定）。
- **做法**：把 `config.yaml` 各可编辑字段与抽屉控件绑定（`inference.*`、`output.history.*`、`comfy.backends.local.*` 只读展示）；保存前校验（host 只读已有）。
- **验收**：改一项 → 重启生效；非法值被拒。

### 3.5 i18n 后端错误文案 5 语（P1，PRD 2.11.1）
- **现状**：前端字典 5 语（含 zh-tw）；后端 `get_error_message` 错误文案是否 5 语覆盖未核对（`locales/{zh,zh-tw,en,ja,ko}.json` 已建，键集合可能不全）。
- **做法**：`tests/test_i18n.py` 断言后端错误键 5 语 100% 非空；补齐缺失。
- **验收**：`test_i18n_coverage` 通过。

### 3.6 Playwright E2E（P1，PRD 12.1）
- **现状**：未安装（requirements 注释）；页面对象 + 6 spec（PRD 附录 F1）未建。
- **做法**：`pip install playwright` + `playwright install chromium`；建 `tests/pages/*.page.ts` + `specs/i18n.spec.ts` / `lora_stack.spec.ts` / `sse.spec.ts` / `batch_9999.spec.ts`；接 `wcag-contrast-test.js`。
- **验收**：`npx playwright test` 全绿。

---

## 4. M6 性能 + 安全 + 发布

### 4.1 水印接入生成管线（P0，PRD 8.6）
- **现状**：`watermark.py` 模块 + 4 测试 + CLI 验证脚本已有；**engine 输出未嵌入水印**（生成链路无 watermark 调用）。
- **位置**：`comfy/engine.py::_fetch_outputs`（保存后）或 `app_server.py` worker（outputs 落盘后循环 embed）。
- **做法**：保存每个输出 PNG 前用 Pillow 读入 → `watermark.embed_watermark(arr, product_id, task_id, ts)` → 回写；`scripts/verify_watermark.py` 可提取。
- **验收**：生成 1 张 → `python scripts/verify_watermark.py outputs/xxx.png` 输出 product_id/task_id 匹配。

### 4.2 输出命名规范（P1，PRD 2.4.5 + 10 章）
- **现状**：保存为 ComfyUI 文件名平铺 `outputs/Flux.2_Klein-9B-Distilled_007xx_.png`；`config.output.organize_by: engine_date`、`naming_template` 未生效。
- **做法**：`_fetch_outputs` 改为 `outputs/{engine}/{date}/{task_id}_original|upscaled|compare.png`（单图时按链路判断类型；9999 批次带 `{chunk}_{item}`）；缩略图与图库路径同步。
- **验收**：输出目录结构符合 PRD；重绘/图库引用一致。

### 4.3 性能基准（P1，PRD §7）
- **现状**：未做基准脚本。
- **做法**：`scripts/benchmark.py`：测 TTFP（提交→首事件 ≤3s）、任务完成→前端显示 ≤500ms、取消→GPU 释放 ≤5s、历史 50 条 <500ms、首页 HTML ≤50KB(gzip)；输出对比表（开/关 SeedVR2）。
- **验收**：关键路径达标（PRD 12.3：≥90% 达标）。

### 4.4 安全审计执行（P1，PRD §8）
- **现状**：中间件（CSRF/RateLimit/RequestID）在、`test_path_guard_attacks`（14 类攻击）在、`test_csrf` 相关在；**全端点 CSRF 覆盖与越权校验未系统执行**。
- **做法**：跑 `test_path_guard_attacks.py` + `test_csrf`；补：所有 POST/PUT/DELETE 无 CSRF 头 → 403 的契约用例；`/api/outputs/download` 路径穿越用例；启动完整性自检（`security/integrity_manifest.json` 比对）。
- **验收**：安全用例 100% 通过；OWASP 无 Critical。

### 4.5 便携包真机验证（P1，PRD §10.5）
- **现状**：`scripts/setup_symlinks.ps1` / `pack_portable.ps1` 已写**未执行验证**。
- **做法**：① 跑 `setup_symlinks.ps1`（shared 模式建 text/unet/vae Junction）核对文件数；② 切 `model_source_mode: portable` → `pack_portable.ps1`（复制模型/清理/7z/SHA256）；③ 干净机器冒烟 7 步（PRD 10.5 STEP 7）。
- **验收**：FR-10.2~10.4 全过；7z 可解压启动出图。

### 4.6 Docker 完善（P2，PRD §10.6）
- **现状**：`Dockerfile` 有；`docker-compose.yml` 缺。
- **做法**：写 compose（nvidia runtime、模型 volume 挂载、`MODELS_SOURCE_MODE=portable`、8288 映射、restart）；镜像基础层 `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`。
- **验收**：容器内 `GET /api/health` 200。

### 4.7 依赖锁 requirements-lock.txt（P2，PRD 9.3）
- **现状**：缺失。
- **做法**：`pip freeze > requirements-lock.txt`（或 pip-compile）；`pip install --require-hashes` 验证。
- **验收**：干净环境按锁文件安装成功。

### 4.8 代码质量门禁（P2，PRD 12.6）
- **现状**：pyproject.toml 有（用户新增）；ruff/mypy 未跑。
- **做法**：`ruff check bin tests`、`mypy bin/integrated_app`（排除 comfy 纯 I/O）清零；覆盖率门禁 ≥60%（当前 81.21% ✓）。
- **验收**：0 error。

---

## 5. 工程与数据收尾（P1/P2 混合）

### 5.1 SSE 事件补全（并入 1.6）——见上
### 5.2 临时文件清理（P1）
- **现状**：根目录出现过诊断 txt（已移入 `.trash/`）；`.gitignore` 需补 `*.txt` 临时产物、`.trash/`、`pytest_out*.txt`、`gen*.txt`、`fp_out*.txt`。
- **做法**：检查 `.gitignore` 补条目；`.trash/` 确认后删除。
- **验收**：`git status` 干净。

### 5.3 git 提交纪律（P1）
- **现状**：用户并行提交多；当前工作树应保持干净。
- **做法**：每完成 §1~§4 一项即提交（feat/test/fix 前缀 + 关联 PRD 编号）。

### 5.4 双模式路径真实验证（P1，PRD §10.1-10.3）
- **现状**：`resolve_model_path` 有测试；shared 模式真实路径（LoRA 扫描 64 个）已验证；portable 未验证。
- **做法**：临时改 `model_source_mode: portable` + 在 `pretrained_models/` 放 1 个小模型 → `GET /api/config/loras` 返回空列表但不报错；引擎工作流校验路径正确（PRD I-19 降级）。
- **验收**：`test_model_path_resolver` 双模式绿。

---

## 6. 风险与注意点

1. **12GB 笔记本限制**：SeedVR2 全开依赖 `--lowvram` 换入换出（预检已放行）；`batch=9999` 全量验收需 4090 级环境（PRD I-5）。
2. **WS 断开场景**：引擎已转 HTTP 轮询兜底 + 1200s 硬超时；ComfyUI 重启时任务会失败（超时/连接错），建议后续加"后端重连自动重试"（P2）。
3. **每次生成后模型驻留显存**：ComfyUI 不自动卸载；长任务序列建议每任务前 `/free`（测试已内置），UI 侧可在设置里加"释放显存"按钮（P2）。
4. **水印接入会小幅增加耗时**（DCT 仅第一通道，影响可忽略）；务必保留 `scripts/verify_watermark.py` 验收闭环。
5. **输出命名规范改动会破坏既有图库路径**：迁移时给 `outputs` 表加一版迁移或启动时扫描重命名（P2）。
6. **Playwright 依赖浏览器下载**（~150MB），CI 可选跳过（`--markers`）。

---

## 7. 建议执行顺序

```
□ 1. M2 收尾（§1）：1.1 取消 → 1.2 batch 分块 → 1.4 LoRA 6 层 → 1.5 引擎加载 API → 1.6 SSE 补全 → 1.7 阶段文案 → 1.8 弹窗
□ 2. M4（§2）：2.1 批量端到端 → 2.2 历史搜索/清理 → 2.3 详情 22 项 → 2.4 图库收藏/下载 → 2.5 缩略图
□ 3. M5（§3）：3.1 防闪烁 → 3.3 系统状态 → 3.4 设置全量 → 3.5 i18n 后端文案 → 3.2 WCAG → 3.6 Playwright
□ 4. M6（§4）：4.1 水印接入 → 4.2 输出命名 → 4.3 性能基准 → 4.4 安全审计 → 4.5 便携包 → 4.6 Docker → 4.7 lock → 4.8 lint
□ 5. 收尾（§5）：临时文件/`.gitignore` → 双模式验证 → 提交纪律
```

每完成一项：跑 `python -m pytest -q` 全绿后 `git commit`（前缀 feat/test/fix + PRD 编号）。

---

## 附录 A：参考索引

- 里程碑与顺序：`MASTER_PLAN.md` §9
- 验收矩阵 I-1~I-19 + N/A：`PRD.md` §12.2
- 代码级迁移清单（14 项 A1-F1）：`PRD.md` 附录 C
- 整改执行记录：`AUDIT_REPORT_2.0.md` 顶部"执行记录"
- 前端接线 F 表：`MASTER_PLAN.md` §7（F1~F10 已基本闭环，剩余见 §3/§2 前端项）
- 当前测试基线：244 passed（含 `test_forward_path_api.py` 5 例真实 ComfyUI 集成）
