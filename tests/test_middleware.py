"""
tests/test_middleware.py — CSRF / RateLimit / RequestID 中间件测试

对应 TEST_AUDIT_REPORT P0-9: 三个中间件零测试
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrated_app.middleware.csrf import CSRFMiddleware
from integrated_app.middleware.rate_limit import RateLimitMiddleware
from integrated_app.middleware.request_id import RequestIDMiddleware


# ── 测试 RequestIDMiddleware ────────────────────────────────
def _make_app_with_request_id() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


class TestRequestIDMiddleware:
    """请求 ID 注入中间件"""

    def test_request_id_injected(self):
        """GET 请求自动注入 X-Request-ID"""
        app = _make_app_with_request_id()
        with TestClient(app) as client:
            r = client.get("/test")
            assert r.status_code == 200
            assert "X-Request-ID" in r.headers
            assert r.headers["X-Request-ID"]  # 非空

    def test_request_id_echoed_from_header(self):
        """客户端传入 X-Request-ID → 原样回传"""
        app = _make_app_with_request_id()
        custom_id = "my-custom-request-id-12345"
        with TestClient(app) as client:
            r = client.get("/test", headers={"X-Request-ID": custom_id})
            assert r.headers["X-Request-ID"] == custom_id


# ── 测试 RateLimitMiddleware ────────────────────────────────
def _make_app_with_rate_limit(
    global_per_minute: int = 5,
    infer_per_minute: int = 2,
    upload_per_minute: int = 1,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        global_per_minute=global_per_minute,
        infer_per_minute=infer_per_minute,
        upload_per_minute=upload_per_minute,
    )

    @app.get("/test")
    async def test_get():
        return {"ok": True}

    @app.post("/api/generate")
    async def generate():
        return {"task_id": "test"}

    @app.post("/api/upload")
    async def upload():
        return {"ok": True}

    return app


class TestRateLimitMiddleware:
    """速率限制中间件"""

    def test_normal_request_passes(self):
        """正常请求通过"""
        app = _make_app_with_rate_limit(global_per_minute=5)
        with TestClient(app) as client:
            r = client.get("/test")
            assert r.status_code == 200

    def test_global_rate_limit_exceeded(self):
        """全局限流：超过 global_per_minute → 429"""
        app = _make_app_with_rate_limit(global_per_minute=3)
        with TestClient(app) as client:
            # 发送 3 次正常请求
            for _ in range(3):
                r = client.get("/test")
                assert r.status_code == 200
            # 第 4 次应该被限流
            r = client.get("/test")
            assert r.status_code == 429, f"Expected 429, got {r.status_code}"
            assert "Retry-After" in r.headers

    def test_infer_rate_limit_exceeded(self):
        """推理限流：超过 infer_per_minute → 429"""
        app = _make_app_with_rate_limit(global_per_minute=100, infer_per_minute=2)
        with TestClient(app) as client:
            for _ in range(2):
                r = client.post("/api/generate")
                assert r.status_code == 200
            r = client.post("/api/generate")
            assert r.status_code == 429

    def test_upload_rate_limit_exceeded(self):
        """上传限流：超过 upload_per_minute → 429"""
        app = _make_app_with_rate_limit(global_per_minute=100, upload_per_minute=1)
        with TestClient(app) as client:
            r = client.post("/api/upload")
            assert r.status_code == 200
            r = client.post("/api/upload")
            assert r.status_code == 429


# ── 测试 CSRFMiddleware ─────────────────────────────────────
def _make_app_with_csrf() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.get("/test")
    async def test_get():
        return {"ok": True}

    @app.post("/submit")
    async def submit():
        return {"ok": True}

    return app


class TestCSRFMiddleware:
    """CSRF 防护中间件"""

    def test_get_sets_csrf_token(self):
        """GET 请求响应中包含 X-CSRF-Token"""
        app = _make_app_with_csrf()
        with TestClient(app) as client:
            r = client.get("/test")
            assert r.status_code == 200
            assert "X-CSRF-Token" in r.headers
            assert r.headers["X-CSRF-Token"]  # 非空

    def test_post_without_csrf_token_403(self):
        """POST 无 X-CSRF-Token → 403"""
        app = _make_app_with_csrf()
        with TestClient(app) as client:
            r = client.post("/submit")
            assert r.status_code == 403

    def test_post_with_wrong_csrf_token_403(self):
        """POST 携带错误的 X-CSRF-Token → 403"""
        app = _make_app_with_csrf()
        with TestClient(app) as client:
            # 先 GET 获取正确 token
            r = client.get("/test")
            correct_token = r.headers["X-CSRF-Token"]

            # 使用错误 token
            r = client.post("/submit", headers={"X-CSRF-Token": "wrong-token"})
            assert r.status_code == 403

    def test_post_with_correct_csrf_token_passes(self):
        """POST 携带正确的 X-CSRF-Token → 200"""
        app = _make_app_with_csrf()
        with TestClient(app) as client:
            # GET 获取 token
            r = client.get("/test")
            token = r.headers["X-CSRF-Token"]
            cookie_token = client.cookies.get("csrf_token", "")

            # 使用 header + cookie 一致的 token
            r = client.post(
                "/submit",
                headers={"X-CSRF-Token": cookie_token or token},
            )
            assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:100]}"
