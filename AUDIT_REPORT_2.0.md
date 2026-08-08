# Image MultiModel · 项目检查与整改报告 v2.0

| 项目 | 内容 |
|---|---|
| 版本 | v2.0（检查整改版） |
| 日期 | 2026-08-08 |
| 检查对象 | 对照 `MASTER_PLAN.md`（v1.0 执行依据）审计当前代码库 |
| 检查结论 | 骨架完成度高（M0 主体 + M1 雏形），但 **2 个阻断项**（应用无法启动 / 前端未接线）+ **若干缺口**，未达 M0 验收 |

> **执行记录（2026-08-08 复查更新）**
> - R1 / R2 / Y1~Y6：✅ 已全部解决（git `c4da858`，102 测试全绿，M0 冒烟：首页/health/config/SSE 全部 200）
> - **F1 生成主链路：✅ 已闭环**（本次修复：① 删除残留模拟函数与监听（startGen/cancelGen/renderOut 定时器）；② `startGenReal` 请求字段与元素选择对齐后端 `GenerateRequest` 全部字段（LoRA 用 `#loraStack` 选择器、SeedVR2 用 upscaleRes/upscaleSeed/colorCorr、补 color_correction/axis/vram_mode/output_prefix）；③ SSE 路径 `/api/events` 与后端一致；④ 补 `sb-gpu` 状态栏元素使 gpu_status SSE 生效；⑤ 展示后端 `estimated_time_s` 预计耗时）
> - **F3 LoRA 下拉：✅ 已闭环**（后端新增 `GET /api/config/loras` 扫描端点，复用 `scan_resource_files('lora')`；前端打开高级参数抽屉即拉取填充 6 个下拉（按文件名保留默认、缺失回退禁用），设置抽屉「完整资源扫描」按钮联动刷新。实测返回 64 个真实 LoRA 文件，mode=shared）
> - **契约测试：✅ 已补充**（新增 `tests/test_api_contract.py` 7 例：health/config/loras/列表端点 200、生成合法体非 422/500、非法体 422、预设创建；全套 **109 测试全绿**）
> - **F4 估算：决策为保持前端**（"预计生成 N 张"依赖实时表单态，前端即时计算是设计使然；后端已提供 `estimated_time_s` 预计耗时并展示）
> - 已实测：`POST /api/generate` 返回业务错误"引擎不可用"而非 422 → 请求体与 Schema 完全对齐；前端无裸 `startGen()/cancelGen()/renderOut()` 残留、`Math.random` 假进度 = 0
> - 剩余：**真实出图联调需本机启动 ComfyUI + 模型**（M2 验收点）；F4 保持前端估算（见上）

---

## 0. 当前进度定位

| 里程碑 | 状态 | 说明 |
|---|---|---|
| 阶段 0 | ✅ 完成 | 参考项目就绪；工作流 JSON ×2、config.yaml、目录骨架 |
| M0 骨架 | 🟡 未达标 | 文件全建好、config 可解析、39 测试绿；但 **app 无法导入（R1）**，前端未接线（R2），M0 验收未过 |
| M1 ComfyUI 适配 | 🟡 雏形 | workflow.py 567 行 + 2 份 Schema 已建；缺 mock 联调测试（Y2） |
| M2~M6 | ⬜ 未开始 | 依赖 M0/M1 打通后按总纲 §9 执行 |

**已验证事实**（检查时的实测结果）：
- `python -m pytest -q` → 39 passed（仅 test_config + test_workflow 两个文件）
- `load_config()` 成功，识别 2 引擎（flux2_klein_9b_distilled / z_image_turbo）
- `python -m compileall` → 仅 1 处错误：`task_queue.py:97`
- `static/index.html` 与原型 `prototypes/figma-refactor/generate.html` **字节相同**（104579 = 104579），`fetch(/EventSource/api/)` 匹配数 = 0
- locales 现有 4 份：zh / en / ja / ko（**缺 zh-tw**）
- 依赖抽查：aiohttp / aiofiles / yaml / pytest_asyncio 可用；Python 3.14.6

---

## 1. 🔴 阻断项（必须最先修复，共 2 项）

### R1. task_queue.py 语法错误 → 应用无法启动

- **位置**：`bin/integrated_app/task_queue.py` **第 97 行**
- **现状**：`logger.warning(f"Status callback error: e}")` —— f-string 缺少左花括号
- **修复**：改为 `logger.warning(f"Status callback error: {e}")`
- **验证**：
  ```bash
  python -m compileall -q bin tests            # 必须 0 错误
  python -c "import sys;sys.path.insert(0,'.');from bin.integrated_app.app_server import create_app;app=create_app();print('routes',len(app.routes))"   # 必须打印 routes N
  ```
- **影响**：不修则 M0/M1 全部无法联调

### R2. 前端完全未接线 → 仍是纯模拟原型

