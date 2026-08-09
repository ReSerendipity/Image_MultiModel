# Image MultiModel · 剩余与后续任务指示报告 v2.0

| 项目 | 内容 |
|---|---|
| 版本 | v2.0（核验后全量指示版，覆盖 v1.0） |
| 日期 | 2026-08-09 |
| 执行依据 | `MASTER_PLAN.md` + `PRD.md` + 本次全量核验结果 |
| 当前基线 | 非集成 265 passed（5.7s）+ 集成 11/11 passed（真实 ComfyUI）；环境：Win 系统 Python 3.12.10 / ComfyUI 0.31.1 / RTX 5070 Ti 12GB |

---

## 0. 已完成且核验通过（无需再做）

- M0/M1 骨架与适配层；M2 最小+全套（SeedVR2/Eses/VRAM）真实出图
- §1.2 分块：**chunk 循环 + 显存自适应 + WS 60s 空闲超时转 HTTP 轮询**（git `16dfbea`，已修复并验证：batch=8/5 全部产出）
- §1.1 取消 <5s（集成测试 PASSED）
- §1.4 LoRA 6 层全开/全关（集成测试 PASSED）
- §1.5 引擎加载 API（`GET /engines`、`POST /load`、`POST /unload` + SSE model_status）
- §1.6 SSE 补全（`gpu_status` 2s 推送、`queue_status` 变更发布）
- §2.1~2.5 历史 CRUD（search/export/tags/cleanup）、图库 fav/download、缩略图 512px、批量接口（集成 PASSED）
- §4.1 水印接入管线（PIL+numpy embed，异常兜底）；§4.2 输出命名 `outputs/{engine}/{date}/{prompt_id}_{type}.png`（已生效）
- §4.3~4.8 文件就位：`scripts/benchmark.py`、`docker-compose.yml`、`requirements-lock.txt`、`.gitignore`、安全审计测试（路径攻击 14 类 + CSRF）、`install.bat`/`start.bat`

---

## 1. P0 立即处理（本次核验发现的真实缺口）

### A1. 进度阶段 i18n 键未闭环（§1.7 残留）
- **现状**：引擎 `_map_phase` 已输出 `phase_sampling` / `phase_executing` / `phase_completed` 等键，但 **5 个 locale JSON（`bin/integrated_app/locales/*.json`）与前端字典（`static/index.html`）均无 `phase_*` 键** → 前端进度条会显示裸键 `phase_sampling · 45%`。
- **位置**：`bin/integrated_app/locales/{zh,zh-tw,en,ja,ko}.json`；`static/index.html` 的 T 字典。
- **做法**：
  1. 引擎侧 PHASE_KEY_MAP 的键集合（`comfy/engine.py` 顶部）逐一列出；
  2. 在 5 个 locale JSON 各补 `phase_connecting / phase_loading_workflow / phase_engine_ready / phase_patching / phase_queuing / phase_sampling / phase_executing / phase_saved / phase_completed`（zh：连接中/加载工作流/引擎就绪/打补丁/排队中/采样中 x/y/执行节点/已保存/完成；其余语言对应翻译）；
  3. 前端 T 字典同步补键，SSE 渲染 `T[phase] || phase` 兜底；
  4. `tests/test_i18n_backend.py` 加断言：PHASE_KEY_MAP 全部键在 5 语非空。
- **验收**：`python -m pytest tests/test_i18n_backend.py -q` 绿；浏览器 5 语下进度阶段显示中文而非裸键。

