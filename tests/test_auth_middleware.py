"""tests/test_auth_middleware.py — 认证中间件（Basic / Bearer）测试

对应安全评估 C-01：``security.basic_auth`` 与 ``security.api_token`` 此前是
"配置幻觉"（有配置、有模型、零实现）。本文件锁定补齐后的行为，重点保证：

1. **默认关闭时零影响** —— 不改变任何既有行为（向后兼容底线）；
2. **启用后未认证请求一律 401** —— 且业务端点确实被保护（而非仅豁免路径生效）；
3. 口令哈希支持 PBKDF2（标准库，无新依赖）与 bcrypt（可选依赖）两种格式；
4. Token 比对恒定时间、豁免路径最小化。
"""

from __future__ import annotations

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrated_app.middleware.auth import (
    AuthMiddleware,
    hash_password_pbkdf2,
    verify_password,
    verify_token,
)


# ── 辅助构造 ──────────────────────────────────────────────────
def _security(
    basic_enabled: bool = False,
    token_enabled: bool = False,
    tokens: list[str] | None = None,
    username: str = "admin",
    pwd_hash: str = "",
):
    """构造最小可用的 security 配置替身。"""
    from types import SimpleNamespace

    return SimpleNamespace(
        basic_auth=SimpleNamespace(
            enabled=basic_enabled, username=username, password_bcrypt_hash=pwd_hash
        ),
        api_token=SimpleNamespace(enabled=token_enabled, tokens=tokens or []),
    )


def _make_app(sec) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, config=_make_config(sec))

    @app.get("/api/tasks")
    def list_tasks() -> dict:
        return {"ok": True}

    @app.post("/api/tasks/cleanup")
    def cleanup() -> dict:
        return {"deleted": 0}

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/")
    def index() -> dict:
        return {"page": "index"}

    return app


def _make_config(sec):
    from types import SimpleNamespace

    return SimpleNamespace(security=sec)


def _basic_header(user: str, pwd: str) -> str:
    raw = f"{user}:{pwd}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")


# ── 1. 默认关闭：零影响 ───────────────────────────────────────
class TestDisabledByDefault:
    def test_all_disabled_allows_anonymous_get(self):
        client = TestClient(_make_app(_security()))
        assert client.get("/api/tasks").status_code == 200

    def test_all_disabled_allows_anonymous_post(self):
        client = TestClient(_make_app(_security()))
        assert client.post("/api/tasks/cleanup").status_code == 200

    def test_all_disabled_allows_health(self):
        client = TestClient(_make_app(_security()))
        assert client.get("/api/health").status_code == 200


