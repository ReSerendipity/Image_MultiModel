# API 调用示例 (examples/)

本目录提供 5 个 Python 示例脚本，演示如何通过 Image MultiModel 的 REST API 和 SSE 事件流进行程序化调用。

## 前置条件

1. **Image MultiModel 已启动**：
   ```bash
   python bin/clean_launch.py
   # 或
   start.bat  # Windows
   ./start.sh # Linux/macOS
   ```
   默认地址：`http://127.0.0.1:8288`

2. **确认原生引擎已就绪**（生成功能需要）：
   - 平台统一走进程内 `NativeEngine`（复用 `comfy_kernel` 源码），无需外部 ComfyUI 进程

3. **Python 依赖**：
   ```bash
   pip install requests
   ```
   仅需 `requests` 库，无需安装项目的完整依赖。

4. **引擎已加载**（生成功能需要）：
   - 通过 Web UI 或 `POST /api/engine/load` 加载引擎

## 示例列表

| # | 文件 | 说明 | 演示的 API |
|---|------|------|-----------|
| 01 | `01_text_to_image.py` | 最简文生图：提交任务 → 轮询状态 → 下载图片 | `POST /api/generate` · `GET /api/tasks/{id}` · `GET /api/outputs/{file}/download` |
| 02 | `02_batch_generate.py` | 批量生成：读 prompts.txt → 批量提交 → 进度查询 → 取消 | `POST /api/generate/batch` · `GET /api/tasks/batch/{id}` · `POST /api/tasks/{id}/cancel` |
| 03 | `03_sse_progress.py` | SSE 实时进度监听（比轮询更优雅） | `GET /api/events` (SSE) |
| 04 | `04_list_history.py` | 查询历史记录：分页 / 搜索 / 筛选 / 详情 | `GET /api/tasks` · `GET /api/tasks/{id}` |
| 05 | `05_apply_preset.py` | 预设管理：创建 → 应用 → 生成 → 清理 | `GET/POST /api/presets` · `POST /api/presets/{id}/apply` · `DELETE /api/presets/{id}` |

## 快速开始

```bash
# 进入项目根目录
cd Image_MultiModel

# 确保服务器已启动
python bin/clean_launch.py &

# 运行示例
python examples/01_text_to_image.py
python examples/02_batch_generate.py
python examples/03_sse_progress.py
python examples/04_list_history.py
python examples/05_apply_preset.py
```

## 需要修改的参数

每个脚本顶部都有 `SERVER_URL` 和相关配置变量。请根据你的环境修改：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SERVER_URL` | `http://127.0.0.1:8288` | Image MultiModel 服务地址 |
| `engine_name` | `z_image_turbo_native` | 使用哪个引擎（`z_image_turbo_native`） |
| `prompts.txt` | 内置 5 条示例 | 批量生成的 Prompt 列表（每行一个） |
| `width` / `height` | `1024` / `1024` | 生成图片分辨率 |
| `steps` | `8` | 采样步数（步数越多质量越好但越慢） |
| `seed` | `-1` | 随机种子（`-1` = 随机） |

## API 速查

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查（后端/引擎/队列/GPU/磁盘状态） |
| `/api/events` | GET (SSE) | 实时事件流（task_status / gpu_status / comfy_preview / model_status / queue_status） |
| `/api/generate` | POST | 提交生成任务 → `{task_id}` |
| `/api/generate/batch` | POST | 批量生成 |
| `/api/tasks` | GET | 历史记录列表（分页/搜索/筛选） |
| `/api/tasks/{id}` | GET | 任务详情 |
| `/api/tasks/{id}/cancel` | POST | 取消任务 |
| `/api/tasks/batch/{id}` | GET | 批量进度 |
| `/api/outputs` | GET | 图库列表 |
| `/api/outputs/{file}/download` | GET | 下载图片 |
| `/api/presets` | GET/POST | 预设列表/创建 |
| `/api/presets/{id}/apply` | POST | 应用预设 |
| `/api/engine/engines` | GET | 引擎列表 |
| `/api/engine/load` | POST | 加载引擎 |
| `/api/config` | GET/PUT | 读取/保存配置 |

完整 API 文档请参阅 [docs/API.md](../docs/API.md)，或启动服务器后访问 `http://127.0.0.1:8288/docs`（FastAPI Swagger UI）。

## 注意事项

- **网络绑定**：默认仅绑定 `127.0.0.1`。如需远程访问，请配置反向代理。
- **CSRF**：POST 请求可能需要 CSRF Token（取决于配置）。如果遇到 403，请从 Cookie 或 Header 获取 Token。
- **超时**：生成任务可能耗时较长（取决于引擎和参数），示例中设置了合理的超时时间。
- **输出目录**：01 示例的图片会保存到 `examples/output/` 目录。
