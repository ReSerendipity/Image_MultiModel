# Third-Party Notices（第三方组件声明）

> 更新日期：2026-08-17。本清单非穷尽：完整依赖以 `requirements.txt` / `requirements-lock.txt`
> 及安装环境的 `pip freeze` 为准；各组件许可以其官方仓库与包内 LICENSE 为准。

## 项目主许可

Image MultiModel 项目代码采用 [Apache License 2.0](../LICENSE)。

## 核心推理引擎

### Z-Image Turbo (diffusers, default) - Apache-2.0

- **组件**: HuggingFace diffusers ZImagePipeline + Z-Image-Turbo 模型权重
- **上游**: <https://huggingface.co/Tongyi-MAI/Z-Image-Turbo> (通义实验室)
- **版本**: diffusers >= 0.39.0 (含 ZImagePipeline)
- **许可**: [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) (Z-Image-Turbo 模型为 Apache-2.0)
- **分发说明**: 
  - **完全兼容项目主许可**: diffusers 框架（BSD-3-Clause）+ Z-Image-Turbo 模型（Apache-2.0）均为宽松许可，与本项目 Apache-2.0 同源，无传染性约束
  - 便携包/Docker 镜像可**直接捆绑分发**，无需额外声明或源代码要求
  - 需保留原作者版权和免责声明（HuggingFace model card 与 diffusers 库 LICENSE）

### ⚠️ 弃用：ComfyUI 内核（仅旧版 z_image_turbo_native 引擎使用）

- ~~**组件**: ComfyUI 推理内核源码（本地目录 `comfy_kernel/`，由原生引擎进程内复用）~~
- ~~**上游**: <https://github.com/Comfy-Org/ComfyUI>（Comfy-Org）~~
- ~~**版本**: v0.32.0-5-gbd34f338~~
- ~~**许可**: [GNU GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html)~~
- ~~**分发边界**: (见 `comfy_kernel/COMPLIANCE-README.md`)~~
- ~~**备注**: ~~z_image_turbo_native~~ (backend: native) 引擎已于 ~~v1.3.0~~ 被标记为 deprecated，推荐使用 diffusers 引擎替代。~~


### 主要 Python 依赖（许可类型为常见归类，以各包 LICENSE 为准）

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
| torchsde | Apache-2.0 | SDE 求解 |
| comfy-aimdo / comfy-kitchen | 未核验 | 原生引擎依赖，见包内 LICENSE |

> 商用分发前，建议对 `requirements-lock.txt` 锁定的依赖版本做一次完整许可扫描。