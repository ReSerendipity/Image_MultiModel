# Image MultiModel · 本机可完成全部任务最终清单 v3.0

| 项目 | 内容 |
|---|---|
| 版本 | v3.0（最终全量指示版，覆盖 v1.0/v2.0） |
| 日期 | 2026-08-09 |
| 范围 | **仅含本机（RTX 5070 Ti 12GB + ComfyUI 0.31.1 + 系统 Python 3.12）可完成的任务**；需 4090 级/干净机器/未安装 Docker 的事项统一列入 §7 排除清单 |
| 基线 | 全量测试 286 passed / 0 failed（含真实 ComfyUI 集成）；ruff clean；水印端到端已修复验证（`43a6682`） |

**结论声明**：本清单 + §7 排除项 = 该项目的全部剩余工作。清单内每一项都核实过依赖在当前环境可用（ComfyUI 在线、浏览器可用、pip 可装），按 §6 顺序做完即达成"本机可完成"的最终验收。

---

## §0 已完成并核验（无需再做）

- 全量测试 **286 passed / 0 failed**（含集成 11+ 例真实出图）
- A1 phase i18n 键（5 语）+ 前端字典 ✅；A2 checkpoint `save()` 接入 ✅；A4 迁移脚本 ✅；A5 清理 ✅
- B1 主题防闪烁 head 脚本 ✅；B7 e2e 用例（3 spec）已写 ✅；C5 ruff+mypy ✅；D2-D7/E1 ✅
- **水印端到端修复并验证**（`43a6682`）：MIN_Q 2→8、新增 MAX_Q=16、引擎裁剪 [0,255] 防 uint8 回绕、CLI 默认 n_bits 160→400；新增 PNG 往返回归测试；实机验证 `verify_watermark.py` 提取 `IMGMULTI-1|任务ID|时间戳` ✅

---

## §1 P0 收尾（本机可做，2 项）

### W1. 集成测试 8 个 `UnraisableExceptionWarning` 清理
- **现状**：`python -m pytest -q` 有 8 个警告，全部来自集成测试（worker 线程 `Event loop is closed` 收尾噪音，装饰性，不影响结果）。
- **位置**：`bin/integrated_app/app_server.py` worker `asyncio.run(run())` 收尾；或 `tests/conftest.py` 过滤。
- **做法**（推荐，改动最小）：worker 内 `asyncio.run()` 包 try/finally，或运行套件时 `-W ignore::pytest.PytestUnraisableExceptionWarning`（写入 `pyproject.toml` 的 `[tool.pytest.ini_options] filterwarnings`）。
- **验收**：`python -m pytest -q 2>&1 | tail -2` 显示 `0 warnings`。

### W2. 运行输出迁移脚本（A4 落地执行）
- **现状**：`scripts/migrate_outputs.py` 已存在未运行；`outputs/` 根部仍有旧平铺 PNG（`Flux.2_Klein-9B-Distilled_007xx_.png`），DB 路径已指向新目录，旧文件成孤儿。
- **做法**：`python scripts/migrate_outputs.py`（先备份或确认脚本支持 --dry-run）；迁移后 `ls outputs/` 根部无散落 PNG。
- **验收**：`outputs/` 只有 `{engine}/{date}/` 目录；`python -m pytest tests/test_api_contract.py -q` 仍绿。

---

## §2 P1 浏览器真机验证（需 Chrome + ComfyUI 在线，7 项）

> 启动：`python start.bat`（或 `python bin\clean_launch.py`），浏览器打开 http://127.0.0.1:8288

### V1. 主题防闪烁 + 明暗切换
- 操作：切暗色 → 刷新页面 → 无白闪；`localStorage['imm_theme']` 持久化生效。
- 验收：F5 无闪烁；明暗切换样式完整。

### V2. 系统状态抽屉真实化
- 操作：打开系统状态抽屉 → 核对 GPU 显存/内存/磁盘/队列/引擎列表与 `GET /api/health` 一致；生成 1 张图时显存数值随 SSE `gpu_status` 变化。
- 验收：数值实时变化；无硬编码占位。

