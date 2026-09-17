# Image MultiModel

![Version](https://img.shields.io/badge/version-1.2.2-blue?style=for-the-badge) ![License](https://img.shields.io/badge/license-Apache2.0-green?style=for-the-badge) ![Python](https://img.shields.io/badge/python-3.10+-yellow?style=for-the-badge&logo=python&logoColor=white) ![GPU](https://img.shields.io/badge/GPU-NVIDIA%20CUDA-76B900?style=for-the-badge&logo=nvidia&logoColor=white) [![CI](https://github.com/ReSerendipity/Image_MultiModel/actions/workflows/ci.yml/badge.svg)](https://github.com/ReSerendipity/Image_MultiModel/actions) [![gitleaks](https://img.shields.io/badge/secret%20scan-gitleaks%20passing-0080FF?style=for-the-badge)](https://github.com/ReSerendipity/Image_MultiModel/actions/workflows/gitleaks.yml)

**Image MultiModel — 多模型 AI 图像生成平台**：基于进程内原生引擎，复用 ComfyUI 源码实现 Z-Image Turbo 推理的「单页 Web UI」

> A unified AI image generation platform powered by the Z-Image Turbo workflow via a native in-process engine (reusing local ComfyUI source), fully decoupled from any external ComfyUI process.

## 功能亮点

| 特性 | 说明 |
|---|---|
| **原生进程内引擎** | 复用项目内 `comfy_kernel` 源码 + aki-v3 自定义节点，`sys.path` 注入后在同一进程内完成 加载→编码→采样→解码，完全脱离外部 ComfyUI 进程 |
| **Z-Image Turbo 工作流** | 内置 Z Image Turbo（阿里通义）高速文生图工作流，支持六层 LoRA 叠加、SeedVR2 超分、Eses 双图对比、显存预留 |
| **显存预检** | 推理前自动估算 VRAM 需求，推荐精度（FP8/FP16）与 batch chunk 大小 |
| **批量任务队列** | 异步任务队列 + SSE 实时推送，支持批量生成、任务取消、断点恢复 |
| **预设管理** | 可保存常用参数组合为预设，一键加载复用 |
| **历史记录** | SQLite 历史数据库，支持搜索、筛选、分页、结果预览 |
| **DCT 数字水印** | 输出图像自动嵌入频域水印，包含 product_id + task_id + timestamp，可溯源 |
| **安全加固** | PathGuard 路径防护、CSRF 中间件、Rate Limit 限流、任务签名完整性校验 |
| **多语言界面** | 内置中文、繁体中文、英文、日文、韩文五种语言 |

## 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（推荐） / Linux |
| GPU | NVIDIA CUDA GPU（推荐 8GB+ VRAM） |
| Python | 系统 Python 3.10+（3.12 最佳），或自行下载 WinPython 3.12 解压到项目根目录（`WPy64-312101/`，完全隔离无需系统 Python） |
| 推理引擎 | 进程内原生引擎（复用项目内 `comfy_kernel` 源码），无需外部 ComfyUI 进程 |

## 快速开始

### 方式一：使用系统 Python（推荐，节省磁盘空间）

1. 安装 [Python 3.10+](https://www.python.org/downloads/)（推荐 3.12.x），务必勾选 "Add Python to PATH"
2. 验证：`python --version`
3. 双击运行 `install.bat`（自动检测系统 Python，安装 PyTorch CUDA 版 + 全部依赖）
4. （可选）复制 `.env.example` 为 `.env` 配置环境变量（`.env` 不入库，注意保管）
5. 确认模型文件已就位（`pretrained_models/`，portable 模式，完全自包含）
6. 双击运行 `start.bat`，浏览器自动打开 <http://127.0.0.1:8288>

> 默认端口 `8288`（`config.yaml → server.port` 可改）。模型路径模式：`portable`（默认，指向 `pretrained_models/`，自包含）或 `shared`（外部共享目录）。

### 方式二：使用便携 WinPython（完全隔离，无需系统 Python）

1. 下载 [WinPython 3.12](https://github.com/winpython/winpython/releases) 并解压到项目根目录，确保 `WPy64-312101/python/python.exe` 存在
2. 双击运行 `install.bat`（检测不到系统 Python 时自动回退到 WinPython）
3. 确保模型已就位 → 双击 `start.bat`

> `install.bat` / `start.bat` 的 Python 查找优先级：常见系统安装路径 → PATH 注册的 `python`（排除 IDE 自带）→ 项目内 WinPython → 兄弟项目（Seedvr2 / TTS_MultiModel）的 WinPython。

### Docker

```bash
docker build -t image-multimodel .
docker run --gpus all -p 8288:8288 \
  -v ./pretrained_models:/app/pretrained_models \
  -v ./outputs:/app/outputs \
  image-multimodel
```

## 内置工作流

| 工作流 | 推荐显存 | 用途 | 引擎 key |
|---|---|---|---|
| Z Image Turbo | ~4GB+ | 高速文生图、实时预览 | `z_image_turbo_native` |

## 原生进程内引擎

自 v1.2.0 起，平台**完全脱离外部 ComfyUI 进程**，统一走进程内原生引擎 `NativeEngine`：

- **不重新实现模型网络**：复用 `comfy_kernel/`（内含 `comfy/`、`comfy_extras/`、`comfy_execution/` 等顶层包）与 aki-v3 自定义节点源码
- **`sys.path` 注入**：通过 `native/source.ensure_loaded()` 把该目录注入 `sys.path[0]`，在同一进程内调用 `comfy.sd` / `comfy.samplers` 完成推理
- **统一引擎 key**：`config.yaml → models.engines.z_image_turbo_native`（`backend: native`）

> 引擎与 comfy_kernel 的架构分工详见 `docs/agents/ARCH_MAP.md`（本地保留、未随仓库发布）。

## 项目结构（概览）

```
Image_MultiModel/
├── app/integrated_app/   # 主应用核心（app_server / native 引擎 / routes / security / middleware / locales / watermark）
├── comfy_kernel/         # vendored ComfyUI 内核（gitignored，克隆后按 docs/GPL_COMPLIANCE.md 履行 GPL-3.0 义务自行获取）
├── workflows/            # 工作流参考目录（引擎由代码构建工作流）
├── pretrained_models/    # 模型检查点存放（portable 模式，gitignored）
├── desktop/              # 桌面分发（Tauri v2 壳 + NSIS 安装器）
├── release/  scripts/  tests/  demo/
└── config.yaml  pyproject.toml
```

## 技术栈

| 层级 | 技术 |
|---|---|
| 推理引擎 | 进程内原生引擎（复用本地 Comfy 源码）+ aki-v3 自定义节点 |
| 深度学习 | PyTorch (CUDA)、工作流：Z Image Turbo |
| Web 框架 | FastAPI + Uvicorn |
| 前端 | 单页应用（SPA，静态托管）+ SSE 实时推送 |
| 数据 | SQLite（历史）、YAML（配置）、JSON（工作流） |
| 安全 | PathGuard + CSRF + Rate Limit + Integrity Check + DCT Watermark |
| 工具链 | pytest + Hypothesis + factory-boy、ruff、coverage |

## API 速查

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/health` | GET | 后端/引擎/队列/GPU/磁盘状态 |
| `/api/events` | GET (SSE) | 实时事件流（task_status / gpu_status / model_status / queue_status） |
| `/api/generate` | POST | 提交生成任务 |
| `/api/generate/batch` | POST | 批量生成 |
| `/api/engine/engines` | GET | 引擎列表 |
| `/api/engine/load` | POST | 加载引擎 |
| `/api/engine/unload` | POST | 卸载引擎 |
| `/api/config` | GET/PUT | 读取/保存配置 |
| `/api/tasks` | GET | 任务列表 |
| `/api/tasks/{id}/cancel` | POST | 取消任务 |

## 开发与测试

```bash
python -m pytest -q                              # 运行测试
python -m ruff check app tests                   # 代码检查
python -m pytest --cov=app/integrated_app --cov-report=term-missing   # 覆盖率
pip install playwright pytest-playwright && playwright install chromium
python -m pytest tests/e2e -m e2e                # E2E 测试
```

## 安全说明

- **网络绑定**：默认仅绑定 `127.0.0.1`，如需局域网访问请配置反向代理 + Basic Auth
- **路径防护**：PathGuard 对文件路径做规范化校验，防止 `../` 路径穿越读取任意文件
- **完整性**：`integrity_manifest.json` 对关键安全模块做 SHA256 校验
- **水印溯源**：所有输出图像自动嵌入 DCT 频域水印（`product_id | task_id | timestamp`）；验证：`python scripts/verify_watermark.py <output.png>`
- **CSRF**：表单提交 / POST 路由统一启用 CSRF Token 校验

## 桌面版（Windows）

桌面分发提供安装器与增量更新两条路径：

- **安装器**：`desktop/installer/setup.nsi`（NSIS 3.09）编译 `ImageMultiModel-Setup-v{ver}.exe`，与数据分卷（`ImageMultiModel-Data.7z.001` 起）同目录；自动终止运行中的壳与 Python 子进程后安装
- **桌面壳**：`desktop/src-tauri`（Tauri v2）——单实例、系统托盘、崩溃自动重启、窗口状态记忆、隐藏控制台；启动侧载 Python 并管理后端生命周期（健康检查 `/api/health` 的 `security.integrity` 字段，完整性失败在托盘告警）
- **增量更新**：应用代码打包 → `app-v{ver}.zip` + SHA256；壳内更新器拉取 GitHub Release `shell-update.json`，验 SHA256 后原子换载 `app/`（保留运行时数据与配置）
- **质量门禁**：`scripts/release_gate.py` 与 `scripts/diag_portable_verify.py`（安装环境验签/完整性诊断）

## 模型许可说明

> 本表为**模型权重**的许可清单（项目代码为 Apache-2.0，见 [LICENSE](LICENSE)）。**接入新模型时：更新本表 + `config.yaml` 中对应引擎的 `license` 字段。**

| 模型 | 引擎 key | 权重许可 | 商用 | 说明 |
|---|---|---|---|---|
| Z-Image Turbo（阿里通义） | `z_image_turbo_native` | Apache-2.0 | 可商用 | 默认引擎 |
| SeedVR2（字节跳动，超分组件） | —（工作流内置） | Apache-2.0 | 可商用 | 见 NOTICE |

### 非官方声明

- 本项目为**独立开源项目**，基于阿里通义实验室（Tongyi-MAI）开源模型 **Z-Image-Turbo**（Apache-2.0）构建，与阿里巴巴集团及通义品牌**无隶属关系**，并非通义官方出品
- "Z-Image" 为阿里通义实验室的官方模型品牌名，本项目中仅作**描述性引用**，不暗示官方身份或背书
- 项目内置的 SeedVR2 超分组件同为第三方集成，相关归属与免责说明见 [SeedVR2 项目声明](https://github.com/ReSerendipity/SeedVR2-lite)

## 许可证

本项目采用 [Apache License 2.0](LICENSE) 开源协议。
