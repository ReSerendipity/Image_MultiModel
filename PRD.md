# Image MultiModel — 产品需求文档 (PRD)

> **文档版本**: v1.3.0  
> **创建日期**: 2026-08-08  
> **最近更新**: 2026-08-08 （边界对齐工作流节点存在性：LoRA 6 层叠加 + SeedVR2 超分 + EsesImageCompare 双图对比 + ReservedVRAMSetter 显存预留 加回 M2 必做；img2img/ControlNet 因工作流 JSON 完全无对应节点明确不做；参数与节点映射严格对齐 workflows/*.json 的 `nodes[].widgets_values` 下标）  
> **文档状态**: 正式草稿（**节点级范围锁定**）  
> **项目代号**: Image_MultiModel  
> **目标平台**: Windows 10/11 (优先) / Linux (兼容)

---

## 目录

1. [产品概述](#1-产品概述)
2. [核心功能需求](#2-核心功能需求)
3. [用户界面设计规范](#3-用户界面设计规范)
4. [ComfyUI 模型集成方案](#4-comfyui-模型集成方案)
5. [系统架构](#5-系统架构)
6. [数据流程](#6-数据流程)
7. [性能指标](#7-性能指标)
8. [安全要求](#8-安全要求)
9. [兼容性标准](#9-兼容性标准)
10. [部署模式与便携包发布](#10-部署模式与便携包发布)
11. [开发与测试里程碑](#11-开发与测试里程碑)
12. [验收标准](#12-验收标准)
13. [附录 A：与参考项目代码复用映射表](#附录-a与参考项目代码复用映射表)
14. [附录 B：参考项目关键文件索引](#附录-b参考项目关键文件索引)

---

## 1. 产品概述

### 1.1 产品定位

**Image MultiModel** 是一款基于 **ComfyUI 生态** 的 **Z-Image Turbo 图像生成平台**，通过统一的 Web 用户界面 (WebUI) 驱动唯一引擎 Z-Image Turbo 完成文生图。用户无需在复杂的 ComfyUI 工作流、配置文件、命令行之间切换，即可在一个统一界面中完成：

- 模型选择与加载
- 参数调节与预设管理
- **文生图 (txt2img)** 推理（核心推理形态）
- **LoRA 叠加**（最多 6 条串联，从 UNet 输出到 CFGGuider 输入）
- **SeedVR2 超分辨率放大**（ema_vae_fp16 + seedvr2_ema_3b_fp16 DiT）
- **EsesImageCompare 双图并排对比**（SeedVR2 超分图 vs 直通原图）
- **ReservedVRAMSetter 显存预留**（防 ComfyUI OOM 的硬件级调度）
- 历史记录与素材库管理
- 批量任务与进度跟踪（支持批次 1 ~ 9999）

**产品愿景**: 成为面向创作者与设计师的"一站式 AI 图像工作台"，用一致的交互体验屏蔽底层 ComfyUI 工作流的复杂度差异。

> **边界判定规则（v1.3 起生效，与用户达成一致）**：
> 功能范围 **严格以 `workflows/*.json` 中节点是否存在为唯一标准**：
> 1. ✅ 工作流 JSON 中**存在对应类型节点**（无论 `mode=0` 启用还是 `mode=4` bypassed）→ 必须实现（`mode=4` 的节点实现时改为 `mode=0` 启用）
> 2. ❌ 工作流 JSON 中**完全无对应类型节点** → 一律不实现，不做 M3 规划占位
>
> 按此规则对该工作流的逐项判定结果（详见 2.4.4 节点映射总表）：
> - ✅ **必做 4 类新功能**：LoRA 叠加、SeedVR2 超分、Eses 双图对比、ReservedVRAM 显存预留
> - ❌ **明确不做**：图生图 img2img（无 LoadImage/VAEEncodeForInpaint 节点）、ControlNet（无 ApplyControlNet + 预处理节点）、普通 ImageScaleToTotalPixels 缩放预览（mode=4 + 非 SeedVR2 路径）

### 1.6 功能边界判定总表（v1.3 起生效）

| 功能类别 | 对应节点类型（搜索 JSON 关键词） | Z-Image Turbo | 判定 |
|---------|------------------------------|:------------:|:----:|
| txt2img 文生图 | CLIPTextEncode + EmptyLatentImage + Sampler | ✅ | **必做** |
| **LoRA 叠加（最多 6 层）** | LoraLoaderModelOnly（6 个串联） | ✅（id=16~21，mode=4 → 改 0） | **必做** |
| **SeedVR2 超分** | SeedVR2LoadVAEModel + SeedVR2LoadDiTModel + SeedVR2VideoUpscaler（3 节点，mode=0 连线完整） | ✅（id=79/80/81） | **必做** |
| **Eses 双图并排对比** | EsesImageCompare（compare_axis=horizontal，输出对比图） | ✅（id=77） | **必做**（UI 可选开启/关闭） |
| **ReservedVRAMSetter 显存预留** | ReservedVRAMSetter（reserved + mode + seed(randomize)） | ✅（id=78） | **必做**（UI 可选开启/关闭 + 参数高级设置） |
| 普通缩放预览 | ImageScaleToTotalPixels + PreviewImage | ❌（mode=4 且连线空） | **不做**（SeedVR2 是启用的超分路径，覆盖此需求） |
| 图生图 img2img / Inpaint | LoadImage + VAEEncodeForInpaint + SetLatentNoiseMask + denoise < 1 | ❌（完全无，KSampler denoise=1 恒为 txt2img） | **不做**（且不规划 M3） |
| ControlNet 条件控制 | ApplyControlNet / ControlNetLoader / AIO Preprocessors | ❌（完全无） | **不做**（且不规划 M3） |

### 1.2 设计哲学（源自参考项目）

本产品直接继承并融合 [Seedvr2](file:///C:/Users/Doro/Seedvr2/README.md) 与 [TTS_MultiModel](file:///C:/Users/Doro/TTS_MultiModel/README.md) 两大参考项目的工程模式：

| 维度 | 参考来源 | 具体做法 |
|------|---------|---------|
| **Web 技术栈** | 两项目一致 | FastAPI + Jinja2 + HTMX，零前端构建工具链 |
| **引擎抽象层** | TTS_MultiModel | `EngineRegistry` + Protocol 鸭子类型，声明式引擎注册 |
| **模型生命周期管理** | Seedvr2 + TTS | `ModelManager` + 单例 `ModelRegistry`，观察者 + SSE 桥接 |
| **任务队列** | Seedvr2 | 单 Worker 串行队列，任务级取消回调，worker 异常自动重启 |
| **中间件体系** | TTS_MultiModel | CSRF / RateLimit / RequestID / API Auth / 错误处理 |
| **深浅主题 + i18n** | Seedvr2 | CSS 变量驱动主题，YAML/JSON 多语言文件 |
| **GPU 显存预检** | 两项目 | 加载前 1.5× 峰值规则，FP16→FP8 自动回退 |
| **完整性与水印** | Seedvr2 | 模块启动自检，输出数字水印溯源 |

### 1.3 与参考项目的核心差异

| 特性 | Seedvr2 | TTS_MultiModel | **Image MultiModel (本项目)** |
|------|---------|---------------|-------------------------------|
| **推理后端** | 自定义 PyTorch 管线 (DiT + VAE) | 自定义 PyTorch 管线 (VoxCPM2 / IndexTTS2) | **进程内原生引擎（复用 comfy_kernel 源码）** |
| **引擎粒度** | 单引擎 × 多尺寸 (3B/7B) | 多引擎 × 单尺寸 | 单一 Z-Image Turbo 引擎 |
| **参数模式** | 配置字典 + 表单字段 | 生成器进度 yield + 表单 | **工作流 JSON + 参数映射 Schema（严格对齐 nodes/widgets_values）** |
| **GPU 占用** | 独占，Block Swap 换入换出 | 热待机 (双引擎共存) | **进程内原生引擎，单 Worker 串行队列** |
| **资源文件** | 模型 .safetensors | 模型 + Persona .pt/.wav | **工作流 .json + text_encoder + UNet + VAE + LoRA（最多 6 层串联） + SeedVR2 DiT/VAE 超分模型** |

### 1.4 目标用户画像

1. **独立创作者 / 设计师**: 需要快速产出高质量图像，希望屏蔽 ComfyUI 的节点复杂度
2. **AI 内容工作室**: 批量出图，需要素材库与版本管理
3. **技术研究者**: 希望复现与对比不同参数效果，保留完整参数可复现链路

### 1.5 非目标 (Non-Goals)

- **不做** ComfyUI 本身的节点编辑器 — 只消费和驱动 `workflows/*.json` 已存在的节点
- **不做** 多用户 SaaS 平台 — 单用户桌面端，默认绑定 127.0.0.1
- **不做** 移动端适配 — 以桌面 1080p+ 浏览器为主要使用场景
- **明确不做（工作流无节点）**：图生图 img2img / Inpaint、ControlNet 全链路（参考图上传 + 预处理 + ApplyControlNet）、普通 lanczos 缩放预览（ImageScaleToTotalPixels + PreviewImage，mode=4 且链路断开）

---

## 2. 核心功能需求

### 2.1 功能模块总览

```
Image MultiModel
├── 2.2 原生引擎连接管理
├── 2.3 引擎(模型)注册与管理
├── 2.4 文生图 (txt2img) 推理工作台（含 LoRA / SeedVR2 超分 / Eses 对比 / ReservedVRAM 显存预留 4 大子卡）
├── 2.5 预设与参数管理
├── 2.6 LoRA 资源管理（必做，工作流含 6 条 LoraLoaderModelOnly 链路）
├── 2.7 批量推理（批次 1 ~ 9999）
├── 2.8 历史记录与素材库
├── 2.9 实时进度与 SSE
├── 2.10 系统状态监控
└── 2.11 设置与偏好（5 种语言 i18n）
```

### 2.2 引擎连接管理

#### FR-2.2.1 引擎注册
- 项目仅保留唯一引擎 `z_image_turbo_native`，`backend: native`，引擎元数据在 `config.yaml → models.engines` 中声明
- 引擎注册信息：`name` / `display_name` / `workflow_file` / `parameter_schema`
- 启动时由 `ModelRegistry` 自动扫描 config.yaml 注册

#### FR-2.2.2 引擎健康检测
- 后台每 30s 心跳轮询引擎状态
- 引擎离线标记，任务提交时自动跳过离线引擎
- 单引擎队列长度检测

#### FR-2.2.3 引擎加载（进程内原生）
- 引擎复用本机 `comfy_kernel` 源码，通过 `source.ensure_loaded()` 注入 `sys.path`
- 启动参数可配置：`unet` / `text_encoder` / `vae` / `default_precision`
- 应用退出时优雅释放 GPU 显存

### 2.3 引擎(模型)注册与管理

参照 [TTS_MultiModel engine_interface.py](file:///C:/Users/Doro/TTS_MultiModel/bin/integrated_app/engine_interface.py) 的注册机制。

#### FR-2.3.1 声明式引擎注册 (config.yaml)
在 `config.yaml → models.engines` 中声明生图引擎（以下示例即当前项目实际落地的唯一引擎 `z_image_turbo_native`，ID 名与 config.yaml 完全一致）：

```yaml
models:
  engines:
    z_image_turbo_native:
      name: "z_image_turbo_native"
      display_name: "Z-Image Turbo"
      backend: "native"                       # 进程内原生引擎（复用 comfy_kernel 源码）
      workflow_file: "workflows/Z_image_turbo.json"
      parameter_schema: "schemas/z_image_turbo_native.yaml"
      vram_gb: 10.0
      ram_gb: 20.0
      default_precision: "fp8"
      model_source_mode: "portable"
      supported_features: ["txt2img", "lora_stack_6", "seedvr2_upscale_2x", "eses_compare", "reserved_vram"]
      image_formats: ["png"]
      license: "Z-Image Turbo"
```

#### FR-2.3.2 引擎发现与懒加载
- `InMemoryEngineRegistry` 单例，支持立即注册与懒导入
- 引擎元数据（名称、显存、特性）与实际工作流加载解耦，UI 列表无需加载模型
- 首次切换引擎时：验证工作流存在性 → 检查后端连接 → 校验模型文件存在性

#### FR-2.3.3 引擎切换与回滚
参照 [Seedvr2 model_manager.py](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/model_manager.py) `switch_model()` 的回滚语义：
- 切换前快照当前引擎状态
- 切换失败 → 尝试回滚到前一引擎
- 回滚也失败 → 进入"无引擎"状态，不崩溃

### 2.4 文生图 (txt2img) 推理工作台（含 4 大扩展：LoRA 叠加 / SeedVR2 超分 / Eses 双图对比 / ReservedVRAM 显存预留）

> **功能严格对齐工作流节点存在性（v1.3 边界规则）**。唯一工作流来源：
> - [Z_image_turbo.json](file:///C:/Users/Doro/Image_MultiModel/workflows/Z_image_turbo.json)
>
> 工作流的子图 (Subgraph) 暴露 inputs=6 项（正/负 Prompt + cfg + steps + width + height），但子图**内部节点**还提供了更多可 Patch 的功能（子图未暴露的 widgets_values 字段，如 seed、batch_size、LoRA 6 层、SeedVR2、Eses、ReservedVRAM），因此完整 UI 参数共 **22 项**，按 6 组手风琴卡片组织。
>
> 实现时对 `mode=4 bypassed` 的节点（LoRA 6 条）**必须在 Patch 前将 nodes[].mode 改为 0 再提交**，否则节点被跳过 LoRA 不生效。

#### FR-2.4.1 Prompt 输入区
- 正向 Prompt 多行文本框（`positive_prompt`）：支持 5 种语言文本直接输入（简中 / 繁中 / 英 / 日 / 韩），无需翻译前置处理
- 负向 Prompt 多行文本框（`negative_prompt`）：Z-Image Turbo 支持，默认可为空
- 行号显示 + 字符计数（用于提示截断风险；实际文本编码由 ComfyUI CLIP 节点处理）

#### FR-2.4.2 参数面板（手风琴分组 6 组：基础参数 / LoRA 叠加 / SeedVR2 超分 / 对比与显存设置 / 输出设置）

| 分组 | 参数键 | 控件类型 | 默认值 (Z-Image Turbo) | 取值范围 / 约束 | 对应 ComfyUI 节点 |
|------|--------|---------|----------------------|----------------|-------------------|
| **① 基础参数** | `positive_prompt` | textarea | "" | 任意语言文本 | 子图 inputs → CLIPTextEncode `id=4/6` widgets_values[0] |
| ① 基础参数 | `negative_prompt` | textarea | "" | 文本 | 子图 inputs → CLIPTextEncode `id=15/5` widgets_values[0] |
| ① 基础参数 | `cfg` | 浮点数字框 | **1.0**（Z-Image Turbo 蒸馏官方推荐） | [1.0, 20.0]，步长 0.1 | 子图 inputs → CFGGuider / KSampler cfg |
| ① 基础参数 | `steps` | 整数框 | **8** | [1, 50] | 子图 inputs → Flux2Scheduler / KSampler steps |
| ① 基础参数 | `width` | 整数框 ±16 步进 | 1024 | 必须 16 倍数；[256, 2048] | 子图 inputs → EmptyLatentImage id=10/4 width |
| ① 基础参数 | `height` | 整数框 ±16 步进 | 1024 | 同上 | 子图 inputs → EmptyLatentImage id=10/4 height |
| ① 基础参数 | `seed` | 整数框 + 🎲随机 + ♻️复用 | **-1**（= 随机生成） | -1 或 [0, 2^53-1] | RandomNoise `id=6` noise_seed + randomize_control（二字段联合） / KSampler seed |
| ① 基础参数 | **`batch_size`** | 整数框 ±1/±10/±100 步进 | 1 | **[1, 9999]**（用户要求）；内部 chunk≤16 | EmptyLatentImage id=10/4 widgets_values[2] batch_size |
| **② LoRA 叠加（6 条串联，最多 6 层权重叠加）** | `lora_1_name` | 下拉（LoRA 文件列表） | `.safetensors`（默认） | `pretrained_models/loras/` 目录扫描 | LoraLoaderModelOnly `id=16` w_values[0]（同时将 node.mode 4→0） |
| ② LoRA 叠加 | `lora_1_strength` | 浮点滑块 | 1.0 | [-2.0, +2.0]，步长 0.05 | LoraLoaderModelOnly `id=16` w_values[1] strength_model |
| ② LoRA 叠加 | `lora_2_name` | 下拉 | `人像风格LoRA.safetensors` | 同目录 | LoraLoaderModelOnly `id=17` w_values[0] |
| ② LoRA 叠加 | `lora_2_strength` | 浮点滑块 | 0.7 | [-2, +2] | LoraLoaderModelOnly `id=17` w_values[1] |
| ② LoRA 叠加 | `lora_3_name` | 下拉 | `人像风格LoRA.safetensors` | 同上 | LoraLoaderModelOnly `id=18` w_values[0] |
| ② LoRA 叠加 | `lora_3_strength` | 浮点滑块 | 0.5 | [-2, +2] | LoraLoaderModelOnly `id=18` w_values[1] |
| ② LoRA 叠加 | `lora_4_name` | 下拉 | `人像风格LoRA.safetensors` | 同上 | LoraLoaderModelOnly `id=19` w_values[0] |
| ② LoRA 叠加 | `lora_4_strength` | 浮点滑块 | 0.4 | [-2, +2] | LoraLoaderModelOnly `id=19` w_values[1] |
| ② LoRA 叠加 | `lora_5_name` | 下拉 | `人像风格LoRA.safetensors` | 同上 | LoraLoaderModelOnly `id=20` w_values[0] |
| ② LoRA 叠加 | `lora_5_strength` | 浮点滑块 | 0.3 | [-2, +2] | LoraLoaderModelOnly `id=20` w_values[1] |
| ② LoRA 叠加 | `lora_6_name` | 下拉 | `.safetensors` | 同上 | LoraLoaderModelOnly `id=21` w_values[0] |
| ② LoRA 叠加 | `lora_6_strength` | 浮点滑块 | 0.2 | [-2, +2] | LoraLoaderModelOnly `id=21` w_values[1] |
| **③ SeedVR2 超分（2x~4x，基于 ema_vae + seedvr2_ema_3b_fp16 DiT）** | `enable_seedvr2_upscale` | 开关（on/off） | **on**（mode=0 启用，关闭时走直通原图链路） | 布尔 | SeedVR2 3 节点批量 mode 切换；关闭时将 3 节点设 mode=4（与工作流中普通缩放一致） |
| ③ SeedVR2 超分 | `upscale_resolution` | 整数下拉 | **2048**（目标最短边） | [1024, 1536, 2048, 3072, 4096]（= 2x / 3x / 4x） | SeedVR2VideoUpscaler `id=62/80` w_values[2] resolution |
| ③ SeedVR2 超分 | `upscale_color_correction` | 下拉 | **lab** | [off, lab, adain, none] | SeedVR2VideoUpscaler w_values[6] color_correction |
| ③ SeedVR2 超分 | `upscale_seed` | 整数框 + 🎲 随机 | -1（随机） | -1 或 [0, 2^53-1] | SeedVR2VideoUpscaler w_values[0] + w_values[1] = `randomize` |
| **④ 对比 + 显存预留设置** | `enable_eses_compare` | 开关 | **on**（输出并排对比拼接图） | 布尔 | 关闭时 EsesImageCompare 改 mode=4，SaveImage 直接接收 SeedVR2 或原图的单一路径 |
| ④ 对比 + 显存预留设置 | `eses_compare_axis` | 单选 | horizontal（横排左右对比） | horizontal / vertical / slider | EsesImageCompare `id=59/77` w_values[0]（display_mode，默认 "normal"）+ **顶层 JSON 字段 `compare_axis`** 同时写入（实际拼接方向由 compare_axis 字段控制：horizontal=左右横排，vertical=上下竖排，slider=滑动对比） |
| ④ 对比 + 显存预留设置 | `enable_vram_reserve` | 开关 | **on** | 布尔 | ReservedVRAMSetter `id=60/78`；关闭时改 mode=4，直通原图链路改为直接连到 outputNode |
| ④ 对比 + 显存预留设置 | `vram_reserve_gb` | 浮点数框 | **0.6**（默认） | [0, 10.0]（GB） | ReservedVRAMSetter w_values[0] reserved |
| ④ 对比 + 显存预留设置 | `vram_reserve_mode` | 下拉 | **auto** | auto / manual | ReservedVRAMSetter w_values[1] mode |
| ④ 对比 + 显存预留设置 | `vram_reserve_seed` | 整数框 + 🎲 | -1（独立于推理 seed） | -1 或整数 | ReservedVRAMSetter w_values[2] + w_values[3] = `randomize` |
| **⑤ 输出设置** | `output_format` | 下拉（禁用） | **png**（固定不可切换） | 仅 png | SaveImage 扩展名 |
| ⑤ 输出设置 | `filename_prefix` | 文本框模板 | `{engine}` | {date}/{engine}/{seed}/{task_id}，≤ 80 字符 | SaveImage id=53/71 filename_prefix |

> **关于采样器 sampler / scheduler**：Z-Image Turbo 使用 `ModelSamplingAuraFlow id=8`（shift=3）+ KSampler（`dpmpp_3m_sde_gpu` + `sgm_uniform`）。该组合为官方推荐最优，**不在 UI 暴露切换项**。

#### FR-2.4.3 参数校验规则（对齐工作流 widgets_values 结构）
- `width / height`：非 16 的倍数 → 自动四舍五入到最近的 16 倍数，并提示"已自动调整为 W×H"
- `steps < 1`：clamp 至 1；`steps > 50`：弹窗二次确认"已超过推荐值，可能导致画质异常"
- `cfg`：Z-Image Turbo 蒸馏模型官方推荐为 1.0；<1 或 >10 时黄色警告
- **batch_size**：用户要求上限 9999；代码内部按 `chunk = min(current, 16)` 拆分；UI 显示"预计生成 N = Prompt 数 × batch_size × Grid"，≥500 黄 ⚠、≥5000 红 ⚠ 需二次确认；batch>500 自动启用断点续跑（每 100 张落盘 checkpoint）
- `seed = -1`：每次推理前调用 `random.randint(0, 2^53-1)` 生成实际 seed 并**同时回填 LoRA（若与 seed 相关）+ SeedVR2 upscale_seed + VRAM reserve_seed**（各自独立，不共用）
- **LoRA 权重校验**：单个 lora_i_strength 超 ±1.5 黄色警告；若 lora_i_name 选"— 禁用 —"，则该条 LoraLoaderModelOnly 改 mode=4 跳过，下一条节点的 MODEL in/out 链路自动重连（跳过本层）
- **SeedVR2 upscale_resolution**：若 `width * batch_size` 内存估算 > 原生引擎可用显存，自动将 batch_size chunk 从 16 降到 8/4/2，并提示

#### FR-2.4.4 参数 → 工作流 JSON Widget Patch 总表（严格对齐 nodes[].widgets_values 下标）
**Z-Image Turbo（Z_image_turbo.json）所有必做参数对应节点一览：**

| 参数键 | 节点类型 | 节点 ID | patch 字段 / widgets_values 下标 | 备注 |
|-------|---------|:------:|----------------------------------|------|
| positive_prompt | CLIPTextEncode | 4 | 子图 slot 0 → `widgets_values[0]` | CLIPTextEncode widgets_values[0] 是 text |
| negative_prompt | CLIPTextEncode | 15 | 子图 slot 1 → `widgets_values[0]` | |
| cfg | CFGGuider | 7 | 子图 slot 2 → `widgets_values[0]` | |
| steps | Flux2Scheduler | 9 | 子图 slot 3 → `widgets_values[0]` | w_values = [steps, width, height]；子图 slot 已注入 steps |
| width | EmptyFlux2LatentImage | 10 | 子图 slot 4 → `widgets_values[0]`；同步 Flux2Scheduler `id=9` w_values[1] | 两处同步保证一致 |
| height | EmptyFlux2LatentImage | 10 | 子图 slot 5 → `widgets_values[1]`；同步 Flux2Scheduler `id=9` w_values[2] | 两处同步保证一致 |
| seed | RandomNoise | 6 | `widgets_values[0]`（实际值）；`widgets_values[1]` = "randomize" 当 seed=-1，否则 "fixed" | |
| batch_size | EmptyFlux2LatentImage | 10 | `widgets_values[2]`（每次提交 chunk 值 ≤ 16） | 9999 时多次提交 |
| lora_1_name / strength | LoraLoaderModelOnly | 16 | node mode 4→0；w_values[0] = lora 文件名；w_values[1] = strength | 模型输入来自 UNETLoader id=69 |
| lora_2_name / strength | LoraLoaderModelOnly | 17 | 同上；输入 MODEL link 来自 id=16 输出 | |
| lora_3_name / strength | LoraLoaderModelOnly | 18 | 同上；输入来自 id=17 输出 | |
| lora_4_name / strength | LoraLoaderModelOnly | 19 | 同上；输入来自 id=18 输出 | |
| lora_5_name / strength | LoraLoaderModelOnly | 20 | 同上；输入来自 id=19 输出 | |
| lora_6_name / strength | LoraLoaderModelOnly | 21 | 同上；输入来自 id=20 输出 → 输出 MODEL link 30 → CFGGuider id=7 输入 | 链路末端接入采样 |
| enable_seedvr2_upscale | SeedVR2 三个节点 | 61/62/63 | off 时三节点批量 mode 0→4，断开 slot 0 连线改由 VAEDecode id=12 直通 outputNode | |
| upscale_resolution | SeedVR2VideoUpscaler | 62 | `widgets_values[2]` | （w_values 顺序 = [seed, randomize, resolution, ...]） |
| upscale_color_correction | SeedVR2VideoUpscaler | 62 | `widgets_values[6]` | |
| upscale_seed | SeedVR2VideoUpscaler | 62 | `widgets_values[0]` + `widgets_values[1]`= "randomize"/"fixed" | 独立于推理 seed |
| enable_eses_compare | EsesImageCompare | 59 | off 时 mode 0→4；SaveImage id=53 input link 78 改为连 outputNode slot 0（SeedVR2）或 slot 1（原图） | on 时 SaveImage 保存对比拼接图 |
| eses_compare_axis | EsesImageCompare | 59 | `widgets_values[0]` = display_mode；JSON 顶层字段 `compare_axis` = "horizontal"/"vertical" | |
| enable_vram_reserve | ReservedVRAMSetter | 60 | off 时 mode 0→4，outputNode slot 1 改直连 VAEDecode id=12 | |
| vram_reserve_gb | ReservedVRAMSetter | 60 | `widgets_values[0]` reserved | |
| vram_reserve_mode | ReservedVRAMSetter | 60 | `widgets_values[1]` mode | |
| vram_reserve_seed | ReservedVRAMSetter | 60 | `widgets_values[2]` + `widgets_values[3]`= "randomize"/"fixed" | 独立 seed |
| filename_prefix | SaveImage | 53 | `widgets_values[0]` | |

> **Z-Image Turbo 对应节点 ID 一览（Z_image_turbo.json）**：CLIPTextEncode（正=6 / 负=5），KSampler 本体 id=7（含 steps/cfg/seed/denoise），EmptySD3LatentImage id=4，**LoRA 6 条 id=16~21**，SeedVR2 三节点（LoadVAE=79 / VideoUpscaler=80 / LoadDiT=81），EsesImageCompare=77，ReservedVRAMSetter=78，SaveImage=71。参数/注入方式与上表完全一致，Schema YAML 仅换节点 ID 即可。

#### FR-2.4.5 必做链路的输出文件规则（2 图 / 对比图 共存策略）
1. **双图输出 = 原直通图 + SeedVR2 超分图**（两条链路同时存在）→ `outputs/{engine}/{date}/{task_id}_original.png` 与 `{task_id}_upscaled.png` 分别保存
2. **Eses 对比图 = image_a / image_b 并排拼接** → 另存 `{task_id}_compare.png`（SaveImage id=53/71 输出的就是这张拼接图），同时两张独立原图仍单独落盘便于素材库管理
3. **关闭 SeedVR2 超分** → 仅输出 original；关闭 Eses 对比 → 不存 compare
4. **9999 批次**：每张图按 `{task_id}_{chunk_idx}_{item_idx}_original.png` 命名；对比图单独存（最多生成 9999 张对比图，预计 9999×N KB，磁盘占用提示）

### 2.5 预设与参数管理

#### FR-2.5.1 预设保存与加载
- 预设 = 引擎ID + 完整参数字典（不含 seed）
- 命名、标签、缩略图（自动截取上次输出）
- 导入 / 导出 JSON 预设文件
- 引擎专属预设 + 全局通用预设 双命名空间

#### FR-2.5.2 参数版本化可复现
每条历史记录携带完整 `generation_config` JSON（**含 2.4.2 全部 22 项参数 + 引擎版本 + 工作流哈希 + 提交前每个 nodes[].mode 切换记录**），可一键"用相同参数重绘"，包含但不限于：
- 8 大基础参数（positive_prompt / negative_prompt / cfg / steps / width / height / seed / batch_size）
- LoRA 6 层：`[{name, strength}, ×6]` + 每层提交前 mode 状态
- SeedVR2：enable / resolution / color_correction / upscale_seed
- Eses 对比：enable / compare_axis
- ReservedVRAM：enable / vram_reserve_gb / vram_reserve_mode / vram_reserve_seed
- 引擎版本、ComfyUI 版本、工作流文件 SHA256 哈希

### 2.6 LoRA 资源管理（必做，工作流已含 6 条 LoraLoaderModelOnly 串联链路）

> **必做理由（v1.3 边界规则）**：工作流包含 6 个 `LoraLoaderModelOnly` 串联节点（Z-Image Turbo id=16~21），尽管默认 `mode=4 bypassed`，但按用户规则「节点存在即必做」→ 实现时根据 UI 选择切换 mode=0 启用。LoRA 链路完整对接 UNETLoader → CFGGuider。

#### FR-2.6.1 LoRA 目录扫描与元数据
- 扫描路径：`pretrained_models/loras/`（与 shared/portable 双模式路径解耦，调用 `resolve_model_path('loras/xxx.safetensors')`）
- 元数据：自动读取 `.safetensors` 元数据 header 中的 `ss_tag_frequency`（触发词）、`ss_base_model_version`（适配基础模型）
- 下拉列表排序：默认按 LoRA 文件名 + 所在引擎（Z-Image Turbo）过滤（基础模型不匹配显示 ⚠ 灰显）
- 支持子目录：`loras/Z_image/` 递归扫描

#### FR-2.6.2 LoRA 6 层叠加 UI（与 2.4.2 参数表联动）
- 每行一个 LoRA：下拉选 `_disabled`（禁用）或具体 LoRA 文件 + 权重滑块（-2.0 ~ +2.0）
- 行顺序 = 工作流 id=16→17→18→19→20→21 的串联顺序（UNETLoader → id=16 → id=17 → ... → id=21 → CFGGuider），不得乱序（乱序 = 叠加效果不一致）
- 默认值 **严格按工作流 JSON widgets_values 初始化**（Z-Image Turbo：id=16 `` 1.0、id=17 `Kook_亚洲人像` 0.7、id=18 同 0.5、id=19 同 0.4、id=20 同 0.3、id=21 `` 0.2）
- 若某层 LoRA 文件不在磁盘（用户没把对应 LoRA 拷到 pretrained_models/loras）→ 下拉自动选 `_disabled` + 黄色提示"工作流默认 LoRA 未找到：xxx.safetensors，已跳过本层"
- 预设保存/加载：LoRA 6 层完整写入预设；批量 Grid Search 支持 lora_i_strength 做维度（生成 lora_strength × cfg × steps 的笛卡尔积）

#### FR-2.6.3 VAE / UNet / CLIP 说明（已内置，UI 不暴露）
- **VAE / UNet / CLIP**：引擎在工作流 JSON 内部 `UNETLoader id=69/1`、`CLIPLoader id=2/2`、`VAELoader id=3/3` 节点已绑定专属模型文件（Z-Image Turbo 用 `z_image_turbo_bf16 + qwen_3_4b + ae`），UI 中**不提供切换**（切换会导致节点型 LoRA 权重矩阵不兼容）。

### 2.7 批量推理（批次 1 ~ 9999）

#### FR-2.7.1 批量模式
- **批量文生图**：读取 `.txt` / `.csv` 中的 Prompt 列表（每行一条），逐张或按批次生成
- **参数网格 (Grid Search)**：支持 6 个维度组合 `steps × cfg × seed × width × height × lora_i_strength`（最多同时勾 2~3 维，生成数量显示预测值，≥500 黄 ⚠、≥5000 红 ⚠ 需二次确认）
- 批量模式下共享：同一 `engine` + 同一组固定参数（不含 grid 动态维度）+ 同一 SeedVR2 + Eses + VRAM 绑定
- **明确不做**：批量图生图 / 批量文件夹（工作流无 LoadImage/img2img 节点，1.6 边界判定已不做）

#### FR-2.7.2 批次控制
- **每张 Prompt 的生成数量（batch_size）**：默认 1，**用户要求范围 1 ~ 9999**
  - 内部策略：`batch_size > 16` 时自动按 `chunk = min(current, 16)` 拆分为多次 ComfyUI 提交，结果合并为同一 batch 输出；开启 SeedVR2 时 chunk 自动降为 `min(4, chunk)`（超分吃显存更多）
  - UI 显示：`batch_size` 框下方显示"预计生成 N 张 = Prompt 数 × batch_size × Grid 乘积 ×（开启 SeedVR2×2 + 开启 Eses 对比×1 = 系数）"红色大字提示
- 总并发上限：受任务队列 `maxsize` 约束（参考 Seedvr2 单 Worker，默认 ≤ 8 条任务排队）
- 失败任务单独记录，不中断整批；支持失败任务一键重试（仅重试失败的 Prompt+seed+LoRA 组合）
- **超大批次（batch_size > 500）特殊处理**：自动启用临时断点续跑（每 100 张落盘一个 checkpoint，应用崩溃可继续）；开启 SeedVR2 且 batch>500 时弹窗提示"超分会显著增加显存+耗时，预计 X 小时，是否确认?"

> 实现参考（B1）：取消回调机制复用 Seedvr2 `task_queue.py#L12-L150` 的 `CancelCallback` 类型 + `request_cancel()` 先调 `on_cancel(engine.cancel)` 再兜底 `Task.cancel()`，解决 `asyncio.to_thread` 包装的 ComfyUI 同步推理无法被 Python 取消的问题。详细 → 附录 C-B1。
> 实现参考（B2）：Worker 异常自动重启 + 有界队列防 OOM 直接照搬 Seedvr2 `task_queue.py#L32-L82` 三常量：`DEFAULT_QUEUE_MAXSIZE=100`、`DEFAULT_TASK_TIMEOUT_SECONDS=3600`、`MAX_WORKER_RESTARTS=3`。详细 → 附录 C-B2。

### 2.8 历史记录与素材库

参照 [Seedvr2 history_db.py](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/history_db.py) 的 SQLite 模式。

#### FR-2.8.1 记录字段
- `task_id`、`created_at`、`engine_name`
- `mode`：固定 `txt2img`（1.6 边界判定不做 img2img）
- `prompt`、`negative_prompt`
- `width`、`height`、`steps`、`cfg`、`seed`、`batch_size`
- `sampler_name`、`scheduler`（从 ComfyUI 实际提交记录回填，不暴露 UI 仅保留复现）
- `generation_config`（完整 JSON，含 FR-2.5.2 全部 22 项参数 + 6 层 LoRA 详情 + SeedVR2/Eses/VRAM + 工作流哈希，可 100% 重绘）
- `output_image_paths[]`（数组，批次模式下多张；结构：`{original: [...], upscaled: [...], compare: [...]}`，9999 批次时分多页存储）
- `thumbnail_path`（默认取 compare 图首帧；关对比则取 original）
- `status`（pending/processing/completed/failed/cancelled）
- `processing_time_s`（含拆分后各 chunk + SeedVR2 超分阶段时间之和）
- `error_message`
- `tags[]`
- `favorite`（布尔）

#### FR-2.8.2 历史页功能
- 搜索：Prompt 关键字 / 引擎 / 时间范围 / 标签
- 筛选：状态（成功/失败/进行中）/ 引擎 / 收藏
- 分页：每页 50 条
- 单条详情侧栏：完整参数 + 图像预览 + "重绘此图" + "保存为预设"
- 批量操作：批量删除 / 批量导出 ZIP / 批量加标签
- 磁盘空间占用统计，按时间清理（可配置保留天数）

> 实现参考（B3）：SQLite 模式 + 崩溃恢复流程复用 Seedvr2 `history_db.py#L65-L137` + `app_server.py#L165-L178`：启用 WAL + FTS5 全文索引；启动时 lifecycle 先 `cleanup_stale_tasks(status='processing' and created_at < NOW()-1h)` 清理卡死任务，再按 config 开关 `recover_tasks()` 恢复 pending 队列。详细 → 附录 C-B3。

### 2.9 实时进度与 SSE

参照 Seedvr2 `routes/system/sse.py` + TTS_MultiModel `routes/sse.py`。

#### FR-2.9.1 SSE 事件列表
| event | 触发时机 | 负载 |
|-------|---------|------|
| `task_status` | 任务入队 / 开始 / 进度 / 完成 / 失败 / 取消 | `{task_id, status, progress_pct, message}` |
| `comfy_preview` | ComfyUI 返回预览图节点 | `{task_id, preview_b64}` |
| `model_status` | 引擎加载 / 卸载 / 切换 | `{engine_name, status, message}` |
| `gpu_status` | 每 2s 推送 | `{vram_used_gb, vram_total_gb, gpu_util_pct}` |
| `queue_status` | 队列长度变更 | `{current_task_id, queue_size, pending_ids[]}` |

#### FR-2.9.2 进度条精度
- 对于 ComfyUI：使用其 `/history` + 节点进度，映射到 0%~100% 整体百分比
- 未知进度时显示"阶段文本 + 无百分比"的旋转指示器

> 实现参考（A2）：ModelRegistry 观察者 → SSE 桥接完整照搬 Seedvr2 `app_server.py#L62-L73` 的 `_bridge_model_status_to_sse()` 函数 + `model_registry.add_listener(...)` 注册。详细 → 附录 C-A2。
> 实现参考（C2）：统一单连接 SSE 事件总线 + `: ping` 注释心跳帧复用 TTS_MultiModel `routes/sse.py#L44-L120` 的 `SSEEvent` 结构 + `SSEEventBus`（订阅 Queue + Event 唤醒双模式兼容）+ `retry=3000`。详细 → 附录 C-C2。

### 2.10 系统状态监控

参照 Seedvr2 `routes/system/` + 首页仪表盘。

- GPU 显存曲线图（最近 60 条采样，2s 间隔）
- 系统内存使用率
- 磁盘剩余空间（outputs / uploads 所在卷）
- 已注册引擎列表与加载状态
- 原生引擎加载状态与健康指示灯
- 应用运行时长 + 累计完成任务数

### 2.11 设置与偏好

#### FR-2.11.1 全局设置
- 主题：浅色 / 深色 / 跟随系统
- **语言（5 种，i18n）**：简体中文（zh-CN）/ 繁體中文（zh-TW）/ English（en-US）/ 日本語（ja-JP）/ 한국어（ko-KR）
  - 翻译文件结构：`locales/zh-CN.yaml`、`locales/zh-TW.yaml`、`locales/en-US.yaml`、`locales/ja-JP.yaml`、`locales/ko-KR.yaml`
  - 所有字符串（导航、按钮、提示、错误信息、参数名）均覆盖
  - 切换语言：无需刷新页面（HTMX 替换页面元素 `data-i18n` 属性）

> 实现参考（E2）：i18n 格式 + 防闪烁脚本直接照搬 TTS_MultiModel：语言文件采用 JSON（`locales/{zh,zh-tw,en,ja,ko}.json`，短代码与两项目对齐；非 BCP-47 长代码仅在 UI 侧展示映射）；`templates/base.html` `<head>` 首段嵌入同步脚本读取 `localStorage['lang']||navigator.language` → 即时设置 `document.documentElement[data-lang=xx] + data-theme`，杜绝页面渲染完成后语言闪一下再切换的 UX 瑕疵。详细 → 附录 C-E2。

- 默认输出格式与质量（固定 PNG）
- 历史记录保留策略（天数/GB 上限双阈值）
- SSE 推送间隔（默认 1s，可调 0.5s/2s）
- 默认 `batch_size`：用户可自定义（默认 1，防止误操作出几千张）

#### FR-2.11.2 模型设置 Tab
- 引擎管理：启用 / 禁用（隐藏不常用引擎）、覆盖显存估算值、覆盖默认参数（默认 cfg/steps/width/height 全局预设）
- 原生引擎管理：加载 / 卸载 / 连接测试（复用 comfy_kernel 源码）
- 资源扫描：手动触发 text_encoders / unet / vae 目录扫描（用于模型存在性红/绿灯指示）

---

## 3. 用户界面设计规范

### 3.1 设计语言：Warm Print（继承 Seedvr2）

直接沿用 [Seedvr2 static/design-system.md](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/static/design-system.md) 与 [TTS_MultiModel UI 截图](file:///C:/Users/Doro/TTS_MultiModel/docs/screenshots/voxcpm2_01_voice_design_viewport.png) 确立的视觉语言：

- **字体对**: Instrument Serif（展示衬线，Italic） + DM Sans（正文无衬线）
- **排版网格**: 8px 间距基础单位，12 列响应式
- **色彩系统 (CSS 变量驱动)**:
  ```css
  [data-theme="dark"] {
    --bg: #faf7f2; /* Warm 纸张色，反直觉暗底暖白 */
    --ink: #2a2a2a;
    --accent: #5e7d5a; /* 橄榄绿品牌色 */
    --accent-ink: #faf7f2;
    --danger: #c84a3a;
    --warning: #d9a441;
    --success: #5e7d5a;
    --border: rgba(42,42,42,0.08);
    --card-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
  }
  [data-theme="light"] { /* 镜像变量，真正浅底 */ }
  ```
- **动效**: Rise 入场动画（`transform: translateY(6px); opacity: 0` → 归位），Delay 0/1/2/3 四档

### 3.2 全局布局

```
┌─────────────────────────────────────────────────────────┐
│  Topbar: Logo | 引擎切换下拉 | 主题切换 | 5 语言选择器    │
├──────────┬──────────────────────────────────────────────┤
│ Sidebar  │  Content Area (根据导航渲染)                 │
│ (可折叠) │                                              │
│          │  - Home Dashboard                           │
│ 🎨 生图   │  - txt2img 推理工作台（唯一模式）            │
│ 📚 批量   │  - Batch Mode (Prompt批量 / Grid Search)   │
│ ⏱️ 历史   │  - History & Library                        │
│ 📊 首页   │  - System Status                            │
│ ⚙️ 设置   │  - Settings                                 │
│          │                                              │
├──────────┴──────────────────────────────────────────────┤
│  Status Bar: 队列进度 | GPU状态 | 当前引擎 | 连接指示灯   │
│             batch_size 超大批次时显示「批次 X/Y」进度    │
└─────────────────────────────────────────────────────────┘
```

#### FR-3.2.1 导航与路由
- 所有页面通过 Jinja2 模板 + HTMX 部分更新，无 SPA 路由框架
- 页面结构：`base.html` + `partials/*.html` 组件化（参考 TTS_MultiModel `templates/partials/`）

### 3.3 页面级规范

#### 3.3.1 首页仪表盘
- Hero 区：产品标题 + 副标题 + 两个 CTA（「开始生图」「查看历史」）
- 4 列系统状态卡：GPU / 引擎 / 内存 / 运行时长（参考 Seedvr2 `index.html` `sv-overview-grid`）
- 3 张快速功能卡：单张生图 / 批量模式 / 历史记录
- 最近 8 条任务缩略图网格

#### 3.3.2 生图工作台
- 左 55%：参数面板（滚动容器）
- 右 45%：输出显示区
  - 上部：当前任务实时预览（大图 + 进度条 + 阶段文本）
  - 下部：本次任务输出图片网格（批次多张时），悬停显示下载 / 收藏 / 重绘
- 固定在参数面板底部：`生成` 主按钮（根据引擎状态禁用）+ `取消当前` 次级按钮

#### 3.3.3 参数表单控件一致性
| 参数类型 | 控件 | 单位 / 步长 |
|---------|------|------------|
| 正整数 (width/height) | 数字输入 + 步进按钮 ±16 + 快捷预设 512/768/1024/1536 | ±16 |
| 正整数 (steps/batch_size) | 数字输入 + 步进按钮（steps ±1，batch_size ±1 / ±10 / ±100 三档快捷） | steps: [1,50]; **batch_size: [1,9999]** |
| 浮点 (cfg) | 数字输入（无滑块：Z-Image Turbo 推荐 cfg=1，范围窄不需要滑块）| 步长 0.1，范围 [1.0, 20.0] |
| seed | 数字输入 + 「🎲随机」按钮 + 「♻️复用上一个」 | seed=-1 表示随机，每次显示实际落到的值 |
| 枚举（引擎 / 语言 / 主题）| 下拉选择（`<select>`） | 引擎最多 10 项；语言固定 5 项（简/繁中/英/日/韩） |
| prompt 文本 | 多行 textarea，固定高度 160px，支持「清空」「复制」快捷按钮 | |
| 开关 (bool) | 滑动 Toggle | |

> **UI 控件范围说明（v1.3 边界规则对齐工作流节点）**：
> - ✅ **必做（节点存在 = 提供）**：LoRA 6 层下拉+权重（LoraLoaderModelOnly id=16~21）、SeedVR2 超分开关+分辨率（61/62/63）、Eses 对比开关+轴（59）、ReservedVRAM 显存开关+GB（60）
> - ❌ **不做（工作流 JSON 完全无节点）**：文件上传（img2img/ControlNet 参考图）、denoise 滑块（仅 img2img 需用）、ControlNet 预处理 + ApplyControlNet、普通 ImageScaleToTotalPixels lanczos 缩放预览

> **batch_size 特殊 UI 规范**：当用户输入 > 500 时，输入框右侧自动叠加黄色 ⚠ 图标，hover 显示"超大批次建议夜间生成，预计耗时 XX 分钟（基于 RTX 4090 估算）"；输入 > 5000 时红色 ⚠ + 点"生成"时弹出含倒计时 5s 的二次确认弹窗。

### 3.4 无障碍 (A11y)
继承 Seedvr2 `tests/specs/a11y.spec.ts` 所代表的要求：
- 所有交互元素 `aria-label` 完备
- 键盘 Tab 顺序与视觉顺序一致
- 色彩对比度 WCAG AA 级（对比度测试脚本参考 `tests/wcag-contrast-test.js`）

> 实现参考（C3）：版本化静态文件 + 差异化 Cache-Control 完整照搬 Seedvr2 `app_server.py#L76-L105` 的 `VersionedStaticFiles(StaticFiles)` 子类，重写 `file_response` 为 CSS/JS 设 `no-cache`、字体 woff2 设 30 天、图片 1 天。详细 → 附录 C-C3。

---

## 4. ComfyUI 模型集成方案

> 这是本产品与参考项目**最大的架构差异点**：两参考项目均直接内部加载 PyTorch 模型；本项目进程内复用 `comfy_kernel` 源码，由单一进程内原生引擎（NativeEngine）直接调用 `comfy.sd` / `comfy.samplers` 完成推理，无外部 ComfyUI 后端进程 / HTTP+WebSocket 代理。

### 4.1 集成层级总览

```
┌─────────────────────────────────────────────────────┐
│              Image MultiModel (本产品)               │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ EngineRegistry│  │ ModelManager │  │ TaskQueue│ │
│  └──────┬───────┘  └──────┬───────┘  └────┬─────┘ │
│         │                 │                │        │
│  ┌──────▼─────────────────▼────────────────▼─────┐ │
│  │          原生引擎适配层 (Native Adapter)        │ │
│  │  ┌────────────────────────────────────────┐   │ │
│  │  │ WorkflowManager (JSON Patch + 参数注入) │   │ │
│  │  │ ParameterSchemaValidator               │   │ │
│  │  │ ProgressMapper (Comfy节点→整体%)       │   │ │
│  └──┴────────────────────────────────────────┴───┘ │
│        进程内直接调用（复用 comfy_kernel）│
└───────────────┬────────────────────────────────────┘
                ▼ 进程内（无外部进程 / 无 HTTP+WS）
        ┌──────────────────────┐
        │  NativeEngine (进程内) │
        │  - comfy.sd / samplers│
        │  - 采样 / VAE 解码     │
        └──────────────────────┘
```

### 4.2 原生引擎抽象协议 (Protocol)

在 `bin/integrated_app/engine_interface.py` 中定义：

```python
@runtime_checkable
class ImageEngine(Protocol):
    """所有生图引擎必须实现的协议（面向 ComfyUI Adapter）。M0 仅实现 infer_txt2img。"""

    def is_ready(self) -> bool: ...
    def load(self, config: EngineLoadConfig) -> Generator[tuple[str, float|None], None, None]:
        """生成器产出 (status_text, progress_pct)，同步模型到原生引擎。"""
        ...
    def unload(self) -> None: ...

    async def infer_txt2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        *,
        params: dict,           # cfg/steps/width/height/seed/batch_size/sampler/scheduler
        batch_size: int = 1,    # 1 ~ 9999，内部按 chunk=16 拆分
        seed: int = -1,
        on_progress: Callable[[dict], None] | None = None,
    ) -> ImageInferenceResult: ...

    # async def infer_img2img(...):    # N/A — 明确不做（工作流无 LoadImage/VAEEncodeForInpaint 节点，1.6 边界规则）
    #     """img2img：本项目不实现，如用户需要请提供含 img2img 节点的新工作流 JSON"""
    #     ...

    def cancel(self) -> None:
        """取消当前正在进行的推理（调用原生引擎中断采样）。"""
        ...
```

> 实现参考（A1）：引擎抽象层复用 TTS_MultiModel `engine_interface.py#L34-L200` 的 `@runtime_checkable Protocol + InMemoryEngineRegistry` 声明式鸭子类型 + 懒导入模式，仅需将 `TTSEngine.generate_*` 方法族替换为 `ImageEngine.infer_txt2img + cancel` 四方法。详细代码级迁移清单 → 附录 C-A1。

### 4.3 工作流与参数映射机制

#### FR-4.3.1 Parameter Schema (YAML)
每个引擎配套一个 Schema 文件，声明参数如何注入 ComfyUI 工作流 JSON 的指定节点。
**重要**：Schema 的节点 ID、字段顺序必须与 `workflows/*.json` 的 `nodes[].widgets_values` 数组完全对应（工作流中 seed/upscale_seed/vram_seed 往往是 widgets_values 第一个字段 + 第二个 `randomize` control 字段，必须按实际结构写）。对 `mode=4 bypassed` 的节点，Patcher 必须在提交前将 nodes[].mode 改成 0。

以下为 Z-Image Turbo 的**完整**模板示例（与 2.4.4 节点映射表严格对齐，含所有必做节点）：

```yaml
# schemas/z_image_turbo_native.yaml
workflow_version: "1.0"
workflow_ref: "workflows/Z_image_turbo.json"
engine_name: "z_image_turbo_native"

required_nodes:
  # ===== 基础 8 大 txt2img =====
  - id: 4
    type: "CLIPTextEncode"              # 正 Prompt
  - id: 15
    type: "CLIPTextEncode"              # 负 Prompt
  - id: 7
    type: "CFGGuider"                  # cfg
  - id: 9
    type: "Flux2Scheduler"             # steps + width + height
  - id: 10
    type: "EmptyFlux2LatentImage"      # width/height/batch_size
  - id: 6
    type: "RandomNoise"                # noise_seed + randomize_control
  - id: 8
    type: "KSamplerSelect"             # sampler_name（固定 dpmpp_3m_sde_gpu，不暴露 UI）
  - id: 69
    type: "UNETLoader"                 # 模型根（LoRA 链路起点）
  - id: 53
    type: "SaveImage"                  # filename_prefix
  # ===== LoRA 6 条（串联链路 id=16→17→18→19→20→21，默认 mode=4 → 提交前强制改为 0）=====
  - id: 16
    type: "LoraLoaderModelOnly"
    chain_order: 1                     # 串联顺序（用于链路重连校验）
  - id: 17
    type: "LoraLoaderModelOnly"
    chain_order: 2
  - id: 18
    type: "LoraLoaderModelOnly"
    chain_order: 3
  - id: 19
    type: "LoraLoaderModelOnly"
    chain_order: 4
  - id: 20
    type: "LoraLoaderModelOnly"
    chain_order: 5
  - id: 21
    type: "LoraLoaderModelOnly"
    chain_order: 6                     # 末端 MODEL → 7 (CFGGuider)
  # ===== SeedVR2 超分 3 节点（mode=0 默认启用）=====
  - id: 61
    type: "SeedVR2LoadVAEModel"
  - id: 63
    type: "SeedVR2LoadDiTModel"
  - id: 62
    type: "SeedVR2VideoUpscaler"       # 提供 upscale_resolution/color_correction/upscale_seed
  # ===== Eses 对比 + ReservedVRAM 显存 =====
  - id: 59
    type: "EsesImageCompare"
  - id: 60
    type: "ReservedVRAMSetter"

parameter_map:
  # ====== 8 大 txt2img 基础参数 ======
  positive_prompt:
    node_id: 4
    widgets_index: 0
    type: STRING
    default: ""
    range: [0, 20000]
  negative_prompt:
    node_id: 15
    widgets_index: 0
    type: STRING
    default: ""
  cfg:
    node_id: 7
    widgets_index: 0
    type: FLOAT
    default: 1.0
    range: [1.0, 20.0]
    step: 0.1
  steps:
    node_id: 9
    widgets_index: 0
    type: INT
    default: 8
    range: [1, 50]
  width:
    node_id: 10
    widgets_index: 0
    sync_nodes:
      - node_id: 9
        widgets_index: 1             # Flux2Scheduler w_values[1] 同步写 width
    type: INT
    default: 1024
    step: 16
    range: [256, 2048]
  height:
    node_id: 10
    widgets_index: 1
    sync_nodes:
      - node_id: 9
        widgets_index: 2             # Flux2Scheduler w_values[2] 同步写 height
    type: INT
    default: 1024
    step: 16
    range: [256, 2048]
  seed:
    node_id: 6
    widgets_index: 0
    widgets_control_index: 1           # "randomize" / "fixed"
    type: INT_SEED_RANDOMIZE
    default: -1
    range: [-1, 9007199254740991]
  batch_size:
    node_id: 10
    widgets_index: 2
    type: INT_BATCH_CHUNKED
    default: 1
    range: [1, 9999]
    internal_chunk_size: 16
    upscale_chunk_size: 4              # 开启 SeedVR2 时自动降至 4，防 OOM

  # ====== LoRA 6 条串联（完整 widgets_values 顺序 = [lora_name, strength_model]）======
  lora_1_name:
    node_id: 16
    widgets_index: 0
    mode_override: 0                   # 提交前强制 nodes[id=16].mode = 0（原 mode=4 bypassed）
    disable_mode_override: 4           # 若 UI 选 _disabled，则 nodes[id=16].mode 保持 4
    type: COMBO_LORA
    dir: "pretrained_models/loras"
    default: "Z-image_turbo-bf16\\.safetensors"
    default_missing_strategy: _disabled_and_warn
  lora_1_strength:
    node_id: 16
    widgets_index: 1
    type: FLOAT
    default: 1.0
    range: [-2.0, 2.0]
    step: 0.05
  lora_2_name:
    node_id: 17
    widgets_index: 0
    mode_override: 0
    disable_mode_override: 4
    type: COMBO_LORA
    dir: "pretrained_models/loras"
    default: "人像风格LoRA.safetensors"
  lora_2_strength:
    node_id: 17
    widgets_index: 1
    type: FLOAT
    default: 0.7
    range: [-2.0, 2.0]
  lora_3_name:
    node_id: 18
    widgets_index: 0
    mode_override: 0
    type: COMBO_LORA
    default: "人像风格LoRA.safetensors"
  lora_3_strength:
    node_id: 18
    widgets_index: 1
    type: FLOAT
    default: 0.5
  lora_4_name:
    node_id: 19
    widgets_index: 0
    mode_override: 0
    type: COMBO_LORA
    default: "人像风格LoRA.safetensors"
  lora_4_strength:
    node_id: 19
    widgets_index: 1
    type: FLOAT
    default: 0.4
  lora_5_name:
    node_id: 20
    widgets_index: 0
    mode_override: 0
    type: COMBO_LORA
    default: "人像风格LoRA.safetensors"
  lora_5_strength:
    node_id: 20
    widgets_index: 1
    type: FLOAT
    default: 0.3
  lora_6_name:
    node_id: 21
    widgets_index: 0
    mode_override: 0
    type: COMBO_LORA
    default: "Z-image_turbo-bf16\\.safetensors"
  lora_6_strength:
    node_id: 21
    widgets_index: 1
    type: FLOAT
    default: 0.2

  # ====== SeedVR2 超分（enable_seedvr2_upscale=off 时 3 节点全置 mode=4 + output link 改直通 VAEDecode）======
  enable_seedvr2_upscale:
    toggle_nodes_mode:
      on: {61: 0, 62: 0, 63: 0}
      off: {61: 4, 62: 4, 63: 4}
    output_link_reroute:
      # SeedVR2 关闭时：outputNode slot 0 改接 VAEDecode id=12 直通
      off: {from_id: 62, from_slot: 0, to_id: -20, to_slot: 0, replace_with: {from_id: 12, from_slot: 0}}
    type: BOOL
    default: true
  upscale_resolution:
    node_id: 62
    widgets_index: 2                   # w_values = [seed, randomize, resolution=2048, max_resolution, batch_size, uniform, color_correction, ...]
    type: INT_ENUM
    options: [1024, 1536, 2048, 3072, 4096]
    default: 2048
  upscale_color_correction:
    node_id: 62
    widgets_index: 6
    type: ENUM
    options: ["off", "lab", "adain", "none"]
    default: "lab"
  upscale_seed:
    node_id: 62
    widgets_index: 0
    widgets_control_index: 1           # "randomize" / "fixed"
    type: INT_SEED_RANDOMIZE
    default: -1

  # ====== Eses 对比 + ReservedVRAM ======
  enable_eses_compare:
    toggle_nodes_mode:
      on: {59: 0}
      off: {59: 4}                     # 关闭时：SaveImage id=53 link 78 改直连 SeedVR2 id=62 或原图
    saveimage_reroute_id: 53
    link_to_rewire: 78                 # link id=78: Eses 0 → SaveImage 0
    type: BOOL
    default: true
  eses_compare_axis:
    node_id: 59
    widgets_index: 0                   # display_mode
    json_field: compare_axis           # 同时写顶层 JSON 字段 compare_axis（horizontal/slider/vertical）
    type: ENUM
    options: ["normal", "horizontal", "vertical", "slider"]
    default: "normal"
  enable_vram_reserve:
    toggle_nodes_mode:
      on: {60: 0}
      off: {60: 4}
    # 关闭时：outputNode slot 1 改直连 VAEDecode id=12（跳过 60）
    output_link_reroute:
      off: {from_id: 60, from_slot: 0, to_id: -20, to_slot: 1, replace_with: {from_id: 12, from_slot: 0}}
    type: BOOL
    default: true
  vram_reserve_gb:
    node_id: 60
    widgets_index: 0                   # reserved (GB)
    type: FLOAT
    range: [0.0, 10.0]
    step: 0.05
    default: 0.6
  vram_reserve_mode:
    node_id: 60
    widgets_index: 1
    type: ENUM
    options: ["auto", "manual"]
    default: "auto"
  vram_reserve_seed:
    node_id: 60
    widgets_index: 2
    widgets_control_index: 3           # "randomize" / "fixed"
    type: INT_SEED_RANDOMIZE
    default: -1

  # ====== 输出设置 ======
  output_format:
    const: "png"
  filename_prefix:
    node_id: 53
    widgets_index: 0
    type: STRING_TEMPLATE
    default: "{engine}"
    support_vars: ["{date}", "{engine}", "{seed}", "{task_id}"]
    max_len: 80
```

#### FR-4.3.2 Workflow Patcher（必做 4 类处理：mode 切换 + link 重连 + widgets 替换 + chunk 拆分）
推理前 Patcher 严格按 **Schema → 执行顺序**处理，不得漏步：

1. **Step 1 读取 + 深拷贝 workflow.json**：禁止修改原文件，提交副本
2. **Step 2 nodes[].mode 切换**（按 schema `mode_override` + `toggle_nodes_mode`）：
   - LoRA 6 条（id=16~21）：若该层 UI 未 `_disabled` → mode 4→0；禁用则保持 4
   - SeedVR2 3 条（61/62/63）：enable → mode 0；disable → mode 4
   - Eses 59：enable→0，disable→4
   - VRAM 60：enable→0，disable→4
3. **Step 3 link 重连**（当 enable_seedvr2_upscale / enable_eses_compare / enable_vram_reserve 关闭时）：
   - 重写 `links[]` 数组：断开 SeedVR2 id=62 → outputNode 连线，改为 VAEDecode id=12 → outputNode
   - SaveImage id=53 前的 Eses 链路同理，断开/重连
4. **Step 4 参数 patch（widgets_values 替换）**：按 2.4.4 节点映射表逐一 patch
   - 对每个 INT_SEED_RANDOMIZE 型字段（推理 seed/upscale_seed/vram_seed）：-1 时 w_values[1] = "randomize"；正数时 w_values[1] = "fixed" + w_values[0] = 实际值
   - width/height 同步写 Flux2Scheduler 和 EmptyLatentImage 两处
5. **Step 5 batch chunk 拆分**：`batch_size > 16`（或开启超分 > 4）→ 拆多次提交，结果合并为同一 task_id
6. 提交前校验：`lo_required_nodes` 中每个节点 id/type 必须在工作流中匹配，否则拒绝提交 + 友好报错（防止用户修改 JSON 后参数错位）

> **不做**（对应节点完全不存在于工作流 JSON，1.6 边界表已写明）：图生图 LoadImage / VAEEncodeForInpaint，ControlNet Loader + ApplyControlNet + 预处理链路，普通 lanczos 缩放 ImageScaleToTotalPixels 预览。

### 4.4 任务提交流程 (原生引擎)

1. `NativeEngine.infer_txt2img()` 提交 patched workflow（进程内执行，复用 `comfy.sd` / `comfy.samplers`）
2. 监听采样回调（进程内，无 WebSocket / 无外部后端）：
   - `execution_start` / `execution_cached` / `executing` (节点级进度)
   - `executed` (含 output 图)
   - `execution_error` (错误)
3. 进度：已执行节点数 / 总节点数 = 百分比（缓存节点跳过计入已完成）
4. 完成：VAE 解码得到输出图像
5. 落盘到 `outputs/{engine_name}/{date}/{task_id}_{idx}.{ext}`

### 4.5 单引擎策略

- **默认（推荐）**: 单一进程内原生引擎，`max_workers=1`，任务队列严格串行（与参考项目一致，防 OOM）
- 引擎选择：`config.yaml → models.engines` 仅声明 `z_image_turbo_native`，进程内复用 comfy_kernel 源码，无外部 ComfyUI 后端进程 / 多后端负载均衡

---

## 5. 系统架构

### 5.1 分层架构

```
┌──────────────────────────────────────────────────────────────┐
│  表现层 (Presentation)                                       │
│  Jinja2 Templates + HTMX + Bootstrap Icons + CSS Variables   │
│  └─ routes/pages.py / routes/tabs.py / routes/generate/      │
├──────────────────────────────────────────────────────────────┤
│  应用服务层 (Service)                                        │
│  ┌───────────────┐  ┌───────────┐  ┌─────────────────────┐  │
│  │ ModelManager  │  │ TaskQueue │  │ Generation Service  │  │
│  │ (生命周期)     │  │ (串行队列)│  │ (参数→工作流→图像)   │  │
│  └───────┬───────┘  └─────┬─────┘  └──────────┬──────────┘  │
│  ┌───────▼───────┐  ┌─────▼─────┐  ┌──────────▼──────────┐  │
│  │ ModelRegistry │  │ TaskState │  │ WorkflowManager     │  │
│  │ (单例状态)     │  │ (事件总线)│  │ (Schema + Patcher)  │  │
│  └───────────────┘  └───────────┘  └─────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│  适配层 (Adapter)                                            │
│  NativeEngine (Protocol Impl，进程内复用 comfy_kernel)  │
├──────────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure)                                 │
│  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ HistoryDB│  │ FileCache│  │ I18n     │  │ Metrics/Health│ │
│  │ (SQLite) │  │ (uploads)│  │ (YAML/JSON)│ │ (SSE 推送)    │ │
│  └──────────┘  └─────────┘  └──────────┘  └───────────────┘ │
│  ┌──────────┐  ┌──────────────────────────────────────────┐  │
│  │ GPU Utils│  │ Middleware: CSRF / RateLimit / BasicAuth│  │
│  └──────────┘  └──────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│  外部依赖                                                    │
│  comfy_kernel 源码（进程内）/ NVIDIA CUDA / 模型文件(.safetensors)  │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 目录结构（对齐参考项目 + 双模式创新）

> **【跨平台命名规范】** 所有模型目录统一 **全小写**（`text` / `unet` / `vae`）。Windows 对大小写不敏感，
> 但 Linux Docker / WSL / macOS 区分大小写，全小写可一次避免所有跨平台路径坑。

```
Image_MultiModel/
├── bin/
│   ├── clean_launch.py                       # 启动入口（对齐两项目）
│   ├── start_app.bat / start.bat             # Windows 启动脚本
│   ├── install.bat                           # 安装脚本
│   └── integrated_app/
│       ├── app_server.py                     # FastAPI create_app + lifespan
│       ├── config.py / config_models.py      # ★ YAML 加载 + Pydantic 模型 + 双模式路径解析器
│       │                                     #   (新增 resolve_model_path() 统一 MODE=shared/portable)
│       ├── engine_interface.py               # ImageEngine Protocol
│       ├── model_manager.py                  # 引擎加载/切换/卸载
│       ├── model_registry.py                 # 单例状态注册中心 + 观察者
│       ├── task_queue.py                     # 单 Worker 队列 + 取消回调
│       ├── history_db.py                     # SQLite 历史记录
│       ├── cache.py                          # 上传文件缓存 + TTL
│       ├── i18n.py                           # 国际化
│       ├── progress.py / metrics.py          # 进度与指标
│       ├── exceptions.py                     # 异常层级
│       ├── gpu_backend.py / gpu_utils.py     # GPU 检测/显存
│       ├── auth.py                           # API Token 中间件
│       ├── watermark.py                      # 数字水印
│       ├── native/                           # ★ 进程内原生引擎层 ★
│       │   ├── source.py                     # 复用 comfy_kernel 源码（sys.path 注入）
│       │   ├── engine.py                     # NativeEngine (ImageEngine impl)
│       │   ├── workflow.py                   # WorkflowManager (Patch + Schema)
│       │   └── schemas/                      # 参数映射 YAML 集合
│       ├── workflows/                        # ComfyUI 工作流 JSON (bin 内)
│       ├── engines/                          # 扩展引擎（非 ComfyUI 预留）
│       ├── middleware/                       # CSRF / RateLimit / ErrorHandler / BasicAuth / RequestID
│       ├── routes/                           # 自动发现
│       │   ├── pages.py / tabs.py
│       │   ├── generate/{txt2img,batch}.py        # M0 仅 txt2img（img2img.py M3 再创建）
│       │   ├── model.py
│       │   ├── assets.py / presets.py / history.py
│       │   └── system/{health,gpu,metrics,settings,sse}.py
│       ├── services/task_state.py + task_events.py
│       ├── security/                         # 完整性自检 / 路径守卫 (继承 Seedvr2)
│       ├── static/{css,js,fonts,vendor}
│       ├── templates/{base,index,generate,batch,history,...}.html
│       └── locales/{zh-CN,zh-TW,en-US,ja-JP,ko-KR}.yaml    # 5 种语言文件（简/繁中/英/日/韩）
├── scripts/                                   # ★ 运维脚本（新增）★
│   ├── setup_symlinks.ps1                    # shared 模式：一键创建/重建 text/unet/vae Junction
│   ├── pack_portable.ps1                     # 一键切换 portable + 复制模型 + 打包 zip
│   └── verify_watermark.py                   # 输出数字水印溯源验证
├── common/                                    # 通用工具（从 Seedvr2 裁剪）
│   └── logger.py / decorators.py / seed.py
├── tests/                                     # pytest + Playwright
│
│ ═══════════ 模型双模式（项目根下的 4 类目录，核心设计）═══════════
│
├── text/                                      # 【MODE=shared】Junction → ComfyUI\models\text_encoders
│   └── Z-image_turbo-bf16\                       #   （MODE=portable 时本目录不使用，代码读 pretrained_models/）
├── unet/                                      # 【MODE=shared】Junction → ComfyUI\models\unet
│   └── Z-image_turbo-bf16\                       #   （全小写，禁止大写 UNet 混用，跨平台一致）
├── vae/                                       # 【MODE=shared】Junction → ComfyUI\models\vae
│   └── Z-image_turbo-bf16\
├── pretrained_models/                         # 【MODE=portable】便携模式内置真实模型（结构 1:1 镜像 ComfyUI）
│   ├── README.txt                             #   切换说明 & 拷贝 checklist
│   ├── text_encoders/                         #   ← qwen_3_Xb_fp8mixed.safetensors
│   ├── unet/                                  #   ← z_image UNet 权重（FP8）
│   ├── vae/                                   #   ← ae.safetensors
│   ├── loras/                                 #   ← LoRA 权重（最多 6 层叠加；含 Z-image_turbo-bf16 默认子目录）
│   ├── seedvr2/                               #   ← ★ SeedVR2 超分模型：ema_vae_fp16.safetensors + seedvr2_ema_3b_fp16.safetensors（★ 2 个必带，便携包不能漏）
│   ├── controlnet/                            #   ← N/A — 明确不做（工作流无 ApplyControlNet 节点），空目录保留以兼容 resolve_model_path()
│   └── checkpoints/                           #   ← N/A — 明确不做（引擎用 UNETLoader 而非 CheckpointLoaderSimple），空目录保留
│ ════════════════════════════════════════════════════════════
│
├── data/
│   ├── history.db
│   ├── uploads/                               # N/A — 明确不做（工作流无 img2img/ControlNet 参考图上传节点），空目录保留
│   ├── cache/                                 # 工作流 schema 与参数缓存（进程内原生引擎使用）
│   └── presets/                               # 预设 JSON 存储
├── outputs/                                   # 按 {engine}/{date} 组织输出图
├── workflows/                                 # 根级工作流备份（用户侧可拖拽放入）
│   └── Z_image_turbo.json                     # 【已存在】当前 Z-Image Turbo 工作流
├── logs/app.log
├── config.yaml                                # ★【已存在】完整双模式产品级配置（13 大模块）
├── pyproject.toml
├── requirements.txt
├── requirements-lock.txt
├── start.bat
└── Dockerfile
```

### 5.3 关键单例组件

| 组件 | 定义位置 | 设计参考 | 线程/协程安全 |
|------|---------|---------|--------------|
| `model_registry` | `model_registry.py` | Seedvr2 观察者 + RLock | threading.RLock |
| `engine_registry` | `engine_interface.py` | TTS_MultiModel 懒导入 + 双重检查锁 | threading.RLock |
| `app.state.model_manager` | `app_server.create_app()` | 两项目一致 | 内部用 registry 锁 |
| `app.state.task_queue` | `app_server.create_app()` | Seedvr2 单 Worker | asyncio 原生 |
| `app.state.history_db` | `app_server.create_app()` | Seedvr2 | aiosqlite 串行 |
| `event_bus` | `routes/system/sse.py` | Seedvr2 SSE 桥接 | asyncio.Queue |

---

## 6. 数据流程

### 6.1 引擎加载流程

```
用户点击「加载引擎」
    │
    ▼
[ModelManager.load_engine(engine_name)]
    │
    ├─► 1. 幂等检查：已加载 → 直接返回
    │
    ├─► 2. 声明式校验：
    │     ├─ engine 是否在 registry 元数据中
    │     ├─ workflow_file 是否存在
    │     └─ parameter_schema 是否可解析
    │
    ├─► 3. 显存预检：
    │     registry.vram_requirement × 1.5 → 与 gpu_utils.get_free_vram() 比较
    │     不足：告警 → 询问是否继续（仍可能 OOM）
    │
    ├─► 4. 进程内原生引擎初始化：
    │     复用 comfy_kernel 源码，准备加载模型权重
    │
    ├─► 5. yield 进度：
    │     ("正在初始化原生引擎…", 10%)
    │     ("正在校验模型文件…", 30%)
    │     ("准备就绪", 100%)
    │
    ├─► 6. model_registry.update_status(loaded=True, ...)
    │        └─► 触发观察者 → SSE 推送 model_status
    │
    └─► 异常：回滚到未加载状态（或切换前的引擎），yield error event
```

> 实现参考（A3）：ModelManager 安全切换 + 自动回滚完整迁移 Seedvr2 `model_manager.py#L58-L150` 的 `switch_engine()` 三阶段：保存 old_engine_ref → 尝试 unload+load new → 失败时 `unload(new); load(old);` 回滚并返回降级状态。详细 → 附录 C-A3。
> 实现参考（B4）：GPU 显存预检 ×1.5 峰值系数 + FP8 自动回退直接复用 Seedvr2 `model_manager.py#L141` 起的 `get_recommended_precision()` + `gpu_utils.check_vram_available(est=estimate*1.5)`；失败时先试 precision=fp8，再失败才报错。本项目扩展函数 `estimate_generation_vram(engine_id, width, height, chunk_size, lora_count, seedvr2_on, vram_reserve_gb)`。详细 → 附录 C-B4。

### 6.2 文生图任务流程

```
[前端] 用户填写表单 → 点击「生成」
  │ POST /api/generate/txt2img (form + hx-sse swap)
  ▼
[Route Handler]
  1. 参数校验（Pydantic GenerateRequest）
  2. 分配 task_id = ulid()
  3. 写入 history_db: status=pending
  4. task_queue.submit(task_id, coro_factory, on_cancel=engine.cancel)
  5. 返回 {task_id}
  │
  ▼
[TaskQueue Worker 串行取出]
  coro_factory() 执行 → engine.infer_txt2img(..., on_progress=...)
    │
    ├─► a. WorkflowManager.patch()
    │       读取 workflow.json + schema.yaml
    │       Step 1：mode 切换（LoRA 6 条 4→0 / SeedVR2 3 节点 / Eses 59 / VRAM 60）
    │       Step 2：link 重连（关闭 SeedVR2/Eses/VRAM 时 outputNode slot 改直连 VAEDecode id=12）
    │       Step 3：Patch 22 参数 widgets_values（含 3 个独立 INT_SEED_RANDOMIZE + width/height 双节点同步）
    │       【N/A 明确不做：ControlNet / img2img 节点（工作流完全无对应类型节点）】
    │
    ├─► b. 【N/A：工作流无外部参考图上传 → 本步骤空操作跳过】
    │
    ├─► c. NativeEngine.execute_inference(patched_workflow, batch_chunk_id)
    │       执行进程内推理
    │
    ├─► d. NativeEngine.listen_progress(callback)
    │       节点级进度回调 → 映射 % → on_progress({pct, phase, preview?})
    │         └─► event_bus → SSE task_status + preview
    │
    ├─► e. NativeEngine.get_output_images() → outputs/engine/date/xxx.png
    │
    ├─► f. watermark.embed() 数字水印嵌入
    │
    ├─► g. history_db.update():
    │       status=completed/failed, output_paths=[...], processing_time, config=JSON
    │
    └─► h. event_bus → SSE task_status:completed
          │
          ▼
    [前端 HTMX OOB swap] 输出区替换结果卡片 + 缩略图
```

### 6.3 数据存储与流转

```
SQLite history.db
├── tasks (主表)
│   ├── task_id (PK, TEXT)
│   ├── engine_name
│   ├── mode (txt2img|batch)              # 固定 txt2img（img2img N/A 明确不做，工作流无节点）
│   ├── status TEXT
│   ├── prompt TEXT
│   ├── negative_prompt TEXT
│   ├── generation_config JSON
│   ├── input_image_path TEXT NULL        # N/A，明确不做（img2img 无节点）；恒为 NULL
│   ├── thumbnail_path TEXT
│   ├── output_count INT
│   ├── processing_time_s REAL
│   ├── error_message TEXT NULL
│   ├── favorite INT DEFAULT 0
│   ├── created_at DATETIME
│   └── updated_at DATETIME
├── outputs (关联表，批次多张)
│   ├── id INTEGER PK
│   ├── task_id FK → tasks
│   ├── output_path TEXT
│   ├── format TEXT
│   ├── file_size_bytes INT
│   ├── width INT
│   ├── height INT
│   └── seed INT
├── tags
│   └── (task_id, tag) 联合主键
└── presets
    ├── id PK
    ├── engine_name
    ├── name
    ├── thumbnail NULL
    ├── config JSON
    └── created_at
```

---

## 7. 性能指标

### 7.1 应用启动性能

| 指标 | 目标值 | 备注 |
|------|--------|------|
| 冷启动到首页可交互 | ≤ 8s (SSD) / ≤ 15s (HDD) | 模型懒加载，不阻塞启动 |
| 启动时路由注册开销 | ≤ 500ms | pkgutil 自动发现，避免懒导入重型依赖 |
| 引擎元数据列表渲染 | ≤ 100ms | 仅读 registry._metadata，不触发实际导入 |

### 7.2 推理任务性能

| 指标 | 基线值 | 测试条件 |
|------|--------|---------|
| 任务提交 → 首个进度事件 (TTFP) | ≤ 3s | 后端空闲，已加载模型 |
| 任务完成 → 前端显示结果 | ≤ 完成后 500ms | 单张 ≤ 4MB PNG |
| 任务取消 → GPU 释放 | ≤ 5s | 原生引擎采样中断后 |
| 批量任务：队列调度开销 | ≤ 50ms / 任务 | 不含实际推理时间 |

> 注：**推理本身的速度取决于原生引擎（复用 ComfyUI 源码）、模型、GPU 型号**，不在本产品控制范围内。本产品只度量 I/O + 编排层面的"附加延迟"。

### 7.3 Web 交互性能

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| 页面首屏 HTML 体积 | ≤ 50KB (gzip) | 参考 Seedvr2 base.html 精简 |
| 首页系统状态刷新延迟 | ≤ 300ms | SSE 推送 + hx-swap |
| 历史 50 条分页加载 | ≤ 500ms | SQLite 分页查询 + 缩略图 |
| 参数面板表单控件响应 | ≤ 100ms | 原生表单 + 轻 JS，避免全量重绘 |

### 7.4 资源占用

| 项目 | 基线 |
|------|------|
| Python 进程空闲内存 (不含模型) | ≤ 800 MB |
| Python 进程空闲 CPU | ≤ 2% |
| SSE 单连接内存开销 | ≤ 50 KB |
| 上传缓存上限 | ≤ 500 MB，TTL 24h (同 Seedvr2) |

---

## 8. 安全要求

> 直接继承 [Seedvr2 README 安全章节](file:///C:/Users/Doro/Seedvr2/README.md#L138-L191) 与 [TTS_MultiModel SECURITY.md](file:///C:/Users/Doro/TTS_MultiModel/.github/SECURITY.md) 的条款。

### 8.1 网络绑定与认证 (CWE-306)

- **强制默认**：`server.host = 127.0.0.1`，禁止 UI 修改为 `0.0.0.0`；用户若需暴露必须手动改 yaml + 打印严重告警
- **Basic Auth 中间件**：若检测到 `SEEDVR2_AUTH_PASSWORD` 环境变量或 `security.auth` 配置，则全路由启用 Basic Auth
- **API Token**：REST API 额外支持 Bearer Token (同 TTS_MultiModel `api_auth`)
- **CORS 白名单**：默认仅允许 `http://127.0.0.1:{port}` 和 `http://localhost:{port}`

### 8.2 CSRF 防护 (CWE-352)

- 所有 POST/PUT/DELETE 表单端点：HTMX `hx-headers` 注入 CSRF Token
- 中间件 `CSRFMiddleware`：双提交 Cookie模式 + 签名 (参考两项目实现)
- 测试：`tests/test_csrf_integration.py`

> 实现参考（C1）：CSRF Double Submit Cookie 模式 + SSE GET 白名单直接照搬 Seedvr2 `middleware/csrf.py#L1-L98`：`CSRFMiddleware(BaseHTTPMiddleware)` + `SameSite=Strict` + `secrets.compare_digest` 防时序攻击 + `_SAFE_GET_PATH_PATTERNS` 正则放行 `/api/tasks/<id>/progress`、`/api/sse/events` 等只读 SSE/进度端点。详细 → 附录 C-C1。

### 8.3 速率限制 (CWE-770)

- 推理提交接口：`rate_limit_per_minute` 30 (同 Seedvr2)
- 上传接口：分块 + 单文件 100MB 上限
- 全局并发：任务队列 maxsize=100，拒绝新提交而非无界堆积

### 8.4 路径穿越防护 (CWE-22)

- `security.path_guard` 模块：
  - 所有文件操作路径必须位于 `allowed_base_dirs`（`outputs/`、`data/uploads/`、`workflows/`）
  - 解析 `..` 符号链接后检查规范化路径前缀
  - 测试：`tests/test_path_traversal.py`

> 实现参考（D1，安全关键）：PathGuard 白名单守卫完整迁移 Seedvr2 `security/path_guard.py#L1-L99` 的 Default Deny + `Path.resolve()`（解析所有 symlink / 反斜杠 / `..` / Unicode 编码）→ `parents` 包含判断；OSError/ValueError 一律视为不安全。本项目 allowed_base_dirs = `[pretrained_models/, workflows/, outputs/, data/, temp/, cache/]`（建议 config.yaml 显式列出）。所有 `open()`、`os.listdir()`、`shutil.*` 前必调 `path_guard.assert_safe(user_path)`。详细 → 附录 C-D1。

### 8.5 模型文件与完整性 (CWE-502)

- **优先 safetensors**：配置中声明的 Checkpoint 路径仅支持 `.safetensors`
- **pickle 告警**：若用户强制使用 `.pt`/`.bin`，启动与加载时打印严重安全告警（参考 Seedvr2）
- **核心模块完整性自检**：`security/integrity_manifest.json` + `integrity_selfcheck.py`，启动时比对核心文件 SHA256

### 8.6 输出溯源 (数字水印)

- 数字水印：`watermark.py` 实现 DCT 频域不可感知水印，嵌入 product_id + task_id + timestamp
- 验证脚本：`scripts/verify_watermark.py` 可提取溯源信息
- 强制接入：生成管线不可禁用水印（参考 TTS_MultiModel `watermark_enabled` 强制代码常量）

### 8.7 Content Security Policy

- `base.html` 顶部 `<meta http-equiv="Content-Security-Policy">`：
  ```
  default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  font-src 'self';
  img-src 'self' data: blob:;
  connect-src 'self' ws://127.0.0.1:* ws://localhost:*;
  ```
- `connect-src` 仅需允许本地回环 WS（无外部后端）

---

## 9. 兼容性标准

### 9.1 操作系统

| 平台 | 支持级别 | 备注 |
|------|---------|------|
| Windows 10/11 x64 | **Tier 1 (必须)** | WinPython 3.12 内置，一键脚本 |
| Ubuntu 22.04 / 24.04 | **Tier 2 (兼容)** | Dockerfile + start.sh |
| macOS (Apple Silicon) | **Tier 3 (尽力)** | MPS 后端 ComfyUI 可用性取决于 ComfyUI 版本 |

### 9.2 GPU 后端

| 后端 | 支持级别 | 最低 VRAM |
|------|---------|----------|
| NVIDIA CUDA (RTX 30xx+) | **Tier 1** | 8 GB (FP8 Z-Image Turbo) / 16 GB (FP16 Z-Image Turbo) |
| NVIDIA CUDA (RTX 20xx) | **Tier 2** | 需 `--lowvram` 选项 |
| AMD ROCm | **Tier 3** | 依赖 ComfyUI ROCm 分支 |
| CPU (无 GPU) | 不推荐 | 仅用于调试界面，不用于实际推理 |

### 9.3 Python 与依赖

- **Python 版本**: 3.12+（与两参考项目对齐）
- **核心依赖锁定**：`requirements-lock.txt`（参考 Seedvr2），支持 `pip install --require-hashes`
- **关键依赖版本约束**：
  ```
  fastapi>=0.110,<0.116
  uvicorn[standard]>=0.27
  pydantic>=2.5
  jinja2>=3.1
  aiofiles>=23.2
  aiosqlite>=0.20
  httpx>=0.27
  websockets>=12
  pillow>=10.0      # 缩略图/水印
  numpy>=1.26
  ```

### 9.4 原生引擎（ComfyUI 源码）兼容性

| ComfyUI 版本 | 兼容性 |
|-------------|--------|
| latest (HEAD 滚动) | 主要测试目标 |
| ≥ v0.1.0 (正式 tag) | 兼容保证下限 |
| ComfyUI-Manager 扩展目录结构 | 兼容 models/ 扫描 |

### 9.5 浏览器支持

| 浏览器 | 最低版本 |
|--------|---------|
| Chrome / Edge / Chromium | 120+ |
| Firefox | 124+ |
| Safari | 17+ |

> 要求支持：HTMX 1.9+ / WebSocket / CSS Variables / CSS `clamp()` / `content-visibility`

### 9.6 Schema 向后兼容

- 工作流 JSON 和参数 Schema 使用 SemVer：`workflow_version` 字段
- Patcher 遇到未知字段按默认值处理并告警，不崩溃
- Schema 目录允许 `{engine_name}_v{major}.yaml` 并存，引擎配置指向具体版本

---

## 10. 部署模式与便携包发布

> **【设计背景】** 当前开发阶段，本机硬盘只有一套 ComfyUI 模型源 → 使用 **Junction 符号链接** 共享；
> 发布给用户或拷到新机器（U 盘/便携硬盘/离线部署）→ **必须物理内嵌模型**，整个文件夹双击即用。
> 两种模式通过 `config.yaml → models.model_source_mode` 一键切换，**代码零修改**。

### 10.1 两种模式对比

| 维度 | **shared（开发共享模式）** | **portable（便携内置模式）** |
|------|---------------------------|----------------------------|
| 适用阶段 | 本机开发 / 联调 / 已有 ComfyUI | 发布版 / U 盘分发 / 新机器离线部署 / Docker 镜像 |
| 模型存储位置 | 外部 ComfyUI `C:\Users\...\ComfyUI\models` | 项目内 `pretrained_models/` |
| 项目根 `text/` `unet/` `vae/` | Windows **Junction 符号链接** → 指向 ComfyUI 对应目录 | 不使用（代码直接从 `pretrained_models/` 读） |
| 切换方式 | `model_source_mode: "shared"` | `model_source_mode: "portable"` |
| 硬盘占用 | 零冗余（共享 ComfyUI，约省 57~66 GB） | 全量拷贝（Z-Image Turbo 所需模型） |
| 启动速度 | 稍快（模型已预热，若 ComfyUI 常开） | 略慢（首次从内置目录扫描） |
| 新增模型 | ComfyUI 那侧加了，本项目自动看见 | 需把新模型拷进 `pretrained_models/` |
| 可移植性 | ❌ 不可（依赖外部路径） | ✅ 完全可移植，整个目录压缩后可发任何机器 |
| 安全自检 | 跳过模型完整性检查（信任 ComfyUI） | 启动时扫描 `pretrained_models/` 做 SHA256 完整性校验（可选） |

### 10.2 路径解析层（核心代码抽象）

在 `bin/integrated_app/config_models.py` 中实现 **统一模型路径解析器** `resolve_model_path()`：

```
config.yaml → models.model_source_mode = "shared" | "portable"
                    │
                    ▼
         resolve_model_path(model_type, sub_path)
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
    MODE = shared          MODE = portable
  ↓ 拼接路径：            ↓ 拼接路径：
  shared.comfy_models_dir + pretrained_models.internal_models_dir
  mount_map[model_type]  + sub_dirs[model_type]
  + sub_path              + sub_path
          │                    │
          └─────────┬──────────┘
                    ▼
        返回单一绝对路径（Path 对象）
        （向上层业务代码屏蔽 MODE 差异）
```

- **引擎加载、工作流校验、工作流 Patch、LoRA 扫描**，所有需要访问模型文件的代码
  **必须唯一通过本函数**，严禁在代码中硬编码相对路径或写死 `pretrained_models/`。
- 测试：`tests/test_model_path_resolver.py` 覆盖 shared / portable 两种模式 + 边界 case（路径穿越字符、非 allowed_base_dirs）。

### 10.3 目录命名规范（强制）

为实现「Windows ↔ Linux Docker ↔ macOS」三端互通，目录名必须遵守：

| 路径 | 强制大小写 | 说明 |
|------|-----------|------|
| 项目根 `text/` | 全小写 | **禁止**写成 `Text/` 或 `TEXT/` |
| 项目根 `unet/` | 全小写 | **禁止**写成 `UNet/` 或 `UNET/`（历史遗留易错） |
| 项目根 `vae/` | 全小写 | **禁止**写成 `VAE/` 或 `Vae/` |
| `pretrained_models/text_encoders/` | 与 ComfyUI 同名 | 保持 ComfyUI 原生命名，方便直接 drag-and-drop 拷贝 |
| `pretrained_models/unet/` | 与 ComfyUI 同名 | ← |
| `pretrained_models/vae/` | 与 ComfyUI 同名 | ← |

> 原因：Windows NTFS 大小写**不敏感**，但 Linux ext4 / Docker / WSL2 / macOS APFS（可选严格模式）
> 大小写**敏感**。混用 `UNet/` 与 `unet/` 在 Windows 下一切正常 → 打包上 Docker 后立即
> `FileNotFoundError`，排查成本极高，**必须从源头统一全小写**。

### 10.4 符号链接（Junction）维护脚本

`scripts/setup_symlinks.ps1`（shared 模式运维），功能：

1. **检测模式**：读 `config.yaml`，若非 `shared` 则告警并退出
2. **检测目标存在**：校验 `shared.comfy_models_dir` 路径可读
3. **按 mount_map 建立链接**：对 `text` / `unet` / `vae` / `lora` / `controlnet` / `checkpoint`
   每项执行：
   - 如已存在且是 Junction → 跳过
   - 如已存在且是普通目录（里面有模型文件）→ 询问用户是否重命名为 `*_待删除` 后缀
   - 如不存在 → `New-Item -ItemType Junction` 创建
4. **校验**：创建完成后列出每个链接下的文件数 + 大小，给出「可安全删除 _待删除 目录约 XXX GB」
5. **可逆**：支持 `-Uninstall` 参数移除所有 Junction（仅拆链接，不动 ComfyUI 源）

### 10.5 便携包打包发布流程（标准操作手册）

发布前必走的 7 步 Checklist（对应 `scripts/pack_portable.ps1` 自动化）：

```
┌─ STEP 1：关闭应用实例，释放文件句柄
│
├─ STEP 2：切换 config.yaml
│    models.model_source_mode:  "shared"  →  "portable"
│    server.host: 保持 127.0.0.1 即可（禁止改成 0.0.0.0 发外网）
│    原生引擎固定复用 comfy_kernel 源码，无需外部后端配置
│    environment.HF_HUB_OFFLINE: 保持 "1"（断网不报错）
│
├─ STEP 3：复制模型进 pretrained_models/（按子目录）
│    Copied 66.11 GB (1 engine)
│    ├── text_encoders/    (Z-Image: qwen_3_4b_fp8_mixed)
│    ├── unet/             (Z-Image: zimageTurboNSFW FP8)
│    ├── vae/              (FLUX AE: ae.safetensors)
│    ├── loras/            (可选，用户常用 LoRA 集)
│    └── seedvr2/          (SeedVR2 超分模型：ema_vae_fp16 + ema_3b)
│
├─ STEP 4：内嵌 Python 环境（WinPython）与原生引擎源码
│    ├── python-3.12.embed/    或 WinPython 整个目录（约 1.8 GB）
│    ├── comfy_kernel/   （原生引擎复用源码，不包含 models）
│    └── requirements-lock.txt  →  pip install --require-hashes  确保依赖哈希一致
│
├─ STEP 5：清理开发期残留
│    $ del /s /q data\cache\*          （删除工作流 object_info 缓存）
│    $ del /s /q data\uploads\*        （删除开发期上传的 img2img 参考图）
│    $ del /s /q logs\*                （删除开发日志，避免泄漏本机路径）
│    $ del /q  text\  unet\  vae\      （删除 Junction 外壳；portable 模式不用它们）
│    $ del /q  *.pyc  __pycache__\     （删除 Python 字节码）
│
├─ STEP 6：打包与完整性校验
│    7z a -t7z -m0=lzma2 -mx=7 Image_MultiModel_v1.0.0_portable.7z .\
│    #   （推荐 7-Zip 固实压缩 + NTFS 硬链接去重；66 GB 模型压完约 62 GB）
│    #   （可选）分卷：-v4500m → 每张 DVD5 / 每个 U 盘 FAT32 限制
│    #   生成 .sha256 校验文件
│
└─ STEP 7：在「干净新机器」上做冒烟验收
     1. 解压到非中文路径 (例 D:\Image_MultiModel\)
     2. 双击 start.bat → 应在 15s 内弹出浏览器并显示首页
     3. 引擎列表应显示唯一引擎（Z-Image Turbo），状态灯「未加载」
     4. 点「加载 Z-Image Turbo」→ 30s 内 model_status:loaded
     5. 输入 prompt 生成 1 张 → 完整 PNG 输出 + 历史入库
     6. 关闭 → 进程全部退出无残留
     7. 以上全部通过 → 标记 Portable Build = QA Pass
```

### 10.6 Docker 镜像发布（Linux 服务器部署）

当发布目标为 Linux GPU 服务器（工作室/实验室集群）时，使用 Docker 模式：

```yaml
# docker-compose.yml（示意，M6 阶段完善）
services:
  img_multimodel:
    image: registry.corp.local/image-multimodel:v1.0.0
    runtime: nvidia
    environment:
      NVIDIA_VISIBLE_DEVICES: "0"
      MODELS_SOURCE_MODE: "portable"    # 镜像内模型用 COPY 内嵌 / 或 mount 共享 volume
    volumes:
      - ./pretrained_models:/app/pretrained_models:ro   # （可选）模型 volume 挂载替代 COPY
      - ./data:/app/data
      - ./outputs:/app/outputs
    ports:
      - "8288:8288"
    restart: unless-stopped
```

- Docker 镜像中**推荐用 volume 单独挂载模型目录**，这样模型更新时不用重打镜像。
- 镜像基础层 `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`（与两参考项目保持一致）。

### 10.7 FR 条目（验收依据）

| 编号 | 需求 | 验收方式 |
|------|------|---------|
| FR-10.1 | `resolve_model_path()` 在 shared / portable 双模式下返回正确且同语义的 Path | `tests/test_model_path_resolver.py` 双模式 + 6 种 model_type 全绿 |
| FR-10.2 | 开发模式 shared：删除 Junction 后运行 `setup_symlinks.ps1` 可一键重建 6 个链接 | 手动脚本 + 列出文件大小匹配 |
| FR-10.3 | 便携模式 portable：断网 + 卸掉外部 ComfyUI 硬盘，仅存 `pretrained_models/` 仍可完整推理 | 集成验收场景矩阵 I-16：离线便携模式 |
| FR-10.4 | 打包脚本生成的 7z 在新机器解压后，start.bat 首启无报错、无 Missing File | QA Checklist STEP 7 (1-7) 100% 通过 |
| FR-10.5 | 路径解析层在任何模式下都拒绝 `..` / 绝对盘符穿越（由 `security.path_guard` 联合拦截） | `tests/test_path_traversal.py` 新增 portable 模式 case |
| FR-10.6 | 目录全小写规范：CI lint 脚本扫描整个项目不得出现根目录 UNet/（大写 U）等违规命名 | `tests/ci/lint_dirnames.py` 扫描仓库 |

> 实现参考（E1）：WinPython 便携包启动脚本 + CUDA 内存分配器加固直接迁移 Seedvr2：
> - **`bin/clean_launch.py`** 顶部三行 `setdefault` 原样抄：`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` + `PYTORCH_ALLOC_CONF=expandable_segments:True` + `PROJECT_ROOT` 计算 + `sys.path.insert(0, PROJECT_ROOT)` + `os.chdir(PROJECT_ROOT)`；CUDA expandable_segments 将 batch 9999 的 OOM 概率降低约 40%（PyTorch 官方推荐），必须开启。
> - **启动脚本**：`start.bat` 结尾调用 `python bin\clean_launch.py`（而非直接 `python -m ...`）；流程三阶段：加载 WinPython env → 检查 `pretrained_models/` 关键文件存在性（缺失时友好红提示不崩溃）→ 启动 App。详细 → 附录 C-E1。

---

## 11. 开发与测试里程碑

### 11.1 里程碑总览 (M0~M6)

```
M0 ──────────► M1 ──────────► M2 ────────────► M3 ────────────► M4 ────────────► M5 ────────────► M6
 项目骨架       ComfyUI适配     txt2img核心工作台    高级功能扩充      批量+素材库       UI/UX+设置      性能+安全+发布
 (2周)          (3周)           (4周)            (2周)             (2周)             (2周)            (3周)
 总 16 周 ≈ 4 个月（与原计划总时长一致，范围收缩到 txt2img 后把空间留给 5 语言 & 批次 9999 稳定性）
```

### 11.2 各里程碑交付物

#### M0 - 项目骨架 + 双模式配置落地 (Week 1-2) ✅ 当前已完成部分
- 参考项目结构复刻：`bin/integrated_app/` 各模块空壳
- **`config.yaml` 13 大模块落地**（含 `models.model_source_mode` + 唯一引擎声明 + 原生引擎 + 水印 + server + i18n）
- `pretrained_models/` 7 个子目录（text_encoders/unet/vae/loras/...） + README.txt 共享/便携切换说明
- `workflows/` 收纳唯一的工作流 JSON（Z-Image Turbo）
- 路由自动发现 + SSE 事件总线 + SQLite 初始化
- `pyproject.toml` / `requirements.txt` / `ruff + mypy + pytest`
- 启动脚本 `start.bat` / `install.bat` / WinPython 集成
- 测试：`conftest.py` + 健康检查 API 绿
- **验收点**：浏览器打开首页看到 Seedvr2 风格空壳；`config.yaml` 解析不报错

#### M1 - 原生引擎适配层 + Workflow Patcher（覆盖 26 节点 + mode 切换/link 重连/batch 拆分） (Week 3-5)
- `native/source.py`：把 `comfy_kernel` + aki-v3 自定义节点源码注入 `sys.path`（幂等）
- `native/workflow.py`：**严格按 2.4.4 节点映射表 + 4.3 Schema YAML** 实现 Workflow Patcher（必做 6 步）
  1. 深拷贝 workflow.json 副本（不污染原文件）
  2. **mode 切换**（6 LoRA 4→0、SeedVR2 3 节点 on→0/off→4、Eses 77、VRAM 78）
  3. **link 重连**（关闭 SeedVR2/Eses/VRAM 时，改写 `links[]` 数组改接 VAEDecode 直通）
  4. **widgets_values 精确 patch**：22 参数 + 3 个独立 INT_SEED_RANDOMIZE（推理/超分/显存各一）+ width/height 双节点同步
  5. **seed 随机化：** -1 替换为真实值并分别写入 3 个 seed 字段
  6. **batch chunk 拆分**：`internal_chunk_size=16`，开 SeedVR2 自动降至 4
- `native/engine.py`：NativeEngine 实现 `ImageEngine` 协议 `infer_txt2img()` 单方法（不做 infer_img2img，1.6 已明确不做），复用 `comfy.sd` / `comfy.samplers` 完成 加载→CLIP编码→采样→VAE解码
- 单引擎生命周期管理 + 健康心跳（30s）
- **集成测试**：Mock 验证 26 节点 patch + mode 切换 + link 重连 + chunk=16 拆分 + batch=9999 拆分 625 次 + LoRA 6 层权重注入 + SeedVR2 resolution 2048 注入 + ReservedVRAM 0.6GB 注入
- **验收点**：单元测试覆盖率 ≥ 70%；Mock 可完整跑通 batch_size=9999 拆分→合并→历史入库；LoRA 6 层 + SeedVR2 + Eses + VRAM 4 大开关 on/off 组合 Patcher 输出 JSON 结构 100% 正确（通过 snapshot 比对）

#### M2 - 引擎注册 + 文生图工作台全功能 (Week 6-9) ⭐ M2 目标 = 全部必做功能交付
- `engine_interface.py` ImageEngine Protocol + `InMemoryEngineRegistry`
- `model_manager.py` / `model_registry.py` 生命周期 + 观察者桥接 SSE
- `task_queue.py` 单 Worker 串行 + 取消回调（9999 批次中取消也能立即停止当前 chunk）
- **生图工作台页面**：单 Tab txt2img，参数卡片 **6 组手风琴式（基础 8 / LoRA 6 / SeedVR2 / 对比+显存 / 输出）**，严格对齐 2.4.2 表
  - 8 大基础：正/负 Prompt + cfg=1.0/steps=8/width=1024/height=1024/seed=-1/**batch_size=1~9999**
  - LoRA 6 层：下拉（_disabled + pretrained_models/loras 目录递归） + 权重滑块 -2.0~+2.0；默认值严格与 JSON widgets_values 一致（Z-Image Turbo 1.0 / 亚洲人像 0.7/0.5/0.4/0.3 /  0.2）；缺失文件自动 _disabled + 黄提示
  - SeedVR2 超分：开关 on/off + 分辨率 1024/1536/**2048**/3072/4096 + 色彩校正 lab + 独立 upscale_seed
  - 对比 + 显存：enable_eses_compare on/off + axis horizontal + enable_vram_reserve on/off + 0.6GB + mode=auto + 独立 vram_seed
  - batch_size UI：±1/±10/±100 步进；> 500 黄 ⚠、> 5000 红 ⚠ + 二次确认；进度条：chunk 进度 % + 超大批次底部「已生成 X/9999」
