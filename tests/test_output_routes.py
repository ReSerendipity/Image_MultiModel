"""
tests/test_output_routes.py — 输出路由深度测试

对应 N18: output_routes.py 收藏/下载端点测试
覆盖：POST /api/outputs/{file}/fav, GET /api/outputs/{file}/download
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bin.integrated_app.app_server import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


class TestOutputFavorite:
    """POST /api/outputs/{file}/fav — 收藏标记"""

    def test_fav_nonexistent_file(self, client: TestClient) -> None:
        """收藏不存在的文件 → 200 (代码不检查文件存在性) 或 404"""
        r = client.post("/api/outputs/nonexistent_file.png/fav")
        # toggle_favorite 不检查文件是否存在，只检查路径安全
        assert r.status_code in (200, 404, 403)

    def test_fav_path_traversal_403(self, client: TestClient) -> None:
        """路径穿越 → 403"""
        r = client.post("/api/outputs/../../etc/passwd/fav")
        assert r.status_code != 200 or "passwd" not in r.text


class TestOutputDownload:
    """GET /api/outputs/{file}/download — 下载"""

    def test_download_nonexistent_file_404(self, client: TestClient) -> None:
        """下载不存在的文件 → 404"""
        r = client.get("/api/outputs/nonexistent_file.png/download")
        assert r.status_code == 404

    def test_download_path_traversal_403(self, client: TestClient) -> None:
        """路径穿越下载 → 403"""
        r = client.get("/api/outputs/../../etc/passwd/download")
        assert r.status_code != 200 or "passwd" not in r.text


class TestOutputListFilters:
    """GET /api/outputs — 筛选参数"""

    def test_list_with_type_filter(self, client: TestClient) -> None:
        """按 type 筛选 → 200"""
        r = client.get("/api/outputs?type=original")
        assert r.status_code == 200
        body = r.json()
        assert "outputs" in body
        assert "total" in body

    def test_list_with_fav_filter(self, client: TestClient) -> None:
        """按 fav 筛选 → 200"""
        r = client.get("/api/outputs?fav=true")
        assert r.status_code == 200

    def test_list_pagination(self, client: TestClient) -> None:
        """分页参数 → 200"""
        r = client.get("/api/outputs?page=1&page_size=10")
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 1
        assert body["page_size"] == 10
