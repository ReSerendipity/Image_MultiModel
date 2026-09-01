"""
routes/generate_routes.py — POST /api/generate + 批量

对应 MASTER_PLAN §5.1: POST /api/generate → {task_id}
对应 MASTER_PLAN §5.1: POST /api/generate/batch
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import get_config
from ..cost_governance import get_vram_scheduler
from ..engine_interface import GenerationConfig
from ..gpu_utils import preflight_vram
from ..i18n import get_error_message
from ..observability.generation_metrics import (
    record_generation_accepted,
    record_generation_rejected,
    record_generation_submitted,
)
from ..observability.metrics import get_metrics
from ..overload_policy import evaluate_overload, fill_ratio_of
from ..task_queue import Task, TaskQueue, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])


def _maybe_reject_overload(task_queue: TaskQueue, cfg: Any, batch_size: int) -> None:
    """P1-8 分级过载策略：入队前评估队列填充率，必要时抛 HTTPException。

    - 70%：仅观察（proceed）
    - 85%：大 batch 快速拒绝 429 + Retry-After
    - 95%：快速拒绝 429 + Retry-After
    - 100%：明确 503

    在创建 history 记录之前调用，避免孤儿记录。
    """
    maxsize = cfg.runtime.task_queue.maxsize
    fill = fill_ratio_of(task_queue.queue_size, maxsize)
    decision = evaluate_overload(fill, batch_size)
    if decision.action == "proceed":
        return
    record_generation_rejected(decision.reason)
    get_metrics().queue_rejected_total.inc(1.0, reason=decision.reason)
    headers = {"Retry-After": str(decision.retry_after_s)} if decision.retry_after_s else None
    raise HTTPException(status_code=decision.status, detail=decision.message, headers=headers)


class GenerateRequest(BaseModel):
    """POST /api/generate 请求体"""
    # 8 基础
    positive_prompt: str = ""
    negative_prompt: str = ""
    cfg: float = 1.0
    steps: int = 8
    width: int = 1024
    height: int = 1024
    seed: int = -1
    batch_size: int = 1
    # LoRA 6 层
    lora_1_name: str = ""
    lora_1_strength: float = 1.0
    lora_2_name: str = ""
    lora_2_strength: float = 0.7
    lora_3_name: str = ""
    lora_3_strength: float = 0.5
    lora_4_name: str = ""
    lora_4_strength: float = 0.4
    lora_5_name: str = ""
    lora_5_strength: float = 0.3
    lora_6_name: str = ""
    lora_6_strength: float = 0.2
    # SeedVR2
    seedvr2_enable: bool = True
    seedvr2_resolution: int = 2048
    seedvr2_seed: int = -1
    seedvr2_color_correction: str = "lab"
    # Eses
    eses_enable: bool = True
    eses_compare_axis: str = "horizontal"
    # VRAM
    vram_enable: bool = True
    vram_reserved_gb: float = 0.6
    vram_mode: str = "auto"
    vram_seed: int = -1
    # 输出
    output_format: str = "png"
    output_prefix: str = ""
    # 引擎
    engine_name: str | None = None
    # 参考图（可选，用于生成前 CLIP 安全检测；二选一，均可为空，为空则跳过图检）
    reference_image_path: str | None = None  # 服务端图片路径（须在 PathGuard 白名单内）
    reference_image_b64: str | None = None   # Base64 图片数据（含或不含 data: 前缀）


class GenerateResponse(BaseModel):
    task_id: str
    status: str = "pending"
    estimated_time_s: float | None = None
    estimated_vram_gb: float | None = None
    warning: str | None = None


def _resolve_reference_image(req: GenerateRequest, cfg: Any) -> str | None:
    """解析请求中的参考图，返回可供 CLIP 检测的本地文件路径。

    无参考图（两个字段均为空）→ None，跳过 CLIP 图检（保持原有行为）。
    reference_image_path → PathGuard 校验 + 存在性检查（对齐 /api/safety/check-image）。
    reference_image_b64 → 解码 + 魔数校验 + PIL verify 后落盘到 uploads 缓存目录。

    Raises:
        HTTPException: 字段冲突(400) / 路径不安全(403) / 文件不存在(404) / 解码失败(400)。
    """
    if req.reference_image_path and req.reference_image_b64:
        raise HTTPException(
            400,
            detail="Provide either reference_image_path or reference_image_b64, not both",
        )

    if req.reference_image_path:
        from ..security.path_guard import PathGuard, PathGuardError

        guard = PathGuard(cfg.security.allowed_base_dirs, cfg.project_root)
        try:
            safe_path = guard.resolve(req.reference_image_path)
        except PathGuardError:
            raise HTTPException(
                403,
                detail=get_error_message("path_traversal", path=req.reference_image_path),
            )
        if not safe_path.exists():
            raise HTTPException(
                404,
                detail=get_error_message("file_not_found", path=req.reference_image_path),
            )
        return str(safe_path)

    if req.reference_image_b64:
        b64 = req.reference_image_b64
        if b64.startswith("data:") and "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            img_data = base64.b64decode(b64)
        except Exception as e:
            raise HTTPException(400, detail=f"Reference image decode failed: {e}")

        # M-03: 体积 + 解压炸弹（像素）上限校验，超过即 413
        from ..security.upload_limits import enforce_upload_limits

        enforce_upload_limits(
            img_data, cfg.output.uploads.max_size_mb, cfg.output.uploads.max_pixels
        )

        # SECURITY: 魔数校验（对齐 preprocess_routes），阻断伪装/非图片数据
        from ..security.magic_check import validate_image_magic

        is_magic, _detected_type, error = validate_image_magic(img_data)
        if not is_magic:
            raise HTTPException(400, detail=f"Reference image decode failed: {error}")

        try:
            from PIL import Image

            img = Image.open(io.BytesIO(img_data))
            img.verify()  # 校验内容完整性（防"伪图片头但损坏内容"）
            img = Image.open(io.BytesIO(img_data))
            cache_dir = Path(cfg.project_root) / cfg.output.uploads.cache_dir
            cache_dir.mkdir(parents=True, exist_ok=True)
            safe_path = cache_dir / f"refcheck_{uuid.uuid4().hex}.png"
            img.convert("RGB").save(str(safe_path), format="PNG")
            return str(safe_path)
        except Exception as e:
            raise HTTPException(400, detail=f"Reference image decode failed: {e}")

    return None


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, request: Request) -> GenerateResponse:
    """POST /api/generate — 提交 txt2img 任务 → {task_id}"""
    cfg = get_config()
    engine_name = req.engine_name or cfg.models.default_engine

    # 验证引擎存在
    if engine_name not in cfg.models.engines:
        record_generation_rejected("engine_not_found")
        raise HTTPException(404, detail=get_error_message("engine_not_found", name=engine_name))

    engine_cfg = cfg.models.engines[engine_name]

    # 验证 batch_size
    if req.batch_size < 1 or req.batch_size > 9999:
        record_generation_rejected("batch_too_large")
        raise HTTPException(400, detail=get_error_message("batch_too_large"))

    # 内容安全过滤（P0 任务1: CLIP 安全检测集成；参考图可选，有则生成前 CLIP 图检）
    from ..security.content_filter import filter_image_generation

    ref_image_path = _resolve_reference_image(req, cfg)
    # CLIP 检测为同步阻塞（首次加载 2-5s，后续每张百 ms 级）：
    # 放入默认线程池执行，避免阻塞事件循环（对齐 task_queue/native engine 的 run_in_executor 风格）
    is_safe, reason = await asyncio.get_running_loop().run_in_executor(
        None,
        filter_image_generation,
        req.positive_prompt,
        ref_image_path,
        cfg.security.content_filter.fail_closed_on_clip_missing,
    )
    if not is_safe:
        record_generation_rejected("content_blocked")
        raise HTTPException(400, detail=get_error_message("content_blocked", reason=reason))

    # 显存预检
    vram_est = preflight_vram(
        engine_vram_gb=engine_cfg.vram_gb,
        width=req.width,
        height=req.height,
        batch_size=req.batch_size,
        enable_seedvr2=req.seedvr2_enable,
        fallback_precision=engine_cfg.fallback_precision,
        default_precision=engine_cfg.default_precision,
        multisample_rule=cfg.inference.vram_multisample_rule,
        headroom_gb=cfg.inference.vram_headroom_gb,
        allow_tight=cfg.inference.vram_tight_continue,
    )

    if not vram_est.can_run:
        record_generation_rejected("vram_insufficient")
        raise HTTPException(
            400,
            detail=get_error_message(
                "vram_insufficient",
                need=vram_est.needed_vram_gb,
                avail=vram_est.available_vram_gb,
            ),
        )

    # P1 VRAM 水位感知动态 batch 上限：把用户请求钳制到调度器允许范围内
    # 注：假引擎（IMM_FAKE_ENGINE=1）不消耗显存，钳制无意义；且真实 GPU 空闲水位
    # 在测试/CI 环境波动会导致 batch_size 被随机钳制，使生成结果不确定（flaky）。
    # 故假引擎路径跳过钳制，保留生产环境（真实 GPU）的钳制语义。
    scheduler = get_vram_scheduler()
    if scheduler.enabled and os.environ.get("IMM_FAKE_ENGINE") != "1":
        clamped = scheduler.clamp(req.batch_size)
        if clamped != req.batch_size:
            logger.info("VRAM scheduler clamped batch_size %s -> %s", req.batch_size, clamped)
            req.batch_size = clamped

    # 构建 GenerationConfig
    gen_config = GenerationConfig(
        positive_prompt=req.positive_prompt,
        negative_prompt=req.negative_prompt,
        cfg=req.cfg,
        steps=req.steps,
        width=req.width,
        height=req.height,
        seed=req.seed,
        batch_size=req.batch_size,
        lora_1_name=req.lora_1_name,
        lora_1_strength=req.lora_1_strength,
        lora_2_name=req.lora_2_name,
        lora_2_strength=req.lora_2_strength,
        lora_3_name=req.lora_3_name,
        lora_3_strength=req.lora_3_strength,
        lora_4_name=req.lora_4_name,
        lora_4_strength=req.lora_4_strength,
        lora_5_name=req.lora_5_name,
        lora_5_strength=req.lora_5_strength,
        lora_6_name=req.lora_6_name,
        lora_6_strength=req.lora_6_strength,
        seedvr2_enable=req.seedvr2_enable,
        seedvr2_resolution=req.seedvr2_resolution,
        seedvr2_seed=req.seedvr2_seed,
        seedvr2_color_correction=req.seedvr2_color_correction,
        eses_enable=req.eses_enable,
        eses_compare_axis=req.eses_compare_axis,
        vram_enable=req.vram_enable,
        vram_reserved_gb=req.vram_reserved_gb,
        vram_mode=req.vram_mode,
        vram_seed=req.vram_seed,
        output_format=req.output_format,
        output_prefix=req.output_prefix,
        engine_name=engine_name,
        latent_channels=getattr(engine_cfg, "latent_channels", None),
        latent_downscale=getattr(engine_cfg, "latent_downscale", None),
    )

    # 获取 TaskQueue
    task_queue: TaskQueue = request.app.state.task_queue
    # P1-8 分级过载策略：入队前评估，避免创建孤儿 history 记录
    _maybe_reject_overload(task_queue, cfg, req.batch_size)
    task_id = task_queue.generate_task_id()

    # 创建任务
    task = Task(
        task_id=task_id,
        engine=engine_name,
        config=gen_config.to_dict(),
        mode="txt2img",
    )

    # 记录到历史
    from ..history_db import HistoryDB
    from ..lineage import compute_lora_checksums, compute_workflow_version
    history_db: HistoryDB = request.app.state.history_db
    history_db.create_task(
        task_id=task_id,
        engine=engine_name,
        mode="txt2img",
        prompt=req.positive_prompt,
        negative_prompt=req.negative_prompt,
        generation_config=gen_config.to_dict(),
        workflow_version=compute_workflow_version(cfg.models.engines[engine_name], cfg.project_root),
        lora_checksums=compute_lora_checksums(gen_config.effective_lora_stack(), cfg),
    )

    # 提交到队列
    record_generation_submitted(engine_name)
    success = await task_queue.submit(task)
    if not success:
        record_generation_rejected("queue_full")
        get_metrics().queue_rejected_total.inc(1.0, reason="full")
        raise HTTPException(503, detail=get_error_message("task_queue_full"))
    record_generation_accepted(engine_name)

    # 估算时间
    est_time = req.batch_size * (2.0 + (3.0 if req.seedvr2_enable else 0))

    return GenerateResponse(
        task_id=task_id,
        status="pending",
        estimated_time_s=est_time,
        estimated_vram_gb=vram_est.needed_vram_gb,
        warning=vram_est.warning or None,
    )


class BatchGenerateRequest(BaseModel):
    """POST /api/generate/batch 请求体"""
    prompts: list[str] = Field(default_factory=list)  # Prompt 列表
    prompt_file: str | None = None  # Prompt 文件路径
    grid_dimensions: dict[str, list[Any]] = Field(default_factory=dict)  # Grid 6 维
    base_config: GenerateRequest = Field(default_factory=GenerateRequest)


@router.post("/generate/batch")
async def generate_batch(req: BatchGenerateRequest, request: Request) -> dict[str, Any]:
    """POST /api/generate/batch — 批量生成（Prompt 文件 × Grid 6 维）"""
    cfg = get_config()
    from ..lineage import compute_lora_checksums, compute_workflow_version
    engine_name = req.base_config.engine_name or cfg.models.default_engine


    # 引擎存在性校验（与单图 /generate 对齐）
    if engine_name not in cfg.models.engines:
        record_generation_rejected("engine_not_found")
        raise HTTPException(404, detail=get_error_message("engine_not_found", name=engine_name))

    # batch_size 校验（与单图 /generate 对齐）
    if req.base_config.batch_size < 1 or req.base_config.batch_size > 9999:
        record_generation_rejected("batch_too_large")
        raise HTTPException(400, detail=get_error_message("batch_too_large"))

    # 生成组合
    prompts = req.prompts
    if req.prompt_file:
        # 读取 prompt 文件
        from ..security.path_guard import PathGuard
        guard = PathGuard(cfg.security.allowed_base_dirs, cfg.project_root)
        try:
            path = guard.resolve(req.prompt_file)
            prompts = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except Exception as e:
            raise HTTPException(400, detail=f"Cannot read prompt file: {e}")

    # Grid 6 维展开
    grid = req.grid_dimensions
    grid_keys = list(grid.keys())
    grid_values = [grid[k] for k in grid_keys]

    # 笛卡尔积
    import itertools
    grid_combos = list(itertools.product(*grid_values)) if grid_values else [()]

    # 内容安全过滤（与单图 /generate 对齐：逐条过滤，任一命中即拒绝；
    # 参考图（若有）CLIP 图检一次，作用于整批）
    from ..security.content_filter import filter_image_generation
    ref_image_path = _resolve_reference_image(req.base_config, cfg)
    # CLIP 检测为同步阻塞（首次加载 2-5s，后续每张百 ms 级）：
    # 放入默认线程池执行，避免阻塞事件循环（对齐 task_queue/native engine 的 run_in_executor 风格）
    for p in prompts:
        is_safe, reason = await asyncio.get_running_loop().run_in_executor(
            None,
            filter_image_generation,
            p,
            ref_image_path,
            cfg.security.content_filter.fail_closed_on_clip_missing,
        )
        if not is_safe:
            raise HTTPException(400, detail=get_error_message("content_blocked", reason=reason))

    # 计算总任务数
    total = len(prompts) * len(grid_combos)
    if total == 0:
        raise HTTPException(400, detail="No prompts or grid combinations provided")

    # 批量提交
    task_queue: TaskQueue = request.app.state.task_queue
    history_db = request.app.state.history_db
    # P1-8 分级过载策略：批量本身即「大 batch」，85% 以上档位直接拒绝
    _maybe_reject_overload(task_queue, cfg, total)
    batch_id = task_queue.generate_task_id()
    task_ids: list[str] = []

    for prompt_idx, prompt in enumerate(prompts):
        for grid_idx, combo in enumerate(grid_combos):
            gen_config = req.base_config.model_copy()
            gen_config.positive_prompt = prompt

            # 应用 Grid 维度
            for i, key in enumerate(grid_keys):
                if hasattr(gen_config, key):
                    setattr(gen_config, key, combo[i])

            task_id = task_queue.generate_task_id()
            task = Task(
                task_id=task_id,
                engine=engine_name,
                config=gen_config.model_dump(exclude={"reference_image_path", "reference_image_b64"}),
                mode="batch",
                batch_id=batch_id,
            )
            history_db.create_task(
                task_id=task_id,
                engine=engine_name,
                mode="batch",
                prompt=prompt,
                generation_config=gen_config.model_dump(exclude={"reference_image_path", "reference_image_b64"}),
                workflow_version=compute_workflow_version(cfg.models.engines[engine_name], cfg.project_root),
                lora_checksums=compute_lora_checksums(gen_config.effective_lora_stack(), cfg),
            )
            record_generation_submitted(engine_name)
            if await task_queue.submit(task):
                record_generation_accepted(engine_name)
                task_ids.append(task_id)
            else:
                record_generation_rejected("queue_full")
                get_metrics().queue_rejected_total.inc(1.0, reason="full")

    return {
        "batch_id": batch_id,
        "total_tasks": total,
        "task_ids": task_ids,
    }


@router.get("/tasks/batch/{batch_id}")
async def get_batch_status(batch_id: str, request: Request) -> dict[str, Any]:
    """GET /api/tasks/batch/{id} — 查询批量进度"""
    task_queue: TaskQueue = request.app.state.task_queue
    tasks = [t for t in task_queue.list_tasks() if t.batch_id == batch_id]

    if not tasks:
        raise HTTPException(404, detail="Batch not found")

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    cancelled = sum(1 for t in tasks if t.status == TaskStatus.CANCELLED)
    processing = sum(1 for t in tasks if t.status == TaskStatus.PROCESSING)
    pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)

    return {
        "batch_id": batch_id,
        "total": total,
        "completed": completed,
        "failed": failed,
        "cancelled": cancelled,
        "processing": processing,
        "pending": pending,
        "progress_pct": int(completed / total * 100) if total > 0 else 0,
    }