- **位置**：`bin/integrated_app/static/index.html`（= 原型逐字节拷贝）
- **现状**：`fetch()` / `EventSource` / `api/` 出现次数均为 **0**；全部模块仍是模拟数据
- **影响**：总纲 §7 前端接入 = 本报告第 3 节（最大工作量），修完 R1 后按第 3 节逐模块执行
- **快速自查命令**：
  ```bash
  grep -c "fetch("  bin/integrated_app/static/index.html   # 应为 >0
  grep -c "EventSource" bin/integrated_app/static/index.html # 应为 1
  ```

---

## 2. 🟡 缺口与风险（非阻断，但须在本阶段补齐）

### Y1. locales 缺 zh-tw（5 语只完成 4 语）
- **位置**：`bin/integrated_app/locales/`（现有 zh/en/ja/ko.json）
- **要求**：新增 `zh-tw.json`，与 `zh.json` 键集合 100% 对齐（简→繁转换）；前端语言菜单 5 项
- **验收**：`tests/test_i18n_coverage.py` 校验 5 文件键集合一致、无空值

### Y2. 测试覆盖不足（M1 验收未达）
- **现状**：仅 test_config + test_workflow（39 例）；engine / routes / task_queue / history_db / path_guard 均无测试
- **必须补**（对应总纲附录 F1 最小集）：
  - `test_comfy_patcher_snapshot.py`：4 大开关（LoRA/SeedVR2/Eses/VRAM）on/off 组合 → patch 后 JSON **快照比对 100% 正确**
  - `test_batch_9999_split.py`：Mock 后端 batch=9999 → chunk=16（开超分 4）拆分次数正确、结果合并
  - `test_task_queue_cancel.py`：取消 → GPU 释放 ≤5s（Mock）
  - `test_path_guard_attacks.py`：14 类路径攻击全拒绝
  - `test_history_db_recovery.py`：崩溃恢复两阶段（cleanup → recover）
  - `test_vram_estimation.py`：×1.5 系数 + FP8 回退 + chunk 推荐
- **验收**：app_layer 覆盖率 ≥60%（M0/M1 目标）

### Y3. 技术选型偏差记录（二选一，必须决策）
- **偏差**：PRD 附录/总纲写 `httpx + aiosqlite`；当前实现用 `aiohttp + sqlite3(同步)`
- **处理**：
  - 方案 A（推荐，改动小）：**保留 aiohttp + sqlite3**，在 `MASTER_PLAN.md` 第 1 节冲突裁决表补一行记录偏差（注明理由：aiohttp 与 ComfyUI WS 生态兼容、sqlite3 同步已够用）
  - 方案 B：按 PRD 统一为 httpx + aiosqlite（需改 comfy/client.py + history_db.py 两处调用层）
- **注意**：若选 A，`requirements.txt` 维持现状即可；若选 B，补 `httpx>=0.27`、`aiosqlite>=0.20`

### Y4. Python 版本记录
- PRD 目标 3.12+，实测 3.14.6 可跑（39 测试绿）；在文档记录"已用 3.14 验证"，若发布便携包建议锁定 3.12 LTS 并在 requirements-lock.txt 固化

### Y5. M0 冒烟验收未执行（修完 R1 后必做）
- 按总纲 M0 验收逐条跑：
  1. `python bin\clean_launch.py`（或 uvicorn）启动 → 浏览器自动打开单页
  2. `GET /api/health` 返回 JSON
  3. `GET /api/config` 返回脱敏配置；`PUT /api/config` 改一项 → 写盘 config.yaml 生效
  4. SSE `/api/sse/events` 连接建立（前端 EventSource 或 curl 可见 `: ping` 心跳）
  5. 设置顶抽屉能读/写 config（前端接线后）

### Y6. 杂项确认
- `data/`、`logs/` 为空属正常（运行时创建）；确认 app_server lifespan 会创建 `data/history.db` 与日志文件
- `comfy/schemas/` 2 份 YAML 已就位 ✓（无需动作）
- 确认 `bin/start.bat` 调 `python bin\clean_launch.py`（而非直接 -m uvicorn）

---

## 3. ⭐ 后续大工作一：前端接线（最大工作量，对应总纲 §7）

> 原则：**UI 结构不动**，把每个模块的"模拟数据/模拟执行"替换为真实 fetch / SSE。
> 接线骨架建议（加在 static/index.html 的 `<script>` 顶部）：
> ```js
> const API = {
>   get: async (p) => (await fetch('/api'+p)).json(),
>   send: async (p, body, method='POST') => (await fetch('/api'+p,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})})).json()
> };
> const evt = new EventSource('/api/sse/events');   // 全局唯一
> ```

