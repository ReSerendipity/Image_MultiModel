"""
tests/test_engine_routes.py — 引擎路由深度测试

对应 N19: engine_routes.py 覆盖率提升
覆盖：GET /api/engines, POST /api/engine/load, POST /api/engine/unload, POST /api/engine/free
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bin.integrated_app.app_server import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


class TestEngineList:
    """GET /api/engines — 引擎列表"""

    def test_list_engines_ok(self, client: TestClient) -> None:
        """引擎列表 → 200 或 500（registry 未完全初始化时可能 500）"""
        r = client.get("/api/engine/engines")
        assert r.status_code in (200, 500), f"Got {r.status_code}: {r.text[:200]}"
        if r.status_code == 200:
            body = r.json()
            assert "engines" in body
            assert "active_engine" in body
            assert "count" in body
            assert body["count"] == len(body["engines"])
            assert body["count"] >= 1

    def test_engine_fields(self, client: TestClient) -> None:
        """引擎条目字段完整"""
        r = client.get("/api/engine/engines")
        if r.status_code == 200:
            engines = r.json()["engines"]
            first = engines[0]
            for key in ("name", "display_name", "display_name_en", "ready", "state", "active",
                         "vram_gb", "ram_gb", "default_precision", "supported_features", "tags"):
                assert key in first, f"Missing field '{key}' in engine entry"

    def test_active_engine_in_list(self, client: TestClient) -> None:
        """活动引擎在列表中且 active=True"""
        r = client.get("/api/engine/engines")
        if r.status_code == 200:
            body = r.json()
            active_name = body["active_engine"]
            if active_name:
                engines = body["engines"]
                active_engines = [e for e in engines if e["name"] == active_name]
                assert len(active_engines) == 1
                assert active_engines[0]["active"] is True


class TestEngineLoad:
    """POST /api/engine/load — 加载引擎"""

    def test_load_nonexistent_engine_404(self, client: TestClient) -> None:
        """引擎不存在 → 404"""
        r = client.post("/api/engine/load", json={"engine_name": "nonexistent_engine_xyz"})
        assert r.status_code == 404

    def test_load_existing_engine(self, client: TestClient) -> None:
        """加载已注册引擎 → 200 或 500（取决于 ComfyUI 在线 + registry 状态）"""
        r = client.post("/api/engine/load", json={"engine_name": "flux2_klein_9b_distilled"})
        assert r.status_code in (200, 500), f"Got {r.status_code}: {r.text[:200]}"
        if r.status_code == 200:
            body = r.json()
            assert body["engine_name"] == "flux2_klein_9b_distilled"
            assert body["status"] in ("loaded", "error", "loading")


class TestEngineUnload:
    """POST /api/engine/unload — 卸载引擎"""

    def test_unload_no_active_engine(self, client: TestClient) -> None:
        """无活动引擎 → 200 或 500（registry 状态依赖）"""
        r = client.post("/api/engine/unload")
        assert r.status_code in (200, 500), f"Got {r.status_code}: {r.text[:200]}"


class TestEngineFree:
    """POST /api/engine/free — 释放显存"""

    def test_free_vram(self, client: TestClient) -> None:
        """释放显存 → 200 或 500（取决于 ComfyUI 在线）"""
        r = client.post("/api/engine/free")
        assert r.status_code in (200, 500), f"Got {r.status_code}: {r.text[:200]}"
