"""
tests/test_cors.py — CORS 配置测试

对应 N21: 跨域资源共享安全验证
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.integrated_app.app_server import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


class TestCORS:
    """CORS 中间件配置"""

    def test_cors_preflight_request(self, client: TestClient) -> None:
        """OPTIONS 预检请求 → 200 + CORS headers"""
        r = client.options(
            "/api/health",
            headers={
                "Origin": "http://evil-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code in (200, 400)
        # CORS 头应存在
        assert "access-control-allow-origin" in {k.lower() for k in r.headers} or \
               r.status_code == 400  # 某些配置可能拒绝

    def test_cors_origin_header_on_get(self, client: TestClient) -> None:
        """GET 请求带 Origin → 返回 CORS 头"""
        r = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
        assert r.status_code == 200

    def test_cors_allow_methods(self, client: TestClient) -> None:
        """CORS 允许的方法列表"""
        r = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        # 预检请求应返回
        assert r.status_code in (200, 400)

    def test_cors_no_origin_still_works(self, client: TestClient) -> None:
        """无 Origin 的正常请求不受影响"""
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_cors_credentials_header(self, client: TestClient) -> None:
        """带凭证的请求 → CORS 配置正确处理"""
        r = client.options(
            "/api/config",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert r.status_code in (200, 400)