### A2. 断点续跑 save() 未接入（§1.3 残留）
- **现状**：`checkpoint.py` 的 `TaskCheckpoint`（save/load/delete/list/should_checkpoint）、app_server 启动扫描、worker 完成时 `delete` 都有，但 **worker/engine 从未调用 `save()`** → 生成中无落盘点，恢复机制无数据可恢复。
- **位置**：`bin/integrated_app/checkpoint.py`；`app_server.py` worker；`comfy/engine.py::infer_txt2img`（chunk 循环）。
- **做法**：
  1. `TaskCheckpoint.save(task_id, {...})` 内容：`{task_id, engine, config, completed_slots: [...], remaining: N, saved_at}`；
  2. engine 的 chunk 循环每完成一个 chunk 回调（新增 `on_chunk_done(slot_index, total)` 可选参数，worker 传入）；
  3. worker 在 `on_chunk_done` 里 `if checkpoint_mgr.should_checkpoint(completed): checkpoint_mgr.save(...)`；
  4. 启动恢复：lifespan 已扫描 `list_checkpoints()`，补"重建未完成任务并续跑剩余槽位"逻辑（构造新 Task，config 里标记从 checkpoint 续跑）；
  5. 新增 `tests/test_checkpoint.py`：Mock 下 save→load→续跑不重复 seed。
- **验收**：杀掉进程后重启，未完成任务从断点续跑且无重复输出。

### A3. 依赖环境收尾（starlette/httpx2 弃用警告）
- **现状**：系统 Python 3.12 上 `fastapi.testclient` 有 `StarletteDeprecationWarning: install httpx2`（当前装 httpx 可用但警告）；本机 Python 3.14 已移除，WinPython（Seedvr2/TTS 项目）3.12 有全栈但缺 aiohttp/hypothesis 等。
- **做法**（选一）：① `pip install httpx2` 消除警告；② 或 `requirements.txt` 固定 starlette 版本；③ 记录"系统 Python 优先 + WinPython 兜底"到 README（`install.bat` 已实现该逻辑）。
- **验收**：`python -m pytest -q` 无弃用警告。

### A4. 输出目录迁移兼容（§4.2 遗留）
- **现状**：`outputs/` 根部仍有一批旧平铺文件（`Flux.2_Klein-9B-Distilled_007xx_.png`）；新格式已写入 `outputs/{engine}/{date}/`。DB `outputs.path` 已指向新路径，旧文件成孤儿。
- **做法**：写一次性脚本 `scripts/migrate_outputs.py`：扫描 `outputs/*.png` 平铺文件 → 按命名规则移入 `outputs/{engine}/{date}/`，更新 DB `outputs.path`；或确认无用后按回收站方式删除。
- **验收**：`outputs/` 根部无散落 PNG；DB 路径全部可访问。

### A5. 工作树与临时文件清理
- **现状**：`.trash/` 有 17 个诊断 txt（可删）；`install.bat`/`start.bat` 未提交（用户新增）。
- **做法**：确认 `.trash/` 无用后删除；`git add install.bat start.bat .gitignore` 提交；本报告替换旧版并提交。
- **验收**：`git status` 干净。

---

## 2. P1 前端真机验证（需浏览器 + ComfyUI 在线）

### B1. 主题防闪烁 head 同步脚本（§3.1，**未做**）
- **现状**：`<html data-theme="light">` 硬编码，无 head 内联同步脚本；localStorage 主题在运行时 JS 才切换 → 刷新闪烁。
- **做法**：`static/index.html` `<head>` 首行插入内联脚本：读 `localStorage['theme']`（'light'/'dark'/系统偏好），设置 `document.documentElement.dataset.theme`；CSS 已有 `data-theme` 变量（10 处），无需改样式。
- **验收**：浏览器开暗色 → 刷新无白闪。

### B2. 系统状态抽屉真实化完整接线（§3.3，部分）
- **现状**：前端有 `fetch('/api/health')`（1 处），GPU/内存/磁盘/队列/引擎是否全部渲染真实值需真机核对；SSE `gpu_status` 已发布，前端是否消费需验证。
- **做法**：打开系统抽屉 → 核对每行数值与 `GET /api/health` + SSE `gpu_status` 一致；缺字段补渲染；磁盘空间建议后端在 health 加 `disk_free_gb`。
- **验收**：显存数值随生成变化实时刷新。

