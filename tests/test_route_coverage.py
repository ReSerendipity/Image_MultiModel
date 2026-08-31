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
        """PUT /api/config with empty body → 200 (No changes message)"""
        r = client.put("/api/config", json={})
        assert r.status_code == 200, f"Expected 200 for empty config update, got {r.status_code}"
        assert "No changes" in r.json().get("message", "") or r.json().get("status") == "ok"


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
        """POST /api/engine/unload（未加载引擎）→ 200 ok（回归：不再掩盖已知 bug）"""
        r = client.post("/api/engine/unload")
        # 此前用 `in (200, 500)` 弱断言掩盖了 factory 为 None 的 TypeError；
        # 正确行为：无 active 引擎时直接返回 ok（200），不应出现 500。
        assert r.status_code == 200, f"unload 应返回 200，实际 {r.status_code}: {r.text[:160]}"
        assert r.json().get("status") == "ok"


    def test_load_engine_missing_body(self, client):
        """POST /engine/load with empty body -> 422 (validation error)"""
        r = client.post("/api/engine/load", json={})
        assert r.status_code == 422, f"Expected 422 for missing load body, got {r.status_code}"


class TestTaskRoutes:
    def test_list_tasks(self, client):
        r = client.get("/api/tasks")
        assert r.status_code == 200

    def test_get_task_not_found(self, client):
        """GET non-existent task -> 404"""
        r = client.get("/api/tasks/nonexistent-task-id-xyz")
        assert r.status_code == 404, f"Expected 404 for missing task, got {r.status_code}"

    def test_cancel_task_not_found(self, client):
        """Cancel non-existent task -> 404"""
        r = client.post("/api/tasks/nonexistent-task-id-xyz/cancel")
        assert r.status_code == 404, f"Expected 404 for cancelling missing task, got {r.status_code}"

    def test_export_tasks(self, client):
        """导出端点：缺必填 ids → 422；ids 无对应输出 → 404。

        回归说明：此前 /api/tasks/export 被动态路由 /{task_id} 吞掉，恒返回 404
        （导出功能实际已坏）。静态路由前移修复后，参数校验语义才真正生效。
        """
        # 缺少必填 ids → 422 校验失败
        r_missing = client.get("/api/tasks/export")
        assert r_missing.status_code == 422, f"缺 ids 应返回 422，实际 {r_missing.status_code}"
        # 提供了 ids 但无对应任务/输出 → 404
        r = client.get("/api/tasks/export", params={"ids": "nonexistent-task-id-xyz"})
        assert r.status_code == 404, f"无输出应返回 404，实际 {r.status_code}"

    def test_add_tags(self, client):
        """Add tags with empty task_ids -> 400 (business validation)"""
        r = client.post("/api/tasks/tags", json={"task_ids": [], "tags": ["a"]})
        assert r.status_code == 400, f"Expected 400 for empty task_ids, got {r.status_code}: {r.text[:150]}"

    def test_cleanup(self, client):
        """Cleanup endpoint should be callable and return 200"""
        r = client.post("/api/tasks/cleanup")
        # Cleanup can succeed even with nothing to clean
        assert r.status_code == 200, f"Cleanup should return 200, got {r.status_code}: {r.text[:150]}"

    def test_delete_tasks(self, client):
        """DELETE /tasks without body -> 400 (business validation)"""
        r = client.delete("/api/tasks")
        assert r.status_code == 400, f"Expected 400 for delete without criteria, got {r.status_code}: {r.text[:150]}"
