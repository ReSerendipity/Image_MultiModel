# Third-Party Notices（第三方组件声明）

> 更新日期：2026-09-02。本清单非穷尽：完整依赖以 `requirements.txt` / `requirements-lock.txt`
> 及安装环境的 `pip freeze` 为准；各组件许可以其官方仓库与包内 LICENSE 为准。

## 项目主许可

Image MultiModel 项目代码采用 [Apache License 2.0](LICENSE)。

## 核心推理引擎

### z_image_turbo_native（默认引擎，backend: native）

- **组件**：进程内原生引擎，复用本地 `comfy_kernel/`（vendored ComfyUI 内核源码）实现 Z-Image-Turbo 推理
- **引擎 key**：`config.yaml → models.engines.z_image_turbo_native`（`backend: native`）
- **上游**：<https://github.com/Comfy-Org/ComfyUI>（Comfy-Org）
- **许可（核心合规点）**：vendored `comfy_kernel/` 为 [GNU GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html)
- **分发义务**：分发本项目需遵守 GPL-3.0（随附许可文本、提供源码获取方式、保留版权声明）；`comfy_kernel/` 作为独立 git 仓库由 `.gitignore` 排除，使用前需满足其许可要求。**源码获取方式与分发前自查清单见 `docs/GPL_COMPLIANCE.md`**（vendored 版本 0.32.0，源码对应提交 `9883be7c`）

### Z-Image-Turbo 模型权重（Apache-2.0）

- **组件**：Z-Image-Turbo 模型权重（用户自行下载并放置于 `model/` 目录）
- **上游**：<https://huggingface.co/Tongyi-MAI/Z-Image-Turbo>（通义实验室）
- **许可**：[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)；再分发需保留原版权声明

## 主要 Python 依赖（许可类型为常见归类，以各包 LICENSE 为准）

| 组件 | 常见许可类型 | 说明 |
|---|---|---|
| torch / torchvision / torchaudio | BSD-3-Clause | 推理框架 |
| fastapi | MIT | Web 框架 |
| uvicorn | BSD-3-Clause | ASGI 服务器 |
| pydantic / pydantic-core | MIT | 数据校验 |
| aiohttp | Apache-2.0 | 异步 HTTP 客户端 |
| aiofiles | Apache-2.0 | 异步文件 IO |
| websockets | BSD-3-Clause | WebSocket |
| numpy | BSD-3-Clause | 数值计算 |
| Pillow | HPND（PIL Software License） | 图像处理 |
| opencv-python-headless | Apache-2.0 | 视觉处理 |
| safetensors | Apache-2.0 | 模型权重加载 |
| einops | MIT | 张量重排 |
| transformers | Apache-2.0 | 模型库 |
| PyYAML | MIT | 配置解析 |
| comfy-aimdo / comfy-kitchen | 未核验 | 原生引擎依赖，见包内 LICENSE |

> 商用分发前，建议对 `requirements-lock.txt` 锁定的依赖版本做一次完整许可扫描；尤其注意 `comfy_kernel/` 的 GPL-3.0 义务。
