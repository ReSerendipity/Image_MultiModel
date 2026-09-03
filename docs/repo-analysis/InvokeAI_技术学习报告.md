# InvokeAI 技术学习报告（Image_MultiModel 竞品对标 · 代码级）

> **性质**：竞品对标学习报告（非建议文档）。事实来自 `C:\Users\Doro\reference_repos\Image_MultiModel\InvokeAI` 浅克隆（`--depth 1`）+ `gh api` 实时核验。
> **核验**：`invoke-ai/InvokeAI` — **28,122★ / Apache-2.0 / Python** / `pushed_at=2026-09-01`（当日活跃）。

## 一、概览
- **定位**：专业级创意引擎（Stable Diffusion 系），工业级 WebUI，多个商业产品的基座。
- **许可**：**Apache-2.0**——与 Image_MultiModel 主体同许可证，可自由借鉴代码结构，**无 GPL 传染风险**（区别于 ComfyUI 内核）。
- **活跃度**：高，当日仍有提交。

## 二、技术栈（README + 仓库结构）
- 运行时：Python；本地托管 Web 服务 + **React UI**（README 原文 "industry-leading React UI"）。
- 架构：**节点化（Node-Based Architecture）** + Workflows 管理；**Unified Canvas** 集成画布（支持 in/out-painting、笔刷工具）。
- 模型管理：Model Manager / Embedding Manager；支持 `ckpt` / `diffusers` / 部分 `gguf`。

## 三、核心能力
- **统一画布（Unified Canvas）**：文生图 / 图生图 / 局部重绘一体化创作协作。
- **工作流与节点**：可组合、可分享的节点式生成管线。
- **画廊与看板（Board & Gallery）**：拖拽式资产管理 + 富元数据回溯（prompt/参数可召回）。
- **模型支持极广**（README 列举）：SD1.5/SD2/SDXL/SD3.5/Flux.1 全系/**Flux.2 Klein(4B/9B)**/**Z-Image Turbo**/**Z-Image Base**/Qwen Image/Qwen Image Edit/Ideogram 4/ERNIE-Image 等；另含 Wan(API)、SAM/SAM2 分割。

## 四、与 Image_MultiModel 对标点（关键）
- **直接命中 Z-Image 主线**：InvokeAI 已原生支持 **Z-Image Turbo** 与 **Z-Image Base**——与 Image_MultiModel 的 Z-Image 主线完全一致，是「Z-Image 官方能力 → WebUI 集成」的现成参照（模型加载、diffusers 管线、参数映射）。
- **Flux.2 Klein**：InvokeAI 支持 Flux.2 Klein 4B/9B——与用户本地 ComfyUI 运行的 Flux2 Klein(9B fp8) 对应，可借鉴其推理封装。
- **节点式 Workflow 范式**：与 Image_MultiModel 的 `comfy_kernel` 工作流思路可对照（但 InvokeAI 自研节点引擎，非 ComfyUI）。
- **量化 / gguf 支持**：与 Image_MultiModel 的 fp8/gguf 量化路线呼应。

## 五、许可与合规
- Apache-2.0：代码可借鉴；但模型权重（SDXL/Flux 等）各有独立许可，须按本仓 `THIRD_PARTY_NOTICES.md` 登记——与现有合规框架一致，无新增风险。

## 六、可借鉴点（P0/P1）
- **P0**：Z-Image / Flux.2 Klein 的 diffusers 推理封装与 UI 集成模式（直接补本仓 Z-Image 主线体验）。
- **P1**：Unified Canvas 的局部重绘交互、节点式 workflow 可视化。
- **注意**：InvokeAI 自研节点引擎 ≠ ComfyUI；借鉴架构思路，不混入 ComfyUI GPL 内核。

## 七、风险 / 不适用
- 体量庞大（3,900+ 文件），直接嵌入成本高；宜取其「模型支持清单 + 推理封装」作参照，而非整库引入。
- React 前端 ≠ Image_MultiModel 既有栈（须确认本仓前端形态）。

## 八、参考文件（克隆内可复核）
- `reference_repos/Image_MultiModel/InvokeAI/README.md`（模型支持清单、能力）
- `reference_repos/Image_MultiModel/InvokeAI/pyproject.toml`（依赖 / 许可）
- `reference_repos/Image_MultiModel/InvokeAI/invokeai/`（引擎代码）
