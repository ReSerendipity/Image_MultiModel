"""
comfy/engine.py — ComfyEngine (ImageEngine 实现)

对应 MASTER_PLAN §4 / PRD §4.1: comfy/engine.py
对应 PRD §6: ComfyEngine（ImageEngine impl，仅 infer_txt2img）
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import get_config
from ..engine_interface import GenerationConfig, ProgressCallback
from .client import ComfyClient
from .workflow import WorkflowManager

logger = logging.getLogger(__name__)

# ── 进度阶段 i18n 键映射（§1.7）──
PHASE_KEY_MAP = {
    "Connecting to ComfyUI...": "phase_connecting",
    "Connecting HTTP...": "phase_connecting",
    "Loading workflow...": "phase_loading_workflow",
    "Engine ready": "phase_engine_ready",
    "Patching workflow...": "phase_patching",
    "Queuing prompt...": "phase_queuing",
    "Completed": "phase_completed",
    "Image saved": "phase_image_saved",
    "cancelling...": "phase_cancelling",
}


def _map_phase(phase_text: str) -> str:
    """将英文阶段文案映射为 i18n 键"""
    # 先尝试直接匹配
    if phase_text in PHASE_KEY_MAP:
        return PHASE_KEY_MAP[phase_text]
    # 处理动态阶段：Sampling x/y → phase_sampling
    if phase_text.startswith("Sampling "):
        return "phase_sampling"
    # 处理动态阶段：Executing node N → phase_executing
    if phase_text.startswith("Executing node "):
        return "phase_executing"
    return phase_text


class ComfyEngine:
    """
    ComfyUI 后端引擎实现。

    实现 ImageEngine Protocol:
    - is_ready / load / unload / infer_txt2img / cancel
    """

    def __init__(
        self,
        name: str,
        display_name: str = "",
        display_name_en: str = "",
        config: dict[str, Any] | None = None,
        client: ComfyClient | None = None,
    ) -> None:
        self._name = name
        self._display_name = display_name or name
        self._display_name_en = display_name_en or name
        self._config = config or {}
        self._client: ComfyClient | None = client
        self._workflow_mgr: WorkflowManager | None = None
        self._ready = False
        self._current_prompt_id: str | None = None
        self._cancel_requested = False
        self._object_info: dict[str, Any] = {}
        self._thumbnail_path: str = ""  # 缩略图路径（§2.5）

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    def is_ready(self) -> bool:
        return self._ready

    async def load(self, on_progress: ProgressCallback | None = None) -> None:
        """加载引擎：建立 ComfyUI 连接 + 初始化 WorkflowManager"""
        if on_progress:
            on_progress(10, _map_phase("Connecting to ComfyUI..."), {})

        cfg = get_config()
        comfy_cfg = cfg.comfy
        backend_name = self._config.get("comfy_backend_preference", "local")
        backend = comfy_cfg.backends.get(backend_name)

        if not backend:
            raise RuntimeError(f"ComfyUI backend '{backend_name}' not found in config")

        if self._client is None:
            self._client = ComfyClient(
                base_url=backend.base_url,
                ws_url=backend.ws_url,
                auth_token=backend.auth_token,
                client_id_prefix=backend.client_id_prefix,
            )

        if on_progress:
            on_progress(40, _map_phase("Connecting HTTP..."), {})

        await self._client.connect()

        if on_progress:
            on_progress(70, _map_phase("Loading workflow..."), {})

        # 初始化 WorkflowManager
        workflow_file = self._config.get("workflow_file", "")
        schema_file = self._config.get("parameter_schema", "")
        project_root = cfg.project_root

        self._workflow_mgr = WorkflowManager(
            workflow_path=str(Path(project_root) / workflow_file) if workflow_file else "",
            schema_path=str(Path(project_root) / schema_file) if schema_file else "",
            project_root=project_root,
        )

        if on_progress:
            on_progress(100, _map_phase("Engine ready"), {})

        # 缓存节点定义（UI→API 转换需要）
        try:
            self._object_info = await self._client.get_object_info()
        except Exception as e:
            logger.warning(f"Failed to fetch object_info: {e}")
            self._object_info = {}

        self._ready = True
        logger.info(f"ComfyEngine '{self._name}' loaded")

    async def unload(self) -> None:
        """卸载引擎：关闭连接"""
        if self._client:
            await self._client.disconnect()
            self._client = None
        self._ready = False
        logger.info(f"ComfyEngine '{self._name}' unloaded")

    async def infer_txt2img(
        self,
        config: GenerationConfig,
        on_progress: ProgressCallback | None = None,
        max_wait_s: int = 1200,
    ) -> list[str]:
        """
        执行文生图推理。

        流程:
        1. WorkflowManager.patch(config) → 生成 patched workflow
        2. client.queue_prompt(workflow) → 提交到 ComfyUI
        3. WS 监听进度 → on_progress 回调
        4. 保存输出 → 返回文件路径列表
        """
        if not self._ready or not self._client or not self._workflow_mgr:
            raise RuntimeError("Engine not ready, please load first")

        self._cancel_requested = False

        # 1. Patch 工作流
        if on_progress:
            on_progress(5, _map_phase("Patching workflow..."), {})

        workflow_data = self._workflow_mgr.patch(config)

        # 2. 转换为 ComfyUI API 格式（子图展开 + bypass 重连 + 具名 inputs）
        api_data = self._workflow_mgr.to_api_format(workflow_data, self._object_info or {})
        if not api_data:
            raise RuntimeError("Patched workflow produced empty API prompt")

        # 3. 提交到 ComfyUI
        if on_progress:
            on_progress(10, _map_phase("Queuing prompt..."), {})

        prompt_id = await self._client.queue_prompt(api_data)
        self._current_prompt_id = prompt_id

        # 3. WS 监听进度；WS 断开/超时后转 HTTP 轮询 history，直到出结果或出错
        await self._client.connect_ws()
        ws_alive = True
        t_start = time.time()

        def _handle_msg(msg: dict[str, Any]) -> str | None:
            """处理一条 WS 消息；返回 'done' 表示正常结束"""
            msg_type = msg.get("type", "")
            data = msg.get("data", {})
            if msg_type == "progress":
                value = data.get("value", 0)
                max_val = data.get("max", 1)
                pct = 10 + int(value / max_val * 80) if max_val > 0 else 10
                if on_progress:
                    on_progress(pct, _map_phase(f"Sampling {value}/{max_val}"), {})
            elif msg_type == "executing":
                node_id = data.get("node_id") if "node_id" in data else data.get("node")
                if node_id is None or node_id == 0:
                    if on_progress:
                        on_progress(100, _map_phase("Completed"), {})
                    return "done"
                if on_progress:
                    on_progress(90, _map_phase(f"Executing node {node_id}"), {})
            elif msg_type == "executed":
                if on_progress:
                    on_progress(95, _map_phase("Image saved"), data)
            elif msg_type == "execution_error":
                raise RuntimeError(f"ComfyUI execution error: {data}")
            elif msg_type == "execution_interrupted":
                raise asyncio.CancelledError("Generation interrupted")
            elif msg_type == "execution_success":
                if on_progress:
                    on_progress(100, _map_phase("Completed"), {})
                return "done"
            return None

        while True:
            if self._cancel_requested:
                await self._client.interrupt()
                raise asyncio.CancelledError("Generation cancelled by user")
            if time.time() - t_start > max_wait_s:
                raise RuntimeError(f"Generation timed out after {max_wait_s}s")

            if ws_alive:
                msg = await self._client.ws_recv()
                if msg is None:
                    ws_alive = False  # WS 关闭 → 转 HTTP 轮询
                    continue
                if _handle_msg(msg) == "done":
                    break
                continue

            # HTTP 轮询 history，直到有输出或明确错误
            history = await self._client.get_history(prompt_id)
            entry = history.get(prompt_id)
            if entry:
                msgs = entry.get("status", {}).get("messages", []) or []
                types = [m[0] for m in msgs if isinstance(m, list) and m]
                if "execution_error" in types:
                    raise RuntimeError(f"ComfyUI execution error: {msgs}")
                if "execution_interrupted" in types:
                    raise asyncio.CancelledError("Generation interrupted")
                if entry.get("outputs"):
                    if on_progress:
                        on_progress(100, _map_phase("Completed"), {})
                    break
            await asyncio.sleep(2)

        # 4. 获取输出
        outputs = await self._fetch_outputs(prompt_id)
        self._current_prompt_id = None
        return outputs

    async def cancel(self) -> None:
        """取消当前推理"""
        self._cancel_requested = True
        if self._client:
            await self._client.interrupt()
        logger.info(f"ComfyEngine '{self._name}' cancel requested")

    async def _fetch_outputs(self, prompt_id: str) -> list[str]:
        """从 ComfyUI 历史获取输出文件并保存到本地（history 写入有延迟，带重试）

        §4.1 水印接入：保存后嵌入 DCT 水印
        §4.2 输出命名规范：outputs/{engine}/{date}/{task_id}_{type}.png
        §2.5 缩略图：生成 512px 缩略图到 data/cache/thumbs/
        """
        if not self._client:
            return []

        outputs_data: dict[str, Any] = {}
        await asyncio.sleep(1.0)  # 等 history 落库
        for attempt in range(40):
            history = await self._client.get_history(prompt_id)
            outputs_data = history.get(prompt_id, {}).get("outputs", {})
            if outputs_data:
                break
            await asyncio.sleep(0.5)
        if not outputs_data:
            # 兜底：拉全量 history 按 id 查找
            all_history = await self._client.get_history("")
            outputs_data = all_history.get(prompt_id, {}).get("outputs", {})
        if not outputs_data:
            logger.warning(f"No outputs in history for {prompt_id} after retries")

        cfg = get_config()
        output_base = Path(cfg.project_root) / cfg.output.base_dir
        output_base.mkdir(parents=True, exist_ok=True)

        # §4.2 输出命名规范：outputs/{engine}/{date}/
        date_str = datetime.now().strftime("%Y%m%d")
        engine_dir = output_base / self._name / date_str
        engine_dir.mkdir(parents=True, exist_ok=True)

        # 水印配置
        wm_cfg = cfg.watermark
        wm_enabled = wm_cfg.enabled_in_code
        product_id = wm_cfg.product_id

        # 缩略图配置
        thumb_enabled = cfg.output.save_thumbnail
        thumb_max_side = cfg.output.thumbnail_max_side
        thumb_dir = Path(cfg.project_root) / "data" / "cache" / "thumbs"
        if thumb_enabled:
            thumb_dir.mkdir(parents=True, exist_ok=True)

        saved_paths: list[str] = []
        out_type_idx = 0
        out_types = ("original", "upscaled", "compare")

        for _node_id, node_output in outputs_data.items():
            for img_info in node_output.get("images", []):
                filename = img_info.get("filename", "")
                subfolder = img_info.get("subfolder", "")
                if not filename:
                    continue
                img_data = await self._client.get_image(filename, subfolder, "output")

                # §4.2 命名规范
                out_type = out_types[out_type_idx] if out_type_idx < len(out_types) else "original"
                out_type_idx += 1
                new_filename = f"{prompt_id[:16]}_{out_type}.png"
                local_path = engine_dir / new_filename
                local_path.write_bytes(img_data)
                local_path_str = str(local_path).replace("\\", "/")
                saved_paths.append(local_path_str)

                # §4.1 水印嵌入
                if wm_enabled and img_data:
                    try:
                        import io

                        import numpy as np
                        from PIL import Image

                        from ..watermark import embed_watermark

                        img = Image.open(io.BytesIO(img_data))
                        arr = np.array(img)
                        wm_arr = embed_watermark(
                            arr, product_id, prompt_id[:16], time.time()
                        )
                        wm_img = Image.fromarray(wm_arr.astype(np.uint8))
                        buf = io.BytesIO()
                        wm_img.save(buf, format="PNG")
                        local_path.write_bytes(buf.getvalue())
                        logger.debug(f"Watermark embedded: {local_path.name}")
                    except Exception as e:
                        logger.warning(f"Watermark embedding failed: {e}")

                # §2.5 缩略图生成
                if thumb_enabled and img_data:
                    try:
                        import io as _io

                        from PIL import Image as PILImage

                        img = PILImage.open(_io.BytesIO(img_data))
                        w, h = img.size
                        scale = thumb_max_side / max(w, h)
                        if scale < 1.0:
                            thumb = img.resize(
                                (int(w * scale), int(h * scale)),
                                PILImage.LANCZOS,
                            )
                        else:
                            thumb = img
                        thumb_filename = f"{prompt_id[:16]}_{out_type}_thumb.png"
                        thumb_path = thumb_dir / thumb_filename
                        thumb.save(str(thumb_path), format="PNG")
                        self._thumbnail_path = str(thumb_path).replace("\\", "/")
                        logger.debug(f"Thumbnail generated: {thumb_path.name}")
                    except Exception as e:
                        logger.warning(f"Thumbnail generation failed: {e}")
                        self._thumbnail_path = local_path_str

        return saved_paths