- **i18n 5 种语言（简中/繁中/英/日/韩）**：每个 locale YAML ≥ 200+ 翻译键 100% 非空覆盖
  - 测试：`test_i18n_coverage.py` 校验 LoRA 子卡 12 参数 + SeedVR2 4 参数 + Eses + VRAM 共 26 新参数名/说明/错误提示 5 语全覆盖
- 预设保存 / 加载 / 导入 / 导出 JSON（**包含 LoRA 6 层 + SeedVR2 + Eses + VRAM 全部 22 参数，不含 seed**）
- **验收点**：对接真实原生引擎
  1. Z-Image Turbo 文生图 1 张（全开 SeedVR2 + Eses + VRAM）= 出 original + upscaled + compare 3 张 PNG ✓
  2. LoRA 全开（6 层）vs 全关（_disabled）：LoRA 全开明显风格变化；参数完整写入 generation_config ✓
  3. SeedVR2 off→on：off 仅出 original；on 出 upscaled 2048×2048，无明显伪影，≤ 10s/张 ✓
  4. Eses off→on：off 不出 compare；on 出 compare 左右横排拼接 ✓
  5. VRAM off→on：关闭时 generation_config.vram.mode 标记 off；开启时 GPU 预留 =0.6GB（监控显示） ✓
  6. batch_size=9999（开超分 chunk=4）：2499 次 chunk 100% 通过 ✓
  7. 5 语言切换无遗漏 ✓
  8. 取消响应 < 5s ✓

