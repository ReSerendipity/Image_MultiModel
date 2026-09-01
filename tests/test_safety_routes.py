"""
tests/test_safety_routes.py — M-07 /api/safety/check-image 路径白名单

M-07：只读图片接口必须使用独立的 image_read_base_dirs 白名单，
不能复用 allowed_base_dirs（后者含 model/，会允许读取权重文件）。

- model/ 下的路径 → 403（image_read_base_dirs 不含 model/）
- outputs/ 下不存在的文件 → 404（白名单通过但文件缺失）
- data/ 下存在的图片 → 200（白名单通过，进入 CLIP 检测）
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.integrated_app.app_server import create_app

pytestmark = pytest.mark.security

_DATA_PNG = next(
    (p for p in Path("data/cache/thumbs").glob("*.png") if p.is_file()),
    None,
)


def _client() -> TestClient:
    c = TestClient(create_app())
    tok = c.get("/api/health").headers.get("X-CSRF-Token", "")
    if tok:
        c.headers["X-CSRF-Token"] = tok
    return c


def test_model_path_rejected_by_image_read_whitelist() -> None:
    """model/ 路径（不在 image_read_base_dirs）→ 403。"""
    with _client() as c:
        r = c.post("/api/safety/check-image", json={"image_path": "model/README.md"})
        assert r.status_code == 403, f"model/ 应被 403 拒绝: {r.status_code} {r.text[:120]}"


def test_outputs_nonexistent_returns_404() -> None:
    """outputs/ 下不存在的文件 → 404（白名单通过但文件缺失）。"""
    with _client() as c:
        r = c.post(
            "/api/safety/check-image",
            json={"image_path": "outputs/_m07_does_not_exist.png"},
        )
        assert r.status_code == 404, f"不存在文件应 404: {r.status_code} {r.text[:120]}"


def test_data_image_allowed_and_checked() -> None:
    """data/ 下存在的图片 → 200，进入 CLIP 检测（M-07 白名单放行）。"""
    if _DATA_PNG is None:
        pytest.skip("data/cache/thumbs 无可用 PNG，跳过")
    with _client() as c:
        r = c.post(
            "/api/safety/check-image",
            json={"image_path": str(_DATA_PNG)},
        )
        assert r.status_code == 200, f"data/ 图片应放行: {r.status_code} {r.text[:160]}"
        body = r.json()
        assert "is_safe" in body, "响应应包含 is_safe 字段"


def test_dotdot_traversal_rejected() -> None:
    """路径穿越（即便指向白名单内扩展名）→ 403。"""
    with _client() as c:
        r = c.post(
            "/api/safety/check-image",
            json={"image_path": "../../etc/passwd"},
        )
        assert r.status_code == 403, f"路径穿越应 403: {r.status_code} {r.text[:120]}"
