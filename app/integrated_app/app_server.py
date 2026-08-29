"""
app_server.py — FastAPI 主应用入口

对应 MASTER_PLAN §4: app_server.py (FastAPI create_app + lifespan)
对应 MASTER_PLAN §3: 单页融合版 FastAPI 托管为 /
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import logging.handlers
import os
import pkgutil
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .checkpoint import TaskCheckpoint
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


class VersionedStaticFiles(StaticFiles):
    """差异化缓存静态文件（来源：Seedvr2 VersionedStaticFiles / TTS_MultiModel CachedStaticFiles）。

    学习参考项目：前端开发时修改 HTML/CSS/JS 后刷新浏览器即生效（不命中旧缓存）；
    同时字体长缓存（30 天）、图片短期缓存（1 天）避免无谓重复下载。
    - CSS/JS/HTML/JSON：no-cache, must-revalidate（开发时经常改）
    - 字体（woff2/woff/ttf/eot/otf）：public, max-age=2592000（30 天）
    - 图片（png/jpg/jpeg/gif/svg/ico/webp）：public, max-age=86400（1 天）
    """

    def file_response(self, *args, **kwargs) -> Response:
        """重写 file_response，根据文件类型添加差异化的 Cache-Control 头。"""
        response = super().file_response(*args, **kwargs)
        if args:
            fp = str(args[0])
            if fp.endswith((".css", ".js", ".html", ".json")):
                response.headers["Cache-Control"] = "no-cache, must-revalidate"
                response.headers["Pragma"] = "no-cache"
            elif fp.endswith((".woff2", ".woff", ".ttf", ".eot", ".otf")):
                response.headers["Cache-Control"] = "public, max-age=2592000"
            elif fp.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp")):
                response.headers["Cache-Control"] = "public, max-age=86400"
        return response


def _auto_discover_routers() -> list:
    """使用 pkgutil 递归发现并注册路由模块（P0-3: 来源 TTS_MultiModel）。

    遍历 ``integrated_app.routes`` 包下的所有模块，自动提取 ``router``
    APIRouter 实例。新增路由文件只需放到 routes/ 目录并在模块内定义
    ``router = APIRouter(prefix="/api/xxx", ...)`` 即可自动注册。

    Returns:
        list: 发现的 APIRouter 实例列表。
    """
    routers: list = []
    try:
        routes_pkg = importlib.import_module(".routes", package=__package__)
    except ImportError as e:
        logger.warning(f"[路由发现] 导入 routes 包失败: {e}")
        return routers

    if not hasattr(routes_pkg, "__path__"):
        return routers

    for _importer, modname, _ispkg in pkgutil.iter_modules(routes_pkg.__path__):
        try:
            mod = importlib.import_module(f".routes.{modname}", package=__package__)
            if hasattr(mod, "router"):
                routers.append(mod.router)
                logger.debug(f"[路由发现] 注册路由模块: routes.{modname}")
        except Exception as e:
            logger.warning(f"[路由发现] 导入 routes.{modname} 失败: {e}")

    return routers


def setup_logging(config) -> None:
    """配置日志：控制台 + 按大小轮转的文件（参数来自 config.yaml logging 段）。

    统一格式：时间戳 + 级别 + 进程/线程 + 模块位置 + 请求ID（request_id） + 消息，
    便于生产环境按 request_id 链路追踪、按 filename:lineno 快速定位。
    """
    log_cfg = config.logging
    log_dir = Path(config.project_root) / log_cfg.file
    log_dir.parent.mkdir(parents=True, exist_ok=True)

    # 日志级别支持环境变量 LOG_LEVEL 覆盖（优先级高于配置文件）
    level_name = os.environ.get("LOG_LEVEL", log_cfg.level).upper()
    log_level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [PID:%(process)d TID:%(thread)d] "
        "[%(name)s:%(filename)s:%(lineno)d] [req=%(request_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    from .middleware.request_id import RequestIDLogFilter

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

    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(RequestIDLogFilter())

    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,
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

    # P1-1: 核心模块完整性自检（来源：Seedvr2）
    from .security.integrity_selfcheck import run_startup_selfcheck
    selfcheck_result = run_startup_selfcheck()
    app.state.integrity_selfcheck = selfcheck_result

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
        # D4: 采样中实时预览 → SSE preview 事件
        if "preview_b64" in extra:
            await sse_bus.publish("preview", {
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

    # 启动 TaskQueue Worker（M8: 支持 native + diffusers 双后端）
    def worker_func(task):
        logger.info(f"Worker processing task: {task.task_id} ({task.engine})")
        started = time.time()
        try:
            cfg = get_config()
            ecfg = cfg.models.engines.get(task.engine)
            if not ecfg:
                raise RuntimeError(f"Engine '{task.engine}' not found in config")

            # M8: 使用工厂方法按 backend 分发引擎
            from .model_registry import get_model_registry

            registry = get_model_registry()
            backend = getattr(ecfg, "backend", "native")
            engine = registry.create_engine_instance(
                engine_name=task.engine,
                display_name=getattr(ecfg, "display_name", task.engine),
                display_name_en=getattr(ecfg, "display_name_en", ""),
                backend=backend,
                config=ecfg.model_dump(),
            )
            gen = GenerationConfig(**task.config)

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
                # 原生引擎单次推理，无 on_chunk_done（批量断点续跑由外层 task_queue 处理）
                return await engine.infer_txt2img(gen, on_progress=prog)

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
        description="Z-Image Turbo 图像生成 Web 应用（进程内原生引擎）",
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

    # CSRF（POST/PUT/DELETE 需 X-CSRF-Token 头，默认开启）
    if config.security.csrf.enabled:
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

    # ── 路由自动发现（P0-3: 来源 TTS_MultiModel） ─────────────
    routers = _auto_discover_routers()
    for router in routers:
        app.include_router(router)
    logger.info(f"Auto-discovered {len(routers)} route modules")

    # ── 全局错误处理中间件（P1-4: 来源 TTS_MultiModel） ─────────
    from .middleware.error_handler import register_error_handlers
    register_error_handlers(app)

    # ── Jinja2 模板引擎 + 静态文件托管 ──────────────────────
    templates_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"

    # 模板上下文辅助函数
    def _locale_for(lang: str) -> str:
        """把 BCP-47 语言代码映射到 locales 目录下的文件名（zh-CN -> zh）。"""
        return lang.split("-")[0].lower()

    # 静态文件托管（Jinja2 模板引用的 CSS/JS/图片）
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 页面路由（服务端渲染）
    if templates_dir.exists():
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        from .i18n import t as _i18n_t

        templates = Jinja2Templates(
            env=Environment(
                loader=FileSystemLoader(str(templates_dir)),
                autoescape=select_autoescape(["html"]),
            ),
        )
        # 模板内提供 _() 翻译函数（回退到当前语言）
        templates.env.globals["_"] = lambda key, **kw: _i18n_t(key, lang="zh", default=key, **kw)
        logger.info(f"Jinja2 templates loaded from: {templates_dir}")

        def _page_ctx(request: Request) -> dict:
            """构造模板渲染上下文（从 cookie 读取主题/语言，与前端 localStorage 保持一致）。"""
            config = get_config()
            return {
                "request": request,
                "config": config,
                "version": config.version,
                "lang": request.cookies.get("imm_lang", "zh-CN"),
                "theme": request.cookies.get("imm_theme", "dark"),
                "locale_file": _locale_for(request.cookies.get("imm_lang", "zh-CN")),
            }

        @app.get("/", include_in_schema=False)
        async def index(request: Request):
            return templates.TemplateResponse(request, "index.html", _page_ctx(request))

        @app.get("/{full_path:path}", include_in_schema=False)
        async def catch_all(request: Request, full_path: str):
            # 静态资源（css/js/images/其他）已由 /static mount 接管，这里不重复处理
            if full_path.startswith(("css/", "js/", "images/", "static/")):
                raise HTTPException(status_code=404, detail="Not Found")
            # 其余路径回退到首页模板（前端路由 / 局部刷新）
            return templates.TemplateResponse(request, "index.html", _page_ctx(request))

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