#### M3 - 未来工作流扩展（暂不规划，等用户提供新的含 img2img/ControlNet 节点的工作流再补充）(Week 10-11)
> **M3 规划留空**：当前工作流 JSON 中不存在图生图 (LoadImage/VAEEncodeForInpaint) + ControlNet (ApplyControlNet/Preprocessors) 节点，按 v1.3 边界规则**明确不做**。仅保留 M3 时间窗口给用户未来新增工作流节点时的实现位置。
- **验收点**：当用户提供含 img2img/ControlNet 节点的新工作流 JSON 时，按 v1.3 判定规则重新规划 M3 条目。

#### M4 - 批量推理 + 历史记录 + 素材库 (Week 12-13)
- Prompt 文件批量（`.txt` / `.csv` 导入）
- Grid Search 参数笛卡尔积（**6 维度：steps/cfg/width/height/lora_i_strength/batch_size**，数量预测提示 500/5000 双阈值弹窗）
- HistoryDB 完整 CRUD + 搜索 + 筛选 + 分页；output_image_paths 字段三层结构 `{original/upscaled/compare}` 分页存储
- 历史详情侧栏：**22 参数完整展示**（8 基础 + LoRA 6 层 + SeedVR2 + Eses + VRAM） + 3 图预览 + 重绘 + 保存预设
- 批量导出 ZIP（original/upscaled/compare 可选分别导出） + 按时间清理策略（天数/GB 双阈值）
- 收藏 + 标签系统
- **验收点**：1000 条测试数据历史页加载 < 500ms；重绘成功率 100%（seed + 22 参数一致 = 像素级一致）；开启 SeedVR2 时 Grid Search lora_i_strength × cfg 组合 = 20 张 → 输出 60 张（20×3 份）结构正确

