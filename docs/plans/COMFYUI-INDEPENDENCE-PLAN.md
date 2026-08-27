# 脱离 ComfyUI 迁移计划（记忆文档）

> 记录日期：2026-08-13 （更新：2026-08-14）
> 状态：**内核已归于 `comfy_kernel/`，运行时不依赖 `references/`**（后续逐步把内核独立成单独项目）

## 一、目标

本项目的最终目标是**完全脱离 ComfyUI**，形成像 Seedvr2 那样自包含、单进程推理、可独立分发的版本。

- **运行时**：不依赖外部 ComfyUI 进程（8188 服务），也不依赖本机任何 ComfyUI 安装路径。
- **模型**：独立运行时模型统一放在项目内 `pretrained_models/`。
- **复用源码**：`native/` 引擎复用的 Comfy 源码即为项目内 `comfy_kernel/`（Vendor 进来的独立推理内核源码），后续可将它**独立成一个单独项目**（可独立维护、供应），本项目不再以 `references/` 形式持有克隆。

## 二、当前状态（2026-08-14）

| 项 | 状态 | 说明 |
|----|------|------|
| Z-Image Turbo 原生出图 | ✅ 可用 | 进程内 `import comfy.*`，不连 8188 |
| 复用内核源码位置 | `comfy_kernel/` | 由原 `references/ComfyUI` 迁移而来，项目内真实目录（保留其独立 git 仓库），新环境装好依赖即可用 |
| `config.yaml → comfy_source_dir` | ✅ 已改 | `comfy_kernel`（相对项目根），`native/engine.py` 拼成绝对路径（Gotcha #16） |
| `native/source.py` 默认根 | ✅ 已改 | `_PROJECT_ROOT / "comfy_kernel"` |
| `native/seedvr.py` 默认源码根 | ✅ 已改 | `comfy_kernel/custom_nodes/ComfyUI-SeedVR2_VideoUpscaler`（未 Vendor 时缺文件报错清晰） |
| 本机绝对路径硬编码（aki） | ✅ 已移除 | `seedvr.py` 不再引用 `C:\Users\Doro\APP\ComfyUI-aki-v3\...` |
| `references/` 剩余内容 | 纯学习参考 | CLIP / diffusers / Fooocus / InvokeAI / generative-models / sd-webui-controlnet / stable-diffusion-webui，均未直接使用，**可安全删除** |
| `pack_portable.ps1` | 需核对 | STEP 4 已改为 `references/ComfyUI` → 应指向 `comfy_kernel/` |

## 三、模型摆放约定（唯一清晰口径）

运行时只认一个模型来源（`resolve_engine_model_paths`）：

- **`portable` 模式**（独立运行/分发）：`config.yaml → models.portable.internal_models_dir` = `pretrained_models/`。
- **`shared` 模式**（开发/复用外部）：`config.yaml → models.shared.comfy_models_dir`。

> 项目根目录**不再允许**出现 `text/`、`unet/`、`vae/` 等模型链接目录，避免误导模型摆放。

## 四、可复用 / 待独立内容

| 目录 | 用途 |
|------|------|
| `comfy_kernel/` | Comfy 推理内核源码（`comfy/` 等），`native/` 进程内复用；已 Vendor 进项目，**不依赖 `references/`** |
| `references/`（CLIP / diffusers / Fooocus / InvokeAI 等） | 其它参考实现（暂未直接使用，纯学习） |

> 后续计划：把 `comfy_kernel/` 提炼为一个**独立、可单独维护的 Comfy 推理内核项目**，供本项目和其它项目复用。

## 五、后续待办（TBD）

- [x] 将运行时依赖的 `references/ComfyUI` 迁移为项目内 `comfy_kernel/`，`references/` 仅剩可删除的学习仓库。
- [ ] 将 `comfy_kernel/` 需要的核心代码提炼为独立项目（模型加载 / 采样 / VAE / 文本编码）。
- [ ] 完全自研或依赖独立内核，移除对本仓库 `comfy_kernel/` 的引用。
- [ ] 权重复制：SeedVR2（6.9GB，超分用）等按需复制进 `pretrained_models/seedvr2/`。
- [ ] `pack_portable.ps1` STEP 4 确认复制 `comfy_kernel/`（而非 `references/ComfyUI`）。
- [ ] 切换 `model_source_mode` 到 `portable` 的自动化与独立打包验证。

## 六、备注

- 超分（SeedVR2）阶段暂缓，当前聚焦 Z-Image Turbo 图像生成。
- 本文件为记忆文档，供后续会话延续该计划。