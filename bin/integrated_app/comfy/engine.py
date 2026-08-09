"""
comfy/engine.py — ComfyEngine (ImageEngine 实现)

对应 MASTER_PLAN §4 / PRD §4.1: comfy/engine.py
对应 PRD §6: ComfyEngine（ImageEngine impl，仅 infer_txt2img）
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..engine_interface import GenerationConfig, ProgressCallback
from ..config import get_config
from .client import ComfyClient
from .workflow import WorkflowManager

logger = logging.getLogger(__name__)


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
        config: Optional[Dict[str, Any]] = None,
        client: Optional[ComfyClient] = None,
    ) -> None:
        self._name = name
        self._display_name = display_name or name
        self._display_name_en = display_name_en or name
        self._config = config or {}
        self._client: Optional[ComfyClient] = client
        self._workflow_mgr: Optional[WorkflowManager] = None
        self._ready = False
        self._current_prompt_id: Optional[str] = None
        self._cancel_requested = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    def is_ready(self) -> bool:
        return self._ready

    async def load(self, on_progress: Optional[ProgressCallback] = None) -> None:
        """加载引擎：建立 ComfyUI 连接 + 初始化 WorkflowManager"""
        if on_progress:
            on_progress(10, "Connecting to ComfyUI...", {})

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
            on_progress(40, "Connecting HTTP...", {})

        await self._client.connect()

        if on_progress:
            on_progress(70, "Loading workflow...", {})

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
            on_progress(100, "Engine ready", {})

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
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[str]:
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
            on_progress(5, "Patching workflow...", {})

        workflow_data = self._workflow_mgr.patch(config)

        # 2. 提交到 ComfyUI
        if on_progress:
            on_progress(10, "Queuing prompt...", {})

        prompt_id = await self._client.queue_prompt(workflow_data)
        self._current_prompt_id = prompt_id

        # 3. WS 监听进度
        await self._client.connect_ws()

        while True:
            if self._cancel_requested:
                await self._client.interrupt()
                raise asyncio.CancelledError("Generation cancelled by user")

            msg = await self._client.ws_recv()
            if msg is None:
                break

            msg_type = msg.get("type", "")

            if msg_type == "progress":
                # {type: progress, data: {value, max, prompt_id}}
                data = msg.get("data", {})
                value = data.get("value", 0)
                max_val = data.get("max", 1)
                pct = 10 + int(value / max_val * 80) if max_val > 0 else 10
                if on_progress:
                    on_progress(pct, f"Sampling {value}/{max_val}", {})

            elif msg_type == "executing":
                data = msg.get("data", {})
                node_id = data.get("node_id")
                if node_id and on_progress:
                    on_progress(90, f"Executing node {node_id}", {})

            elif msg_type == "executed":
                data = msg.get("data", {})
                if on_progress:
                    on_progress(95, "Image saved", data)

            elif msg_type == "execution_error":
                data = msg.get("data", {})
                raise RuntimeError(f"ComfyUI execution error: {data}")

            elif msg_type == "execution_interrupted":
                raise asyncio.CancelledError("Generation interrupted")

            elif msg_type == "execution_success":
                if on_progress:
                    on_progress(100, "Completed", {})
                break

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

    async def _fetch_outputs(self, prompt_id: str) -> List[str]:
        """从 ComfyUI 历史获取输出文件并保存到本地"""
        if not self._client:
            return []

        history = await self._client.get_history(prompt_id)
        outputs_data = history.get(prompt_id, {}).get("outputs", {})

        cfg = get_config()
        output_base = Path(cfg.project_root) / cfg.output.base_dir
        output_base.mkdir(parents=True, exist_ok=True)

        saved_paths: List[str] = []
        for _node_id, node_output in outputs_data.items():
            for img_info in node_output.get("images", []):
                filename = img_info.get("filename", "")
                subfolder = img_info.get("subfolder", "")
                if not filename:
                    continue
                img_data = await self._client.get_image(filename, subfolder, "output")
                # 保存到本地
                local_path = output_base / filename
                local_path.write_bytes(img_data)
                saved_paths.append(str(local_path).replace("\\", "/"))

        return saved_paths