#### M5 - UI/UX + 设置 + 可访问性 (Week 14-15)
- 首页仪表盘：4 列系统状态卡（GPU / 引擎 / 内存 / 运行时长）+ 最近任务缩略图 8 张（默认取 compare 缩略图）
- 系统状态页：GPU / 内存 60 条曲线图 + 引擎 / 后端状态列表 + LoRA 资源扫描（loras 目录存在性红/绿灯，2 引擎默认 LoRA 缺失自动黄提示）
- 设置页：引擎管理 Tab / 后端管理 Tab / 偏好（默认 SeedVR2/Eses/VRAM on/off）/ 资源扫描（text_encoders/unet/vae/LoRA 6 默认 4 类）
- 深浅主题切换（防闪烁：`base.html` CSS 变量 preload 脚本）
- Status Bar 固定底栏 + 超大批次「X/Y」进度（超大 batch=9999 + SeedVR2 时显示剩余小时预估）
- **验收点**：Playwright E2E 截图比对参考项目视觉规范，WCAG AA 对比度通过

#### M6 - 性能基准 + 安全审计 + 便携包发布 (Week 16-18)
- 性能基准（第 7 章所有指标跑通）：TTFP / 推理吞吐（开超分 vs 关超分对比）/ 首帧延迟
- 安全审计：`test_path_traversal.py` / `test_csrf_integration.py` / `test_security.py`
- 完整性自检清单 + 数字水印验证脚本（original/upscaled/compare 三份分别嵌入水印）
- Dockerfile + `docker-compose.yml`
- **便携包 QA**：按 10.5 节 7 步 Checklist 全通过（冒烟 7 步 + 离线 I-19，便携包必须附带 SeedVR2 ema_vae_fp16 + seedvr2_ema_3b_fp16 两个超分模型到 pretrained_models/）
- **验收点**：所有 P0/P1 用例 100% 通过，安全扫描 Critical = 0，便携包 7z 哈希校验 OK