### B3. 设置抽屉全量读写核对（§3.4）
- **现状**：config GET/PUT 已接；需真机核对每个控件↔字段映射、保存后重启生效、非法值被拒、host 只读。
- **做法**：逐项对照 `config.yaml` 可编辑字段与抽屉控件；补 `restoreBtn` 默认值（已有）；保存前前端校验。
- **验收**：改「心跳轮询/保留策略」→ 保存 → 重启生效。

### B4. 批量底抽屉端到端（§2.1 前端）
- **现状**：后端批量接口已通过集成测试；前端批量抽屉提交 → `POST /api/generate/batch` → 批次进度 → 图库刷新需真机走通。
- **做法**：浏览器批量输入 2 条 prompt × batch 2 → 验证 4 张入库、批次进度条、失败单条提示。
- **验收**：PRD I-11 前端路径。

### B5. 5 语切换 + 阶段文案（联动 A1）
- **做法**：浏览器 5 语切换全界面文案；进度阶段显示翻译后文案。
- **验收**：zh-TW/en/ja/ko 无裸键。

### B6. WCAG AA 对比度抽查（§3.2）
- **现状**：`wcag-contrast-test.js` 未接入（未在仓库中找到运行入口）。
- **做法**：手测关键对比对（薰衣草紫按钮白字、浅灰提示、焦点环）或用临时脚本遍历计算；不合格色值修正到 `--seed-*` 派生层。
- **验收**：≥4.5:1（正文）/3:1（大字）。

### B7. Playwright E2E 落地（§3.6，**未做**）
- **现状**：requirements 仍注释 `playwright>=1.40.0`，未安装。
- **做法**：`pip install playwright && playwright install chromium`；建 `tests/pages/*.page.ts` + 关键 spec（i18n 切换/引擎切换/生成进度/批量抽屉）；CI 可选跳过。
- **验收**：`npx playwright test` 全绿。

---

## 3. P1 质量与发布

### C1. 性能基准运行达标（§4.3）
- **现状**：`scripts/benchmark.py` 已写，**未运行过**。
- **做法**：ComfyUI 在线时 `python scripts/benchmark.py`（TTFP、完成→前端显示、取消→GPU 释放、历史 50 条、首页体积）；对照 PRD §7 指标记录达标率。
- **验收**：≥90% 指标达标；不达标项记录到 AUDIT。

### C2. 便携包真机验证（§4.5，需干净机器）
- **做法**：① `scripts/setup_symlinks.ps1`（shared 建 Junction）核对文件数；② 切 portable → `pack_portable.ps1`（复制模型/清理/7z/SHA256）；③ 干净机器按 PRD 10.5 STEP 7 冒烟 7 步。
- **验收**：7z 解压启动出图。

### C3. Docker 构建与运行（§4.6）
- **现状**：`Dockerfile` + `docker-compose.yml` 已写，**未构建**。
- **做法**：`docker compose build` → `docker compose up`（portable 模式 + 模型 volume 挂载）→ `GET /api/health` 200 → 出 1 张图。
- **验收**：容器内全链路。

### C4. requirements-lock 哈希验证（§4.7）
- **做法**：`pip install --require-hashes -r requirements-lock.txt`（干净 venv）验证可复现安装；不通过则用 `pip-tools` 重新生成。
- **验收**：干净环境按锁文件安装成功。

### C5. 代码质量门禁（§4.8）
- **现状**：pyproject 有 `[tool.ruff]`；**mypy 未配置**；ruff 未跑过。
- **做法**：`python -m ruff check bin tests` 清零；`pip install mypy` + pyproject 加 `[tool.mypy]`（`bin/integrated_app`，comfy 层可加 `# type: ignore` 白名单）；`coverage report` 确认 ≥60%。
- **验收**：0 error；覆盖率报告存档。

---

