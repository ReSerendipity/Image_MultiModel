"""MCP (Model Context Protocol) 服务器模块（Image MultiModel 版）。

提供符合 MCP 规范的服务器实现，允许 AI 助手（如 Claude Desktop、Cursor 等）
通过标准化协议调用 Image_MultiModel 的功能：

提供的 MCP 工具 (Tools):
- list_tools: 列出所有可用的图像生成工具及能力描述
- txt2img: 文生图生成（构建 GenerationConfig → 引擎推理 → 返回输出路径）
- status: 获取引擎加载状态与任务队列状态
- cancel: 取消进行中的生成任务

支持的传输方式：
- stdio: 标准输入输出（默认，用于 Claude Desktop 等桌面客户端）

设计要点：
- 遵循 MCP 规范（JSON-RPC 2.0 消息格式）
- 延迟导入引擎/队列，避免服务器启动时加载大模型
- 异步实现，支持并发请求
- 提供工具描述、参数 schema 供 LLM 理解
- 与现有 engine_interface / model_registry / task_queue 集成，复用业务逻辑

参考来源：TTS_MultiModel/app/integrated_app/mcp_server.py（签名保持一致）。
"""

from __future__ import annotations

import asyncio
import json
import inspect
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("image_multimodel")


# ---------------------------------------------------------------------------
# MCP 协议常量
# ---------------------------------------------------------------------------

MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "image-multimodel"
MCP_SERVER_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class MCPTool:
    """MCP 工具定义。

    Attributes:
        name: 工具名称（唯一标识）。
        description: 工具描述（供 LLM 理解用途）。
        input_schema: JSON Schema 定义输入参数。
        handler: 异步处理函数。
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Any


@dataclass
class MCPRequest:
    """MCP JSON-RPC 请求。

    Attributes:
        id: 请求 ID（用于响应匹配）。
        method: 方法名。
        params: 参数字典。
    """

    id: int | str | None
    method: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPResponse:
    """MCP JSON-RPC 响应。

    Attributes:
        id: 请求 ID（与请求对应）。
        result: 成功结果。
        error: 错误信息。
    """

    id: int | str | None
    result: Any | None = None
    error: dict[str, Any] | None = None

    def to_json(self) -> str:
        """序列化为 JSON 字符串。

        Returns:
            JSON 字符串。
        """
        response: dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error is not None:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return json.dumps(response, ensure_ascii=False)


# ---------------------------------------------------------------------------
# MCP 服务器类
# ---------------------------------------------------------------------------


class MCPServer:
    """MCP 服务器实现。

    处理 JSON-RPC 2.0 消息，提供 tools/list 和 tools/call 等标准方法，
    将 Image_MultiModel 功能暴露给 AI 助手。

    Usage::

        server = MCPServer()
        await server.run_stdio()
    """

    def __init__(self) -> None:
        """初始化 MCP 服务器，注册所有工具。"""
        self._tools: dict[str, MCPTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """注册默认的 Image_MultiModel 相关工具。"""
        self.register_tool(
            MCPTool(
                name="list_tools",
                description="列出所有可用的图像生成工具及其能力描述。",
                input_schema={"type": "object", "properties": {}},
                handler=self._handle_list_tools,
            )
        )

        self.register_tool(
            MCPTool(
                name="txt2img",
                description="文本生成图像。支持提示词、负向提示词、分辨率、步数、CFG、seed、批量数等参数。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "正向提示词（描述想生成的画面）",
                        },
                        "negative_prompt": {
                            "type": "string",
                            "description": "负向提示词（不希望出现的内容）",
                            "default": "",
                        },
                        "width": {
                            "type": "integer",
                            "description": "输出图像宽度（512-4096，16 的倍数）",
                            "default": 1024,
                        },
                        "height": {
                            "type": "integer",
                            "description": "输出图像高度（512-4096，16 的倍数）",
                            "default": 1024,
                        },
                        "steps": {
                            "type": "integer",
                            "description": "采样步数（1-50）",
                            "default": 8,
                        },
                        "cfg": {
                            "type": "number",
                            "description": "CFG 引导强度（1.0-10.0）",
                            "default": 1.0,
                        },
                        "seed": {
                            "type": "integer",
                            "description": "随机种子（-1 表示随机）",
                            "default": -1,
                        },
                        "batch_size": {
                            "type": "integer",
                            "description": "批量生成数量（1-9999）",
                            "default": 1,
                        },
                        "engine": {
                            "type": "string",
                            "description": "引擎名称（默认使用配置文件中的 default_engine）",
                        },
                    },
                    "required": ["prompt"],
                },
                handler=self._handle_txt2img,
            )
        )

        self.register_tool(
            MCPTool(
                name="status",
                description="获取当前引擎加载状态、GPU 显存使用情况与任务队列状态。",
                input_schema={"type": "object", "properties": {}},
                handler=self._handle_status,
            )
        )

        self.register_tool(
            MCPTool(
                name="cancel",
                description="取消指定的生成任务。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "要取消的任务 ID",
                        }
                    },
                    "required": ["task_id"],
                },
                handler=self._handle_cancel,
            )
        )

    def register_tool(self, tool: MCPTool) -> None:
        """注册一个 MCP 工具。

        Args:
            tool: MCPTool 实例。
        """
        self._tools[tool.name] = tool

    async def _handle_request(self, request: MCPRequest) -> MCPResponse:
        """处理单个 MCP 请求。

        Args:
            request: MCP 请求。

        Returns:
            MCP 响应。
        """
        try:
            if request.method == "initialize":
                return self._handle_initialize(request)
            elif request.method == "tools/list":
                return self._handle_tools_list(request)
            elif request.method == "tools/call":
                return await self._handle_tools_call(request)
            elif request.method == "ping":
                return MCPResponse(id=request.id, result={})
            else:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32601,
                        "message": f"方法未找到: {request.method}",
                    },
                )
        except Exception as e:
            logger.error(f"[MCP] 处理请求失败: {e}", exc_info=True)
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"内部错误: {str(e)}",
                },
            )

    def _handle_initialize(self, request: MCPRequest) -> MCPResponse:
        """处理 initialize 方法，返回服务器能力。

        Args:
            request: 初始化请求。

        Returns:
            包含服务器信息和能力的响应。
        """
        return MCPResponse(
            id=request.id,
            result={
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "serverInfo": {
                    "name": MCP_SERVER_NAME,
                    "version": MCP_SERVER_VERSION,
                },
                "capabilities": {
                    "tools": {"listChanged": False},
                },
            },
        )

    def _handle_tools_list(self, request: MCPRequest) -> MCPResponse:
        """处理 tools/list 方法，返回所有已注册工具。

        Args:
            request: 请求。

        Returns:
            工具列表响应。
        """
        tools_list = []
        for tool in self._tools.values():
            tools_list.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
            )

        return MCPResponse(
            id=request.id,
            result={"tools": tools_list},
        )

    async def _handle_tools_call(self, request: MCPRequest) -> MCPResponse:
        """处理 tools/call 方法，调度到对应工具处理函数。

        Args:
            request: 工具调用请求（包含 name 和 arguments 参数）。

        Returns:
            工具执行结果响应。
        """
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        if tool_name not in self._tools:
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32602,
                    "message": f"未知工具: {tool_name}",
                },
            )

        tool = self._tools[tool_name]
        try:
            result = tool.handler(**arguments)
            if inspect.iscoroutine(result) or hasattr(result, "__await__"):
                result = await result
            return MCPResponse(
                id=request.id,
                result={
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2),
                        }
                    ]
                },
            )
        except TypeError as e:
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32602,
                    "message": f"参数错误: {str(e)}",
                },
            )
        except Exception as e:
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"工具执行失败: {str(e)}",
                },
            )

    # -----------------------------------------------------------------------
    # 工具处理函数
    # -----------------------------------------------------------------------

    async def _handle_list_tools(self, **kwargs: Any) -> dict[str, Any]:
        """列出所有可用的图像生成工具及能力描述。

        Returns:
            工具列表与数量。
        """
        tools = []
        for tool in self._tools.values():
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "required_params": [
                        k for k, v in tool.input_schema.get("properties", {}).items()
                        if k in tool.input_schema.get("required", [])
                    ],
                }
            )
        return {"tools": tools, "count": len(tools)}

    async def _handle_txt2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 8,
        cfg: float = 1.0,
        seed: int = -1,
        batch_size: int = 1,
        engine: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """文本生成图像工具处理函数。

        构建 GenerationConfig，通过引擎推理生成图像。

        Args:
            prompt: 正向提示词。
            negative_prompt: 负向提示词。
            width: 输出宽度。
            height: 输出高度。
            steps: 采样步数。
            cfg: CFG 引导强度。
            seed: 随机种子（-1 随机）。
            batch_size: 批量数量。
            engine: 引擎名称（None 使用默认）。

        Returns:
            包含生成结果信息的字典。
        """
        try:
            from .config import get_config
            from .engine_interface import GenerationConfig, get_registry
            from .model_manager import get_model_manager
            from .model_registry import get_model_registry
            from .spec import validate_output_size

            cfg_obj = get_config()
            engine_name = engine or cfg_obj.models.default_engine

            if engine_name not in cfg_obj.models.engines:
                return {
                    "success": False,
                    "message": f"引擎不存在: {engine_name}",
                    "available_engines": list(cfg_obj.models.engines.keys()),
                }

            # 校验输出尺寸
            w, h = validate_output_size(width, height)

            # 构建 GenerationConfig
            gen_config = GenerationConfig(
                positive_prompt=prompt,
                negative_prompt=negative_prompt,
                cfg=cfg,
                steps=steps,
                width=w,
                height=h,
                seed=seed,
                batch_size=batch_size,
                engine_name=engine_name,
            )

            # 获取或创建引擎实例
            registry = get_model_registry()
            reg = get_registry()

            eng = reg.get_active()
            if eng is None or getattr(eng, "name", "") != engine_name:
                engine_cfg = cfg_obj.models.engines[engine_name]
                eng = registry.create_engine_instance(
                    engine_name=engine_name,
                    display_name=engine_cfg.display_name,
                    display_name_en=engine_cfg.display_name_en,
                    backend=getattr(engine_cfg, "backend", "native"),
                    config=engine_cfg.model_dump(),
                )
                reg.register(engine_name, lambda **_: eng)
                reg.set_active(engine_name)

            # 确保引擎已加载
            if not eng.is_ready():
                manager = get_model_manager()
                await manager.load_engine(engine_name, eng)

            # 执行推理
            output_paths = await eng.infer_txt2img(gen_config)

            return {
                "success": True,
                "engine": engine_name,
                "output_paths": output_paths,
                "count": len(output_paths),
                "width": w,
                "height": h,
                "message": f"成功生成 {len(output_paths)} 张图像",
            }

        except Exception as e:
            logger.error(f"[MCP] 文生图失败: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    async def _handle_status(self, **kwargs: Any) -> dict[str, Any]:
        """获取引擎状态与任务队列状态。

        Returns:
            引擎列表、活动引擎、队列状态。
        """
        try:
            from .config import get_config
            from .engine_interface import get_registry
            from .model_manager import get_model_manager

            cfg = get_config()
            registry = get_registry()
            manager = get_model_manager()

            engines = []
            for name in cfg.models.engines:
                state = manager.get_state(name)
                engines.append(
                    {
                        "name": name,
                        "display_name": cfg.models.engines[name].display_name,
                        "state": state.value,
                        "is_active": name == registry.active_engine_name,
                    }
                )

            return {
                "engines": engines,
                "active_engine": registry.active_engine_name,
                "default_engine": cfg.models.default_engine,
                "version": cfg.version,
            }

        except Exception as e:
            logger.error(f"[MCP] 获取状态失败: {e}", exc_info=True)
            return {"error": str(e)}

    async def _handle_cancel(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        """取消生成任务。

        MCP stdio 模式下，优先尝试取消活动引擎的当前推理；
        若 HTTP 服务器有全局 TaskQueue 也尝试取消对应任务。

        Args:
            task_id: 任务 ID（MCP stdio 模式下可选，传空串则取消当前引擎推理）。

        Returns:
            取消结果。
        """
        try:
            from .engine_interface import get_registry

            cancelled = False

            # 1. 尝试取消活动引擎的当前推理
            reg = get_registry()
            eng = reg.get_active()
            if eng is not None:
                await eng.cancel()
                cancelled = True

            # 2. 尝试取消 HTTP 服务器的队列任务（如果有）
            if not cancelled and task_id:
                try:
                    from .app_server import app

                    queue = app.state.task_queue
                    cancelled = await queue.cancel(task_id)
                except Exception:
                    pass

            return {
                "success": cancelled,
                "task_id": task_id,
                "message": "取消请求已发送" if cancelled else "无活动任务可取消",
            }

        except Exception as e:
            logger.error(f"[MCP] 取消任务失败: {e}", exc_info=True)
            return {"success": False, "message": str(e), "task_id": task_id}

    # -----------------------------------------------------------------------
    # 传输层
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_message(line: str) -> MCPRequest | None:
        """解析一行 JSON-RPC 消息。

        Args:
            line: JSON 字符串行。

        Returns:
            MCPRequest 实例，解析失败返回 None。
        """
        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
            return MCPRequest(
                id=data.get("id"),
                method=data.get("method", ""),
                params=data.get("params", {}),
            )
        except json.JSONDecodeError as e:
            logger.warning(f"[MCP] JSON 解析失败: {e}, line: {line[:100]}")
            return None

    async def run_stdio(self) -> None:
        """通过 stdio 运行 MCP 服务器。

        从 stdin 读取 JSON-RPC 请求，处理后将响应写入 stdout。
        这是 Claude Desktop 等桌面客户端的标准接入方式。
        """
        logger.info("[MCP] MCP 服务器启动 (stdio 模式)")

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)

        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="replace")
                request = self._parse_message(line_str)

                if request is None:
                    continue

                response = await self._handle_request(request)
                response_json = response.to_json()

                sys.stdout.write(response_json + "\n")
                sys.stdout.flush()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MCP] 主循环错误: {e}", exc_info=True)

        logger.info("[MCP] MCP 服务器停止")


# ---------------------------------------------------------------------------
# 便捷启动函数
# ---------------------------------------------------------------------------


def run_mcp_server(transport: str = "stdio") -> None:
    """启动 MCP 服务器。

    Args:
        transport: 传输方式，目前支持 "stdio"。
    """
    server = MCPServer()

    if transport == "stdio":
        asyncio.run(server.run_stdio())
    else:
        raise ValueError(f"不支持的传输方式: {transport}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_mcp_server()
