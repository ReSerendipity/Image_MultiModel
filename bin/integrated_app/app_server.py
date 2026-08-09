"""
app_server.py — FastAPI 主应用入口

对应 MASTER_PLAN §4: app_server.py (FastAPI create_app + lifespan)
对应 MASTER_PLAN §3: 单页融合版 FastAPI 托管为 /
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .checkpoint import TaskCheckpoint
from .comfy.engine import ComfyEngine
from .config import get_config, load_config
from .engine_interface import GenerationConfig
from .gpu_utils import get_gpu_info
from .history_db import HistoryDB
from .middleware.csrf import CSRFMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.request_id import RequestIDMiddleware
from .model_registry import get_model_registry
from .sse import get_sse_bus
from .task_queue import Task, TaskQueue

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
        # D4: 采样中实时预览 → SSE comfy_preview 事件
        if "preview_b64" in extra:
            await sse_bus.publish("comfy_preview", {
                "task_id": task_id,
                "b64": extra["preview_b64"],
                "format": extra.get("preview_format", "jpg"),
            })

    async def on_status(task_id: str, status, extra: dict | None = None):
        await sse_bus.publish("task_status", {
            "task_id": task_id,
            "status": status.value if hasattr(status, "value") else str(status),
            **(extra or {}),
        })
        # 同时发布 queue_status 事件（§1.6 SSE 补全）
        await sse_bus.publish("queue_status", task_queue.get_queue_status())

    # TaskQueue 回调运行在 worker 线程 → 用主循环线程安全投递
    main_loop = asyncio.get_event_loop()

    def sync_on_progress(task_id, progress, phase, extra):
        asyncio.run_coroutine_threadsafe(on_progress(task_id, progress, phase, extra), main_loop)

    def sync_on_status(task_id, status, extra=None):
        asyncio.run_coroutine_threadsafe(on_status(task_id, status, extra), main_loop)

    task_queue.add_progress_callback(sync_on_progress)
    task_queue.add_status_callback(sync_on_status)

    # 启动 SSE 心跳
    heartbeat_task = asyncio.ensure_future(sse_bus.start_heartbeat())

    # 启动 GPU 状态定期推送（§1.6 SSE 补全：每 2s 发布 gpu_status）
    async def gpu_monitor_loop():
        while True:
            try:
                gpu = get_gpu_info()
                await sse_bus.publish("gpu_status", {
                    "name": gpu.gpu_name,
                    "backend": gpu.backend,
                    "total_vram_gb": gpu.total_vram_gb,
                    "used_vram_gb": gpu.used_vram_gb,
                    "free_vram_gb": gpu.free_vram_gb,
                    "timestamp": time.time(),
                })
            except Exception as e:
                logger.warning(f"GPU monitor error: {e}")
            await asyncio.sleep(2)
    gpu_monitor_task = asyncio.ensure_future(gpu_monitor_loop())

    # D6: 历史清理 cron 调度
    async def history_cleanup_cron():
        """按 cron 表达式定时清理超期任务"""
        import datetime as _dt
        cron_expr = config.output.history.cleanup_cron
        keep_days = config.output.history.keep_days
        if not cron_expr or keep_days <= 0:
            logger.info("History cleanup cron disabled (keep_days=0 or no cron)")
            return
        parts = cron_expr.split()
        if len(parts) != 5:
            logger.warning(f"Invalid cron expression: {cron_expr}")
            return
        cron_min, cron_hour, _, _, _ = parts
        while True:
            try:
                now = _dt.datetime.now()
                # 计算下一次运行时间
                target_hour = int(cron_hour) if cron_hour != "*" else now.hour
                target_min = int(cron_min) if cron_min != "*" else now.minute
                next_run = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
                if next_run <= now:
                    next_run = next_run + _dt.timedelta(days=1)
                sleep_s = (next_run - now).total_seconds()
                logger.info(f"History cleanup scheduled at {next_run}, sleeping {sleep_s:.0f}s")
                await asyncio.sleep(sleep_s)
                # 执行清理
                deleted = history_db.cleanup_old_tasks(keep_days=keep_days)
                logger.info(f"History cleanup: deleted {deleted} tasks (keep_days={keep_days})")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"History cleanup cron error: {e}")
                await asyncio.sleep(3600)  # 出错后 1h 重试
    cleanup_task = asyncio.ensure_future(history_cleanup_cron())

    # 初始化断点续跑 Checkpoint（§1.3）
    checkpoint_mgr = TaskCheckpoint(
        checkpoint_dir=str(Path(config.project_root) / config.runtime.task_queue.checkpoint_dir)
    )
    # 启动时扫描未完成 checkpoint（可恢复批量中断任务）
    pending_checkpoints = checkpoint_mgr.list_checkpoints()
    if pending_checkpoints:
        logger.info(f"Found {len(pending_checkpoints)} pending checkpoints for recovery")
    app.state.checkpoint_mgr = checkpoint_mgr

    # 启动 TaskQueue Worker（M2：接通 ComfyEngine 真实推理）
    def worker_func(task):
        logger.info(f"Worker processing task: {task.task_id} ({task.engine})")
        started = time.time()
        try:
            cfg = get_config()
            ecfg = cfg.models.engines.get(task.engine)
            if not ecfg:
                raise RuntimeError(f"Engine '{task.engine}' not found in config")
            engine = ComfyEngine(
                name=task.engine,
                display_name=getattr(ecfg, "display_name", task.engine),
                config={
                    "workflow_file": ecfg.workflow_file,
                    "parameter_schema": ecfg.parameter_schema,
                    "comfy_backend_preference": getattr(ecfg, "comfy_backend_preference", "local"),
                },
            )
            gen = GenerationConfig(**task.config)

            # 断点续跑：on_chunk_done 回调
            checkpoint_every = config.runtime.task_queue.checkpoint_every
            completed_items: list[dict] = []

            def on_chunk_done(completed: int, total: int):
                completed_items.append({"completed": completed, "total": total})
                if checkpoint_mgr.should_checkpoint(completed, checkpoint_every):
                    try:
                        checkpoint_mgr.save(
                            task_id=task.task_id,
                            engine=task.engine,
                            total=total,
                            completed_items=completed_items,
                            remaining=[{"index": i} for i in range(completed, total)],
                            config=task.config,
                        )
                    except Exception as e:
                        logger.warning(f"Checkpoint save failed: {e}")

            def prog(pct, phase, extra):
                task.progress = pct
                task.phase = phase
                task_queue._notify_progress(task.task_id, pct, phase, extra or {})
                if task.cancel_requested and not engine._cancel_requested:
                    asyncio.create_task(engine.cancel())

            async def run():
                await engine.load(on_progress=prog)
                if task.cancel_requested:
                    await engine.cancel()
                    raise asyncio.CancelledError("cancelled before start")
                return await engine.infer_txt2img(gen, on_progress=prog, on_chunk_done=on_chunk_done)

            outputs = asyncio.run(run())
            task.result = outputs or []

            # 查找缩略图路径（engine._fetch_outputs 可能已生成缩略图）
            thumb = (outputs[0] if outputs else "")
            # 如果引擎返回了缩略图，使用它；否则用第一个输出
            if hasattr(engine, '_thumbnail_path') and engine._thumbnail_path:
                thumb = engine._thumbnail_path

            history_db.update_task_status(
                task.task_id, "completed",
                processing_time_s=time.time() - started,
                output_count=len(outputs or []),
                thumbnail=thumb,
            )
            out_types = ("original", "upscaled", "compare")
            for i, p in enumerate(outputs or []):
                history_db.add_output(
                    task.task_id, p, "png",
                    output_type=out_types[i] if i < len(out_types) else "original",
                )

            # 批量任务断点续跑：完成时清理 checkpoint
            if task.batch_id:
                checkpoint_mgr.delete(task.task_id)
        except asyncio.CancelledError:
            history_db.update_task_status(task.task_id, "cancelled")
            task.error = "cancelled"
            return
        except Exception as e:
            logger.exception(f"Task {task.task_id} worker error")
            history_db.update_task_status(task.task_id, "failed", error=str(e))
            task.error = str(e)
            raise

    await task_queue.start(worker_func)
    app.state.task_queue = task_queue

    # 启动恢复：从断点续跑 checkpoint 重建未完成任务并续跑剩余槽位
    for cp in pending_checkpoints:
        try:
            cp_task_id = cp.get("task_id", "")
            cp_engine = cp.get("engine", "")
            cp_config = cp.get("config", {})
            cp_completed = cp.get("completed", 0)
            cp_total = cp.get("total", 0)
            if not cp_task_id or not cp_engine or cp_completed >= cp_total:
                checkpoint_mgr.delete(cp_task_id)
                continue
            logger.info(f"Resuming task {cp_task_id} from checkpoint ({cp_completed}/{cp_total})")
            # 构造续跑 Task，减少 batch_size 为剩余数量
            remaining_count = cp_total - cp_completed
            resume_config = dict(cp_config)
            resume_config["batch_size"] = remaining_count
            resume_task = Task(
                task_id=cp_task_id,
                engine=cp_engine,
                config=resume_config,
                mode="txt2img",
            )
            await task_queue.submit(resume_task)
        except Exception as e:
            logger.warning(f"Failed to resume checkpoint: {e}")

    # 初始化 ModelRegistry
    model_registry = get_model_registry()
    model_registry.init_from_config(config)
    app.state.model_registry = model_registry

    logger.info(f"=== Image MultiModel ready on http://{config.server.host}:{config.server.port} ===")

    yield

    # ── 关闭 ──────────────────────────────────────────────────
    logger.info("=== Image MultiModel shutting down ===")
    # 取消后台任务
    gpu_monitor_task.cancel()
    heartbeat_task.cancel()
    cleanup_task.cancel()
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

    # CSRF（POST/PUT/DELETE 需 X-CSRF-Token 头）
    if config.security.basic_auth.enabled or config.security.api_token.enabled:
        app.add_middleware(CSRFMiddleware)

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
    from .routes.engine_routes import router as engine_router
    from .routes.generate_routes import router as generate_router
    from .routes.output_routes import router as output_router
    from .routes.preset_routes import router as preset_router
    from .routes.system_routes import router as system_router
    from .routes.task_routes import router as task_router

    app.include_router(config_router)
    app.include_router(system_router)
    app.include_router(generate_router)
    app.include_router(task_router)
    app.include_router(output_router)
    app.include_router(preset_router)
    app.include_router(engine_router)

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
