"""
tests/test_security_audit.py — 安全审计测试补充

对应 REMAINING_TASKS_REPORT §4.4: 安全审计执行
- 全端点 CSRF 覆盖
- /api/outputs/download 路径穿越
- 启动完整性自检
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from integrated_app.middleware.csrf import CSRFMiddleware
from integrated_app.security.path_guard import PathGuard, PathGuardError


# ── 路径穿越测试（§4.4）──────────────────────────────────────
class TestPathTraversalDownload:
    """下载端点路径穿越攻击"""

    @pytest.fixture
    def guard(self):
        return PathGuard(
            allowed_base_dirs=["outputs/", "data/", "workflows/", "model/"],
            project_root=str(PROJECT_ROOT),
        )

    def test_double_dot_traversal(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("../../../etc/passwd", base_dir="outputs/")

    def test_double_dot_in_outputs(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("../../../etc/passwd", base_dir="outputs/")

    def test_absolute_path(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("C:/Windows/System32/config/SAM", base_dir="outputs/")

    def test_unix_absolute_path(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("/etc/shadow", base_dir="outputs/")

    def test_null_byte_injection(self, guard):
        # null 字节攻击（不使用 base_dir，让 PathGuard 检查全白名单）
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/test\0../../../etc/passwd")

    def test_url_encoded_traversal(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("%2e%2e/%2e%2e/etc/passwd", base_dir="outputs/")

    def test_mixed_slashes(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("..\\..\\..\\etc\\passwd", base_dir="outputs/")

    def test_long_path_attack(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("A" * 500 + "/../../../etc/passwd", base_dir="outputs/")

    def test_valid_path_accepted(self, guard):
        """正常路径应通过"""
        p = guard.resolve("test.png", base_dir="outputs/")
        assert "outputs" in str(p)


# ── CSRF 中间件测试（§4.4）──────────────────────────────────
class TestCSRFCoverage:
    """全 POST/PUT/DELETE 端点 CSRF 头校验"""

    def _make_csrf_app(self) -> FastAPI:
        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.get("/api/test")
        async def get_test():
            return {"ok": True}

        @app.post("/api/test")
        async def post_test():
            return {"ok": True}

        @app.put("/api/test")
        async def put_test():
            return {"ok": True}

        @app.delete("/api/test")
        async def delete_test():
            return {"ok": True}

        return app

    def test_get_no_csrf_needed(self):
        """GET 请求不需要 CSRF 头"""
        app = self._make_csrf_app()
        with TestClient(app) as c:
            r = c.get("/api/test")
            assert r.status_code == 200

    def test_post_without_csrf_rejected(self):
        """POST 无 CSRF 头 → 403"""
        app = self._make_csrf_app()
        with TestClient(app) as c:
            r = c.post("/api/test")
            assert r.status_code == 403

    def test_put_without_csrf_rejected(self):
        """PUT 无 CSRF 头 → 403"""
        app = self._make_csrf_app()
        with TestClient(app) as c:
            r = c.put("/api/test")
            assert r.status_code == 403

    def test_delete_without_csrf_rejected(self):
        """DELETE 无 CSRF 头 → 403"""
        app = self._make_csrf_app()
        with TestClient(app) as c:
            r = c.delete("/api/test")
            assert r.status_code == 403

    def test_post_with_csrf_accepted(self):
        """POST 带 X-CSRF-Token → 200"""
        app = self._make_csrf_app()
        with TestClient(app) as c:
            # 先 GET 获取 CSRF token
            r = c.get("/api/test")
            csrf_token = r.headers.get("X-CSRF-Token", "test-token")
            r = c.post("/api/test", headers={"X-CSRF-Token": csrf_token})
            assert r.status_code == 200


# ── 完整性自检测试（§4.4）──────────────────────────────────
class TestIntegritySelfCheck:
    """启动完整性自检"""

    def test_manifest_file_exists(self):
        """integrity_manifest.json 存在"""
        manifest_path = PROJECT_ROOT / "app" / "integrated_app" / "security" / "integrity_manifest.json"
        assert manifest_path.exists(), f"Integrity manifest not found: {manifest_path}"


# ── Checkpoint 测试（§1.3）──────────────────────────────────
class TestCheckpoint:
    """断点续跑 checkpoint 模块"""

    def test_save_and_load(self, tmp_path):
        from integrated_app.checkpoint import TaskCheckpoint

        mgr = TaskCheckpoint(checkpoint_dir=str(tmp_path))
        mgr.save(
            task_id="test-001",
            engine="z_image_turbo_native",
            total=500,
            completed_items=[{"prompt": "p1", "seed": 42}],
            remaining=[{"prompt": "p2", "seed": 99}],
            config={"steps": 8},
        )

        data = mgr.load("test-001")
        assert data is not None
        assert data["task_id"] == "test-001"
        assert data["total"] == 500
        assert data["completed"] == 1
        assert len(data["remaining"]) == 1

    def test_delete_checkpoint(self, tmp_path):
        from integrated_app.checkpoint import TaskCheckpoint

        mgr = TaskCheckpoint(checkpoint_dir=str(tmp_path))
        mgr.save(
            task_id="test-002",
            engine="test",
            total=10,
            completed_items=[],
            remaining=[],
            config={},
        )
        assert mgr.delete("test-002") is True
        assert mgr.load("test-002") is None

    def test_list_pending_checkpoints(self, tmp_path):
        from integrated_app.checkpoint import TaskCheckpoint

        mgr = TaskCheckpoint(checkpoint_dir=str(tmp_path))
        mgr.save("task-1", "e", 100, [{"p": "a"}] * 50, [{"p": "b"}] * 50, {})
        mgr.save("task-2", "e", 100, [{"p": "a"}] * 100, [], {})  # 已完成
        pending = mgr.list_checkpoints()
        assert len(pending) == 1
        assert pending[0]["task_id"] == "task-1"

    def test_should_checkpoint(self, tmp_path):
        from integrated_app.checkpoint import TaskCheckpoint

        mgr = TaskCheckpoint(checkpoint_dir=str(tmp_path))
        assert mgr.should_checkpoint(100, 100) is True
        assert mgr.should_checkpoint(50, 100) is False
        assert mgr.should_checkpoint(0, 100) is False