---

## 12. 验收标准

### 12.1 功能验收 (Functional Acceptance)

**每个「FR-x.x.x」需求项必须同时满足：**
1. 存在至少 1 个单元测试 / 集成测试覆盖正向路径
2. 存在至少 1 个 Playwright E2E 用例验证端到端交互
3. 错误路径（参数非法 / 引擎加载失败 / OOM）：返回结构化错误 JSON，前端展示用户友好消息，应用不崩溃

> 实现参考（F1）：pytest + Playwright 双轨测试体系 1:1 迁移 Seedvr2 `tests/`：
> - **pytest（逻辑层）**：`test_model_manager_switch_with_rollback()`（A3）、`test_task_queue_on_cancel_kills_comfy_thread()`（B1）、`test_path_guard_14_attacks()`（D1）、`test_config_models_roundtrip()`、`test_csrf_signed()`、`test_integrity_selfcheck()`
> - **Playwright E2E（UI 层）**：`tests/pages/*.page.ts`（页面对象模式：IndexPage / SettingsPage / HistoryPage / GeneratePage）+ `tests/specs/i18n.spec.ts`（5 语言切换无刷新无闪烁）+ `tests/specs/lora_stack.spec.ts`（6 层滑杆全 0→全开→全关）+ `tests/specs/batch_9999.spec.ts`（提交→取消→断点续跑）+ `tests/specs/sse.spec.ts`（事件推送顺序正确）+ `wcag-contrast-test.js`（自动比对 WCAG AA 对比度）。详细 → 附录 C-F1。

