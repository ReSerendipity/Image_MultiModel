"""
tests/test_api_contract.py — REST 契约测试（TestClient 级）

覆盖 MASTER_PLAN §5.1 REST 接口的可用性契约：
- 只读列表接口均 200
- POST /api/generate：合法体不得 422/500（引擎未就绪时允许业务错误 400）
- 非法请求体返回 422（Pydantic 校验生效）
- 预设创建可写
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bin.integrated_app.app_server import create_app  # noqa: E402


def _valid_generate_payload() -> dict:
    """与前端 startGenReal 提交体一致（后端 GenerateRequest 全字段）"""
    return {
        "positive_prompt": "一位亚洲女性肖像，柔和自然光，浅景深",
        "negative_prompt": "",
        "cfg": 1.0, "steps": 8, "width": 1024, "height": 1024,
        "seed": -1, "batch_size": 1,
        "lora_1_name": "", "lora_1_strength": 1.0,
        "lora_2_name": "", "lora_2_strength": 0.7,
        "lora_3_name": "", "lora_3_strength": 0.5,
        "lora_4_name": "", "lora_4_strength": 0.4,
        "lora_5_name": "", "lora_5_strength": 0.3,
        "lora_6_name": "", "lora_6_strength": 0.2,
        "seedvr2_enable": True, "seedvr2_resolution": 2048,
        "seedvr2_seed": -1, "seedvr2_color_correction": "lab",
        "eses_enable": True, "eses_compare_axis": "horizontal",
        "vram_enable": True, "vram_reserved_gb": 0.6,
        "vram_mode": "auto", "vram_seed": -1,
        "output_format": "png", "output_prefix": "{engine}",
        "engine_name": "flux2_klein_9b_distilled",
    }


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_config_ok(client: TestClient) -> None:
    r = client.get("/api/config")
    assert r.status_code == 200
    assert "server" in r.json()


def test_config_loras_ok(client: TestClient) -> None:
    """GET /api/config/loras — LoRA 下拉数据源（F3）"""
    r = client.get("/api/config/loras")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"loras", "count", "mode"}
    assert isinstance(body["loras"], list)
    assert body["count"] == len(body["loras"])


def test_list_endpoints_ok(client: TestClient) -> None:
    for path in ("/api/tasks", "/api/presets", "/api/outputs", "/api/sse/events"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"


def test_generate_valid_payload_not_422_or_500(client: TestClient) -> None:
    """合法请求体不得 422（字段对齐）或 500；引擎未就绪时允许 400 业务错误"""
    r = client.post("/api/generate", json=_valid_generate_payload())
    assert r.status_code in (200, 400, 409, 503), f"got {r.status_code}: {r.text[:120]}"


def test_generate_invalid_payload_422(client: TestClient) -> None:
    """非法请求体（类型错误）触发 Pydantic 422"""
    r = client.post("/api/generate", json={"positive_prompt": 12345})
    assert r.status_code == 422


def test_presets_create_ok(client: TestClient) -> None:
    r = client.post(
        "/api/presets",
        json={"name": "契约测试预设", "engine_name": "flux2_klein_9b_distilled", "config": {"steps": 8}},
    )
    assert r.status_code == 200