## 4. P2 中期增强

### D1. 双模式（portable）路径验证（§5.4）
- 临时切 `model_source_mode: portable` + `pretrained_models/` 放小模型 → `/api/config/loras` 空列表不报错、引擎路径校验（PRD I-19 降级）；完事切回 shared。

### D2. WS 重连自动重试（风险 2）
- ComfyUI 重启时任务失败（连接错/超时）。做法：engine 检测 `ConnectionError` → 重试 `connect()`+`queue_prompt`（≤3 次，指数退避）；配 `max_wait_s` 兜底。

### D3. 「释放显存」按钮（风险 3）
- 设置抽屉加按钮 → `POST /api/comfy/free`（转发 `/free`）→ SSE `gpu_status` 刷新。

### D4. SSE `comfy_preview` 事件（P2 可选）
- WS 收到 `b_preview` → base64 → SSE 推送；前端采样中实时预览（量大，可加节流）。

### D5. batch=9999 全量验收（PRD I-5，需 4090）
- 4090 环境跑 9999 拆分→合并→历史入库；断点续跑（A2）配合。

### D6. 历史清理 cron 接入
- `config.output.history.cleanup_cron` 已配置，后端调度未接。做法：启动时 `asyncio` 定时任务按 cron 调 `cleanup_old_tasks`；日志记录清理量。

### D7. 日志轮转
- `setup_logging` 加 `RotatingFileHandler`（5MB×5）；`logs/` 入 `.gitignore`（已加）。

---

## 5. P3 发布与长期

- E1 用户手册/README：安装（install.bat/start.bat）、端口、双模式说明、水印验证命令（`scripts/verify_watermark.py`）。
- E2 正式部署：非 8288 端口、API Token/Basic Auth 开启验证（CSRF 中间件已按配置启用）、HTTPS 反代说明。
- E3 监控告警：`/api/health` 轮询脚本 + 队列积压告警（可复用 cron 能力）。
- E4 多后端负载均衡验证：`comfy.backends` 多实例 + `load_balance: prefer_local` 回退逻辑真机验证。

---

## 6. 建议执行顺序

```
P0（今天）: A1 phase 键 → A2 checkpoint save → A3 依赖警告 → A4 输出迁移 → A5 清理提交
P1（本周）: B1~B5 前端真机（浏览器+ComfyUI）→ C1 基准 → C2 便携包（干净机）→ C3 Docker → C4 lock → C5 lint
P2（两周）: D1 双模式 → D2 WS 重连 → D3 释放显存 → D4 preview → D5 9999（4090）→ D6 cron → D7 日志
P3（发布）: E1~E4
```

每项完成：`python -m pytest -q` 全绿后提交（前缀 feat/test/fix/docs + 编号如 `A1`）。

---

## 附录：核验记录与环境注意

- **本次核验结论**：用户提交 `8f928f9`（§1.3-§5.2）→ 非集成 265 全绿；集成 11/11 全绿（真实 ComfyUI）；发现并修复 2 缺陷（`16dfbea`：分块循环+自适应+WS 超时）。
- **首次复现的失败**：batch=32 无超分在 12GB OOM（原 chunk=16 固定）→ 已改自适应；全量套件 26% 挂起 → WS 静默（缓存命中）阻塞 → 已修。
- **环境注意**：① 本机 Python 3.14 已移除，系统默认 3.12（依赖已装齐，含 httpx）；② starlette 新版 testclient 提示 httpx2（见 A3）；③ 两个集成测试文件需 ComfyUI 在线否则自动跳过；④ `outputs/` 根部旧平铺文件与 `.trash/` 待清理（A4/A5）。
- **参考索引**：里程碑 `MASTER_PLAN.md §9`；验收矩阵 `PRD.md §12.2`；整改记录 `AUDIT_REPORT_2.0.md` 顶部；前端接线 F 表 `MASTER_PLAN.md §7`。
