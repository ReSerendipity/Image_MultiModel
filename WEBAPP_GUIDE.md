# Image MultiModel · 线框原型转 Web 应用指导报告

| 项目 | 内容 |
|---|---|
| 状态 | 草案 v1 · 待评审 |
| 日期 | 2026-08-08 |
| 前置 | 单页融合版线框已获确认（`prototypes/figma-refactor/generate.html`） |
| 目标 | 将可交互线框升级为本地 Web 应用（FastAPI 托管，单页融合版为唯一 WebUI） |

---

## 1. 结论与边界

**当前交付物是"可交互线框"，不是应用。** 交互范式（抽屉四方位、参数快照、i18n、主题、masonry 自适应）已经可用，但所有执行与数据均为模拟：生成为假进度、历史/图库为样例数据、设置不落盘、预设不持久化。

**本次目标：线框 → Web 应用。** 前端保持单页融合版不动（主画布 + 右/左/顶/底抽屉 + 悬浮层），由 FastAPI 托管，前端通过 REST 接口取真实数据、触发真实执行；数据最终落在真实文件与 `outputs/` 目录。

三层结构（已在原型验证，应用沿用）：

- 主画布：对话式生成（Prompt + 生成 + 参数快照 + 结果）
- 抽屉：右（高级参数/预设）、左（历史）、顶（图片展示/设置/关于/系统状态）、底（批量）
- 悬浮：图片查看器、队列面板

---

## 2. 现状盘点

### 2.1 原型已具备（直接复用，不改结构）
- 全部 UI 交互：抽屉互斥、子视图（历史详情/预设编辑）、悬浮查看器拖动缩放对比、队列悬浮球
- 五语言 i18n、明暗主题、顶栏图标菜单（模型/语言切换）
- 22 项参数控件、估算/阈值警告、批量 Prompt 文件 + 参数网格、masonry 自适应
- Figma 化线框视觉与种子令牌（`--seed-*`）

### 2.2 尚缺（需要后端与真实数据补齐）
| 缺口 | 说明 |
|---|---|
| 生成执行 | 前端模拟进度 → 真实提交 ComfyUI 工作流 |
| 历史数据 | 样例行 → 真实任务记录（落盘） |
| 图库数据 | 样例卡片 → 读取 `outputs/` 真实文件 |
| 设置持久化 | 抽屉表单 → 读写 `config.yaml` |
| 预设持久化 | 卡片/表单 → `presets.json` |
| 队列真实态 | 静态队列 → 后端任务队列状态 |
| 错误处理 | 无 → 失败态/重试/超时 |

---

## 3. 技术栈与形态

- 后端：Python 3.10+ · FastAPI + Uvicorn（沿用 `config.yaml`：`host: 127.0.0.1`、`port: 8288`、`workers: 1`、`auto_open_browser: true`）
- 前端：单页静态 HTML（`generate.html`）为唯一入口，无构建步骤；FastAPI 直接托管静态文件，同源 fetch 调 REST
- 任务执行：单 Worker 串行队列（与 config `workers=1` 一致，防 OOM）；大批次支持断点续跑（每 100 张 checkpoint）
- 参考复用：SeedVR2（FastAPI + Jinja2 模式，代码复用约 70%）与 TTS_MultiModel 的声明式引擎约定

---

## 4. 建议目录结构

```
Image_MultiModel/
├── app/
│   ├── main.py            # FastAPI 入口：挂载路由 + 静态托管
│   ├── routes/
│   │   ├── config.py      # /api/config 读写
│   │   ├── generate.py    # /api/generate + 任务状态
│   │   ├── tasks.py       # /api/tasks 历史/队列
│   │   ├── outputs.py     # /api/outputs 图库
│   │   └── presets.py     # /api/presets
│   ├── core/
│   │   ├── settings.py    # config.yaml 加载/保存
│   │   └── store.py       # tasks.json / presets.json 持久化
│   ├── engine/
│   │   ├── comfy.py       # ComfyUI 工作流提交/轮询
│   │   └── workflow.py    # 22 参数 → 工作流 JSON 映射
│   ├── tasks/
│   │   └── queue.py       # 单 Worker 任务队列（checkpoint 续跑）
│   ├── static/
│   │   └── index.html     # 单页融合版（由 generate.html 引入）
│   └── data/              # 运行时数据（gitignore）
│       ├── tasks.json
│       └── presets.json
└── outputs/               # 生成结果（original/upscaled/compare）
```

前端改动约定：单页文件内部以 `window.APP = { apiBase: '' }` 提供 API 前缀，方便后续部署调整。

---

## 5. API 契约（REST，全部 JSON）

### 5.1 健康与状态
| 接口 | 说明 |
|---|---|
| `GET /api/health` | 后端/引擎/队列状态摘要 |

