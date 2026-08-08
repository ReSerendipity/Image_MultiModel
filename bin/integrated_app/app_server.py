"""
app_server.py — FastAPI 主应用入口

对应 MASTER_PLAN §4: app_server.py (FastAPI create_app + lifespan)
对应 MASTER_PLAN §3: 单页融合版 FastAPI 托管为 /
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_config, load_config
from .history_db import HistoryDB
from .sse import get_sse_bus
from .task_queue import TaskQueue
from .model_registry import get_model_registry
from .middleware.request_id import RequestIDMiddleware
from .middleware.rate_limit import RateLimitMiddleware

# ── 日志配置 ──────────────────────────────────────────────────
logger = logging.getLogger("integrated_app")


def setup_logging(config) -> None:
    """配置日志"""
    log_cfg = config.logging
    log_dir = Path(config.project_root) / log_cfg.file
    log_dir.parent.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]
    try:
        handlers.append(logging.handlers.RotatingFileHandler(
            str(log_dir),
            maxBytes=log_cfg.max_size_mb * 1024 * 1024,
            backupCount=log_cfg.backup_count,
            encoding="utf-8",
        ))
    except Exception as e:
        logger.warning(f"Could not set up file logging: {e}")

    logging.basicConfig(
        level=getattr(logging, log_cfg.level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ── 启动 ──────────────────────────────────────────────────
    config = load_config()
    app.state.config = config
    setup_logging(config)
    logger.info(f"=== Image MultiModel starting (v{config.version}) ===")
    logger.info(f"Project root: {config.project_root}")
    logger.info(f"Model mode: {config.models.model_source_mode}")

    # 初始化 HistoryDB
    db_path = Path(config.project_root) / config.output.history.db_path
    history_db = HistoryDB(db_path)
    app.state.history_db = history_db

    # 崩溃恢复：清理卡死任务
    recovered = history_db.recover_stuck_tasks()
    if recovered > 0:
        logger.warning(f"Recovered {recovered} stuck tasks from previous session")

    # 初始化 TaskQueue
    task_queue = TaskQueue(
        maxsize=config.runtime.task_queue.maxsize,
        cancel_timeout_s=config.runtime.task_queue.cancel_timeout_s,
        max_timeout_s=config.runtime.task_queue.max_timeout_s,
    )
    app.state.task_queue = task_queue

    # 注册 SSE 进度/状态回调
    sse_bus = get_sse_bus()

    async def on_progress(task_id: str, progress: int, phase: str, extra: dict):
        await sse_bus.publish("task_status", {
            "task_id": task_id,
            "progress": progress,
            "phase": phase,
            **extra,
        })

    async def on_status(task_id: str, status, extra: dict = None):
        await sse_bus.publish("task_status", {
            "task_id": task_id,
            "status": status.value if hasattr(status, "value") else str(status),
            **(extra or {}),
        })

    # 由于 TaskQueue 回调是同步的，需要包装为异步
    def sync_on_progress(task_id, progress, phase, extra):
        asyncio.ensure_future(on_progress(task_id, progress, phase, extra))

    def sync_on_status(task_id, status, extra=None):
        asyncio.ensure_future(on_status(task_id, status, extra))

    task_queue.add_progress_callback(sync_on_progress)
    task_queue.add_status_callback(sync_on_status)

    # 启动 SSE 心跳
    asyncio.ensure_future(sse_bus.start_heartbeat())

    # 启动 TaskQueue Worker（空 worker，M1 阶段接通引擎）
    def worker_func(task):
        logger.info(f"Worker processing task: {task.task_id}")
        # M0 阶段：空处理，直接标记完成
        # M1+ 阶段：调用 ComfyEngine.infer_txt2img()
        task.status = "completed"
        task.result = []
        history_db.update_task_status(task.task_id, "completed")

    await task_queue.start(worker_func)
    app.state.task_queue = task_queue

    # 初始化 ModelRegistry
    model_registry = get_model_registry()
    model_registry.init_from_config(config)
    app.state.model_registry = model_registry

    logger.info(f"=== Image MultiModel ready on http://{config.server.host}:{config.server.port} ===")

    yield

    # ── 关闭 ──────────────────────────────────────────────────
    logger.info("=== Image MultiModel shutting down ===")
    await task_queue.stop()
    sse_bus.stop()
    history_db.close()
    logger.info("=== Image MultiModel stopped ===")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    config = load_config()

    app = FastAPI(
        title="Image MultiModel",
        description="基于 ComfyUI 生态的多模型图片生成 Web 应用",
        version=config.version,
        lifespan=lifespan,
    )

    # ── 中间件 ────────────────────────────────────────────────
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.security.cors.allowed_origins,
        allow_credentials=config.security.cors.allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # RequestID
    app.add_middleware(RequestIDMiddleware)

    # RateLimit
    app.add_middleware(
        RateLimitMiddleware,
        global_per_minute=config.security.rate_limit.global_per_minute,
        infer_per_minute=config.security.rate_limit.infer_per_minute,
        upload_per_minute=config.security.rate_limit.upload_per_minute,
    )

    # ── 路由自动发现 ──────────────────────────────────────────
    from .routes.config_routes import router as config_router
    from .routes.system_routes import router as system_router
    from .routes.generate_routes import router as generate_router
    from .routes.task_routes import router as task_router
    from .routes.output_routes import router as output_router
    from .routes.preset_routes import router as preset_router

    app.include_router(config_router)
    app.include_router(system_router)
    app.include_router(generate_router)
    app.include_router(task_router)
    app.include_router(output_router)
    app.include_router(preset_router)

    # ── 静态文件托管（单页 HTML） ─────────────────────────────
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        # 挂载静态文件
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        # 根路径 → index.html（唯一前端入口）
        from fastapi.responses import FileResponse

        @app.get("/", include_in_schema=False)
        async def index():
            return FileResponse(str(static_dir / "index.html"))

        @app.get("/{full_path:path}", include_in_schema=False)
        async def catch_all(full_path: str):
            # 其他静态资源
            file = static_dir / full_path
            if file.exists() and file.is_file():
                return FileResponse(str(file))
            # SPA fallback
            return FileResponse(str(static_dir / "index.html"))

    return app


# ── 入口 ──────────────────────────────────────────────────────
app = create_app()


def run():
    """直接运行"""
    import uvicorn

    config = get_config()
    uvicorn.run(
        "integrated_app.app_server:app",
        host=config.server.host,
        port=config.server.port,
        workers=config.server.workers,
        reload=False,
    )


if __name__ == "__main__":
    run()
