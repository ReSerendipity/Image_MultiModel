“本文由 2026-08-27 家族治理 E3 从 AGENTS.md §6 移出，内容逐字保留”

# 构建 / 启动命令

### 6.1 一键启动脚本（推荐）
| 平台 | 安装依赖（首次） | 启动服务 |
|------|:---------------:|---------|
| **Windows** | 双击 / 终端执行根目录 `install.bat` → 自动检测系统 Python，装 PyTorch CUDA 版 + 全部依赖 + 创建数据目录 | 执行根目录 `start.bat` → 自动打开 `http://127.0.0.1:8288` |
| **Linux/macOS** | `chmod +x install.sh && ./install.sh` | `chmod +x start.sh && ./start.sh` |

### 6.2 手动启动命令
```bash
# 推荐方式（app/clean_launch.py，含环境检测 + 配置加载 + 数据目录创建 + 健康检查）
cd bin
python clean_launch.py
# 或根目录直接（start.bat 内部就是这么调的）
python app/clean_launch.py
# → 监听 http://127.0.0.1:8288
# 成功标志：按 §6.3 探针验证（`GET /api/health` 返回 200 + JSON）

# 纯 Uvicorn 前台调试（开发场景，不推荐生产）
cd bin
uvicorn integrated_app.app_server:app --host 127.0.0.1 --port 8288 --reload
# ⚠️ --reload 仅限开发！生产禁用（会重复加载引擎，VRAM 直接翻倍 → OOM）

# 生产守护进程（建议 systemd / NSSM）
uvicorn integrated_app.app_server:app --host 127.0.0.1 --port 8288 --workers 1
# ⚠️ workers 只能 = 1！TaskQueue 是全局单例，多 worker 会绕过串行队列并发推理 → OOM
```

### 6.3 启动后验证
3 步快速验证启动成功：
1. 浏览器打开 `http://127.0.0.1:8288` → 看到 Web UI 首页
2. `GET http://127.0.0.1:8288/api/health` → 返回：
   ```json
   {
     "status": "ok",
     "version": "2.0.0",
     "engines_available": ["z_image_turbo_native"],
     "engines_loaded": [],
     "gpu_vram_total_mb": 24576,
     "gpu_vram_used_mb": 1234
   }
   ```
3. `GET http://127.0.0.1:8288/api/engine/engines` → 返回唯一引擎 `z_image_turbo_native` 配置列表

---
