# 总体架构文档 (Architecture)

本文档描述 Image MultiModel 的系统架构、数据流、技术选型决策和工作流扩展指南。

---

## 目录

- [分层架构](#分层架构)
- [数据流](#数据流)
- [模块职责](#模块职责)
- [原型选型说明](#原型选型说明)
- [工作流扩展指南](#工作流扩展指南)
- [安全架构](#安全架构)
- [技术选型决策](#技术选型决策)

---

## 分层架构

从上到下分为 6 层，每层只依赖下层，不允许反向引用：

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户浏览器（Web UI）                           │
│  static/index.html — 单页应用（SPA）                             │
│  fetch() REST API + EventSource SSE + localStorage i18n/theme   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────────┐
│  FastAPI Routes 层 (routes/)                                     │
│  参数校验（Pydantic）→ 调用服务层 → 返回 JSON响应                │
│  ├─ generate_routes   POST /api/generate + /api/generate/batch  │
│  ├─ task_routes       GET/DELETE /api/tasks + cancel/redraw     │
│  ├─ engine_routes     GET/POST /api/engine (load/unload/free)   │
│  ├─ config_routes     GET/PUT /api/config + /api/config/loras   │
│  ├─ preset_routes     CRUD /api/presets + apply/import/export   │
│  ├─ output_routes     GET /api/outputs + download/fav            │
│  └─ system_routes     GET /api/health + /api/events(SSE) + /gpu │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 函数调用
┌──────────────────────────▼──────────────────────────────────────┐
│  Service 业务层                                                  │
│  ├─ task_queue.py     异步任务队列（单Worker串行 + 取消 + 恢复） │
│  ├─ history_db.py     SQLite 历史记录（WAL + FTS5 + 崩溃恢复）  │
│  ├─ model_manager.py  引擎生命周期管理（load/unload + 观察者）   │
│  ├─ gpu_utils.py      VRAM 预检 + 精度推荐 + chunk 计算          │
│  ├─ checkpoint.py     断点续跑（batch>100 每100张落盘）          │
│  ├─ watermark.py      DCT 频域水印嵌入/提取                      │
│  ├─ i18n.py           后端错误文案 5 语映射                      │
│  └─ sse.py            SSE 事件总线（订阅/发布/心跳）             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 接口调用
┌──────────────────────────▼──────────────────────────────────────┐
│  Comfy Engine 抽象层 (comfy/)                                    │
│  ImageEngine Protocol: is_ready / load / unload / infer / cancel│
│  ├─ engine.py         ComfyEngine（ImageEngine 实现）            │
│  ├─ client.py         HTTP + WebSocket 双通道客户端（自动重连）  │
│  ├─ workflow.py       WorkflowManager Patcher 6 步              │
│  └─ vram_scheduler.py VRAM 调度器（高低水位线 + 动态 batch）     │
│  Native Engine 抽象层 (native/)   ← 双后端模式的进程内引擎       │
│  ├─ engine.py         NativeEngine（ImageEngine 实现）           │
│  ├─ source.py         复用 references/ComfyUI 源码（sys.path）   │
│  ├─ executor.py       复用 comfy.sd / comfy.samplers 推理        │
│  └─ lora/seedvr/compares/vram/preview.py                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │      WebSocket / HTTP   │  直接调用（进程内）
┌──────────────────────────▼──────────────────────┐  │
│  ComfyUI Server（本地或远程，comfyui 后端）      │  │
│  接收工作流 JSON → 执行节点图 → GPU 推理 → 返回  │  │
└─────────────────────────────────────────────────┘  │
┌──────────────────────────▼──────────────────────┐  │
│  本地 Comfy 源码（native 后端，进程内 GPU 推理）  │◄─┘
│  references/ComfyUI + aki-v3 自定义节点源码      │
└─────────────────────────────────────────────────┘
                           │ CUDA
┌──────────────────────────▼──────────────────────────────────────┐
│  GPU 硬件层                                                      │
│  NVIDIA CUDA（PyTorch + ComfyUI 后端）                           │
└─────────────────────────────────────────────────────────────────┘
```

### 中间件层（横切关注点）

```
middleware/
├─ csrf.py           CSRF Token 校验（POST/PUT/DELETE）
├─ rate_limit.py     限流（全局/推理/上传三维度）
├─ request_id.py     请求 ID 注入（日志追踪）
└─ error_handler.py  全局错误处理 + JSON 错误响应
```

### 安全层（横切关注点）

```
security/
├─ path_guard.py            PathGuard 路径防护（14 类攻击拒绝）
├─ integrity_selfcheck.py   启动时 SHA256 完整性校验
└─ integrity_manifest.json  关键安全模块哈希清单
```

---

## 数据流

### 文生图完整流程

```
用户在 Web UI 输入 Prompt + 参数
         │
         ▼
[1] POST /api/generate  ──── generate_routes.py
         │                    ├─ Pydantic 校验请求体
         │                    ├─ 验证引擎存在
         │                    ├─ 验证 batch_size (1~9999)
         │                    ├─ preflight_vram() 显存预检
         │                    ├─ 构建 GenerationConfig (22项)
         │                    ├─ HistoryDB.create_task() 写历史
         │                    └─ TaskQueue.submit() 入队
         │                         └─ 返回 {task_id, estimated_time_s}
         │
[2] TaskQueue Worker 取任务 ──── task_queue.py (后台线程)
         │                    ├─ 创建 ComfyEngine 实例
         │                    ├─ engine.load(on_progress) 加载模型
         │                    └─ engine.infer_txt2img(gen_config)
         │
[3] ComfyEngine 执行推理 ──── comfy/engine.py
         │                    ├─ WorkflowManager.patch() 6步参数注入
         │                    │    ├─ ① 深拷贝工作流 JSON
         │                    │    ├─ ② 模式切换（LoRA/SeedVR2/Eses/VRAM）
         │                    │    ├─ ③ link 重连（关闭功能时改直通）
         │                    │    ├─ ④ widgets 精确 patch（22参数）
         │                    │    ├─ ⑤ batch chunk 拆分（16/4）
         │                    │    └─ ⑥ 节点校验
         │                    ├─ ComfyClient.queue_prompt() 提交
         │                    ├─ WS 监听进度（progress/executing/executed）
         │                    ├─ WS b_preview → base64 实时预览
         │                    └─ 轮询 /history 获取结果
         │
[4] 结果处理 ──────────────── app_server.py worker_func
         │                    ├─ Watermark.embed() 嵌入DCT水印
         │                    ├─ 生成缩略图 (max 512px)
         │                    ├─ HistoryDB.add_output() 写记录
         │                    ├─ HistoryDB.update_task_status("completed")
         │                    └─ Checkpoint.delete() 清理断点（批量时）
         │
[5] SSE 实时推送 ──────────── sse.py
         │                    ├─ task_status: 进度百分比 + 阶段
         │                    ├─ comfy_preview: base64 采样预览
         │                    ├─ gpu_status: VRAM 使用情况 (2s)
         │                    ├─ model_status: 引擎加载状态
         │                    └─ queue_status: 队列深度
         │
         ▼
用户浏览器通过 EventSource 实时渲染进度条 / 预览图 / GPU状态
```

### 批量生成流程

```
用户在批量抽屉输入 prompts.txt × Grid 6维
         │
         ▼
POST /api/generate/batch
         │
    笛卡尔积展开 (prompts × grid_combos)
         │
    逐个提交到 TaskQueue (每个 = 独立 task_id)
         │
    每 100 张完成 → Checkpoint.save() 落盘
         │
    ┌─── 正常完成 → Checkpoint.delete()
    │
    └─── 崩溃 → 重启时扫描 checkpoint
              → 恢复未完成 task (减少 batch_size = remaining)
              → 续跑剩余槽位，无重复输出
```

---

## 原生进程内引擎（双后端模式）

自 v1.2.0 起，平台支持双后端：`comfyui`（默认，需外部 ComfyUI 进程）与 `native`（进程内复用本地 Comfy 源码）。`routes/engine_routes.py` 按引擎配置的 `backend` 字段分发到 `ComfyEngine` 或 `NativeEngine`。

### native/ 包模块职责

| 模块 | 职责 |
|------|------|
| `native/source.py` | **Comfy 源码装载**：把 `references/ComfyUI`（含 `comfy/`、`comfy_extras/`、`comfy_execution/`、`nodes.py` 等兄弟顶层包）整体注入 `sys.path[0]`，保证 `import comfy` 命中本地复用源码而非外部安装的 ComfyUI 包；`ensure_loaded()` 幂等，仅装载一次 |
| `native/executor.py` | **推理执行器**：复用 `comfy.sd`（`load_diffusion_model` / `load_clip` / `VAE`）、`comfy.samplers`（`calculate_sigmas` / `sampler_object` / `sample`）完成 加载→CLIP 编码→采样→VAE 解码 全链路；同步阻塞，供 async 层包在 executor 线程 |
| `native/engine.py` | **NativeEngine**：实现 `ImageEngine` Protocol（`is_ready / load / unload / infer_txt2img / cancel`）；`load()` 解析模型路径 + 调用 `source.ensure_loaded()`，`infer_txt2img()` 在线程池运行 `executor.txt2img`，结果经 `_save_outputs()` 落盘 + DCT 水印 + 缩略图 |
| `native/lora.py` / `seedvr.py` / `compares.py` / `vram.py` / `preview.py` | 原生引擎的 LoRA / SeedVR2 超分 / 双图对比 / 显存预留 / 实时预览等能力（Phase 3） |

### 如何复用 Comfy 源码（sys.path 注入）

```
native/source.py
  ensure_loaded(comfy_root=None)
    ├─ comfy_root 默认 = <项目根>/references/ComfyUI
    ├─ 校验 dir/comfy 存在
    ├─ sys.path.insert(0, comfy_root)          # 命中 comfy/comfy_extras/... 顶层包
    ├─ [可选] custom_nodes_dir 注入 custom_nodes/
    └─ import comfy                            # 验证可导入
```

> ⚠️ `comfy_source_dir` 为相对路径时，需基于项目根拼成**绝对路径**后再装载（见 AGENTS.md Known Gotchas）。

### executor 调用 comfy 关键流程

```
executor.txt2img(config, model_paths, on_progress, cancel_flag)
  ├─ source.ensure_loaded(comfy_root)
  ├─ comfy.sd.load_diffusion_model(unet_path)     # 自动检测 Z-Image/Lumina2 架构
  ├─ comfy.sd.load_clip([te_path])                # qwen_image 类型自动检测
  ├─ comfy.sd.VAE(sd=...)                         # 加载 VAE
  ├─ clip.tokenize + encode_from_tokens_scheduled # CLIP 编码
  ├─ comfy.samplers.calculate_sigmas(model_sampling, sgm_uniform, steps)
  ├─ comfy.samplers.sampler_object(dpmpp_3m_sde_gpu)
  ├─ comfy.samplers.sample(...)                   # 采样 + 进度/取消回调
  └─ vae.decode(→RGB 张量)                        # VAE 解码出图
```

### 双模式注册与前端切换

- **注册**：`model_registry.py` 扫描 `config.yaml → models.engines.*`，按 `backend` 字段实例化 `ComfyEngine` 或 `NativeEngine`（`z_image_turbo_native` 即 `backend: native` 示例）。
- **路由分发**：`routes/engine_routes.py` 的 load/unload/infer 统一走 `ImageEngine` Protocol，对上层透明。
- **前端切换**：`static/index.html` 引擎菜单顶部提供「全部 / ComfyUI / 原生」过滤，按 `backend` 展示引擎列表。

---

## 模块职责

| 模块 | 文件 | 职责 | 依赖 |
|------|------|------|------|
| **应用入口** | `app_server.py` | FastAPI create_app + lifespan + 路由自动发现 + 静态托管 | 全部 |
| **配置** | `config.py` / `config_models.py` | YAML 加载 + Pydantic 校验 + 双模式路径解析 | 无 |
| **引擎接口** | `engine_interface.py` | ImageEngine Protocol + Registry + GenerationConfig (22项) | config |
| **ComfyUI 客户端** | `comfy/client.py` | HTTP + WS 双通道 + 自动重连 (≤3次指数退避) | config |
| **ComfyUI 引擎** | `comfy/engine.py` | ComfyEngine 实现 (load/unload/infer/cancel) | client, workflow |
| **工作流管理** | `comfy/workflow.py` | Patcher 6步 + Schema YAML 加载 + 节点校验 | config |
| **VRAM 调度** | `comfy/vram_scheduler.py` | 高低水位线 + 动态 batch 调整 | gpu_utils |
| **原生引擎（进程内）** | `native/engine.py` | NativeEngine 实现，进程内复用 Comfy 源码推理 | native/source, native/executor |
| **Comfy 源码装载** | `native/source.py` | 把 `references/ComfyUI` + aki-v3 自定义节点注入 sys.path | — |
| **原生执行器** | `native/executor.py` | 复用 comfy.sd / comfy.samplers 完成出图链路 | source, torch |
| **任务队列** | `task_queue.py` | 异步单Worker串行 + 取消回调 + 超时 + 恢复 | engine_interface |
| **历史数据库** | `history_db.py` | SQLite WAL+FTS5 + tasks/outputs/presets + 崩溃恢复 | config |
| **模型管理** | `model_manager.py` / `model_registry.py` | 引擎生命周期 + 观察者模式 → SSE | engine_interface |
| **GPU 工具** | `gpu_utils.py` | VRAM 预检 (×1.5系数) + FP8 回退 + chunk 推荐 | torch |
| **断点续跑** | `checkpoint.py` | batch>100 每100张 checkpoint + 恢复 | config |
| **SSE 总线** | `sse.py` | 订阅/发布模式 + 心跳 (30s) + 5类事件 | asyncio |
| **水印** | `watermark.py` | DCT 频域嵌入 (product_id+task_id+timestamp) | numpy |
| **i18n** | `i18n.py` + `locales/*.json` | 5语映射 + 后端错误文案 | config |
| **PathGuard** | `security/path_guard.py` | 路径规范化 + 14类攻击拒绝 | config |
| **完整性校验** | `security/integrity_selfcheck.py` | 启动时 SHA256 校验安全模块 | manifest |

---

## 原型选型说明

在开发 Web UI 之前，我们使用 Figma 设计了 **8 种布局方案**进行 A/B 对比，最终选定了 **d-drawer（抽屉式）** 布局。

### 8 种布局方案对比

| 方案 | 名称 | 布局特点 | 优点 | 缺点 | 评分 |
|------|------|----------|------|------|------|
| a | creative | 全屏画布 + 浮动工具栏 | 视觉冲击力强 | 工具栏遮挡内容 | ★★★☆ |
| b | split | 左右 55/45 分屏 | 参数和结果同屏 | 移动端无法使用 | ★★★☆ |
| c | collapsible | 可折叠侧边栏 | 灵活切换 | 折叠动画卡顿 | ★★★☆ |
| **d** | **drawer** | **主画布 + 四方位抽屉** | **移动端好/路径短/空间利用率高** | **抽屉互斥需管理** | **★★★★★** |
| e | wizard | 步骤向导式 | 引导性强 | 步骤繁琐 | ★★☆☆ |
| f | pipeline | 管道流式 | 可视化流程 | 占用垂直空间 | ★★★☆ |
| g | master-detail | 主从详情 | 适合列表场景 | 生成场景不适用 | ★★☆☆ |
| h | minimal | 极简模式 | 干净 | 功能隐藏太深 | ★★★☆ |

### 选择 d-drawer 的理由

1. **移动端适配好**：抽屉在小屏幕上自动变为全屏覆盖，桌面端保持侧边滑出。8 种方案中只有 d 和 h 在移动端可用，d 的功能可见性更好。

2. **用户操作路径短**：主画布始终可见，用户不需要切换页面就能访问所有功能（高级参数 / 历史 / 图库 / 批量 / 预设都在抽屉中）。

3. **空间利用率高**：抽屉互斥设计（同一时间只开一个）避免了界面拥挤。四方位分配：
   - 右抽屉：高级参数（22项手风琴）+ 预设管理
   - 左抽屉：历史记录（筛选表格 + 详情）
   - 顶抽屉：图片展示（masonry）+ 设置 + 关于 + 系统状态
   - 底抽屉：批量模式（Prompt文件 + 参数网格 + 队列）

4. **视觉层次清晰**：主画布是核心（生成 + 结果），抽屉是辅助（参数/历史/管理），悬浮层是增强（图片查看器/队列面板）。

5. **与 ComfyUI 工作流模式匹配**：生成是核心动作（主画布），参数调整是辅助（抽屉），符合「写 Prompt → 调参数 → 生成 → 看结果」的自然流程。

### 原型文件位置

```
prototypes/
├─ figma-refactor/
│   ├─ layout-compare/          # 8 种布局对比
│   │   ├─ a-creative.html
│   │   ├─ b-split.html
│   │   ├─ c-collapsible.html
│   │   ├─ d-drawer.html         # ★ 最终选定
│   │   ├─ e-wizard.html
│   │   ├─ f-pipeline.html
│   │   ├─ g-master-detail.html
│   │   └─ h-minimal.html
│   ├─ batch.html               # 各页面独立原型
│   ├─ gallery.html
│   ├─ generate.html             # ★ 最终前端（复制为 static/index.html）
│   ├─ history.html
│   ├─ presets.html
│   └─ ia-map.html               # 信息架构地图
└─ style-compare/                # Figma 风格还原对比
```

---

## 工作流扩展指南

### 新增一个工作流的步骤

1. **准备 ComfyUI 工作流 JSON**

   在 ComfyUI 中导出工作流（API 格式），放入 `workflows/` 目录：

   ```bash
   workflows/
   ├─ Flux.2_Klein-9B-Distilled.json    # 已有
   ├─ Z_image_turbo.json                 # 已有
   └─ your_new_workflow.json             # 新增
   ```

2. **创建 Schema YAML**

   在 `bin/integrated_app/comfy/schemas/` 下创建参数映射文件。Schema 定义工作流 JSON 中 `widgets_values` 的下标与 `GenerationConfig` 参数的对应关系：

   ```yaml
   # bin/integrated_app/comfy/schemas/your_new_workflow.yaml
   workflow_file: workflows/your_new_workflow.json
   node_mappings:
     # 基础参数
     positive_prompt:
       node_id: "6"          # ComfyUI 中的节点 ID
       widget_index: 0        # widgets_values 数组下标
     negative_prompt:
       node_id: "7"
       widget_index: 0
     width:
       node_id: "5"
       widget_index: 3
       sync_node_id: "9"      # 需要同步的另一个节点
     height:
       node_id: "5"
       widget_index: 2
       sync_node_id: "9"
     cfg:
       node_id: "3"
       widget_index: 2
     steps:
       node_id: "3"
       widget_index: 0
     seed:
       node_id: "3"
       widget_index: 1
       control_after_generate: true   # 有 control_after_generate 下拉
     batch_size:
       node_id: "5"
       widget_index: 4
     # LoRA 6 层
     lora_1_name:
       node_id: "16"
       widget_index: 0
       mode_widget_index: 1           # mode 下拉需在提交前改为 0
     lora_1_strength:
       node_id: "16"
       widget_index: 2
     # ... 以此类推
   ```

3. **在 config.yaml 中注册引擎**

   ```yaml
   models:
     engines:
       your_new_engine:
         name: your_new_engine
         display_name: "Your New Engine"
         display_name_en: "Your New Engine"
         backend: comfyui
         comfy_backend_preference: local
         workflow_file: workflows/your_new_workflow.json
         parameter_schema: bin/integrated_app/comfy/schemas/your_new_workflow.yaml
         text_encoder:
           sub_dir: text
           sub_path: your_model/text_encoder.safetensors
         unet:
           sub_dir: unet
           sub_path: your_model/unet.safetensors
         vae:
           sub_dir: vae
           sub_path: your_model/vae.safetensors
         vram_gb: 12.0
         ram_gb: 24.0
         default_precision: fp8
         fallback_precision: fp8
         supported_features:
           - txt2img
           - lora_stack_6
         default_width: 1024
         default_height: 1024
         image_formats:
           - png
         license: "Your License"
         tags:
           - your_tag
   ```

4. **验证 Schema 映射正确性**

   编写快照测试，验证参数注入后的工作流 JSON 与预期一致：

   ```python
   # tests/test_your_workflow.py
   def test_your_workflow_patch_snapshot():
       manager = WorkflowManager("your_new_engine")
       config = GenerationConfig(
           positive_prompt="test",
           width=1024,
           height=1024,
           steps=8,
           cfg=1.0,
           seed=42,
           batch_size=1,
           lora_1_name="test_lora.safetensors",
           lora_1_strength=0.8,
       )
       patched = manager.patch(config)
       # 验证关键节点的 widgets_values 已正确注入
       assert patched["6"]["widgets_values"][0] == "test"
       assert patched["5"]["widgets_values"][3] == 1024
   ```

5. **重启应用，引擎自动出现在列表中**

   ```bash
   curl http://127.0.0.1:8288/api/engine/engines
   # 返回的 engines 数组中应包含 your_new_engine
   ```

### Schema YAML 编写要点

- **node_id** 必须与 ComfyUI 导出的 JSON 中的节点 ID 严格一致（字符串类型）
- **widget_index** 是 `widgets_values` 数组的下标，从 0 开始
- **mode_widget_index** 用于 LoRA 节点：ComfyUI 中 mode=4 是「随机权重」模式，提交前必须改为 0
- **sync_node_id** 用于需要同步的节点（如 EmptyLatentImage 的 width/height 需要同步到两个节点）
- **control_after_generate** 为 true 时，seed 节点后面会多一个 `control_after_generate` 下拉，需要跳过
- **batch_chunk_size** 工作流支持的最大单次 batch（默认 16，开超分时 4）

---

## 安全架构

```
                    ┌─────────────────┐
                    │   HTTP 请求      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  CORS 中间件     │ ← 允许的源白名单
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  CSRF 中间件     │ ← POST/PUT/DELETE 需 X-CSRF-Token
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  RequestID      │ ← 注入 X-Request-ID
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  RateLimit      │ ← 全局600/min + 推理30/min + 上传10/min
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  路由处理        │
                    │  ├─ Pydantic校验 │ ← 请求体类型校验
                    │  ├─ PathGuard    │ ← 文件路径规范化（防 ../ 穿越）
                    │  └─ 业务逻辑     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  SQLite 参数化   │ ← 防 SQL 注入
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  输出图片        │
                    │  └─ DCT 水印     │ ← product_id+task_id+timestamp 溯源
                    └─────────────────┘

启动时自检：
  integrity_selfcheck → SHA256 校验安全模块哈希
  history_db.recover_stuck_tasks → 清理卡死任务
```

### 安全配置项

| 配置 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| 网络绑定 | `server.host` | `127.0.0.1` | 仅本机访问 |
| CORS | `security.cors.allowed_origins` | 本机端口 | 白名单 |
| RateLimit | `security.rate_limit` | 600/30/10 | 三维度限流 |
| Basic Auth | `security.basic_auth.enabled` | `false` | 可选开关 |
| API Token | `security.api_token.enabled` | `false` | 可选开关 |
| 模型格式 | `security.model_format.only_safetensors` | `true` | 拒绝 pickle |
| 完整性校验 | `security.integrity_selfcheck.enabled` | `true` | 启动时检查 |
| 路径防护 | `security.allowed_base_dirs` | 4 个目录 | 限制文件操作范围 |

---

## 技术选型决策

### 为什么用 aiohttp 而不是 httpx？

**决策**：保留 `aiohttp`（PRD 原写 `httpx + aiosqlite`，实际用 `aiohttp + sqlite3`）

**理由**：
1. aiohttp 与 ComfyUI WebSocket 生态兼容（ComfyUI 官方示例使用 aiohttp）
2. aiohttp 的 WebSocket 客户端更成熟（`aiohttp.ClientWebSocketResponse`）
3. sqlite3 同步已够用（单 Worker 串行，无高并发写压力）
4. 参考项目 Seedvr2 / TTS_MultiModel 已验证可行

### 为什么用 SQLite 而不是 PostgreSQL？

**决策**：SQLite + WAL + FTS5

**理由**：
1. 单机部署场景，无需多节点共享数据库
2. SQLite WAL 模式支持并发读 + 单写，性能足够
3. FTS5 全文检索支持 Prompt 搜索
4. 崩溃恢复简单（单文件 .backup 即可）
5. 无需额外数据库进程，降低部署复杂度

### 为什么用单 Worker 串行而不是并行？

**决策**：TaskQueue 单 Worker 串行执行

**理由**：
1. ComfyUI 是单 GPU 串行推理，并行提交只会增加队列等待
2. 避免显存竞争（多任务并行可能 OOM）
3. 取消逻辑简单（只需中断当前任务）
4. batch=9999 通过 chunk 拆分（每次 16 张）实现吞吐，不需要并行

### 为什么前端用单页静态 HTML 而不是 React/Vue？

**决策**：单页融合版（纯静态 HTML + 原生 JS + fetch + EventSource）

**理由**：
1. 无构建步骤，降低维护成本
2. 前端只有 1 个页面（生成工作台），不需要路由库
3. FastAPI 直接托管静态文件，无需 Node.js
4. 原型设计阶段已用 HTML 完成，直接复用
5. 加载快（28.7KB gzip），WCAG AA 无障碍好做
