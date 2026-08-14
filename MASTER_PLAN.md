# Image MultiModel · 开发总纲（PRD + 原型转应用指南 合并版）

> **版本**: v1.0（合并版）· **日期**: 2026-08-08
> **取代**: `PRD.md`（v1.3，产品需求与里程碑）与 `WEBAPP_GUIDE.md`（v1，原型转应用指导）→ 两份保留存档，执行以本文件为准
> **项目现状**: 纯骨架（config.yaml + 2 个工作流 JSON + pretrained_models/text/unet/vae 空目录），**无任何 Python 代码，M0 未开始**；参考项目 Seedvr2 / TTS_MultiModel 位于 `C:\Users\Doro\`（代码复用约 62%，见附录）
> **前端决策（用户已确认）**: 单页融合版（`prototypes/figma-refactor/generate.html`）为**唯一 WebUI**，FastAPI 托管，前端通过 REST + SSE 取真实数据

---

## 1. 文档关系与冲突裁决

PRD 与 WEBAPP_GUIDE 存在 6 处不一致，按用户已确认决策裁决如下（执行一律以此为准）：

| 冲突点 | PRD（原） | WEBAPP_GUIDE（原） | **合并裁决** |
|---|---|---|---|
| 前端技术栈 | Jinja2 + HTMX 多页模板，Sidebar 布局 | 单页静态 HTML + fetch REST | **单页融合版唯一入口**（生成页 = 主画布 + 抽屉），后端只托管静态文件 + 提供 JSON API；Jinja2/HTMX 多页方案废弃 |
| 交互布局 | 3.2 Sidebar 导航 / 3.3.2 左右 55/45 工作台 | 主画布 + 右/左/顶/底抽屉 + 悬浮层 | **抽屉式单页布局**（已确认），PRD §3 UI 章节仅保留"视觉令牌/无障碍/防闪烁"等原则 |
| 历史/预设存储 | SQLite（history.db + presets 表，2.8/6.3） | tasks.json / presets.json（第 6 节） | **SQLite**（与参考项目对齐，支持 FTS5 全文检索与崩溃恢复） |
| 目录结构 | `bin/integrated_app/`（5.2，与参考项目对齐） | `app/`（第 4 节） | **bin/integrated_app/**，静态单页放 `static/`，`app/` 方案作废 |
| i18n | FR-2.11.1：YAML + HTMX data-i18n | 前端 JS 字典 + data-i18n | **前端 JS 字典**（沿用原型实现）+ localStorage 持久化 + 防闪烁（附录 E2 原则）；后端错误文案并入前端字典 |
| API 形态 | HTMX form + hx-sse | REST JSON + 轮询 | **REST JSON 为主 + SSE 单连接推送**（PRD 2.9 事件 + 附录 C2） |
| HTTP 客户端 | httpx + aiosqlite（PRD 附录） | — | **保留 aiohttp + sqlite3**（理由：aiohttp 与 ComfyUI WebSocket 生态兼容、sqlite3 同步已够用，参考项目 Seedvr2/TTS_MultiModel 已验证可行） |
| Python 版本 | 3.12+（PRD 目标） | — | **3.12.10 已验证**（WinPython WPy64-312101），3.14.6 亦兼容（39 测试绿）；发布便携包锁定 3.12 LTS |

里程碑映射：PRD M0~M6（16 周，功能导向）为主干线；WEBAPP_GUIDE M0~M3（骨架/执行/数据）并入对应阶段（见 §9）。

---

## 2. 产品定位与范围（源自 PRD §1，节点级锁定）

- 定位：基于 ComfyUI 生态的 Z-Image Turbo 图像生成平台，统一界面驱动唯一引擎 Z-Image Turbo（`z_image_turbo_native`）
- 核心形态：txt2img + LoRA 六层叠加 + SeedVR2 超分 + Eses 双图对比 + ReservedVRAM 显存预留 + 批量（1~9999）+ 历史/素材库 + 预设 + 5 语言 i18n
- 边界规则（v1.3 生效）：**范围严格以 `workflows/*.json` 节点是否存在为唯一标准**
  - 必做：txt2img、LoRA 6 层（id=16~21）、SeedVR2（id=61/62/63）、Eses（59）、ReservedVRAM（60）
  - **明确不做**：img2img/Inpaint、ControlNet、普通 lanczos 缩放预览（工作流无对应节点，M3 不规划）

---

## 3. 最终前端形态（单页融合版，用户已确认）

```
唯一入口 generate.html（由原型直接引入，FastAPI 托管为 /）
├── 主画布：对话式 Prompt + 生成 + 参数快照（引擎/分辨率/steps/cfg/预计）+ 结果 masonry
├── 顶栏：主题 ◐ / 关于 ⓘ / 设置 ⚙ / 模型 ◈（弹出菜单）/ 语言 文（弹出菜单）/ 分享 / 头像
├── 模块入口行：⚙ 高级参数 · ▦ 图片展示 · ◷ 历史记录 · ▤ 批量模式 · ▣ 预设管理
├── 抽屉（互斥，四方位）：
│   ├── 右：高级参数（22 项手风琴 02-06）、预设管理（卡片 + 编辑子视图）
│   ├── 左：历史记录（筛选表格 + 详情子视图）
│   ├── 顶：图片展示（masonry 自适应 + 悬浮查看器）、设置、关于、系统状态
│   └── 底：批量模式（Prompt 文件 / 参数网格 + 估算 + 队列）
└── 悬浮：图片查看器（拖动/缩放/对比）、队列面板（生成联动）
```
- 前端无构建步骤（纯静态单文件）；同源 fetch REST；单 EventSource 收 SSE
- 视觉沿用 Figma 化线框（浅灰/薰衣草紫/Inter）——按 PRD §3 原则后续可做品牌色回归（Warm Print）与 WCAG AA

---

## 4. 系统架构与目录结构（采用 PRD §5.2，改前端）

```
Image_MultiModel/
├── bin/
│   ├── clean_launch.py / start.bat / install.bat      # 启动加固（附录 E1）
│   └── integrated_app/
│       ├── app_server.py            # FastAPI create_app + lifespan
│       ├── config.py / config_models.py               # YAML + Pydantic + resolve_model_path()（shared/portable 双模式）
│       ├── engine_interface.py      # ImageEngine Protocol + InMemoryEngineRegistry（附录 A1）
│       ├── model_manager.py / model_registry.py       # 生命周期 + 观察者 → SSE（附录 A2/A3）
│       ├── task_queue.py            # 单 Worker 串行 + 取消回调 + 重启（附录 B1/B2）
│       ├── history_db.py            # SQLite：tasks/outputs/presets + WAL/FTS5 + 崩溃恢复（附录 B3）
│       ├── i18n.py                  # 前端字典由原型承担；后端错误文案按 5 语映射
│       ├── gpu_utils.py             # 显存预检 ×1.5 + FP8 回退 + chunk 推荐（附录 B4）
│       ├── security/                # PathGuard（附录 D1）/ integrity / watermark
│       ├── middleware/              # CSRF（C1）/ RateLimit / RequestID / API Auth
│       ├── native/
│       │   ├── source.py            # 把 references/ComfyUI 源码注入 sys.path（幂等）
│       │   ├── engine.py            # NativeEngine（ImageEngine impl，仅 infer_txt2img）
│       │   ├── executor.py          # 复用 comfy.sd / comfy.samplers 推理
│       │   └── schemas/             # z_image_turbo_native.yaml
│       ├── routes/                  # 自动发现：config / generate / tasks / outputs / presets / system(sse,health,gpu)
│       ├── static/                  # ★ generate.html（唯一前端）+ css/js 资源
│       └── locales/                 # 5 语言（前端字典的源文件）
├── workflows/                       # 已存在：Z_image_turbo.json
├── pretrained_models/               # 已建空目录骨架（portable 模式模型）
├── text/ unet/ vae/                 # 已建空目录（shared 模式 Junction 挂载点，附录 E3 脚本）
├── data/ history.db / presets / cache
├── outputs/                         # {engine}/{date}/{task_id}_original|upscaled|compare.png
├── config.yaml                      # ★ 已存在（13 大模块，唯一配置源）
└── tests/                           # pytest（9 项最小集）+ Playwright（6 spec，附录 F1）
```

---

## 5. 接口契约（REST + SSE 合并版）

### 5.1 REST（前端 fetch）
| 接口 | 说明 | 存储/来源 |
|---|---|---|
| `GET /api/health` | 后端/引擎/队列状态摘要 | 实时 |
| `GET /api/config` / `PUT /api/config` | 读/写 config.yaml（脱敏 + host 只读校验） | config.yaml |
| `POST /api/generate` | 提交 txt2img 任务 → `{task_id}` | TaskQueue |
| `GET /api/tasks?status=&engine=&q=&page=` | 历史分页筛选 | SQLite |
| `GET /api/tasks/{id}` | 任务详情（含 generation_config 22 项 + 三路输出） | SQLite |
| `POST /api/tasks/{id}/cancel` | 取消（/interrupt + 队列清理，附录 B1） | TaskQueue |
| `POST /api/tasks/{id}/redraw` | 相同参数重绘 | SQLite + Queue |
| `DELETE /api/tasks` | 批量删除 | SQLite |
| `POST /api/generate/batch` | 批量（Prompt 文件 × Grid 6 维），`GET /api/tasks/batch/{id}` 查进度 | SQLite + Queue |
| `GET /api/outputs?type=&fav=&page=` | 图库真实文件（宽高→masonry 比例） | outputs/ 扫描 |
| `POST /api/outputs/{file}/fav` | 收藏标记 | SQLite |
| `GET /api/presets` / `POST/PUT/DELETE` | 预设 CRUD（含导入导出） | SQLite presets |
| `POST /api/presets/{id}/apply` | 应用预设 → 返回参数回填前端 | SQLite |

### 5.2 SSE（单连接事件总线，附录 C2）
`task_status` / `comfy_preview` / `model_status` / `gpu_status`（2s）/ `queue_status`——前端只建一个 EventSource 分派。

### 5.3 关键字段：generation_config（22 项，PRD 2.4.2/2.5.2）
8 基础（正/负 Prompt、cfg、steps、width、height、seed、batch_size）+ LoRA 6 层 ×（name/strength）+ SeedVR2（enable/res/color/seed）+ Eses（enable/axis）+ VRAM（enable/gb/mode/seed）+ 输出（format/prefix）+ 引擎版本/工作流 SHA256；`seed=-1` 时提交前生成实际值并回填三个独立 seed 字段。

---

## 6. ComfyUI 集成要点（PRD §4 精华，M1 执行依据）

- `ImageEngine` Protocol 仅 4 方法：`is_ready / load(生成器进度) / unload / infer_txt2img(…, on_progress) / cancel`
- 每引擎一份 Schema YAML（节点 ID 严格对齐 `widgets_values` 下标；LoRA mode=4 提交前强制改 0）
- **Workflow Patcher 6 步**（PRD 4.3.2）：① 深拷贝 ② mode 切换（LoRA/SeedVR2/Eses/VRAM）③ link 重连（关闭时改 VAEDecode 直通）④ widgets 精确 patch（含 width/height 双节点同步、3 个独立 INT_SEED_RANDOMIZE）⑤ batch chunk 拆分（16；开超分 4）⑥ 提交前必做节点校验
- 输出规则（PRD 2.4.5）：双图（original + upscaled）+ compare 共存；关超分仅 original；关对比不存 compare；9999 批次带 chunk 下标命名

---

## 7. 前端接入点（每模块：模拟 → 真实，UI 结构不动）

| 模块 | 模拟（现状） | 真实接入（阶段） |
|---|---|---|
| 生成 + 进度 + 队列球 | 定时器假进度 | `POST /api/generate` + SSE task_status（M1） |
| 高级参数抽屉 | 22 项控件 | 提交体映射 generation_config；LoRA 下拉读 `GET /api/config` 资源扫描（M2） |
| 参数快照/估算 | 本地估算 | 后端估算（含真实显存系数，附录 B4）（M2） |
| 历史左抽屉 | 样例行 + 假详情 | `GET /api/tasks` + 详情 + 重绘/删除（M4） |
| 图库顶抽屉 + 悬浮查看器 | 样例卡片 | `GET /api/outputs` 真实文件 + 真实宽高比例（M4） |
| 批量底抽屉 | 静态估算/队列 | `POST /api/generate/batch` + 批次进度（M4） |
| 设置顶抽屉 | 表单不落盘 | `GET/PUT /api/config` + 资源扫描（M0） |
| 预设右抽屉 | 卡片/表单模拟 | `GET/POST/PUT/DELETE /api/presets` + apply 回填（M2） |
| 系统状态顶抽屉 | 静态数值 | `GET /api/health` + SSE gpu_status（M2/M5） |
| i18n / 主题 | 仅前端切换 | localStorage 持久化 + 防闪烁（M0）；错误文案并入字典（M2） |

---

## 8. 数据模型（SQLite，PRD 6.3）

- `tasks`：task_id/engine/mode(txt2img|batch)/status/prompt/negative_prompt/generation_config(JSON 22 项)/thumbnail/output_count/processing_time_s/error/favorite/tags/created_at/updated_at/interrupted_at_reboot
- `outputs`：task_id FK → path/format/file_size/width/height/seed（批次多张）
- `presets`：id/engine_name/name/thumbnail/config(JSON，不含 seed)/created_at
- 崩溃恢复（附录 B3）：启动先清理卡死 processing（>1h）→ 再按 config 恢复 pending；断点续跑每 100 张 checkpoint

---

## 9. 执行路线图（统一顺序，按依赖排序 —— 本文件核心）

> 每阶段含：做什么（来源编号）→ 依赖 → 验收。M3 按 PRD v1.3 边界规则**留空**（无 img2img/ControlNet 节点）。

### 阶段 0 · 环境与决策确认（0.5 天）
- 确认 Seedvr2 / TTS_MultiModel 本地仓库可读（附录复用依据）
- 确认本机 `references/ComfyUI` 源码可复用；确认唯一工作流 JSON 与 Schema 就位
- 将 `generate.html` 复制为 `bin/integrated_app/static/index.html`（唯一前端入口）
- **验收**：原型在浏览器直接可开（现状已满足），后续所有改动基于此副本

### M0 · 项目骨架 + 单页托管 + 配置层（1-2 周）
- bin/integrated_app 全部空壳落地（PRD M0）；路由自动发现 + SSE 总线 + SQLite 初始化（PRD M0）
- config_models.py + resolve_model_path() 双模式解析（PRD 10.2）
- `GET/PUT /api/config` 真实读写 config.yaml（GUIDE 5.2）；`GET /api/health`
- 前端：FastAPI 托管单页；设置顶抽屉接通 config；i18n/主题 localStorage 持久化 + 防闪烁（附录 E2）
- **验收**：浏览器打开即应用；改设置→写盘重启生效；SSE 连接建立；路径解析器双模式单测绿

### M1 · 原生引擎适配层 + Workflow Patcher（3 周）
- native/source.py（复用 references/ComfyUI 源码）、native/engine.py（NativeEngine 实现 ImageEngine）
- native/workflow.py Patcher 6 步 + Schema YAML（PRD M1）
- 前端：生成按钮接 `POST /api/generate` + SSE 进度 + 队列球联动（GUIDE 7）
- **验收**（PRD M1）：Mock batch=9999 拆分 625 次正确；LoRA/SeedVR2/Eses/VRAM 开关组合 patch 快照 100% 正确；单测覆盖 ≥70%

### M2 · 文生图工作台全功能（4 周，⭐ 必做功能全部交付）
- task_queue 单 Worker + 取消（B1/B2）；ModelManager/Registry + SSE 桥接（A2/A3）；显存预检（B4）
- 前端：高级参数抽屉 22 项全接通（LoRA 下拉读资源扫描、batch 1~9999 + 500/5000 警告）；参数快照/估算走后端；预设右抽屉 CRUD + apply 回填
- i18n 5 语：前端字典补全后端错误/警告文案（PRD M2 i18n 验收）
- **验收**（PRD M2 1-8）：真实 ComfyUI 出 3 图（original/upscaled/compare）；LoRA on/off 风格差异；SeedVR2/Eses/VRAM 开关行为正确；batch=9999 通过；5 语无遗漏；取消 <5s

### M4 · 批量 + 历史 + 素材库（2 周）
- 批量接口（Prompt 文件 + Grid 6 维 + 断点续跑）；HistoryDB 完整 CRUD + 搜索/筛选/分页 + 详情 + 批量删除/ZIP/标签/清理
- 图库接口（outputs 扫描 + 收藏）
- 前端：批量底抽屉、历史左抽屉（详情子视图）、图库顶抽屉（masonry 真实比例）全接通
- **验收**（PRD M4）：1000 条历史 <500ms；重绘 seed+22 参数一致（像素级）；Grid 组合输出份数正确

### M5 · UI/UX + 设置 + 可访问性（2 周）
- 深浅主题防闪烁、WCAG AA、StatusBar 超大批次进度、系统状态顶抽屉数据真实化（SSE gpu_status）
- **验收**（PRD M5）：Playwright E2E 截图比对 + WCAG AA 通过

### M6 · 性能 + 安全 + 发布（3 周）
- 性能基准（PRD 7）；安全审计（8：CSRF/路径穿越/RateLimit/水印）；便携包 7 步打包（10.5）；Docker（10.6）
- **验收**（PRD M6）：P0/P1 用例 100%；安全 Critical=0；便携包 7z 哈希校验 OK + 离线冒烟 7 步通过

### M3 · 留空
- 无 img2img/ControlNet 节点，不规划（PRD v1.3 边界规则）；用户提供含对应节点的新工作流后再补

### M7 · 原生进程内引擎（已完成，v1.2.0）
- **目标**：无需外部 ComfyUI 进程即可在应用进程内出图，复用本机 Comfy 源码，不重新实现模型网络。
- `bin/integrated_app/native/` 包落地：
  - `source.py`：把 `references/ComfyUI` + aki-v3 自定义节点注入 `sys.path`（幂等）
  - `executor.py`：复用 `comfy.sd` / `comfy.samplers` 完成 加载→CLIP编码→采样→VAE解码
  - `engine.py`：`NativeEngine` 实现 `ImageEngine` Protocol，输出经 `PathGuard` 校验落盘 + DCT 水印 + 缩略图
  - `lora.py` / `seedvr.py` / `compares.py` / `vram.py` / `preview.py`：Phase 3 能力扩展
- `config.yaml` 保留唯一引擎 `z_image_turbo_native`（`backend: native`）；`routes/engine_routes.py` 引擎工厂统一走 `NativeEngine`（已删除 `/engine/free` 端点）；前端引擎菜单仅展示 Z-Image Turbo。
- `engine_interface.py` 的 `GenerationConfig` 新增 `lora_stack` 动态字段。
- 测试：`tests/test_native_*.py`（zimage_poc / lora / seedvr / compares / vram / preview / batch_cancel / security）。
- **验收**：原生引擎出图链路代码走通；`_save_outputs` 路径穿越攻击向量全部被 `PathGuard` 拒绝；版本号三处同步至 v1.2.0。

**总计 ≈ 16 周**（与 PRD 一致）；前端因单页化省去多页模板开发，余量用于 5 语言与 batch=9999 稳定性。

---

## 10. 风险与注意点（合并）

1. 前端栈变更（Jinja2/HTMX → 单页 REST）影响 PRD §3/§5.1：CSP 需允许 `connect-src 'self' ws://localhost:*`；CSRF 适配 JSON fetch（Token 头注入）
2. ComfyUI 工作流参数映射是最高风险点：Schema 必须与 `widgets_values` 下标严格一致（PRD 2.4.4），建议 M1 先 Mock 后端快照比对再上真实
3. 单 Worker 串行 + OOM：batch 9999 依赖 chunk 拆分、断点续跑、expandable_segments（附录 E1）
4. 显存估算需真实基准校准（原型估算值不可直接沿用）
5. 本机安全：只绑 127.0.0.1；config.yaml host 只读
6. 参考项目路径依赖：Seedvr2/TTS_MultiModel 的 14 项迁移清单（PRD 附录 C）需按附录 A 复用比例执行

---

## 11. 待确认输入

- [ ] 参考项目仓库路径确认（C:\Users\Doro\Seedvr2 / TTS_MultiModel）
- [ ] 本地 ComfyUI 版本与 2 个工作流的 Schema 节点核对（M1 前完成）
- [ ] outputs/ 保留策略落盘实现（90 天/100GB 双阈值）
- [ ] 5 语言后端错误文案清单（M2 提供）
- [ ] 预设/历史落盘字段（§8 为建议，可调整）

---

## 附录（引用 PRD 原文，不重复展开）

- **A. 代码复用映射表**：PRD 附录 A（整体复用 ≈62%）
- **B. 参考项目文件索引**：PRD 附录 B
- **C. 代码级迁移清单（14 项）**：PRD 附录 C（A1-A3 / B1-B4 / C1-C3 / D1 / E1-E2 / F1）——各阶段实施时按编号取用
- **D. 验收矩阵 I-1~I-19 + N/A**：PRD §12.2（集成验收）
- **E. 性能/安全/兼容性**：PRD §7/§8/§9

*执行顺序以 §9 为准；冲突裁决以 §1 表为准。*
