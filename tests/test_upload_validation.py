"""
tests/test_upload_validation.py — 文件上传 / 参考图校验绕过测试

对应测试体系评估 P1-5（安全缺口 #3：文件上传校验绕过）。

项目通过 /api/generate 的 reference_image_path（PathGuard 白名单）与
reference_image_b64（魔数校验 + PIL.verify）做上传前校验，校验在路由层同步执行，
无需 GPU。本文件验证绕过手段均被拒绝：
- 路径穿越（reference_image_path 越权）
- 不存在文件 / 路径冲突
- 非图片载荷（脚本 / HTML / 随机字节）伪装为图片
- 合法图片头但内容损坏（截断）
全部在校验阶段返回 400/403/404，绝不落盘为可执行文件或越权读文件。
"""

from __future__ import annotations

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.integrated_app.app_server import create_app  # noqa: E402

pytestmark = pytest.mark.security


def _client() -> TestClient:
    c = TestClient(create_app())
    health = c.get("/api/health")
    token = health.headers.get("X-CSRF-Token", "")
    if token:
        c.headers["X-CSRF-Token"] = token
    return c


def _valid_png_b64() -> str:
    """用 PIL 生成一张真正合法、可通过魔数+verify 的小 PNG。"""
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (128, 128, 128)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


_VALID_PNG_B64 = _valid_png_b64()

# 伪装成图片的恶意载荷
_SCRIPT_PAYLOAD = b"#!/usr/bin/env python\nimport os\nos.system('calc.exe')\n"
_HTML_PAYLOAD = b"<html><script>alert('xss')</script></html>"
_RANDOM_PAYLOAD = bytes(range(256)) * 100  # 随机字节，非图片魔数


def _post_with_ref(c: TestClient, **ref_kw) -> tuple[int, str]:
    payload = {
        "positive_prompt": "a normal landscape",
        "cfg": 1.0, "steps": 4, "width": 256, "height": 256,
        "seed": 1, "batch_size": 1,
        "engine_name": "z_image_turbo_native",
    }
    payload.update(ref_kw)
    r = c.post("/api/generate", json=payload)
    return r.status_code, (r.text or "")


def test_path_traversal_rejected() -> None:
    """reference_image_path 路径穿越 → 403（PathGuard）。"""
    with _client() as c:
        code, body = _post_with_ref(c, reference_image_path="../../../etc/passwd")
        assert code == 403, f"路径穿越未被拦截: {code} {body[:120]}"


def test_absolute_path_rejected() -> None:
    """绝对路径（系统目录）→ 403。"""
    with _client() as c:
        code, body = _post_with_ref(c, reference_image_path="/etc/shadow")
        assert code == 403, f"绝对路径未被拦截: {code} {body[:120]}"


def test_nonexistent_file_rejected() -> None:
    """不存在的（白名单内）文件 → 404。"""
    with _client() as c:
        code, body = _post_with_ref(c, reference_image_path="outputs/does_not_exist.png")
        assert code == 404, f"不存在文件未被拦截: {code} {body[:120]}"


def test_path_and_b64_conflict_rejected() -> None:
    """同时提供 path 与 b64 → 400 字段冲突。"""
    with _client() as c:
        code, body = _post_with_ref(
            c,
            reference_image_path="outputs/x.png",
            reference_image_b64=_VALID_PNG_B64,
        )
        assert code == 400, f"字段冲突未被拦截: {code} {body[:120]}"


def test_script_payload_rejected() -> None:
    """脚本伪装成图片（base64）→ 400 魔数校验失败。"""
    with _client() as c:
        code, body = _post_with_ref(
            c, reference_image_b64=base64.b64encode(_SCRIPT_PAYLOAD).decode()
        )
        assert code == 400, f"脚本载荷未被拦截: {code} {body[:120]}"
        assert "decode failed" in body or "Reference image" in body, \
            f"拦截原因非上传校验: {body[:120]}"


def test_html_payload_rejected() -> None:
    """HTML 伪装成图片 → 400。"""
    with _client() as c:
        code, body = _post_with_ref(
            c, reference_image_b64=base64.b64encode(_HTML_PAYLOAD).decode()
        )
        assert code == 400, f"HTML 载荷未被拦截: {code} {body[:120]}"