```json
{ "ok": true, "engine": "FLUX.2 Klein", "loaded": true, "queue": { "running": 1, "pending": 0 } }
```

### 5.2 配置
| 接口 | 说明 |
|---|---|
| `GET /api/config` | 读 config.yaml（脱敏） |
| `PUT /api/config` | 写回 config.yaml |

```json
{ "server": { "port": 8288 }, "models": { "default_engine": "FLUX.2 Klein-9B Distilled" }, "run": { "heartbeat_s": 30, "auto_spawn": true, "balance": "round_robin" }, "retention": { "days": 90, "gb": 100 } }
```

### 5.3 生成
| 接口 | 说明 |
|---|---|
| `POST /api/generate` | 提交生成任务，返回 task_id |
| `GET /api/tasks/{id}` | 任务状态与进度 |
| `POST /api/tasks/{id}/cancel` | 取消任务 |

请求体（GenerationConfig，与前端 22 项参数一一对应）：

```json
{
  "engine": "FLUX.2 Klein-9B Distilled",
  "prompt": "一位亚洲女性肖像，柔和自然光，浅景深，胶片质感",
  "negative_prompt": "",
  "cfg": 1.0, "steps": 8, "width": 1024, "height": 1024,
  "seed": -1, "batch_size": 1,
  "lora": [
    { "name": ".safetensors", "strength": 1.0 },
    { "name": "Kook_Flux_klein_亚洲人像.safetensors", "strength": 0.7 }
  ],
  "seedvr2": { "on": true, "res": 2048, "color": "lab", "seed": -1 },
  "eses": { "on": true, "axis": "h" },
  "vram": { "on": true, "gb": 0.6, "mode": "auto", "seed": -1 },
  "output": { "format": "png", "prefix": "{engine}" }
}
```

任务状态机：`queued → sampling → upscale → compare → done | cancelled | failed`，每阶段带 `progress`（0-100）与阶段文案，前端进度条与队列悬浮球据此渲染。

### 5.4 历史
| 接口 | 说明 |
|---|---|
| `GET /api/tasks?status=&engine=&q=&page=&page_size=` | 分页筛选 |
| `GET /api/tasks/{id}` | 详情（含完整 config 与三路输出路径） |
| `POST /api/tasks/{id}/redraw` | 用相同参数重绘 |
| `DELETE /api/tasks` | 批量删除 |

### 5.5 图库
| 接口 | 说明 |
|---|---|
| `GET /api/outputs?type=original\|upscaled\|compare&fav=&page=` | 真实文件列表（含宽高/比例/时间） |
| `POST /api/outputs/{file}/fav` | 收藏标记 |
| `GET /api/outputs/{file}/download` | 下载 |

前端 masonry 直接使用接口返回的 `width/height` 计算 `--ar`。

### 5.6 预设
| 接口 | 说明 |
|---|---|
| `GET /api/presets` | 预设列表 |
| `POST /api/presets` | 新建（保存当前参数） |
| `PUT /api/presets/{id}` | 编辑 |
| `DELETE /api/presets/{id}` | 删除 |
| `POST /api/presets/{id}/apply` | 应用（返回参数供前端回填） |

### 5.7 批量
| 接口 | 说明 |
|---|---|
| `POST /api/generate/batch` | 提交批量任务（文件行 × 网格组合） |
| `GET /api/tasks/batch/{id}` | 批次进度（子任务汇总 + checkpoint） |

---

## 6. 数据模型与映射

### 6.1 GenerationConfig（22 项）
与前端高级参数抽屉结构一致（见 5.3 请求体），由 `engine/workflow.py` 映射为 ComfyUI 工作流 JSON：
- LoRA 顺序 = 工作流节点 id=16→21（UNETLoader → CFGGuider），选「— 禁用 —」跳过并重连链路
- SeedVR2 节点、Eses 拼接节点、ReservedVRAM 节点各自独立参数

### 6.2 Task 记录（tasks.json）
```json
{
  "id": "88421",
  "status": "done", "progress": 100, "phase": "保存与入库",
  "engine": "FLUX.2 Klein-9B Distilled",
  "config": { "…完整 GenerationConfig…" },
  "outputs": [
    { "kind": "original", "path": "outputs/88421_original.png", "width": 1024, "height": 1024 },
    { "kind": "upscaled",  "path": "outputs/88421_upscaled.png",  "width": 2048, "height": 2048 },
    { "kind": "compare",   "path": "outputs/88421_compare.png",   "width": 4096, "height": 2048 }
  ],
  "created_at": "2026-08-08T15:24:00+08:00", "duration_s": 42.3,
  "fav": false, "tags": []
}
```

### 6.3 Preset（presets.json）
```json
{ "id": "p1", "name": "默认预设（FLUX.2）", "desc": "亚洲人像基线", "engine": "FLUX.2 Klein-9B Distilled",
  "config": { "…GenerationConfig…" }, "tags": ["人像"], "fav": true, "updated_at": "…" }
```

