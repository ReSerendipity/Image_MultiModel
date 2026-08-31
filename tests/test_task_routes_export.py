"""
tests/test_task_routes_export.py — /api/tasks/export 路径安全（M-01）

验收：
- 输出相对路径经 PathGuard 解析到 outputs 基目录，正确打包（修复空 ZIP 功能缺陷）；
- 越权/穿越路径被跳过（DB 污染也不导致任意文件读取）；
- 无可导出文件时返回 404 而非空 ZIP。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _fake_config(project_root: Path) -> SimpleNamespace:
    output = SimpleNamespace(base_dir="outputs/")
    security = SimpleNamespace(allowed_base_dirs=["outputs/", "data/", "workflows/", "model/"])
    return SimpleNamespace(output=output, security=security, project_root=str(project_root))


@pytest.fixture
def client_and_fs(tmp_path, monkeypatch):
    # 真实输出文件（相对 outputs 基目录）
    out_file = tmp_path / "outputs" / "z_image_turbo_native" / "20260831" / "abc.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(b"fake-png-bytes")

    # 被"污染"的 DB：含一条越权路径
    poisoned = tmp_path / "secret.txt"
    poisoned.write_text("topsecret")

    tasks = {
        "ok1": {"outputs": [{"path": "z_image_turbo_native/20260831/abc.png", "output_type": "original"}]},
        "bad1": {"outputs": [{"path": "../../secret.txt", "output_type": "original"}]},
        "empty1": {"outputs": []},
    }

    class FakeDB:
        def get_task(self, tid):
            return tasks.get(tid)

    # 通过 config 单例注入假配置（get_config() 返回 config._config）
    monkeypatch.setattr("integrated_app.config._config", _fake_config(tmp_path))

    app = FastAPI()
    from integrated_app.routes.task_routes import router

    app.include_router(router)
    app.state.history_db = FakeDB()
    yield TestClient(app), out_file


def test_export_valid_path_packages_file(client_and_fs):
    """合法相对输出路径应正确打包（空 ZIP 缺陷修复）。"""
    client, out_file = client_and_fs
    resp = client.get("/api/tasks/export", params={"ids": "ok1"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    assert any(n.endswith("abc.png") for n in z.namelist())


def test_export_skips_traversal_path(client_and_fs):
    """越权路径被跳过，仅含合法输出的任务正常导出（不读取 secret.txt）。"""
    client, _ = client_and_fs
    resp = client.get("/api/tasks/export", params={"ids": "ok1,bad1"})
    assert resp.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    # 越权文件绝不应出现在 ZIP 中
    assert not any("secret" in n for n in z.namelist())
    assert any(n.endswith("abc.png") for n in z.namelist())


def test_export_empty_returns_404(client_and_fs):
    """无可导出文件时返回 404（而非空 ZIP）。"""
    client, _ = client_and_fs
    resp = client.get("/api/tasks/export", params={"ids": "empty1"})
    assert resp.status_code == 404