### 12.2 集成验收 (Integration Acceptance)

使用真实硬件 + 原生引擎执行如下场景矩阵（**I-1~I-19 中除标注「明确不做（1.6 边界规则）」外，全部为 M0~M2 必过**）：

| # | 场景 | 预期结果 |
|---|------|---------|
| I-1 | 首次启动 → 自动打开浏览器首页 | ≤ 15s 内渲染完成 |
| I-2 | 注册 + 连接本地 ComfyUI | 健康灯绿色，`/system_stats` 正常返回 |
| I-3 | 加载真实引擎（Z-Image Turbo）| Z-Image Turbo ≤ 30s 加载完成；SSE model_status:loaded 均推送 |
| I-4 | 引擎 txt2img 生成 1 张（默认全开：SeedVR2 2048 + Eses compare + VRAM 0.6GB + LoRA 6 层默认权重）| 输出 3 份 PNG：original (1024×1024) + upscaled (2048×2048) + compare (拼接横排 4096×2048)；history generation_config 22 参数与提交完全一致；同一 seed 重绘像素级一致（hash 同） |
| **I-5** | **超大批次：batch_size=9999**，单条 Prompt，SeedVR2=on | chunk=4 × 2499 次提交 100% 成功；输出 9999 张 original + 9999 张 upscaled + 9999 张 compare（共 29997 张）全部可读；中途点击「取消」< 5s 停止当前 chunk；断点续跑 100% 补齐剩余；seed 无重复 |
| **I-6** | **LoRA 6 层叠加**：Z-Image Turbo，加载工作流默认 LoRA 6 层（ 1.0 / 亚洲人像 0.7/0.5/0.4/0.3 /  0.2）vs LoRA 6 层全选 `_disabled` | 生成对比两张（同一 seed=12345）：LoRA 开 6 层 = 亚洲人像风格明显 +  效果叠加；LoRA 全关 = 基础模型风格；两种结果 22 参数分别写入 generation_config；LoRA 缺失某文件 → 自动 _disabled + 黄提示 UI 正常显示 |
| **I-7** | **SeedVR2 超分**：关闭（仅 original）→ 1024 → 开启（2048）→ 开启（4096） | off → 仅出 original（1024×1024，无 upscaled）；on@2048 → upscaled 严格 2048×2048，无黑边/伪影，单张 ≤ 10s；on@4096 → upscaled 严格 4096×4096； upscale_seed 相同 → 两张 4096 超分细节 hash 一致（可复现）|
| **I-8** | **EsesImageCompare 双图对比**：off → on（horizontal）→ on（vertical/slider） | off → SaveImage 仅保存 SeedVR2 输出单图（无 compare 文件）；on horizontal → compare.png 宽=2×宽（左右横排）；on vertical → 高=2×高（上下竖排）；on slider → slider_pos=0.5 JSON 字段写入 compare_axis |
| **I-9** | **ReservedVRAMSetter 显存预留**：off → on@0.6GB → on@2.0GB | off → GPU 预留前后 < 100MB 差别；on@0.6GB → 原生引擎侧显存监控 + 预留值差值 ≤ 10%；vram_reserve_seed=固定值时，不同推理种子下 ReservedVRAMSetter 内部分配逻辑固定；Patcher 关闭 VRAM 时 link 由 VAEDecode id=12 → outputNode slot 1 直通 |
| **I-10** | **5 语言切换全覆盖（简中→繁中→英→日→韩→简中）**| 无样式崩坏；所有字符串翻译覆盖（测试脚本 200+ key 100% 非空）；LoRA 子卡 12 参数 + SeedVR2 4 参数 + Eses + VRAM 新参数提示 5 语全部正确；超大批次红/黄警告文案 5 语均与 UI 实际阈值对齐 |
| I-11 | 批量 txt2img：20 条 Prompt CSV + batch_size=5，总计 100 张（SeedVR2=on）| 300 份 PNG 全部成功或单独失败不阻塞；失败 1 条可一键重试仅该条（不含未失败项）；「预计生成数=300」与实际数一致 |
| I-12 | 生成中（Z-Image Turbo，steps=8，batch_size=32 + SeedVR2 on，执行到第 4 chunk）点击「取消」| 原生引擎 5s 内中断成功；SeedVR2 显存 ≤ 3s 内释放回基线 < 6GB；任务 status=cancelled |
| I-13 | 历史详情页点击「重绘此图」（原记录 seed=12345 + LoRA 6 层全默认 + SeedVR2=2048 + Eses on + VRAM=0.6）| 新任务 22 参数与原记录字节级一致；original hash 同；upscaled hash 同；compare hash 同（像素级一致）|
| I-14 | 预设导出为 JSON → 删除该预设 → 重新导入 JSON | 所有字段完整还原（cfg/steps/width/height/batch_size/LoRA 6 层×2/SeedVR2 4 项/Eses 2 项/VRAM 4 项/引擎名/正负 Prompt；不含 seed） |
| I-15 | 引擎加载 → 卸载 → 重新加载，来回两次 + 每次切换各生成 1 张 | 两次切换无显存泄漏（GPU 差值 < 1GB）；LoRA 下拉自动切换引擎对应子目录（Z-image）；第三次引擎 SSE model_status:loaded；回滚机制：手动移走 bf16 模型 → 加载失败自动回滚 + 红 UI 错误提示不崩溃 |
| I-16 | 深色主题 ↔ 浅色主题切换 | 无样式崩坏；CSS 变量全部正确应用；WCAG AA 对比度通过 |
| I-17 | 重启应用（重启前有 1 条进行中 SeedVR2 任务 + 3 条 pending 队列含 2 条 LoRA）| 进行中任务标记 interrupted_at_reboot；pending 3 条入队；22 参数 + 原始 seed 100% 不丢失；generation_config 无字段截断 |
| I-18 | 水印验证脚本：100 张随机输出（每个 original / upscaled / compare 分别 33~34 张）| 300 张 100% 能提取正确的 product_id；compare 拼接图的 2 个水印（左/右或上/下）均能提取且一一对应 |
| **I-19** | **便携模式离线验收**：改 `model_source_mode=portable`，移除 text/unet/vae Junction，模拟拔掉 LoRA + SeedVR2 超分模型源盘（确保 pretrained_models/loras + text_encoders + unet + vae + SeedVR2 模型全在内部），重新启动 + Z-Image Turbo 生成 1 张（全开 SeedVR2 + Eses + VRAM + LoRA 默认 6 层）| 从启动到出图全程不报 FileNotFound；所有路径均从 `pretrained_models/` 读取；3 份 PNG 正常输出；LoRA 默认 6 层全部命中（不触发 _disabled 黄提示）；SeedVR2 加载成功；generation_config.path_mode 标记 portable |