### 6.4 config.yaml ↔ /api/config 映射
`server.*`、`models.*`、`run.*`（心跳/自动拉起/负载均衡）、`retention.*` 等键位映射到设置抽屉各分组；写回前校验 `server.host` 不得改为非回环地址（安全强制，沿用 config 注释）。

---

## 7. 前端改造清单（generate.html → 真应用）

按模块列出替换点，全部为"模拟 → fetch"替换，UI 结构不动：

| 模块 | 现在（模拟） | 改为（真实） |
|---|---|---|
| 生成 | `startGen()` 定时器假进度 | `POST /api/generate` → 轮询 `GET /api/tasks/{id}` 渲染进度/阶段；取消 → `POST …/cancel` |
| 结果区 | 静态三卡 | `renderOut()` 渲染三路输出真实路径；masonry 用真实宽高比 |
| 历史抽屉 | 样例行 + 假详情 | `GET /api/tasks` 渲染列表；点行进详情拉 `GET /api/tasks/{id}`；筛选/分页/重绘/删除接通 |
| 图库抽屉 | 样例卡片 | `GET /api/outputs` 渲染；收藏/下载接通；`--ar` 用真实比例 |
| 设置抽屉 | 表单不落盘 | `GET/PUT /api/config`，进入时加载、修改后保存（含资源扫描触发） |
| 预设抽屉 | 卡片/表单模拟 | `GET/POST/PUT/DELETE /api/presets`；「应用」回填主画布参数 |
| 批量抽屉 | 静态估算/队列 | `POST /api/generate/batch`；估算改为后端返回；队列读真实批次进度 |
| 队列悬浮球 | 生成时本地进度 | 轮询健康接口的队列态；多任务时展示真实队列 |
| 系统状态 | 静态数值 | `GET /api/health` 刷新 GPU/内存/磁盘/后端/引擎状态 |
| 语言/主题 | 仅前端切换 | 持久化到 config（`ui.locale/theme`）或 localStorage |
| 错误处理 | 无 | 全接口统一错误提示条；失败任务显示原因与重试 |

---

## 8. 里程碑计划（含验收标准）

### M0 骨架整合（1-2 天）
- FastAPI 起服务（沿用 config.yaml），托管单页融合版为 `/` 首页
- `GET /api/health`、`GET/PUT /api/config`（真实读写 config.yaml）
- 前端设置抽屉接通 config（其余仍模拟）
- 验收：浏览器打开自动出应用；改设置 → 重启生效；config.yaml 被真实写入

### M1 生成链路（3-5 天）
- `POST /api/generate` 提交 ComfyUI 工作流；任务状态机 + 进度轮询 + 取消
- 单 Worker 队列；500/5000 阈值与断点续跑逻辑（沿用原型警告）
- 验收：真实生成 1 张全流程出三路文件；取消可中断；大批次触发断点续跑

### M2 数据层（2-3 天）
- 历史/图库读真实 `outputs/` 与 tasks.json；预设落盘 presets.json
- 验收：生成后历史立即出现真实记录；图库显示真实图片与正确比例；预设可增删改并回填

### M3 打磨（按需）
- 错误/重试/超时、队列真实态、性能（缩略图、懒加载）、安全复核（仅本机绑定）、可选 Electron/Tauri 桌面壳

---

## 9. 风险与注意点

1. **ComfyUI 工作流映射**：22 参数 → 工作流 JSON 需逐节点核对（LoRA id=16→21 等），建议先接 1 条最小链路再扩展
2. **单 Worker 串行 + OOM**：批量/超分大任务须遵守显存预留与 checkpoint 续跑；队列拒绝并发
3. **真实显存估算**：`big-est` 与 500/5000 警告的耗时/显存参数需用真实基准校准，不能沿用原型估算
4. **本机安全**：只绑 `127.0.0.1`，禁止 UI 改 `0.0.0.0`；内部工具不引入登录
5. **前端无构建**：静态单文件 + 同源 fetch，无需 CORS；如未来前后端分离需补 CORS 配置
6. **数据迁移**：原型样例数据不进入真实库；首个真实任务从 M1 开始记录

---

## 10. 待确认/待提供输入

- [ ] 后端骨架是否已有（或从 SeedVR2 直接复用 main.py 模式）
- [ ] 真实引擎工作流文件（`workflows/flux2_klein_9b_distilled.json` 等）与参数节点映射表
- [ ] `outputs/` 目录命名与归档约定（保留策略 90 天/100GB 的落盘实现）
- [ ] 任务/预设落盘格式（本文档第 6 节为建议，可调整）
- [ ] 资源扫描（LoRA/模型目录）的返回结构与展示粒度

---

*报告完毕。确认后从 M0 开始实施；M0 验收通过再进入 M1。*
