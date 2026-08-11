"""
tests/test_error_handler_edge.py — 错误处理器异常分支覆盖（提升覆盖率）
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from integrated_app.exceptions import ImageAppError
from integrated_app.middleware import error_handler as eh
from integrated_app.middleware.error_handler import register_error_handlers


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/test/http404")
    async def notfound():
        raise StarletteHTTPException(status_code=404, detail="not found")

    register_error_handlers(app)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def _run(coro):
    return asyncio.run(coro)


class TestEdgeBranches:
    def test_get_request_id_attribute_error(self):
        """_get_request_id 内部异常时回退空串"""
        req = Request({"type": "http", "method": "GET", "path": "/"})
        assert eh._get_request_id(req) == ""

    def test_parse_validation_errors_missing_loc(self):
        exc = RequestValidationError([{"msg": "no loc", "type": "t"}])
        parsed = eh._parse_validation_errors(exc)
        assert parsed[0]["field"] == "request"

    def test_parse_validation_errors_whole_failure(self, monkeypatch):
        """errors() 返回不可迭代对象时走 structure_fallback"""
        exc = RequestValidationError([])
        monkeypatch.setattr(type(exc), "errors", lambda self: None)
        parsed = eh._parse_validation_errors(exc)
        assert parsed[0]["field"] == "__all__"

    def test_http_exception_handler_no_detail(self):
        req = Request({"type": "http", "method": "GET", "path": "/"})
        resp = _run(eh._http_exception_handler(req, StarletteHTTPException(status_code=405)))
        assert resp.status_code == 405

    def test_http_exception_handler_inner_failure(self, monkeypatch):
        """http handler 内部异常回退 FATAL_ERROR"""
        req = Request({"type": "http", "method": "GET", "path": "/"})

        def boom(request):
            raise RuntimeError("state broken")

        monkeypatch.setattr(eh, "_get_request_id", boom)
        resp = _run(eh._http_exception_handler(req, StarletteHTTPException(status_code=404)))
        assert resp.status_code == 500

    def test_generic_handler_passes_http_exception(self, client):
        """generic handler 放行 StarletteHTTPException"""
        r = client.get("/test/http404")
        assert r.status_code == 404
        body = r.json()
        assert body["error"]["code"] == "HTTP_404"
        assert body["error"]["message"] == "not found"

    def test_build_error_response_with_request_id(self):
        resp = eh._build_error_response(
            code="C", message="m", status_code=400, detail="d", request_id="rid-1"
        )
        body = json.loads(resp.body)
        assert body["error"]["request_id"] == "rid-1"
        assert body["error"]["detail"] == "d"

    def test_image_error_handler_inner_failure(self, monkeypatch):
        """image handler 内部异常回退 FATAL_ERROR"""
        req = Request({"type": "http", "method": "GET", "path": "/"})
        exc = ImageAppError(code="X", message="m", status_code=400)

        def boom(request):
            raise RuntimeError("state broken")

        monkeypatch.setattr(eh, "_get_request_id", boom)
        resp = _run(eh.image_error_handler(req, exc))
        assert resp.status_code == 500

    def test_generic_handler_inner_failure(self, monkeypatch):
        """generic handler 内部异常回退 FATAL_ERROR"""
        req = Request({"type": "http", "method": "GET", "path": "/"})
        exc = RuntimeError("boom")

        def boom(request):
            raise RuntimeError("state broken")

        monkeypatch.setattr(eh, "_get_request_id", boom)
        resp = _run(eh.generic_error_handler(req, exc))
        assert resp.status_code == 500
