"""
native/engine.py — NativeEngine（ImageEngine 进程内引擎实现）

在应用进程内复用本地 Comfy 源码直接推理，不依赖外部 ComfyUI 进程。

实现 ImageEngine Protocol：is_ready / load / unload / infer_txt2img / cancel。
Phase 1 保证：出图 + 保存 + DCT 水印 + 缩略图。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import get_config
from ..config_models import resolve_engine_model_paths
from ..engine_interface import GenerationConfig, ProgressCallback
from ..security.path_guard import PathGuard
from . import executor, output_pipeline

logger = logging.getLogger(__name__)

# 采样阶段 -> i18n 阶段键（与 comfy/engine.py 风格一致）
PHASE_KEY_MAP = {
    "Loading native models...": "phase_loading_workflow",
    "Encoding prompts...": "phase_patching",
    "Sampling...": "phase_sampling",
    "Decoding...": "phase_sampling",
    "Completed": "phase_completed",
}


def _map_phase(phase_text: str) -> str:
    """把 executor 阶段文案映射为 i18n 键。"""
    if phase_text in PHASE_KEY_MAP:
        return PHASE_KEY_MAP[phase_text]
    if phase_text.startswith("Sampling "):
        return "phase_sampling"
    return phase_text


class NativeEngine:
    """进程内原生引擎（复用本地 Comfy 源码推理）。"""

    def __init__(
        self,
        name: str,
        display_name: str = "",
        display_name_en: str = "",
        config: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._display_name = display_name or name
        self._display_name_en = display_name_en or name
        self._config = config or {}
        self._ready = False
        self._cancel_requested = False
        self._model_paths: dict[str, str] = {}
        self._thumbnail_path = ""

    # ── 协议属性 ────────────────────────────────────────────
    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    def is_ready(self) -> bool:
        return self._ready

    # ── 协议方法 ────────────────────────────────────────────
    async def load(self, on_progress: ProgressCallback | None = None) -> None:
        """解析模型路径并装载 Comfy 源码（模型按需在首次推理时加载）。"""
        if on_progress:
            on_progress(10, _map_phase("Loading native models..."), {})

        cfg = get_config()
        engine_cfg = cfg.models.engines.get(self._name)
        if engine_cfg is None:
            raise RuntimeError(f"Engine '{self._name}' not found in config.models.engines")

        self._model_paths = resolve_engine_model_paths(engine_cfg, cfg.models, cfg.project_root)
        if not self._model_paths:
            raise RuntimeError(f"Engine '{self._name}' has no resolvable model paths")

        # 装载 Comfy 源码（幂等），不在此处加载 8B 权重
        from . import source

        comfy_root = self._config.get("comfy_source_dir") or None
        if comfy_root:
            # Gotcha #16：相对路径需拼项目根为绝对路径，避免基于进程 cwd 解析到错误位置
            p = Path(comfy_root)
            if not p.is_absolute():
                p = Path(cfg.project_root) / p
            comfy_root = str(p.resolve())
        source.ensure_loaded(comfy_root=comfy_root)

        if on_progress:
            on_progress(100, _map_phase("Completed"), {})
        self._ready = True
        logger.info("NativeEngine '%s' loaded (model paths resolved)", self._name)

    async def unload(self) -> None:
        """卸载引擎：释放缓存并标记未就绪。"""
        try:
            import comfy.model_management

            comfy.model_management.soft_empty_cache()
        except Exception as e:  # pragma: no cover - 环境相关
            logger.warning("unload cache clear failed: %s", e)
        self._ready = False
        self._model_paths = {}
        logger.info("NativeEngine '%s' unloaded", self._name)

    async def infer_txt2img(
        self,
        config: GenerationConfig,
        on_progress: ProgressCallback | None = None,
    ) -> list[str]:
        """执行进程内文生图推理，返回输出图像绝对路径列表。"""
        if not self._ready or not self._model_paths:
            raise RuntimeError("Native engine not ready, please load first")

        self._cancel_requested = False
        cancel_flag = [False]

        def cancel_cb() -> None:
            cancel_flag[0] = True

        # 推理为同步阻塞（线程池隔离事件循环），支持取消
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(
            None,
            lambda: executor.txt2img(
                config, self._model_paths, on_progress=on_progress, cancel_flag=cancel_flag
            ),
        )

        # 注册取消：内部标志置位 + 取消 future
        watcher = asyncio.create_task(self._watch_cancel(fut, cancel_cb))
        try:
            images = await fut
        finally:
            watcher.cancel()
            self._cancel_requested = False

        return self._save_outputs(images, config)

    async def cancel(self) -> None:
        """取消当前推理（置位取消标志）。"""
        self._cancel_requested = True
        logger.info("NativeEngine '%s' cancel requested", self._name)

    # ── 内部辅助 ────────────────────────────────────────────
    async def _watch_cancel(self, fut: Any, cancel_cb: Any) -> None:
        """监控取消标志；用户在推理中调用 cancel() 时触发内部取消。"""
        while not fut.done():
            if self._cancel_requested:
                cancel_cb()
                return
            await asyncio.sleep(0.05)

    def _save_outputs(self, images: list[Any], config: GenerationConfig) -> list[str]:
        """把解码后的图像张量落盘 + 嵌入 DCT 水印 + 生成缩略图。

        输出命名：outputs/{engine}/{date}/{taskid}_{type}.png
        """
        cfg = get_config()
        guard = PathGuard(cfg.security.allowed_base_dirs, cfg.project_root)

        date_str = datetime.now().strftime("%Y%m%d")
        engine_dir = guard.ensure_dir(Path(cfg.output.base_dir) / self._name / date_str)
        task_id = config.workflow_sha256 or f"{int(time.time() * 1000):016x}"

        wm_enabled = cfg.watermark.enabled_in_code
        product_id = cfg.watermark.product_id
        thumb_enabled = cfg.output.save_thumbnail
        thumb_max_side = cfg.output.thumbnail_max_side
        thumb_dir: Path | None = None
        if thumb_enabled:
            thumb_dir = guard.ensure_dir(Path("data") / "cache" / "thumbs")

        saved: list[str] = []
        for idx, img_tensor in enumerate(images):
            width, height = img_tensor.shape[1], img_tensor.shape[0]
            fname = f"{task_id[:16]}_{idx}.png"
            path = engine_dir / fname
            output_pipeline.finalize_output(
                path,
                img_tensor,
                is_tensor=True,
                wm_enabled=wm_enabled,
                product_id=product_id,
                task_id=task_id[:16],
                thumb_enabled=thumb_enabled,
                thumb_dir=thumb_dir,
                thumb_name=f"{task_id[:16]}_{idx}_thumb.png",
                thumb_max_side=thumb_max_side,
            )

            # 存相对路径（相对 outputs/ 目录），供前端 /api/outputs/<rel> 直接访问
            base = (Path(cfg.project_root) / cfg.output.base_dir).resolve()
            rel = str(path.relative_to(base)).replace("\\", "/")
            saved.append(rel)
        return saved
