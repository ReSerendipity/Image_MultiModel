"""
middleware/error_handler.py — 全局异常处理器

P1-4 改造（来源：TTS_MultiModel）：
作为 FastAPI 应用的最后一道防线，捕获所有业务与框架异常并转换为
结构一致的 JSON 响应。

统一响应结构：
    {"success": false, "error": {"code": ..., "message": ..., "detail": ...}}

四类异常与响应映射：
    ① ImageAppError 及其子类：透传 status_code / code / message
    ② RequestValidationError（Pydantic）：422 VALIDATION_ERROR
    ③ StarletteHTTPException：透传 status 与 detail
    ④ 兜底 Exception：500 INTERNAL_ERROR，绝不返回堆栈给前端
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..exceptions import ImageAppError

logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str:
    """安全地从 request.state 获取 request_id。"""
    try:
        return str(getattr(request.state, "request_id", ""))
    except (AttributeError, ValueError):
        return ""


def _build_error_response(
    code: str,
    message: str,
    status_code: int,
    detail: Any = None,
    request_id: str = "",
) -> JSONResponse:
    """构建统一格式的错误 JSON 响应。"""
    content: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if detail is not None:
        content["error"]["detail"] = detail
    if request_id:
        content["error"]["request_id"] = request_id

    try:
        return JSONResponse(status_code=status_code, content=content)
    except (TypeError, ValueError, UnicodeEncodeError) as e:
        logger.error("_build_error_response JSON 序列化失败: %s", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "FATAL_ERROR", "message": "Fatal error"}},
        )


def _parse_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """安全解析 Pydantic errors() 为字段级列表。"""
    result: list[dict[str, Any]] = []
    raw_errors = exc.errors()
    try:
        for error in raw_errors:
            try:
                loc_parts = error.get("loc", ())
                field_name = ".".join(str(x) for x in loc_parts) if loc_parts else "request"
                result.append(
                    {
                        "field": field_name,
                        "message": str(error.get("msg", "Unknown validation error")),
                        "type": str(error.get("type", "unknown")),
                    }
                )
            except (KeyError, TypeError, ValueError) as e:
                logger.debug("单条 validation error 解析失败: %s", e)
                result.append(
                    {"field": "__raw__", "message": str(error), "type": "parse_fallback"}
                )
    except (TypeError, AttributeError) as e:
        logger.warning("validation errors() 整体结构异常: %s", e)
        result = [{"field": "__all__", "message": str(raw_errors), "type": "structure_fallback"}]
    return result


async def image_error_handler(request: Request, exc: ImageAppError) -> JSONResponse:
    """ImageAppError 及其子类处理器。"""
    try:
        request_id = _get_request_id(request)
        logger.warning(
            "ImageAppError code=%s status=%s message=%s request_id=%s",
            exc.code,
            exc.status_code,
            exc.message,
            request_id,
        )
        return _build_error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            detail=getattr(exc, "detail", None),
            request_id=request_id,
        )
    except Exception as inner:
        logger.exception("ImageAppError handler 内部异常: %s", inner)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "FATAL_ERROR"}},
        )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic RequestValidationError 处理器。"""
    try:
        request_id = _get_request_id(request)
        logger.warning("Validation error request_id=%s exc=%s", request_id, exc)
        errors = _parse_validation_errors(exc)
        return _build_error_response(
            code="VALIDATION_ERROR",
            message="请求参数验证失败",
            status_code=422,
            detail=errors,
            request_id=request_id,
        )
    except Exception as inner:
        logger.exception("ValidationError handler 内部异常: %s", inner)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "FATAL_ERROR"}},
        )


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """StarletteHTTPException 处理器（404 / 405 等框架级 HTTP 错误）。"""
    try:
        request_id = _get_request_id(request)
        return _build_error_response(
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail) if exc.detail else f"HTTP {exc.status_code}",
            status_code=exc.status_code,
            detail=exc.detail,
            request_id=request_id,
        )
    except Exception as inner:
        logger.exception("StarletteHTTPException handler 内部异常: %s", inner)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "FATAL_ERROR"}},
        )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常兜底处理器。

    绝不把 exc.args / 堆栈 / 文件路径返回给前端。
    完整堆栈仅通过 logger.exception 写入服务端日志。
    """
    try:
        request_id = _get_request_id(request)

        # 放行 FastAPI 原生的 HTTPException
        if isinstance(exc, StarletteHTTPException):
            return await _http_exception_handler(request, exc)

        logger.error(
            "Unhandled exception type=%s exc=%s request_id=%s",
            type(exc).__name__,
            exc,
            request_id,
            exc_info=True,
        )
        return _build_error_response(
            code="INTERNAL_ERROR",
            message="服务器内部错误，请稍后重试",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=None,
            request_id=request_id,
        )
    except Exception as inner:
        logger.exception("generic_error_handler 自身异常: %s", inner)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "FATAL_ERROR"}},
        )


def register_error_handlers(app: FastAPI) -> None:
    """在 FastAPI 应用实例上一次性注册所有异常处理器。

    注册顺序：先注册更具体的类型，最后注册通用 Exception。
    """
    app.add_exception_handler(ImageAppError, image_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_error_handler)  # type: ignore[arg-type]
