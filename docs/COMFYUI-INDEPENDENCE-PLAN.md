# 脱离 ComfyUI 迁移计划（记忆文档）

> 记录日期：2026-08-13
> 状态：**规划中**（已清理遗留，后续逐步脱离）

## 一、目标

本项目的最终目标是**完全脱离 ComfyUI**，形成像 Seedvr2 那样自包含、单进程推理、可独立分发的版本。

- **运行时**：不依赖外部 ComfyUI 进程（8188 服务），也不依赖本机任何 ComfyUI 安装路径。
- **模型**：独立运行时模型统一放在项目内 `pretrained_models/`。
- **复用源码**：目前 `native/` 引擎复用的 Comfy 源码，后续将**独立成一个单独项目**（可独立维护、供应），本项目不再持有。

## 二、当前状态（2026-08-13）

| 项 | 状态 | 说明 |
|----|------|------|
| Z-Image Turbo 原生出图 | ✅ 可用 | 进程内 `import comfy.*`，不连 8188 |
| 复用 Comfy 源码位置 | `references/ComfyUI` | 项目内真实目录（非链接），新环境装好依赖即可用 |
| 引擎分发 | ✅ 已修 | [app_server.py](bin/integrated_app/app_server.py) worker 按 `backend` 分发 `NativeEngine` / `ComfyEngine` |
| `comfy_source_dir` 相对路径 | ✅ 已修 | `native/engine.py` 相对路径拼 `cfg.project_root` 为绝对路径（Gotcha #16） |
| 根目录 Junction（text/unet/vae） | ✅ 已删除 | 遗留链接，运行时从未使用，已清理 |
| `pack_portable.ps1` | ✅ 已改 | STEP 3 直接读 `shared.comfy_models_dir` 拷贝，不再依赖根目录链接 |
| `setup_symlinks.ps1` | ✅ 已退役 | 运行时不再需要根目录 Junction |

## 三、模型摆放约定（唯一清晰口径）

运行时只认两个模型来源（`resolve_engine_model_paths`）：

- **`shared` 模式**（开发/复用外部）：`config.yaml → models.shared.comfy_models_dir`（当前指向 aki 的 `models/`）。
- **`portable` 模式**（独立运行/分发）：`config.yaml → models.portable.internal_models_dir` = `pretrained_models/`。

> 项目根目录**不再允许**出现 `text/`、`unet/`、`vae/` 等模型链接目录，避免误导模型摆放。

## 四、可复用 / 待独立内容（集中在 `references/`）

`references/` 是"可复用、待独立成项目"的源码集中地：

| 目录 | 用途 |
|------|------|
| `references/ComfyUI` | ComfyUI 核心源码（`comfy/` 等），currently `native/` 进程内复用 |
| `references/CLIP` / `diffusers` / `generative-models` / `Fooocus` / `InvokeAI` / `stable-diffusion-webui` 等 | 其它参考实现（暂未直接使用） |

> 后续计划：把 `references/ComfyUI` 提炼为一个**独立、可单独维护的 Comfy 推理内核项目**，供本项目和其它项目复用。

## 五、后续待办（TBD）

- [ ] 将 `references/ComfyUI` 需要的核心代码提炼为独立项目（模型加载 / 采样 / VAE / 文本编码）。
- [ ] 完全自研或依赖独立内核，移除对本仓库 `references/ComfyUI` 的引用。
- [ ] 权重复制：SeedVR2（6.9GB，超分用）等按需复制进 `pretrained_models/`。
- [ ] 切换 `model_source_mode` 到 `portable` 的自动化与独立打包验证。

## 六、备注

- 超分（SeedVR2）阶段暂缓，当前聚焦 Z-Image Turbo 图像生成。
- 本文件为记忆文档，供后续会话延续该计划。