### V3. 设置抽屉全量读写
- 操作：改「心跳轮询」「保留策略」等 → 保存 → 重启 → 生效；非法值被拒；host 字段只读。
- 验收：重启后 config.yaml 对应字段已更新。

### V4. 批量底抽屉端到端
- 操作：批量输入 2 条 prompt × batch=2 → 提交 → 批次进度 → 4 张入库图库。
- 验收：`GET /api/tasks` 出现批次任务；图库 4 张新图。

### V5. 5 语切换 + 进度阶段文案
- 操作：切换 zh-TW/en/ja/ko → 全界面文案切换；生成时进度条显示翻译后阶段（无裸 `phase_*` 键）。
- 验收：5 语无英文残留/裸键。

### V6. WCAG AA 对比度抽查（B6 落地）
- 操作：检查关键对比对（薰衣草紫按钮白字、浅灰提示文字、焦点环）——用浏览器 DevTools 或临时脚本算对比度。
- 验收：正文 ≥4.5:1、大字 ≥3:1；不合格色值改 `--seed-*` 派生层。

### V7. Playwright E2E 落地运行（B7 收尾）
- **现状**：`tests/e2e/test_engine_switch.py`、`test_generate_progress.py`、`test_i18n_switch.py` + conftest 已写；playwright 包与浏览器**未安装**。
- 做法：`pip install playwright pytest-playwright && playwright install chromium` → `python -m pytest tests/e2e -v`（ComfyUI 在线）。
- 验收：3 个 spec 全绿。

---

## §3 P1 质量与基准（本机可做，4 项）

### Q1. 性能基准运行与记录（C1 落地）
- **现状**：`scripts/benchmark.py` 已写未运行。
- 做法：`python scripts/benchmark.py > benchmark_report.txt`；对照 PRD §7 指标（TTFP ≤3s、完成→显示 ≤500ms、取消→GPU 释放 ≤5s、历史 50 条 <500ms、首页 ≤50KB gzip）记录达标率。
- 验收：≥90% 达标；不达标项写进 `AUDIT_REPORT_2.0.md`。

### Q2. requirements-lock 可复现安装验证（C4 落地）
- 做法：干净 venv：`python -m venv _venv && _venv\Scripts\python -m pip install --require-hashes -r requirements-lock.txt`；失败则 `pip-compile` 重新生成。
- 验收：安装成功；测试可运行。

### Q3. ruff + mypy 复跑确认（C5 收尾）
- 做法：`python -m ruff check bin tests`、`python -m mypy bin/integrated_app`（如需安装 `pip install mypy`）；新增代码（如 §1/§2 改动）同样清零。
- 验收：0 error；提交前必跑。

### Q4. 水印回归（已完成，复核即可）
- 做法：任取一张新生成图 `python scripts/verify_watermark.py <图> -p IMGMULTI-1`。
- 验收：`校验: ✅`。

---

## §4 P2 增强与实测（本机可做，6 项）

### E1. 双模式（portable）路径验证（D1 落地）
- 做法：`config.yaml` 临时 `model_source_mode: portable` → 重启 → `GET /api/config/loras` 返回空列表不报错 → 切回 shared。
- 验收：不报错；`test_model_path_resolver` 双模式绿。

### E2. WS 重连实测（D2 真机验证）
- 做法：提交一个慢任务（开 SeedVR2）→ 中途重启 ComfyUI → 观察 worker 按 `_queue_with_retry`（≤3 次指数退避）重连。
- 验收：任务最终完成或明确失败，无永久挂起。

### E3. 释放显存按钮浏览器验证（D3 收尾）
- 操作：设置抽屉点「释放显存」→ nvidia-smi 显存回落 → SSE `gpu_status` 刷新。
- 验收：显存从 ~8GB 降至 ~1GB。

### E4. 历史清理 cron 手动触发（D6 落地）
- 做法：临时改 `cleanup_cron` 为 `* * * * *` → 重启 → 观察 `history_cleanup_cron` 每分钟执行日志 → 改回。
- 验收：日志出现清理执行；超期数据被删。

