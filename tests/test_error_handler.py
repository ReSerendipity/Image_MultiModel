"""
tests/test_error_handler.py — 全局错误处理中间件测试

P1-4 改造：验证三类 handler 的正确性
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

from integrated_app.exceptions import (
    ComfyUIConnectionError,
    EngineNotReadyError,
    TaskNotFoundError,
    ValidationError,
)
from integrated_app.middleware.error_handler import register_error_handlers


@pytest.fixture
def app():
    """创建带错误处理器的测试 FastAPI 应用"""
    app = FastAPI()

    @app.get("/test/custom")
    async def raise_custom():
        raise EngineNotReadyError("引擎未就绪测试")

    @app.get("/test/notfound")
    async def raise_not_found():
        raise TaskNotFoundError("任务不存在", task_id="test-123")

    @app.get("/test/validation")
    async def raise_validation():
        raise ValidationError("参数错误", field="seed")

    @app.get("/test/generic")
    async def raise_generic():
        raise RuntimeError("未知内部错误")

    @app.get("/test/comfy")
    async def raise_comfy():
        raise ComfyUIConnectionError("ComfyUI 不可达", url="http://localhost:8188")

    register_error_handlers(app)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


class TestImageAppErrorHandler:
    """ImageAppError handler 测试"""

    def test_custom_error_returns_json(self, client):
        """自定义异常返回 JSON 而非 HTML"""
        resp = client.get("/test/custom")
        assert resp.status_code == 503
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "ENGINE_NOT_READY"
        assert "引擎未就绪测试" in data["error"]["message"]

    def test_not_found_error_returns_404(self, client):
        """TaskNotFoundError 返回 404"""
        resp = client.get("/test/notfound")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "TASK_NOT_FOUND"

    def test_validation_error_returns_400(self, client):
        """ValidationError 返回 400"""
        resp = client.get("/test/validation")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "参数错误" in data["error"]["message"]

    def test_comfy_error_returns_503(self, client):
        """ComfyUIConnectionError 返回 503"""
        resp = client.get("/test/comfy")
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "COMFY_NOT_REACHABLE"


class TestGenericErrorHandler:
    """兜底 Exception handler 测试"""

    def test_generic_error_returns_500_json(self, client):
        """未捕获异常返回 JSON 500，不含堆栈"""
        resp = client.get("/test/generic")
        assert resp.status_code == 500
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "INTERNAL_ERROR"
        # 不应包含堆栈信息
        assert "RuntimeError" not in resp.text
        assert "raise_generic" not in resp.text


class TestValidationErrorHandler:
    """Pydantic ValidationError handler 测试"""

    def test_pydantic_validation_error(self, app):
        """Pydantic 422 验证错误返回字段级列表"""
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str
            value: int

        @app.post("/test/pydantic")
        async def create_item(item: Item):
            return {"item": item}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/test/pydantic", json={"name": "test", "value": "not_int"})
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert isinstance(data["error"]["detail"], list)
