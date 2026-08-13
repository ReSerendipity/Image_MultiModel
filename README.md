# Image MultiModel

![Version](https://img.shields.io/badge/version-2.0.0-blue?style=for-the-badge) ![License](https://img.shields.io/badge/license-Apache%202.0-green?style=for-the-badge) ![Python](https://img.shields.io/badge/python-3.10+-yellow?style=for-the-badge&logo=python&logoColor=white) ![GPU](https://img.shields.io/badge/GPU-NVIDIA%20CUDA-76B900?style=for-the-badge&logo=nvidia&logoColor=white) [![CI](https://github.com/ReSerendipity/Image_MultiModel/actions/workflows/ci.yml/badge.svg)](https://github.com/ReSerendipity/Image_MultiModel/actions)

**多模型 AI 图像生成平台 — 基于 ComfyUI 工作流引擎，支持 Flux.2、Z Image Turbo 等多模型工作流的统一 Web UI**

> **Image MultiModel** — A unified multi-model AI image generation platform powered by ComfyUI workflow engine. Supports Flux.2 Klein-9B Distilled, Z Image Turbo, and extensible to more workflows.
## 🧪 在线模拟演示（GitHub Pages）

无需 ComfyUI / GPU / 模型权重，纯前端仿真环境即可体验生图工作台完整流程：

**<https://reserendipity.github.io/Image_MultiModel/>** （由 `.github/workflows/pages-deploy.yml` 自动部署 `demo/` 目录，详见 [demo/README.md](demo/README.md)）

---


---

## 界面预览

*浅色主题 — 生图工作台主页 / 高级参数 / 预设管理 / 历史记录 / 图片展示 / 批量模式*

![主页浅色](docs/screenshots/current/light/01-home-full.png)

![高级参数浅色](docs/screenshots/current/light/02-advanced-params-drawer.png)

![预设管理浅色](docs/screenshots/current/light/03-presets-drawer.png)

![历史记录浅色](docs/screenshots/current/light/04-history-drawer.png)

![图片展示浅色](docs/screenshots/current/light/05-gallery-drawer.png)

![批量模式浅色](docs/screenshots/current/light/06-batch-drawer.png)

---

## 功能亮点

| 特性 | 说明 |
|---|---|
| **多工作流引擎** | 内置 Flux.2 Klein-9B Distilled、Z Image Turbo 工作流，支持一键扩展 |
| **双后端模式** | ComfyUI 后端（默认，需外部 ComfyUI 进程）或原生进程内引擎（`backend: native`，复用本机 Comfy 源码，无需外部 ComfyUI 进程即可出图） |
| **显存预检** | 推理前自动估算 VRAM 需求，推荐精度（FP8/FP16）与 batch chunk 大小 |
| **批量任务队列** | 异步任务队列 + SSE 实时推送，支持批量生成、任务取消、断点恢复 |
| **预设管理** | 可保存常用参数组合为预设，一键加载复用 |
| **历史记录** | SQLite 历史数据库，支持搜索、筛选、分页、结果预览 |
| **DCT 数字水印** | 输出图像自动嵌入频域水印，包含 product_id + task_id + timestamp，可溯源 |
| **安全加固** | PathGuard 路径防护、CSRF 中间件、Rate Limit 限流、任务签名完整性校验 |
| **多语言界面** | 内置中文、繁体中文、英文、日文、韩文五种语言 |

---

## 环境要求

| 项目 | 要求 |
|---|---|
| **操作系统** | Windows 10/11（推荐） / Linux |
| **GPU** | NVIDIA CUDA GPU（推荐 8GB+ VRAM） |
| **Python** | **两种方式均可**：<br>• **推荐**：系统 Python 3.10+（3.12 最佳），需勾选 "Add Python to PATH"<br>• **备选**：内置 WinPython（`WPy64-312101/`），完全隔离无需系统 Python |
| **后端引擎** | 双模式：ComfyUI 后端（需外部 ComfyUI 进程，默认）或原生进程内引擎（`backend: native`，复用本机 Comfy 源码，无需外部 ComfyUI 进程） |

---

## 快速开始

### 方式一：使用系统 Python（推荐，节省磁盘空间）

1. 安装 [Python 3.10+](https://www.python.org/downloads/)，推荐 3.12.x。安装时**务必勾选 "Add Python to PATH"**
2. 验证安装：打开命令提示符（CMD），运行：
   ```bat
   python --version
   ```
   应显示类似 `Python 3.12.x`
3. 双击运行 **`install.bat`**（会自动检测系统 Python，安装 PyTorch CUDA 版 + 全部依赖）
4. 配置 `config.yaml`，设置 ComfyUI 地址 / 工作流路径 / 模型路径
5. 将工作流 JSON 放入 `workflows/` 目录（已内置两个示例）
6. 双击运行：
   ```bat
   start.bat
   ```
7. 浏览器自动打开 Web UI（默认地址 `http://127.0.0.1:8288`）

> 💡 **优势**：多个项目（SeedVR2、TTS_MultiModel、Image_MultiModel）共享一套 Python + PyTorch + 依赖，避免每个项目重复 1~2GB 的 WinPython 环境。

> 📌 **默认端口**：`8288`（可在 `config.yaml` → `server.port` 修改）；ComfyUI 默认端口 `8188`（可在 ComfyUI 启动参数修改）。

> 📌 **模型路径模式**（`config.yaml` → `models.model_source_mode`）：
> - `shared`（默认）：模型路径直接指向 ComfyUI 的 `models/` 目录，与 ComfyUI 共享模型文件，无需复制。
> - `portable`：模型路径指向项目内 `pretrained_models/` 目录，适合便携包模式（完全自包含）。
> - 切换模式后重启应用即可生效。

---

### 方式二：使用内置 WinPython（完全隔离，无需系统 Python）

1. 下载 [WinPython 3.12](https://github.com/winpython/winpython/releases) 并解压到项目根目录，确保：
   - `WPy64-312101/python/python.exe` 存在
2. 双击运行 **`install.bat`**（检测不到系统 Python 时会自动回退到 WinPython）
3. 配置 `config.yaml`，准备好工作流和模型
4. 双击运行：
   ```bat
   start.bat
   ```

> 💡 **检测顺序说明**：`install.bat` 和 `start.bat` 会按以下优先级查找 Python：
> 1. 常见系统安装路径（`C:\Python312\`、`C:\Program Files\Python312\`、用户目录下的 Python）
> 2. 系统 PATH 中注册的 `python` 命令（排除 IDE/编辑器自带的 Python）
> 3. 项目内的 WinPython（`WPy64-312101\`、`WinPython` 等目录）
> 4. 共享兄弟项目的 WinPython（Seedvr2 / TTS_MultiModel）

---

### Docker

```bash
docker build -t image-multimodel .
docker run --gpus all -p 8080:8080 \
  -v ./pretrained_models:/app/pretrained_models \
  -v ./outputs:/app/outputs \
  image-multimodel
```

---

## 内置工作流

| 工作流 | 推荐显存 | 用途 | 配置文件 |
|---|---|---|---|
| **Flux.2 Klein-9B Distilled** | ~12GB (FP8) / ~24GB (FP16) | 高保真文生图、极致画质 | `workflows/Flux.2_Klein-9B-Distilled.json` |
| **Z Image Turbo** | ~4GB+ | 高速文生图、实时预览 | `workflows/Z_image_turbo.json` |

工作流 schema / 参数映射配置：
```
bin/integrated_app/comfy/schemas/
├── flux2_klein_9b_distilled.yaml
└── z_image_turbo.yaml
```

---

## 双后端模式

自 v1.2.0 起，平台支持 **两种推理后端**，每个引擎通过 `config.yaml → models.engines.*.backend` 指定：

| 后端 | `backend` 值 | 依赖 | 说明 |
|---|---|---|---|
| **ComfyUI 后端**（默认） | `comfyui` | 需要运行中的外部 ComfyUI（本地或远程，`8188` 端口） | 通过 HTTP + WebSocket 客户端提交工作流 JSON，由外部 ComfyUI 进程执行推理 |
| **原生进程内引擎** | `native` | 复用项目内 `references/ComfyUI` 源码 + aki-v3 自定义节点源码，**无需外部 ComfyUI 进程** | 在应用进程内直接调用 `comfy.sd` / `comfy.samplers` 完成加载→编码→采样→解码出图 |

> ℹ️ **原生引擎不重新实现模型网络**：它复用 `references/ComfyUI/`（内含 `comfy/`、`comfy_extras/`、`comfy_execution/` 等顶层包）与 aki-v3 自定义节点源码，通过 `native/source.ensure_loaded()` 把该目录注入 `sys.path`，在同一进程内完成推理。
>
> 原生引擎示例条目（`config.yaml`）：
> ```yaml
> z_image_turbo_native:
>   name: z_image_turbo_native
>   backend: native
>   comfy_source_dir: references/ComfyUI
>   # ... 与 comfyui 引擎相同的 text_encoder / unet / vae 模型路径
> ```

**前端切换**：引擎菜单顶部可切换 **全部 / ComfyUI / 原生**，按后端过滤引擎列表；选中后加载对应引擎即可生成。

---

## 项目结构

```
Image_MultiModel/
├── bin/                          # 应用入口与主程序
│   ├── clean_launch.py          # 启动清理 + 环境检测脚本
│   ├── install.bat              # 依赖安装脚本（Win根目录版）
│   ├── start.bat                # 旧版启动脚本（bin目录版）
│   └── integrated_app/          # 主应用核心
│       ├── app_server.py        # FastAPI 应用 + 生命周期管理
│       ├── comfy/               # ComfyUI 引擎层（client / engine / workflow）
│       │   ├── schemas/         # 工作流参数映射 YAML
│       │   ├── client.py        # ComfyUI WebSocket + HTTP 客户端
│       │   ├── engine.py        # 推理引擎封装
│       │   └── workflow.py      # 工作流加载 / 参数注入 / 校验
│       ├── native/              # 原生进程内引擎（backend: native）
│       │   ├── source.py        # 复用 references/ComfyUI 源码（sys.path 注入）
│       │   ├── executor.py      # 复用 comfy.sd / comfy.samplers 推理流程
│       │   ├── engine.py        # NativeEngine（ImageEngine 实现）
│       │   ├── lora.py / seedvr.py / compares.py / vram.py / preview.py
│       ├── routes/              # API 路由（生成 / 任务 / 预设 / 系统 / 配置）
│       ├── middleware/          # CSRF、限流、Request ID 中间件
│       ├── security/            # PathGuard 路径防护 + integrity 完整性
│       ├── locales/             # i18n 多语言（zh / zh-tw / en / ja / ko）
│       ├── watermark.py         # DCT 频域不可感知数字水印
│       ├── gpu_utils.py         # GPU VRAM 预检 + 精度 / chunk 推荐
│       ├── history_db.py        # SQLite 历史记录
│       └── task_queue.py        # 异步任务队列（SSE 推送）
├── workflows/                   # ComfyUI 工作流 JSON
├── pretrained_models/           # 模型检查点存放
│   ├── checkpoints/
│   ├── vae/
│   ├── unet/
│   ├── text_encoders/
│   ├── loras/
│   └── controlnet/
├── data/                        # 运行时数据（预设 / 上传 / 缓存）
├── outputs/                     # 生成结果输出
├── logs/                        # 运行日志
├── scripts/                     # 工具脚本
├── tests/                       # pytest + Hypothesis 测试套件
├── start.bat                    # ✅ Windows 启动脚本（统一风格，优先系统 Python）
├── install.bat                  # ✅ Windows 安装脚本（统一风格）
├── requirements.txt             # ✅ Python 依赖清单（已补充完整）
├── requirements-lock.txt        # 依赖哈希锁文件（可复现安装：`pip install --require-hashes -r requirements-lock.txt`）
├── config.yaml                  # 应用配置（ComfyUI 地址 / 工作流路径 / 端口等）
├── pyproject.toml               # 工具配置（pytest / ruff / coverage）
└── Dockerfile                   # Docker 构建
```

---

## 技术栈

| 层级 | 技术 |
|---|---|
| 推理后端 | 双模式：ComfyUI Engine + WebSocket/HTTP 客户端（`comfyui`）或原生进程内引擎（`native`，复用本地 Comfy 源码） |
| 深度学习 | PyTorch (CUDA)、工作流：Flux.2 Klein-9B、Z Image Turbo |
| Web 框架 | FastAPI + Uvicorn |
| 前端 | 单页应用（SPA，静态托管）+ SSE 实时推送 |
| 数据 | SQLite（历史）、YAML（配置）、JSON（工作流） |
| 安全 | PathGuard + CSRF + Rate Limit + Integrity Check + DCT Watermark |
| 工具链 | pytest + Hypothesis + factory-boy、ruff、coverage |

---

## 脚本检测优先级（三个项目一致）

所有 `.bat` 脚本（`start.bat` / `install.bat`）按**相同的优先级顺序**查找 Python 解释器：

| 优先级 | 类型 | 说明 |
|---|---|---|
| 1️⃣ 最高 | **系统 Python** | 按路径匹配：`C:\Python312\` → `C:\Python311\` → `C:\Python310\` → 程序 Files → 用户目录 |
| 2️⃣ 次高 | **PATH 注册** | `where python` 的结果（自动排除 IDE / TRAE 等编辑器自带的嵌入式 Python） |
| 3️⃣ 次低 | **项目内置 WinPython** | `WPy64-312101\` / `WinPython64-*\` / `WinPython\` |
| 4️⃣ 最低 | **兄弟项目共享** | Seedvr2 / TTS_MultiModel 的 WinPython（仅 Image_MultiModel 启用） |
| ❌ 全部失败 | — | 打印两条安装路径（系统 Python / WinPython），暂停并退出 |

---

## 安全说明

- **网络绑定**：默认仅绑定 `127.0.0.1`，如需局域网访问请配置反向代理 + Basic Auth
- **路径防护**：PathGuard 对文件路径做规范化校验，防止 `../` 路径穿越读取任意文件
- **完整性**：`integrity_manifest.json` 对关键安全模块做 SHA256 校验
- **水印溯源**：所有输出图像自动嵌入 DCT 频域水印，可追溯 `product_id | task_id | timestamp`
- **CSRF**：表单提交 / POST 路由统一启用 CSRF Token 校验

---

## 高级功能

### 断点续跑（§1.3）

batch>100 时每 100 张自动落盘 checkpoint。应用崩溃后重启，未完成任务自动从断点续跑且无重复输出。

```bash
# checkpoint 存储位置
data/checkpoints/{task_id}.json
```

### 释放显存（D3）

设置抽屉 →「释放显存」按钮 → 调用 `POST /api/engine/free` → ComfyUI 卸载模型释放 VRAM → SSE `gpu_status` 实时刷新。

### WS 重连自动重试（D2）

ComfyUI 重启时，引擎检测 `ConnectionError` → 自动重试 `connect()` + `queue_prompt()`（≤3 次，指数退避 2s/4s/8s），配 `max_wait_s` 兜底。

### 实时预览（D4）

WS 收到 `b_preview` 二进制 → base64 → SSE `comfy_preview` 事件 → 前端采样中实时预览。

### 历史清理 cron（D6）

`config.yaml` 中 `output.history.cleanup_cron` 配置 cron 表达式（默认 `0 3 * * *` = 每天凌晨 3 点），`keep_days` 设置保留天数。启动时自动调度定时清理任务。

### 水印验证

```bash
# 验证输出图像中的水印
python scripts/verify_watermark.py outputs/flux2_klein_9b_distilled/20260809/xxx_original.png
```

### 输出迁移

```bash
# 将旧平铺文件迁移到 engine/date 结构
python scripts/migrate_outputs.py --dry-run  # 预览
python scripts/migrate_outputs.py             # 执行迁移
```

---

## API 速查

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/health` | GET | 后端/引擎/队列/GPU/磁盘状态 |
| `/api/events` | GET (SSE) | 实时事件流（task_status / gpu_status / comfy_preview / model_status / queue_status） |
| `/api/generate` | POST | 提交生成任务 |
| `/api/generate/batch` | POST | 批量生成 |
| `/api/engine/engines` | GET | 引擎列表 |
| `/api/engine/load` | POST | 加载引擎 |
| `/api/engine/unload` | POST | 卸载引擎 |
| `/api/engine/free` | POST | 释放显存（D3） |
| `/api/config` | GET/PUT | 读取/保存配置 |
| `/api/tasks` | GET | 任务列表 |
| `/api/tasks/{id}/cancel` | POST | 取消任务 |

---

## 开发与测试

```bash
# 运行测试
python -m pytest -q

# 代码检查
python -m ruff check bin tests

# 覆盖率
python -m pytest --cov=bin/integrated_app --cov-report=term-missing

# E2E 测试（需先安装 Playwright）
pip install playwright pytest-playwright
playwright install chromium
python -m pytest tests/e2e -m e2e
```

---


## 模型许可说明

> 本表为**模型权重**的许可清单（项目代码为 Apache-2.0，见 [LICENSE](LICENSE)）。
> **接入新模型时：更新本表 + `config.yaml` 中对应引擎的 `license` 字段。**

| 模型 | 引擎 key | 权重许可 | 商用 | 说明 |
|---|---|---|---|---|
| FLUX.2 Klein-9B（含第三方衍生权重，如 DarkBeast 量化版） | `flux2_klein_9b_distilled` | FLUX Non-Commercial | ❌ 需向 Black Forest Labs 取得商业授权 | 默认引擎；商用发行物请勿内嵌其权重 |
| Z-Image Turbo（阿里通义） | `z_image_turbo` | Apache-2.0 | ✅ 可商用 | 建议作为商用默认引擎 |
| SeedVR2（字节跳动，超分组件） | —（工作流内置） | Apache-2.0 | ✅ 可商用 | 见 NOTICE |

**新增模型检查清单**：① 在 `config.yaml` 填写真实 `license` 字段；② 更新本表；③ 非商用模型（NC/自定义许可）不得作为商用发行物默认引擎、不随商业发行物分发；④ 使用前核对许可最新版本。
## 许可证

本项目采用 [Apache License 2.0](LICENSE) 开源协议。