### E5. 日志轮转验证（D7 落地）
- 做法：`config.logging.max_size_mb` 临时调小 → 跑几轮生成 → 检查 `logs/` 出现 `.1/.2` 轮转文件 → 调回。
- 验收：RotatingFileHandler 轮转生效。

### E6. SSE 全事件浏览器核对（1.6/D4 收尾）
- 做法：DevTools Network → EventStream 过滤 → 生成/取消/加载引擎/释放显存时核对 `task_status / gpu_status / queue_status / model_status / comfy_preview` 事件类型齐全。
- 验收：5 类事件均可观测。

---

## §5 文档与提交（3 项）

### D1. 提交纪律
- 每完成一项：`python -m pytest -q` 全绿 → `git add` → 提交（前缀 + 编号，如 `fix(W1): ...`、`test(V7): ...`）。

### D2. 状态文档同步
- 更新 `AUDIT_REPORT_2.0.md`（§1 执行记录：v3 核验结论 + 水印修复）与 `MASTER_PLAN.md`（里程碑勾选），将本报告替换为最终验收清单。

### D3. README 完整性核对（E1 收尾）
- 核对 README 含：install.bat/start.bat 用法、端口、双模式说明、`verify_watermark.py` 命令、requirements-lock 说明；补缺失章节。

---

## §6 执行顺序与最终验收

```
第 1 步  P0：W1 警告清零 → W2 迁移运行
第 2 步  P1 浏览器：V1→V7（先 V7 装 playwright，其余按序）
第 3 步  P1 质量：Q1 基准 → Q2 lock → Q3 lint → Q4 水印复核
第 4 步  P2 实测：E1→E6
第 5 步  文档：D1 提交 → D2 同步 → D3 README
最终验收（本机）：
  □ python -m pytest -q          → 全绿且 0 warnings
  □ python -m ruff check bin tests → 0 error
  □ 浏览器冒烟：5 语/暗色/系统抽屉/设置保存/批量抽屉/释放显存 全部走通
  □ scripts/verify_watermark.py  → ✅
```

---

## §7 排除清单（需高规格/特殊环境，勿在本机强做）

| 项 | 原因 | 何时做 |
|---|---|---|
| batch=9999 全量验收（D5/PRD I-5） | 需 4090 级显存 | 具备 4090 后按 PRD I-5 验收 |
| 便携包干净机器冒烟（C2） | 需未污染 Windows 机器 | 发布前在干净机按 PRD 10.5 STEP 7 |
| Docker 构建运行（C3） | 本机未安装 Docker | 安装 Docker Desktop 后 `docker compose up` |
| 多后端负载均衡真机验证（E4 发布） | 需 2 个 ComfyUI 实例长期运行 | 发布部署阶段 |
| API Token/Basic Auth 开启后全量回归（发布 E2） | 开启后日常开发受鉴权干扰 | 发布前统一验证 CSRF 联动 |
| 监控告警/HTTPS 反代（发布 E3） | 部署环境事项 | 正式部署时 |
| 3 图全量对比（original+upscaled+compare 同时出 3 文件） | 12GB 显卡 SeedVR2+Eses 全开时工作流仅落 1 张对比图；完整 3 文件链路需 4090 | 4090 环境 |

---

## 附录：环境事实（执行时对照）

- Python：系统 3.12.10（`C:\Python312`，依赖已装齐含 httpx）；WinPython 兜底：`C:\Users\Doro\Seedvr2\WPy64-312101\python\python.exe`（缺 aiohttp/hypothesis 等，装后可作 portable 运行时）
- ComfyUI：127.0.0.1:8188（0.31.1，`--lowvram` 换入换出支撑 12GB 跑 SeedVR2）
- 集成测试（`tests/test_forward_path_api.py`、`test_forward_batch_and_cancel.py`）需 ComfyUI 在线，否则自动跳过
- 测试基线：286 passed；关键提交：`8f928f9`（A1-E1）、`16dfbea`（分块+WS）、`43a6682`（水印）