# ── 2. Bearer Token 模式 ──────────────────────────────────────
class TestBearerToken:
    def test_missing_token_returns_401(self):
        app = _make_app(_security(token_enabled=True, tokens=["secret-token-abc"]))
        r = TestClient(app).get("/api/tasks")
        assert r.status_code == 401
        assert r.headers.get("WWW-Authenticate") == "Bearer"

    def test_wrong_token_returns_401(self):
        app = _make_app(_security(token_enabled=True, tokens=["secret-token-abc"]))
        r = TestClient(app).get("/api/tasks", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401

    def test_correct_token_passes(self):
        app = _make_app(_security(token_enabled=True, tokens=["secret-token-abc"]))
        r = TestClient(app).get(
            "/api/tasks", headers={"Authorization": "Bearer secret-token-abc"}
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_x_api_token_header_also_accepted(self):
        app = _make_app(_security(token_enabled=True, tokens=["tk"]))
        r = TestClient(app).get("/api/tasks", headers={"X-API-Token": "tk"})
        assert r.status_code == 200

    def test_protects_state_changing_post(self):
        """受保护的不只是 GET：POST 业务端点同样需要凭据。"""
        app = _make_app(_security(token_enabled=True, tokens=["tk"]))
        assert TestClient(app).post("/api/tasks/cleanup").status_code == 401
        assert (
            TestClient(app)
            .post("/api/tasks/cleanup", headers={"Authorization": "Bearer tk"})
            .status_code
            == 200
        )

    def test_empty_token_list_denies_everything(self):
        """启用但未登记任何 token → 一律拒绝（fail-closed）。"""
        app = _make_app(_security(token_enabled=True, tokens=[]))
        assert TestClient(app).get("/api/tasks").status_code == 401

    def test_placeholder_token_is_not_a_real_credential(self):
        """config.yaml 中的占位符不应被当作有效 token。"""
        app = _make_app(_security(token_enabled=True, tokens=["tk"]))
        r = TestClient(app).get(
            "/api/tasks",
            headers={"Authorization": "Bearer REPLACE_WITH_YOUR_BEARER_TOKEN_32BYTES"},
        )
        assert r.status_code == 401


# ── 3. HTTP Basic 模式 ────────────────────────────────────────
class TestBasicAuth:
    def test_missing_header_returns_401(self):
        sec = _security(basic_enabled=True, pwd_hash=hash_password_pbkdf2("pw123"))
        r = TestClient(_make_app(sec)).get("/api/tasks")
        assert r.status_code == 401
        assert r.headers.get("WWW-Authenticate") == 'Basic realm="Image MultiModel"'

    def test_wrong_password_returns_401(self):
        sec = _security(basic_enabled=True, pwd_hash=hash_password_pbkdf2("pw123"))
        r = TestClient(_make_app(sec)).get(
            "/api/tasks", headers={"Authorization": _basic_header("admin", "bad")}
        )
        assert r.status_code == 401

    def test_wrong_username_returns_401(self):
        sec = _security(basic_enabled=True, pwd_hash=hash_password_pbkdf2("pw123"))
        r = TestClient(_make_app(sec)).get(
            "/api/tasks", headers={"Authorization": _basic_header("root", "pw123")}
        )
        assert r.status_code == 401

    def test_correct_credentials_pass(self):
        sec = _security(basic_enabled=True, pwd_hash=hash_password_pbkdf2("pw123"))
        r = TestClient(_make_app(sec)).get(
            "/api/tasks", headers={"Authorization": _basic_header("admin", "pw123")}
        )
        assert r.status_code == 200

    def test_malformed_basic_header_returns_401(self):
        sec = _security(basic_enabled=True, pwd_hash=hash_password_pbkdf2("pw123"))
        for bad in ["Basic !!!not-base64!!!", "Basic", "Basic "]:
            r = TestClient(_make_app(sec)).get(
                "/api/tasks", headers={"Authorization": bad}
            )
            assert r.status_code == 401, f"应拒绝畸形头: {bad!r}"

    def test_empty_password_hash_denies(self):
        """未配置口令哈希时启用 Basic → 一律拒绝（不出现空口令放行）。"""
        sec = _security(basic_enabled=True, pwd_hash="")
        r = TestClient(_make_app(sec)).get(
            "/api/tasks", headers={"Authorization": _basic_header("admin", "")}
        )
        assert r.status_code == 401


# ── 4. 双模式并存 ─────────────────────────────────────────────
class TestBothModes:
    def test_either_credential_succeeds(self):
        sec = _security(
            basic_enabled=True,
            token_enabled=True,
            tokens=["tk"],
            pwd_hash=hash_password_pbkdf2("pw123"),
        )
        client = TestClient(_make_app(sec))
        assert (
            client.get("/api/tasks", headers={"Authorization": "Bearer tk"}).status_code
            == 200
        )
        assert (
            client.get(
                "/api/tasks", headers={"Authorization": _basic_header("admin", "pw123")}
            ).status_code
            == 200
        )

    def test_neither_credential_fails(self):
        sec = _security(
            basic_enabled=True, token_enabled=True, tokens=["tk"]
        )
        r = TestClient(_make_app(sec)).get("/api/tasks")
        assert r.status_code == 401


# ── 5. 豁免路径 ───────────────────────────────────────────────
class TestExemptPaths:
    def test_health_is_exempt_for_probing(self):
        sec = _security(token_enabled=True, tokens=["tk"])
        assert TestClient(_make_app(sec)).get("/api/health").status_code == 200

    def test_index_is_exempt(self):
        sec = _security(token_enabled=True, tokens=["tk"])
        assert TestClient(_make_app(sec)).get("/").status_code == 200

    def test_sse_events_stream_is_protected(self):
        """SSE 是真实数据通道，不豁免。"""
        app = FastAPI()
        app.add_middleware(AuthMiddleware, config=_make_config(_security(token_enabled=True, tokens=["tk"])))

        @app.get("/api/events")
        def events() -> dict:
            return {"stream": True}

        assert TestClient(app).get("/api/events").status_code == 401
        assert (
            TestClient(app)
            .get("/api/events", headers={"Authorization": "Bearer tk"})
            .status_code
            == 200
        )


# ── 6. 口令哈希与 token 比对 ──────────────────────────────────
class TestPasswordHashing:
    def test_pbkdf2_roundtrip(self):
        h = hash_password_pbkdf2("correct horse battery staple")
        assert verify_password("correct horse battery staple", h)
        assert not verify_password("Correct horse battery staple", h)

    def test_pbkdf2_uses_distinct_salts(self):
        """同一口令两次哈希应不同（盐随机），但都能校验通过。"""
        h1 = hash_password_pbkdf2("same")
        h2 = hash_password_pbkdf2("same")
        assert h1 != h2
        assert verify_password("same", h1)
        assert verify_password("same", h2)

    def test_pbkdf2_format(self):
        h = hash_password_pbkdf2("x")
        parts = h.split("$")
        assert parts[0] == "pbkdf2_sha256"
        assert len(parts) == 4
        assert int(parts[1]) >= 100_000

    def test_corrupted_hash_rejected(self):
        h = hash_password_pbkdf2("x")
        assert not verify_password("x", h.replace("pbkdf2_sha256$", "pbkdf2_sha256$X"))
        assert not verify_password("x", "pbkdf2_sha256$abc$def$ghi")
        assert not verify_password("x", "pbkdf2_sha256$0$c2FsdA==$aGFzaA==")
        assert not verify_password("x", "pbkdf2_sha256$480000$c2FsdA==$!!!notb64!!!")

    def test_empty_inputs_rejected(self):
        assert not verify_password("", hash_password_pbkdf2("x"))
        assert not verify_password("x", "")

    def test_unknown_scheme_rejected(self):
        assert not verify_password("x", "md5$deadbeef")
        assert not verify_password("x", "plaintext")


class TestTokenComparison:
    def test_exact_match(self):
        assert verify_token("a" * 32, ["a" * 32])

    def test_prefix_is_not_a_match(self):
        assert not verify_token("a" * 31, ["a" * 32])

    def test_empty_presented_rejected(self):
        assert not verify_token("", ["tk"])

    def test_multiple_tokens_any_match(self):
        assert verify_token("b", ["a", "b", "c"])

    def test_non_string_entries_skipped(self):
        assert not verify_token("tk", [None, 123, "tk2"])  # type: ignore[list-item]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