| # | 模块 | 现在（模拟） | 改为（真实） | 接口（总纲 §5） | 优先级 |
|---|---|---|---|---|---|
| F1 | 生成 + 进度 + 队列球 | `startGen()` 定时器假进度 | `POST /api/generate` → SSE `task_status` 渲染进度/阶段；取消 → `POST /api/tasks/{id}/cancel` | generate / tasks / SSE | P0 |
| F2 | 设置顶抽屉 | 表单不落盘 | 进入 `GET /api/config` 加载，修改 `PUT /api/config` 保存（host 字段只读） | config | P0 |
| F3 | 高级参数抽屉 | 22 项控件（本地） | 提交体映射 `generation_config`；LoRA 下拉从 `GET /api/config` 资源扫描结果填充 | generate / config | P0 |
| F4 | 参数快照 / 估算 | 本地估算公式 | 后端估算（含显存系数 B4）；500/5000 阈值由后端返回 | generate（估算字段） | P1 |
| F5 | 预设右抽屉 | 卡片/表单模拟 | `GET/POST/PUT/DELETE /api/presets`；「应用」→ apply 返回参数回填主画布 | presets | P1 |
| F6 | 历史左抽屉 | 样例行 + 假详情 | `GET /api/tasks`（筛选/分页）→ 点行 `GET /api/tasks/{id}` 详情；重绘/删除接通 | tasks | P1 |
| F7 | 图库顶抽屉 + 悬浮查看器 | 样例卡片 | `GET /api/outputs` 渲染真实文件；`--ar` 用接口返回宽高比；收藏/下载接通 | outputs | P1 |
| F8 | 批量底抽屉 | 静态估算/队列 | `POST /api/generate/batch`；估算走后端；队列读批次进度 | generate/batch + tasks | P2 |
| F9 | 系统状态顶抽屉 | 静态数值 | `GET /api/health` + SSE `gpu_status`（2s）刷新 | system / SSE | P2 |
| F10 | i18n / 主题 | 仅前端切换 | localStorage 持久化（lang/theme）+ 防闪烁（附录 E2）；后端错误文案并入前端字典 | —（前端） | P1 |

**验收**：按 F1→F10 顺序逐个验证；全部完成后 `grep -c "fetch("` ≥ 10、`EventSource` = 1；M0 冒烟 5 条全过。

---

## 4. ⭐ 后续大工作二：M1 收尾 + M2~M6 主线（总纲 §9）

| 阶段 | 任务 | 前置 | 验收要点 |
|---|---|---|---|
| M1 收尾 | Mock ComfyServer 集成测试（Y2 补全）；`comfy/engine.py` 与 TaskQueue 联调；取消回调真实验证 | R1、Y2 | batch=9999 拆分正确；取消 <5s；4 开关快照 100% |
| M2 | task_queue 单 Worker + 取消落地；ModelManager 切换回滚（A3）；显存预检（B4）；i18n 5 语补全；预设 CRUD 前后端（F5）；高级参数全接通（F3/F4） | M1 | 真实 ComfyUI 出 3 图；LoRA/SeedVR2/Eses/VRAM 行为正确；5 语无遗漏 |
| M4 | 批量接口 + 历史 CRUD + 图库扫描（F6-F8）；断点续跑；批量删除/ZIP/标签/清理 | M2 | 1000 条历史 <500ms；重绘像素级一致 |
| M5 | 主题防闪烁 + WCAG AA；系统状态真实化（F9）；StatusBar 超大批次进度 | M4 | Playwright E2E + 截图比对 |
| M6 | 性能基准（PRD §7）；安全审计（§8：CSRF/路径穿越/RateLimit/水印）；便携包 7 步；Docker | M5 | P0/P1 100%；Critical=0；便携包冒烟 7 步 |
| M3 | 留空（工作流无 img2img/ControlNet 节点） | — | 用户提供新工作流后再规划 |

---

## 5. 建议执行顺序（自检清单）

```
□ 1. 修 R1（task_queue.py:97）→ compileall 0 错误 → create_app() 成功
□ 2. M0 冒烟（Y5）：启动 → /api/health → /api/config 读写 → SSE 心跳
□ 3. 补 Y1：zh-tw.json（与 zh.json 键对齐）
□ 4. 决策 Y3：aiohttp+sqlite3（推荐）或 httpx+aiosqlite，记录到 MASTER_PLAN 裁决表
□ 5. 补 Y2 测试最小集（M1 验收用）
□ 6. 前端接线 F1→F10（第 3 节，最大工作量）
□ 7. 进入 M1 收尾 → M2 → M4 → M5 → M6（第 4 节）
```

**完成信号**：`compileall` 0 错误、39+ 测试全绿、`grep fetch` ≥10、浏览器打开即应用（真实数据）、`/api/health` 正常、5 语可切。

---

*报告完毕。修复与实施均以 `MASTER_PLAN.md` 为契约；本文件为执行清单，可逐项勾销。*