| ════════ 下列场景为 N/A（明确不做，工作流 JSON 完全无对应节点，1.6 边界判定表已写明） ════════ |
| N/A-1 | 图生图 img2img / Inpaint：参考图上传 + denoise 0.5 | 不做（无 LoadImage / VAEEncodeForInpaint / SetLatentNoiseMask 节点）|
| N/A-2 | ControlNet 全链路（canny/depth/openpose 预处理 + 参考图 + ApplyControlNet）| 不做（无 ControlNetLoader + ApplyControlNet 节点）|
| N/A-3 | 普通 lanczos 缩放预览（ImageScaleToTotalPixels + PreviewImage）| 不做（SeedVR2 是启用的超分路径且 mode=4 且链路空，用户未提供对应启用节点）|

### 12.3 性能验收 (Performance Acceptance)

对第 7 章所有指标执行基准：
- **达标**: ≥ 90% 指标达到目标值，且无低于基线值 80% 的项
- **可接受**: ≥ 80% 指标达标，且关键路径（TTFP / 取消响应）达标
- **不达标**: 关键路径任一不达标 → 必须修复

### 12.4 安全验收 (Security Acceptance)

- **OWASP Top 10 自动化扫描**（ZAP / Nikto）：无 Critical / High 级别告警
- **自定义安全测试套件**（两项目共 80% 用例可直接复用）：100% 通过
  - CSRF / Path Traversal / RateLimit / Basic Auth / API Token
  - 完整性自检失败场景（手动篡改 manifest）
  - pickle `.pt` 文件加载告警

### 12.5 兼容性验收 (Compatibility Acceptance)

- Windows 11 + Chrome 125 + RTX 4090 (24GB) 环境：I-1 ~ I-15 全绿
- Windows 10 + Edge 124 + RTX 3090 (24GB) 环境：I-1 ~ I-15 全绿
- Ubuntu 24.04 Docker 部署 + RTX 4090：I-1 ~ I-10 通过（含 batch=9999）
- 最低显存 RTX 3060 (12GB) + FP8 Z-Image Turbo：I-3 / I-4 通过（自动 FP8 回退）
- 5 种语言浏览器环境（系统语言为繁中/日/韩时首次启动自动匹配）：UI 默认语言正确

### 12.6 可维护性验收 (Maintainability)

- **代码质量**：Ruff 0 error；Mypy app_layer 0 error；Black 格式化一致
- **测试覆盖**：`app_layer`（`bin/integrated_app` 排除 comfy 纯 I/O 与引擎）覆盖率 ≥ 60%
- **文档**：每个引擎新增仅需添加 `workflows/X.json` + `schemas/X.yaml` + `config.yaml` 声明，无需改代码
- **日志**：所有关键路径（加载 / 提交 / 完成 / 失败 / 取消）INFO 级日志，异常含 traceback

---

## 附录 A：与参考项目代码复用映射表

| 本项目模块 | 复用来源 | 复用比例 | 修改说明 |
|-----------|---------|---------|---------|
| `app_server.py` | Seedvr2 + TTS | 80% | 增加原生引擎初始化 |
| `model_registry.py` | Seedvr2 | 95% | 单引擎原生设计，无后端 ID 字段扩展
| `model_manager.py` | Seedvr2 | 60% | load/unload 改为 NativeEngine 语义 |
| `task_queue.py` | Seedvr2 | 95% | 几乎不变 |
| `history_db.py` | Seedvr2 | 80% | 表结构扩展 outputs/presets |
| `middleware/*` | TTS + Seedvr2 | 90% | 合并 RequestID / RateLimit / CSRF |
| `security/*` | Seedvr2 | 90% | 更新 product_id 常量 |
| `static/css` / `fonts` | Seedvr2 | 95% | 品牌色替换 |
| `templates/base.html` | Seedvr2 | 90% | CSP 扩展 WS 白名单 |
| `i18n.py` / `locales/` | 两项目各半 | 80% | 新增生图专用翻译键 |
| `gpu_backend.py` / `gpu_utils.py` | TTS | 85% | 去除 MPS 专用分支（图像依赖 CUDA 更强） |
| `config.py` | Seedvr2 | 70% | Pydantic 模型扩展 models.engines |
| **`config_models.py`（新增）** | TTS engines 注册语义 + 自建双模式 | 20% 复用 / 80% 新增 | 新增 `resolve_model_path()`：MODE=shared/portable 统一路径解析层；EngineConfigPydantic 模型；allowed_base_dirs 联合校验 |
| **`config.yaml`（骨架已落地）** | 两项目结构合并 | 字段级 60% 复用 | 新增 13 大模块：双模式切换段 `models.shared / models.portable`、原生引擎配置、图像推理参数 `inference.*`、水印、模型命名规范 |
| **`scripts/setup_symlinks.ps1`（新增）** | 本项目独创 | 0% | Junction 创建/重建/移除 + 模式检测 + 备份重命名询问 |
| **`scripts/pack_portable.ps1`（新增）** | 本项目独创 | 0% | 一键切换模式 + 复制模型 + 清理开发残留 + 7z 打包 + SHA256 |
| **`scripts/verify_watermark.py`（新增）** | TTS watermark.py 逆向 | 40% 复用 | DCT 频域水印提取 + 控制台报告溯源 ID |

> 预计整体代码复用率：**原 70% → 调整为 ≈ 62%**（新增 ~38%：双模式路径解析层、Junction/打包运维脚本、原生引擎适配层、图像生图业务）。

---

## 附录 B：参考项目关键文件索引

**Seedvr2 架构参考**：
- [README.md](file:///C:/Users/Doro/Seedvr2/README.md) - 产品定位与功能清单
- [app_server.py](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/app_server.py) - FastAPI 生命周期与路由发现
- [model_manager.py](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/model_manager.py) - 模型加载/切换/回滚
- [model_registry.py](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/model_registry.py) - 单例 + 观察者 + SSE 桥接
- [engine_interface.py](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/engine_interface.py) - ABC 抽象接口
- [task_queue.py](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/task_queue.py) - 单 Worker + 取消回调
- [config.yaml](file:///C:/Users/Doro/Seedvr2/config.yaml) - 配置字段模板
- [base.html](file:///C:/Users/Doro/Seedvr2/bin/integrated_app/templates/base.html) - 主题防闪烁 + i18n 注入

**TTS_MultiModel 参考**：
- [README.md](file:///C:/Users/Doro/TTS_MultiModel/README.md) - 声明式引擎抽象与产品形态
- [engine_interface.py](file:///C:/Users/Doro/TTS_MultiModel/bin/integrated_app/engine_interface.py) - Protocol + InMemoryEngineRegistry + 懒导入
- [model_manager.py](file:///C:/Users/Doro/TTS_MultiModel/bin/integrated_app/model_manager.py) - PreloadService / PersonaWarmupService / 热待机判断
- [config.yaml](file:///C:/Users/Doro/TTS_MultiModel/config.yaml) - 声明式 engines 配置范式
- [app_server.py](file:///C:/Users/Doro/TTS_MultiModel/bin/integrated_app/app_server.py) - 中间件顺序 / 路由自动发现

**本项目（Image_MultiModel）已落地文件**：
- [config.yaml](file:///C:/Users/Doro/Image_MultiModel/config.yaml) - 13 大模块双模式产品级配置（models.model_source_mode / inference / watermark 等）
- [PRD.md](file:///C:/Users/Doro/Image_MultiModel/PRD.md) - 本文档，v1.1 新增部署模式章节
- 工作流 JSON：[Z_image_turbo.json](file:///C:/Users/Doro/Image_MultiModel/workflows/Z_image_turbo.json)
- [pretrained_models/README.txt](file:///C:/Users/Doro/Image_MultiModel/pretrained_models/README.txt) - portable 模式切换说明与拷贝 Checklist

---

## 附录 C：参考项目代码级迁移清单（14 项 — v1.3 新增）

> **用法说明**：
> - 本附录对应正文中 14 处「实现参考（C-xx）」短标记，读者在 FR 段看到即可翻到对应条目获取完整迁移说明。
> - 迁移等级：⭐ 一级（完整 copy，改类名/文件路径即可）；⭐⭐ 二级（结构 copy，约 30% 代码需适配本项目）；⭐⭐⭐ 三级（参考思路，需大量重写）。
> - 「12.2 编号」列：每项可直接验证的集成验收场景（如 I-15），对应 §12.2 集成验收矩阵行号。

---

### C.1 解耦架构层（3 项：A1 / A2 / A3）

| 编号 | 借鉴点 | 来源文件与行号 | 迁移等级 | 为何适合本项目 | 本项目迁移要点 | 12.2 编号 |
|------|--------|--------------|:--------:|--------------|--------------|:---------:|
| **A1** | 基于 `Protocol` 的引擎抽象层 + `InMemoryEngineRegistry` 声明式注册 + 懒导入 | TTS：`engine_interface.py#L34-L200` | ⭐ 一级 | 当前 §4.2 仅写了 ImageEngine 伪代码，缺少声明式协议定义 + 引擎注册表运行时动态发现；懒导入可避免启动时加载原生引擎（复用 ComfyUI 源码）heavy 依赖，冷启动提速 30%+ | 1) 新建 `bin/integrated_app/engine_interface.py`；2) `@runtime_checkable class ImageEngine(Protocol)` 声明 4 方法：`is_ready()`、`load(EngineLoadConfig)→Generator[tuple[str,float\|None]]`、`unload()`、`async infer_txt2img(...)→ImageInferenceResult`、`cancel()`；3) `InMemoryEngineRegistry` 实现：`register(engine_id, factory_fn, lazy=True)`、`get(engine_id)→ImageEngine`、`list_available()→list[EngineMeta]`；4) engines 模块 `__init__.py` 中用懒导入装饰器注册 `z_image_turbo_native`；5) 单元测试 `test_engine_registry_ext.py` 用例：协议鸭子类型 `isinstance(obj, ImageEngine)` 通过。 | I-3 |
| **A2** | 观察者模式桥接 `ModelRegistry → SSE`（状态变更解耦广播） | Seedvr2：`app_server.py#L62-L73` | ⭐ 一级 | 当前 §6.1 仅写了「触发观察者 → SSE 推送 model_status」一行，但未说明具体桥接机制如何避免循环 import；直接 copy 可确保 ModelRegistry（核心层）不依赖 SSE（表现层）。 | 1) 在 `model_registry.py` 中实现 `add_listener(callback_fn: Callable[[str,dict],None])`、`remove_listener(...)`、`_notify_listeners(event_name, payload)`；2) 在 FastAPI lifespan 中注册 `model_registry.add_listener(_bridge_model_status_to_sse)`；3) 触发事件：`model_loading`、`model_loaded`、`model_unloaded`、`model_switch_started`、`model_switch_rolled_back`。 | I-3 / I-15 |
| **A3** | `ModelManager.switch_engine()` 三阶段安全切换 + 异常自动回滚 | Seedvr2：`model_manager.py#L58-L150` | ⭐ 一级 | 桌面端用户切换引擎频率高（卸载/重载 Z-Image Turbo）；若切换失败（模型文件缺失 / CUDA OOM）无回滚保护，会导致服务 degraded 无法再生成 | 1) 三阶段：① `old = self.engine` 保存引用 ② `try: unload(old); load(new);` ③ **失败捕获**：`except (ModelLoadError, InsufficientVRAMError, FileNotFoundError)` → `unload(new) + load(old)` 回滚；2) 每步调 `registry.update_status(...)` 触发 A2 SSE；3) pytest `test_model_manager_switch_with_rollback()`：成功 → 失败回滚 → 成功 3 次切换。 | I-15 |

---

### C.2 任务与推理可靠性层（4 项：B1 / B2 / B3 / B4）

| 编号 | 借鉴点 | 来源文件与行号 | 迁移等级 | 为何适合本项目 | 本项目迁移要点 | 12.2 编号 |
|------|--------|--------------|:--------:|--------------|--------------|:---------:|
| **B1** | 单 Worker 任务队列 + `on_cancel` 取消回调（解决 `asyncio.to_thread` 同步推理无法被 Python 取消的硬伤） | Seedvr2：`task_queue.py#L12-L150`（`CancelCallback` #L29、`submit` #L96、`request_cancel` #L125） | ⭐ 一级 | **本项目 batch 9999 + SeedVR2 超分单次时长可达数小时**；若取消只能 kill 进程，GPU 资源锁死桌面卡死；原生引擎为进程内同步采样，无法被 Python 协程直接取消 → 必须注入 `on_cancel=bridge.request_cancel()` 调 `NativeEngine.cancel()`（设置采样取消标志） | 1) 新建 `bin/integrated_app/task_queue.py` **完整 copy Seedvr2 ~150 行**（三常量 + TaskQueue 类）；2) `submit` 保留 `on_cancel: CancelCallback \| None = None` 参数；3) `NativeEngine.cancel(self)` 实现：① 设置内部 `threading.Event.cancel_flag` → ② 中断当前进程内采样 → ③ 释放 GPU / 清理未启动 chunk；4) pytest `test_task_queue_on_cancel_kills_comfy_thread()`：模拟 60s 推理，2s 取消 → **断言 ≤ 5s GPU 显存回基线（<6GB 空闲）**。 | I-5 / I-11 / I-12 |
| **B2** | Worker 异常自动重启（最多 3 次）+ 有界队列防 OOM | Seedvr2：`task_queue.py#L32-L82` | ⭐ 一级 | 原生引擎（复用 ComfyUI 源码）偶发 `CUDA illegal memory access` 会把 worker 打死不重启；同时 batch 9999 用户重复点提交 20 次会爆内存 | 1) 三常量 **原样抄**：`DEFAULT_QUEUE_MAXSIZE=100`、`DEFAULT_TASK_TIMEOUT_SECONDS=3600`、`MAX_WORKER_RESTARTS=3`；2) `_worker_guarded()` 中超过重启阈值 → `logger.critical + stop()`；3) Queue Full 立即 HTTP 429 "队列已满，请稍后"。 | I-5 / §8.3 |
| **B3** | `HistoryDB` SQLite（WAL + FTS5）+ 崩溃恢复两阶段（先 `cleanup_stale_tasks` 再 `recover_tasks`） | Seedvr2：`history_db.py#L65-L137` + `app_server.py#L165-L178` | ⭐⭐ 二级（结构 copy，字段改成本项目 Image 语义） | §2.7.2 仅写了"超大批次 checkpoint 续跑"，未写**全局崩溃恢复**：重启时 processing 状态卡死任务必须先标 interrupted_at_reboot 再决定是否续跑；否则历史表会出现"processing 永远进行中"脏数据 | 1) `TaskRecord` 新增 `interrupted_at_reboot: bool = False`；2) `initialize()` 执行：① `PRAGMA journal_mode=WAL` ② `PRAGMA synchronous=NORMAL` ③ `PRAGMA busy_timeout=30000` ④ CREATE TABLE + FTS5 trigger；3) lifespan 启动：先 `UPDATE status='cancelled' WHERE status IN ('processing','pending') AND updated_at < NOW()-1h`（清理卡死）→ 再若 `auto_recover=true` 从 interrupted_at_reboot 记录按 generation_config 恢复 task，seed 不变保证可复现。 | I-5 / I-17 |
| **B4** | GPU 显存预检 ×1.5 峰值系数 + FP16→FP8 自动回退 + chunk 智能推荐 | Seedvr2：`model_manager.py#L141` `get_recommended_precision()` + `gpu_utils.check_vram_available(est * 1.5)` | ⭐⭐ 二级（估算公式适配 5 大开关组合：LoRA/SeedVR2/Eses/VRAM/batch） | batch 9999 + SeedVR2 显存峰值是估算的 1.2~1.8×；无预检会中途 OOM，前期进度全损。config.yaml 已有 `vram_multisample_rule=1.5` 但未落地 | 1) 新增 `estimate_generation_vram(engine_id, w, h, chunk, lora_cnt, seedvr2_on, vram_reserve_gb)→(required_gb, available_gb, recommended_chunk, recommended_precision)`；2) 公式：`base = engine.vram_gb + (w*h*3*4/1e9)*chunk*1.1 + lora_cnt*0.15 + (seedvr2_on? max(w,h)/1024*6.0 : 0) + vram_reserve_gb`；`required = base * 1.5`；3) 不足时先试 precision=fp8（×0.6）仍不足 → 推荐 `chunk = chunk // 2` 递归；4) UI 提交前预检弹窗："预估 XGB > 可用 YGB，建议 chunk=Z / FP8 精度 / 关 SeedVR2" + 3 按钮（强制继续 / 自动调整 / 取消）。 | I-4 / I-7 / I-5 |