def test_random_bytes_rejected() -> None:
    """随机字节伪装成图片 → 400。"""
    with _client() as c:
        code, body = _post_with_ref(
            c, reference_image_b64=base64.b64encode(_RANDOM_PAYLOAD).decode()
        )
        assert code == 400, f"随机字节未被拦截: {code} {body[:120]}"


def test_corrupt_png_rejected() -> None:
    """合法 PNG 头但内容截断（损坏）→ PIL.verify 失败 → 400。"""
    corrupt = _VALID_PNG_B64[:20]  # 截断，破坏结构
    with _client() as c:
        code, body = _post_with_ref(c, reference_image_b64=corrupt)
        assert code == 400, f"损坏 PNG 未被拦截: {code} {body[:120]}"


def test_valid_png_passes_upload_validation() -> None:
    """合法 PNG 通过上传校验（不被 upload 阶段拒绝）。"""
    with _client() as c:
        code, body = _post_with_ref(c, reference_image_b64=_VALID_PNG_B64)
        # 上传校验通过；无 GPU 下可能 400（显存预检）但绝不因图片解码失败
        assert code != 500, f"合法 PNG 导致 500: {body[:200]}"
        assert "Reference image decode failed" not in body, \
            f"合法 PNG 被上传校验误拦: {body[:200]}"


# ── M-03: 上传体积 / 像素（解压炸弹）上限（M-03）─────────────────────
from fastapi import HTTPException  # noqa: E402

from app.integrated_app.security.upload_limits import enforce_upload_limits  # noqa: E402


def test_enforce_rejects_oversized_bytes() -> None:
    """单元：超 max_size_mb 字节 → 413。"""
    with pytest.raises(HTTPException) as ei:
        enforce_upload_limits(b"x" * (2 * 1024 * 1024), max_size_mb=1, max_pixels=10**9)
    assert ei.value.status_code == 413


def test_enforce_rejects_bomb_pixels() -> None:
    """单元：超 max_pixels 像素（解压炸弹）→ 413。"""
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (128, 128, 128)).save(buf, format="PNG")
    with pytest.raises(HTTPException) as ei:
        enforce_upload_limits(buf.getvalue(), max_size_mb=10**9, max_pixels=1000)
    assert ei.value.status_code == 413


def test_enforce_allows_normal_image() -> None:
    """单元：正常小图不触发限制。"""
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (128, 128, 128)).save(buf, format="PNG")
    # 不应抛出
    enforce_upload_limits(buf.getvalue(), max_size_mb=10**9, max_pixels=10**9)


def test_oversized_upload_rejected_413() -> None:
    """路由：超体积（> max_size_mb）→ 413（M-03 字节上限）。

    必须在 create_app()（会 load_config 重置单例）之后打补丁。
    """
    import app.integrated_app.config as cfg_mod

    with _client() as c:
        cfg = cfg_mod.get_config()
        saved = cfg.output.uploads.max_size_mb
        try:
            cfg.output.uploads.max_size_mb = 0  # 任意非空载荷即超限
            code, body = _post_with_ref(c, reference_image_b64=_VALID_PNG_B64)
            assert code == 413, f"超大上传未被拦截(413): {code} {body[:120]}"
        finally:
            cfg.output.uploads.max_size_mb = saved


def test_decompression_bomb_rejected_413() -> None:
    """路由：解压炸弹（高像素 PNG）→ 413（M-03 像素上限）。"""
    from PIL import Image as _PILImage

    import app.integrated_app.config as cfg_mod

    with _client() as c:
        cfg = cfg_mod.get_config()
        saved = cfg.output.uploads.max_pixels
        try:
            cfg.output.uploads.max_pixels = 1000  # 任意 100×100 图即超限
            buf = io.BytesIO()
            Image.new("RGB", (100, 100), (128, 128, 128)).save(buf, format="PNG")
            bomb = base64.b64encode(buf.getvalue()).decode()
            code, body = _post_with_ref(c, reference_image_b64=bomb)
            assert code == 413, f"解压炸弹未被拦截(413): {code} {body[:160]}"
        finally:
            cfg.output.uploads.max_pixels = saved
            _PILImage.MAX_IMAGE_PIXELS = saved  # 还原进程级 PIL 纵深防御

