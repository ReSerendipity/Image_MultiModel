"""
tests/test_system_routes.py — 系统路由深度测试

覆盖 system_routes.py: SSE 事件流 + disk 信息 + GPU 状态
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bin.integrated_app.app_server import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


class TestHealthDeep:
    """GET /api/health 深度字段验证"""

    def test_health_full_fields(self, client: TestClient) -> None:
        """health 端点完整字段"""
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "timestamp" in body
        assert "server" in body
        assert "host" in body["server"]
        assert "port" in body["server"]
        assert "gpu" in body
        assert "name" in body["gpu"]
        assert "backend" in body["gpu"]
        assert "total_vram_gb" in body["gpu"]
        assert "free_vram_gb" in body["gpu"]
        assert "disk" in body
        assert "total_gb" in body["disk"]
        assert "engines" in body
        assert isinstance(body["engines"], list)
        assert "queue" in body

    def test_health_engine_list(self, client: TestClient) -> None:
        """health 端点的引擎列表"""
        r = client.get("/api/health")
        engines = r.json()["engines"]
        assert len(engines) >= 1
        first = engines[0]
        assert "name" in first
        assert "display_name" in first
        assert "ready" in first
        assert "active" in first


class TestSSEEvents:
    """GET /api/events — SSE 事件流"""

    def test_sse_endpoint_in_openapi(self, client: TestClient) -> None:
        """SSE 端点在 OpenAPI 规范中"""
        spec = client.get("/openapi.json").json()
        assert "/api/events" in spec["paths"]

    def test_sse_endpoint_method(self, client: TestClient) -> None:
        """SSE 端点支持 GET 方法"""
        spec = client.get("/openapi.json").json()
        events_spec = spec["paths"].get("/api/events", {})
        assert "get" in events_spec


class TestGpuStatus:
    """GET /api/gpu — GPU 状态"""

    def test_gpu_status_fields(self, client: TestClient) -> None:
        """GPU 端点字段完整"""
        r = client.get("/api/gpu")
        assert r.status_code == 200
        body = r.json()
        assert "name" in body
        assert "backend" in body
        assert "total_vram_gb" in body
        assert "used_vram_gb" in body
        assert "free_vram_gb" in body
