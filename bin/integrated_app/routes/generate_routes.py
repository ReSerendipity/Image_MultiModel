"""
routes/generate_routes.py — POST /api/generate + 批量

对应 MASTER_PLAN §5.1: POST /api/generate → {task_id}
对应 MASTER_PLAN §5.1: POST /api/generate/batch
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import get_config
from ..engine_interface import GenerationConfig
from ..gpu_utils import preflight_vram
from ..i18n import get_error_message
from ..task_queue import Task, TaskQueue, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])


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


class GenerateResponse(BaseModel):
    task_id: str
    status: str = "pending"
    estimated_time_s: float | None = None
    estimated_vram_gb: float | None = None
    warning: str | None = None


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, request: Request) -> GenerateResponse:
    """POST /api/generate — 提交 txt2img 任务 → {task_id}"""
    cfg = get_config()
    engine_name = req.engine_name or cfg.models.default_engine

    # 验证引擎存在
    if engine_name not in cfg.models.engines:
        raise HTTPException(404, detail=get_error_message("engine_not_found", name=engine_name))

    engine_cfg = cfg.models.engines[engine_name]

    # 验证 batch_size
    if req.batch_size < 1 or req.batch_size > 9999:
        raise HTTPException(400, detail=get_error_message("batch_too_large"))

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
        raise HTTPException(
            400,
            detail=get_error_message(
                "vram_insufficient",
                need=vram_est.needed_vram_gb,
                avail=vram_est.available_vram_gb,
            ),
        )

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
    )

    # 获取 TaskQueue
    task_queue: TaskQueue = request.app.state.task_queue
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
    history_db: HistoryDB = request.app.state.history_db
    history_db.create_task(
        task_id=task_id,
        engine=engine_name,
        mode="txt2img",
        prompt=req.positive_prompt,
        negative_prompt=req.negative_prompt,
        generation_config=gen_config.to_dict(),
    )

    # 提交到队列
    success = await task_queue.submit(task)
    if not success:
        raise HTTPException(503, detail=get_error_message("task_queue_full"))

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
    engine_name = req.base_config.engine_name or cfg.models.default_engine

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

    # 计算总任务数
    total = len(prompts) * len(grid_combos)
    if total == 0:
        raise HTTPException(400, detail="No prompts or grid combinations provided")

    # 批量提交
    task_queue: TaskQueue = request.app.state.task_queue
    history_db = request.app.state.history_db
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
                config=gen_config.model_dump(),
                mode="batch",
                batch_id=batch_id,
            )
            history_db.create_task(
                task_id=task_id,
                engine=engine_name,
                mode="batch",
                prompt=prompt,
                generation_config=gen_config.model_dump(),
            )
            await task_queue.submit(task)
            task_ids.append(task_id)

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
