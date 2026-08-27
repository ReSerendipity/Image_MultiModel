**ADR-0001: native 引擎 + comfy_kernel 进程内复用**

- **状态**: Implemented
- **日期**: 2026-08-27
- **决策者**: 项目维护者 + AI 指挥（家族规范审计确认）

---

# 背景与问题

项目需要同时提供自研图像生成（native）与 ComfyUI 生态能力。曾规划"ComfyUI 适配"里程碑
（含 `comfy/client.py` 等拟新增文件，**尚未实现**，见 AGENTS.md M1「计划，未实现」）；实际代码采用
**内嵌 comfy_kernel 进程内复用**方案。

# 评估的备选方案

- **方案 A：独立 ComfyUI 进程 + HTTP 调用** —— 隔离彻底但部署复杂、启动慢。不采用。
- **方案 B：进程内 `sys.path` 注入复用 comfy_kernel** —— 在同一进程内调用 `comfy.sd` / `comfy.samplers` 完成推理。**采用**。

# 决策

- 运行时引擎：`app/integrated_app/native/engine.py`（配置键 `config.yaml → models.engines.z_image_turbo_native`，`backend: native`）。
- ComfyUI 能力：内嵌 `comfy_kernel/`（含 `comfy/`、`comfy_extras/`、`comfy_execution/` 等顶层包），
  经 `native/source.ensure_loaded()` 注入 `sys.path[0]` 进程内复用。
- 规划中的 `comfy/client.py` / `comfy/workflow.py` / `comfy/vram_scheduler.py` 属**计划未实现**，文档中不得写成现存量。

# 实施影响

- 许可证：`comfy_kernel/` 派生自 GPL-3.0 上游，存在传染风险，进程内复用须评估隔离边界（见 D6 许可证台账）。

# 可回滚路径与待验证项

- 回滚：恢复为仅 native 引擎（`INFERENCE_BACKEND` 类开关），comfy_kernel 不再加载。
- 待验证：审计器对 AGENTS.md 中 ComfyUI 适配的表述必须为「计划，未实现」；`comfy/` 顶层包实测存在。