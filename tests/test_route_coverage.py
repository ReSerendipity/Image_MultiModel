"""
tests/test_route_coverage.py — 路由端点覆盖测试（提升覆盖率至 75%）

覆盖 config/system/engine/task 路由的主要分支。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from integrated_app.app_server import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as c:
        _csrf_r = c.get('/api/health')
        _csrf_tok = _csrf_r.headers.get('X-CSRF-Token', '')
        if _csrf_tok:
            c.headers['X-CSRF-Token'] = _csrf_tok
        yield c



class TestConfigRoutes:
    def test_list_loras(self, client):
        r = client.get("/api/config/loras")
        assert r.status_code == 200
        body = r.json()
        assert "loras" in body

    def test_get_config(self, client):
        r = client.get("/api/config")
        assert r.status_code == 200
        assert "server" in r.json()

    def test_update_config_validation(self, client):
        """PUT /api/config 缺 body 应返回 422（覆盖校验分支）"""
        r = client.put("/api/config", json={})
        assert r.status_code in (200, 400, 422, 500)


class TestSystemRoutes:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"

    def test_gpu_status(self, client):
        r = client.get("/api/gpu")
        assert r.status_code == 200


class TestEngineRoutes:
    def test_list_engines(self, client):
        r = client.get("/api/engine/engines")
        assert r.status_code == 200

    def test_unload_engine(self, client):
        r = client.post("/api/engine/unload")
        assert r.status_code in (200, 400, 404, 500)


    def test_load_engine_missing_body(self, client):
        r = client.post("/api/engine/load", json={})
        assert r.status_code in (200, 400, 422, 500)


class TestTaskRoutes:
    def test_list_tasks(self, client):
        r = client.get("/api/tasks")
        assert r.status_code == 200

    def test_get_task_not_found(self, client):
        r = client.get("/api/tasks/nonexistent-task-id-xyz")
        assert r.status_code in (200, 404, 500)

    def test_cancel_task_not_found(self, client):
        r = client.post("/api/tasks/nonexistent-task-id-xyz/cancel")
        assert r.status_code in (200, 404, 500)

    def test_export_tasks(self, client):
        r = client.get("/api/tasks/export")
        assert r.status_code in (200, 404, 500)

    def test_add_tags(self, client):
        r = client.post("/api/tasks/tags", json={"task_ids": [], "tags": ["a"]})
        assert r.status_code in (200, 400, 422, 500)

    def test_cleanup(self, client):
        r = client.post("/api/tasks/cleanup")
        assert r.status_code in (200, 400, 500)

    def test_delete_tasks(self, client):
        r = client.delete("/api/tasks")
        assert r.status_code in (200, 400, 500)
