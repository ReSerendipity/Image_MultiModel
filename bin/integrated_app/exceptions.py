"""
exceptions.py — Image MultiModel 统一异常层次

P1-4 改造（来源：TTS_MultiModel）：
定义系统所有业务异常的继承体系，提供标准化的错误编码、
HTTP 状态码映射以及附加元数据字段。

与 middleware/error_handler 的协作：
    error_handler.py 中的全局异常处理器会捕获本模块定义的异常，
    读取 code / status_code / message 等字段，构造标准化的
    JSON 错误响应。

HTTP 状态码映射约定：
    400   客户端请求错误（ValidationError / EngineNotReadyError）
    404   资源不存在（TaskNotFoundError / PresetNotFoundError）
    500   服务端内部错误（GenerationError）
    503   资源不可用（ComfyUIConnectionError）
"""

from __future__ import annotations

from typing import Any


class ImageAppError(Exception):
    """Image MultiModel 基础应用异常基类。

    Attributes:
        message: 人类可读的错误描述文本。
        code: 机器可读的错误编码，供前端做分支判断。
        status_code: 映射到 HTTP 响应的状态码。
        detail: 可选的结构化详情字典。
    """

    def __init__(
        self,
        message: str = "",
        code: str = "APP_ERROR",
        status_code: int = 400,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.message: str = message
        self.code: str = code
        self.status_code: int = status_code
        self.detail: dict[str, Any] | None = detail
        super().__init__(message)


class EngineNotReadyError(ImageAppError):
    """引擎未就绪异常（HTTP 503）。"""

    def __init__(self, message: str = "引擎未就绪，请先加载模型") -> None:
        super().__init__(message, code="ENGINE_NOT_READY", status_code=503)


class EngineNotFoundError(ImageAppError):
    """引擎不存在异常（HTTP 404）。"""

    def __init__(self, message: str = "引擎不存在", engine_name: str = "") -> None:
        self.engine_name: str = engine_name
        super().__init__(message, code="ENGINE_NOT_FOUND", status_code=404)


class TaskNotFoundError(ImageAppError):
    """任务不存在异常（HTTP 404）。"""

    def __init__(self, message: str = "任务不存在", task_id: str = "") -> None:
        self.task_id: str = task_id
        super().__init__(message, code="TASK_NOT_FOUND", status_code=404)


class PresetNotFoundError(ImageAppError):
    """预设不存在异常（HTTP 404）。"""

    def __init__(self, message: str = "预设不存在") -> None:
        super().__init__(message, code="PRESET_NOT_FOUND", status_code=404)


class ValidationError(ImageAppError):
    """请求参数校验失败异常（HTTP 400）。"""

    def __init__(self, message: str, field: str = "") -> None:
        self.field: str = field
        super().__init__(message, code="VALIDATION_ERROR", status_code=400)


class ComfyUIConnectionError(ImageAppError):
    """原生引擎连接异常（HTTP 503，遗留兼容类）。"""

    def __init__(self, message: str = "引擎不可达", url: str = "") -> None:
        self.url: str = url
        super().__init__(message, code="COMFY_NOT_REACHABLE", status_code=503)


class GenerationError(ImageAppError):
    """生成流程异常（HTTP 500）。"""

    def __init__(self, message: str = "生成失败", engine: str = "") -> None:
        self.engine: str = engine
        super().__init__(message, code="GENERATION_ERROR", status_code=500)