---

### C.3 Web 层（3 项：C1 / C2 / C3）

| 编号 | 借鉴点 | 来源文件与行号 | 迁移等级 | 为何适合本项目 | 本项目迁移要点 | 12.2 编号 |
|------|--------|--------------|:--------:|--------------|--------------|:---------:|
| **C1** | `CSRFMiddleware` Double Submit Cookie + SameSite=Strict + `secrets.compare_digest` 防时序攻击 + SSE GET 白名单 | Seedvr2：`middleware/csrf.py#L1-L98` | ⭐ 一级 | §8.2 仅写了"双提交 Cookie"一行；若不完整实现，会出现 SSE 进度端点被拦截导致前端进度条不更新、HTTPS 环境 Secure 漏设导致浏览器拒收等坑 | 1) 新建 `bin/integrated_app/middleware/csrf.py` **完整 copy 98 行**；2) `_SAFE_GET_PATH_PATTERNS` 适配：`/api/tasks/<id>/progress`、`/api/sse/events`、`/api/outputs/download/*`；3) pytest `test_csrf_signed.py`：无 cookie/header 403 / 正确 200 / SSE 通。 | §8.2 / NFR-安全 |
| **C2** | 统一 SSE 事件总线（单 TCP 多路复用 8 类事件 + `: ping` 注释心跳 15s + 标准事件帧格式） | TTS：`routes/sse.py#L44-L120`（`SSEEvent` + `SSEEventBus` + `_format_sse_frame`） | ⭐ 一级 | §2.9.1 写了 8 类事件但未规定单连接多路复用；若前端 progress/model_status/gpu_status/queue_status 各开一条 EventSource，会打满浏览器同域 6 连接上限 → 普通 HTTP 请求排队超时 | 1) 新建 `bin/integrated_app/routes/sse.py` **完整 copy TTS 结构**：`SSEEvent(type,data={},id=None,retry=3000)`、`SSEEventBus(max_queue=1000)`（15s 心跳双常量）、`_SSE_HEARTBEAT_COMMENT = ": ping\n\n"`；2) `GET /api/sse/events` 返回 StreamingResponse，每个连接领独立 asyncio.Queue；3) 前端只创建**一个** EventSource，`addEventListener('task_status',fn)` 分派；4) 15s 注释心跳（客户端完全忽略），防 Nginx 60s idle 断链。 | §7（SSE 单连接 ≤50KB）/ I-10 |
| **C3** | `VersionedStaticFiles(StaticFiles)` 差异化 Cache-Control（CSS/JS no-cache / 字体 30d / 图片 1d） | Seedvr2：`app_server.py#L76-L105` | ⭐ 一级（零改动 copy） | Bootstrap CSS ~160KB、Instrument Serif woff2 ~80KB × 4 字重；无缓存控制 → 每次刷新重下首屏慢 1~2s；字体中期缓存可提速 80%；CSS/JS no-cache 保证开发时热更新有效 | 1) 在 `app_server.py` 中 copy `class VersionedStaticFiles(StaticFiles):` 类 30 行；2) `app.mount('/static', VersionedStaticFiles(directory='bin/integrated_app/static'), name='static')`；3) DevTools Network 验证：woff2 有 `max-age=2592000`（30d）、app.css 有 `no-cache`、png 有 `max-age=86400`（1d）。 | §7（首屏 ≤ 15s）/ I-1 |

---

### C.4 安全层（1 项：D1 — 安全关键，CWE-22 最后防线）

| 编号 | 借鉴点 | 来源文件与行号 | 迁移等级 | 为何适合本项目 | 本项目迁移要点 | 12.2 编号 |
|------|--------|--------------|:--------:|--------------|--------------|:---------:|
| **D1** | `PathGuard` 路径白名单守卫（Default Deny + `Path.resolve()` 解析所有 symlink/反斜杠/`..`/Unicode/NUL + `parents` 包含判断） | Seedvr2：`security/path_guard.py#L1-L99` | ⭐ 一级（完整 copy，仅改配置来源） | 本项目大量用户可控路径访问：① 历史下载 `/outputs/download?path=xxx.png` → `../../Windows/System32/cmd.exe`；② LoRA 目录扫描；③ 输出目录设置 → 必须白名单守卫。Seedvr2 实现已覆盖所有 Windows 绕过手段（反斜杠、盘符、symlink 跳转、混大小写、NUL、`....//` 变体）。 | 1) 新建 `security/path_guard.py` **完整 copy 99 行**；2) 初始化来源：**config.yaml 显式声明** `security.allowed_base_dirs = ["pretrained_models/", "workflows/", "outputs/", "data/", "temp/", "cache/"]`（内部自动 resolve 转绝对）；3) 全局单例 `path_guard = PathGuard(...)`；4) **强制合规**：所有 `open()` / `os.listdir()` / `shutil.*` 调用前必调 `path_guard.assert_safe(path)`（抛 400）；5) pytest `test_path_guard_14_attacks.py` 覆盖 14 类攻击样例 → **全部拒绝**。 | §8.4 / FR-10.5 |

---

### C.5 可维护性与发布层（2 项：E1 / E2）

| 编号 | 借鉴点 | 来源文件与行号 | 迁移等级 | 为何适合本项目 | 本项目迁移要点 | 12.2 编号 |
|------|--------|--------------|:--------:|--------------|--------------|:---------:|
| **E1** | `clean_launch.py` 启动加固：`expandable_segments:True` CUDA 分配器（减少碎片 OOM 约 40%）+ `chdir(PROJECT_ROOT)`（防双击 bat 时 CWD 错） | Seedvr2：`app_server.py#L25-L42`（3 行 `setdefault`） + `bin/clean_launch.py` + `start.bat` 结尾 | ⭐ 一级（copy 即可） | **batch 9999 连续 3h+ 生图时 PyTorch 默认 Best-Fit 分配器碎片 OOM 高发**。`expandable_segments` 是 PyTorch 2.1+ 官方推荐方案，降 OOM 约 40%。另外 `os.chdir(PROJECT_ROOT)` 避免双击 start.bat 时 CWD=`C:\Windows\System32` 找不着模型的经典坑。 | 1) 新建 `bin/clean_launch.py` **顶部 6 行原样抄**：`os.environ.setdefault('KMP_DUPLICATE_LIB_OK','TRUE')` + `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` + `PYTORCH_ALLOC_CONF=expandable_segments:True` + `PROJECT_ROOT` 计算 + `sys.path.insert(0,PROJECT_ROOT)` + `os.chdir(PROJECT_ROOT)`；2) 末尾 `from bin.integrated_app.app_server import main; main()`；3) `start.bat` 调用 `python bin\clean_launch.py`（禁止直接 `-m ...`）；4) 冒烟测试：`echo $env:PYTORCH_CUDA_ALLOC_CONF` 应用进程内为 `expandable_segments:True`。 | I-19 / I-5 |
| **E2** | i18n JSON 文件 + 短代码（zh/zh-tw/en/ja/ko）+ base.html `<head>` 同步阻塞防闪烁脚本（零 FOUC） | TTS：`locales/{zh,zh-tw,en,ja,ko}.json`（目录结构） + Seedvr2 `templates/base.html` `<head>` 首段同步脚本 | ⭐⭐ 二级（与 PRD 原 FR-2.11.1 的长代码 YAML 方案冲突，现在统一迁移到更优的 JSON + 短代码 + 映射展示） | **您是资深 UX/UI 设计师，对闪烁零容忍**：默认 HTML 先渲染 body 默认中文 → JS 再替换成韩文的经典 FOUC 必须消灭。防闪烁方案是在 `<head>` 任何样式之前同步阻塞设置 `data-lang`，CSS 用属性选择器先占位文本，HTMX 正式替换后再加载翻译。短代码比 BCP-47 长代码更易维护。 | 1) **翻译文件统一改为 JSON + 短代码**：`bin/integrated_app/locales/{zh,zh-tw,en,ja,ko}.json`（每个 ≥200 键）；UI 展示名用映射表 `locale_map = { "zh-CN":"zh", "zh-TW":"zh-tw", "en-US":"en", "ja-JP":"ja", "ko-KR":"ko" }` 内部转短代码（对外仍展示 BCP-47 全名，符合 §2.11.1 对外规范）；2) `templates/base.html` **`<head>` 第一行**（在任何 `<link rel=stylesheet>` 之前）插入同步阻塞脚本：```<script>!function(){try{var l=localStorage.getItem('lang')||(navigator.language||'en').toLowerCase();var m={'zh-cn':'zh','zh-hans-cn':'zh','zh-tw':'zh-tw','zh-hant-tw':'zh-tw','en-us':'en','ja-jp':'ja','ko-kr':'ko'};l=m[l]||'en';var t=localStorage.getItem('theme')||'auto';document.documentElement.setAttribute('data-lang',l);document.documentElement.setAttribute('data-theme',t)}catch(e){document.documentElement.setAttribute('data-lang','en');document.documentElement.setAttribute('data-theme','auto')}}();</script>```；3) Playwright `specs/i18n.spec.ts`：切韩文 → 拍首屏 → 与默认中文首屏像素对比 → **差异率=0%**（任何"先闪中文再切韩文"的 UX 瑕疵会出现像素差异，测试自动失败）。 | I-10 / §3 UI UX |

---

### C.6 测试层（1 项：F1 — pytest 逻辑层 + Playwright UI 层双轨）

| 编号 | 借鉴点 | 来源文件与行号 | 迁移等级 | 为何适合本项目 | 本项目迁移要点 | 12.2 编号 |
|------|--------|--------------|:--------:|--------------|--------------|:---------:|
| **F1** | pytest（逻辑层，覆盖率 ≥70%）+ Playwright E2E（UI 层）双轨体系；页面对象模式（Page Object）；场景 spec 粒度；WCAG 自动对比度脚本 | Seedvr2：`tests/`（`test_task_queue.py` / `test_model_manager.py` / `test_csrf_signed.py` / `test_path_guard.py` + `playwright.config.ts` + `pages/base.page.ts` / `index.page.ts` / `settings.page.ts` + `specs/i18n.spec.ts` / `specs/sse.spec.ts` + `wcag-contrast-test.js`） | ⭐⭐ 二级（copy 结构 + 改本项目场景）；§11.2 M0 已写 pytest ≥70% 验收点 | PRD §12.1 仅写了"每个 FR 要有单元 + E2E"，未给具体测试清单 + 文件分组。Seedvr2 经过多轮迭代的测试体系可直接避免"覆盖率 <30% 导致一改就崩"。 | **pytest 最小必测集**（9 项）：① `test_engine_interface_protocol.py` 鸭子类型检查；② `test_model_manager_switch_with_rollback.py`（A3 3 场景）；③ `test_task_queue_on_cancel_kills_comfy_thread.py`（B1 取消 5s 回基线）；④ `test_history_db_recovery.py`（B3 cleanup/recover 双阶段）；⑤ `test_csrf_signed.py`（C1 6 种绕过全 403）；⑥ `test_path_guard_14_attacks.py`（D1 14 种路径攻击全拒绝）；⑦ `test_vram_estimation_fallback.py`（B4 ×1.5 系数 + FP8 回退边界）；⑧ `test_clean_launch_env.py`（E1 3 个环境变量在子进程均设置）；⑨ `test_generation_config_hash.py`（重绘 I-13 seed/LoRA/SeedVR2/Eses/VRAM 全参数 → generation_config hash 固定）。<br><br>**Playwright E2E 最小必测集**（6 spec + 1 脚本）：① `pages/` 页面对象：IndexPage（仪表盘）、GeneratePage（含 `set_lora_layer(i,name,strength)`、`set_seedvr2_resolution(px)`、`click_generate()` → 返回 `Promise<TaskCompletedEvent>`）、HistoryPage（`open_detail`/`click_redraw`）、SettingsPage（`switch_lang(code)`）；② `specs/lora_stack.spec.ts`（LoRA 6 层全 0 / 全默认 / 全开 2.0 三态滑杆快照）；③ `specs/i18n.spec.ts`（5 语切换循环 × 首屏像素差异率=0 防闪烁 × 翻译键 100% 非空）；④ `specs/batch_9999.spec.ts`（提交 → 1s 取消 → status=cancelled + 5s 内 GPU 回基线；红/黄警告文案 5 语均与阈值对齐）；⑤ `specs/sse.spec.ts`（model_load 事件顺序 loading→loaded + UI 指示灯）；⑥ `specs/seedvr2_eses_vram.spec.ts`（4 大开关 off/on 组合，断言 Eses compare 文件存在性与 VRAM 预留值误差 ≤10%）；⑦ `wcag-contrast-test.js`（Playwright 截所有 Tab → 遍历文本元素计算对比度 → ≥ WCAG AA：小字 4.5:1 / 大字 3:1，输出报告 CSV）。 | §12.1 / I-6 / I-10 / I-13 / I-12 / I-16 / I-7 / I-8 / I-9 |

---

*— 文档结束 —*
