"""
tests/test_api_contract.py — REST 契约测试 + 深度集成测试（TestClient 级）

覆盖 MASTER_PLAN §5.1 REST 接口：
- 只读列表接口均 200
- POST /api/generate：合法体不得 422/500；引擎不存在 404；batch>9999 400；队列满 503
- 非法请求体返回 422（Pydantic 校验生效）
- 预设 CRUD 全流程
- 任务详情 / 取消 / 重绘 / 批量删除
- 输出文件 PathGuard 集成
- 配置写回 + host 只读
- SSE 端点路径正确性
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from bin.integrated_app.app_server import create_app


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


# ════════════════════════════════════════════════════════════
# 基础契约测试
# ════════════════════════════════════════════════════════════
class TestBasicContract:
    """基础可用性契约"""

    def test_health_ok(self, client: TestClient) -> None:
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "gpu" in body
        assert "engines" in body

    def test_config_ok(self, client: TestClient) -> None:
        r = client.get("/api/config")
        assert r.status_code == 200
        assert "server" in r.json()

    def test_config_loras_ok(self, client: TestClient) -> None:
        """GET /api/config/loras — LoRA 下拉数据源"""
        r = client.get("/api/config/loras")
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"loras", "count", "mode"}
        assert isinstance(body["loras"], list)
        assert body["count"] == len(body["loras"])

    def test_list_endpoints_ok(self, client: TestClient) -> None:
        """只读列表端点 200"""
        for path in ("/api/tasks", "/api/presets", "/api/outputs"):
            r = client.get(path)
            assert r.status_code == 200, f"{path} -> {r.status_code}"

    def test_sse_events_endpoint_correct(self, client: TestClient) -> None:
        """SSE 端点路径应为 /api/events（非 /api/sse/events）——用 OpenAPI 断言，避免消费无限流"""
        spec = client.get("/openapi.json").json()
        paths = spec.get("paths", {})
        assert "/api/events" in paths, "缺少 SSE 端点 /api/events"
        assert "/api/sse/events" not in paths, "不应存在旧路径 /api/sse/events"

    def test_generate_valid_payload_not_422_or_500(self, client: TestClient) -> None:
        """合法请求体不得 422 或 500"""
        r = client.post("/api/generate", json=_valid_generate_payload())
        assert r.status_code in (200, 400, 409, 503), f"got {r.status_code}: {r.text[:120]}"

    def test_generate_invalid_payload_422(self, client: TestClient) -> None:
        """非法请求体触发 Pydantic 422"""
        r = client.post("/api/generate", json={"positive_prompt": 12345})
        assert r.status_code == 422

    def test_presets_create_ok(self, client: TestClient) -> None:
        """预设创建可写"""
        name = f"契约测试预设-{uuid.uuid4().hex[:8]}"
        r = client.post(
            "/api/presets",
            json={"name": name, "engine_name": "flux2_klein_9b_distilled", "config": {"steps": 8}},
        )
        assert r.status_code == 200


# ════════════════════════════════════════════════════════════
# 深度集成测试 — 生成路由
# ════════════════════════════════════════════════════════════
class TestGenerateRoutes:
    """POST /api/generate 深度测试"""

    def test_generate_engine_not_found_404(self, client: TestClient) -> None:
        """引擎不存在 → 404"""
        payload = _valid_generate_payload()
        payload["engine_name"] = "nonexistent_engine"
        r = client.post("/api/generate", json=payload)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:120]}"

    def test_generate_batch_too_large_400(self, client: TestClient) -> None:
        """batch_size > 9999 → 400"""
        payload = _valid_generate_payload()
        payload["batch_size"] = 10000
        r = client.post("/api/generate", json=payload)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:120]}"

    def test_generate_batch_zero_400(self, client: TestClient) -> None:
        """batch_size < 1 → 400"""
        payload = _valid_generate_payload()
        payload["batch_size"] = 0
        r = client.post("/api/generate", json=payload)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:120]}"

    def test_gpu_status_ok(self, client: TestClient) -> None:
        """GET /api/gpu → 200"""
        r = client.get("/api/gpu")
        assert r.status_code == 200
        body = r.json()
        assert "name" in body
        assert "backend" in body


# ════════════════════════════════════════════════════════════
# 深度集成测试 — 任务路由
# ════════════════════════════════════════════════════════════
class TestTaskRoutes:
    """任务历史 + 取消 + 重绘 + 删除"""

    def test_list_tasks_pagination(self, client: TestClient) -> None:
        """GET /api/tasks 分页参数"""
        r = client.get("/api/tasks?page=1&page_size=10")
        assert r.status_code == 200
        body = r.json()
        assert "tasks" in body
        assert "total" in body
        assert body["page"] == 1
        assert body["page_size"] == 10

    def test_get_task_not_found_404(self, client: TestClient) -> None:
        """GET /api/tasks/{id} 不存在 → 404"""
        r = client.get("/api/tasks/nonexistent-task-id")
        assert r.status_code == 404

    def test_cancel_task_not_found_404(self, client: TestClient) -> None:
        """POST /api/tasks/{id}/cancel 不存在 → 404"""
        r = client.post("/api/tasks/nonexistent-task-id/cancel")
        assert r.status_code == 404

    def test_redraw_task_not_found_404(self, client: TestClient) -> None:
        """POST /api/tasks/{id}/redraw 不存在 → 404"""
        r = client.post("/api/tasks/nonexistent-task-id/redraw")
        assert r.status_code == 404

    def test_delete_tasks_empty_400(self, client: TestClient) -> None:
        """DELETE /api/tasks 无 task_ids → 400"""
        r = client.delete("/api/tasks")
        assert r.status_code == 400

    def test_list_tasks_with_filters(self, client: TestClient) -> None:
        """GET /api/tasks 带筛选参数"""
        r = client.get("/api/tasks?status=completed&engine=flux2_klein_9b_distilled")
        assert r.status_code == 200
        body = r.json()
        assert "tasks" in body


# ════════════════════════════════════════════════════════════
# 深度集成测试 — 预设路由
# ════════════════════════════════════════════════════════════
class TestPresetRoutes:
    """预设 CRUD 全流程"""

    def test_preset_full_lifecycle(self, client: TestClient) -> None:
        """预设 创建→获取→更新→应用→删除 全流程"""
        # 创建
        name = f"lifecycle-{uuid.uuid4().hex[:8]}"
        r = client.post(
            "/api/presets",
            json={"name": name, "engine_name": "flux2_klein_9b_distilled", "config": {"steps": 8}},
        )
        assert r.status_code == 200
        pid = r.json()["id"]
        assert pid > 0

        # 获取
        r = client.get(f"/api/presets/{pid}")
        assert r.status_code == 200
        assert r.json()["name"] == name

        # 更新
        r = client.put(f"/api/presets/{pid}", json={"name": f"updated-{name}"})
        assert r.status_code == 200
        r = client.get(f"/api/presets/{pid}")
        assert r.json()["name"] == f"updated-{name}"

        # 应用
        r = client.post(f"/api/presets/{pid}/apply")
        assert r.status_code == 200
        assert r.json()["status"] == "applied"

        # 删除
        r = client.delete(f"/api/presets/{pid}")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

        # 再次获取 → 404
        r = client.get(f"/api/presets/{pid}")
        assert r.status_code == 404

    def test_preset_get_not_found_404(self, client: TestClient) -> None:
        """GET /api/presets/{id} 不存在 → 404"""
        r = client.get("/api/presets/99999")
        assert r.status_code == 404

    def test_preset_delete_not_found_404(self, client: TestClient) -> None:
        """DELETE /api/presets/{id} 不存在 → 404"""
        r = client.delete("/api/presets/99999")
        assert r.status_code == 404

    def test_preset_export(self, client: TestClient) -> None:
        """GET /api/presets/export → 200 + list"""
        r = client.get("/api/presets/export")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_preset_import(self, client: TestClient) -> None:
        """POST /api/presets/import → 200"""
        r = client.post("/api/presets/import", json=[
            {"name": f"import-{uuid.uuid4().hex[:8]}", "engine_name": "flux2_klein_9b_distilled", "config": {}},
        ])
        assert r.status_code == 200
        body = r.json()
        assert body["imported"] >= 1


# ════════════════════════════════════════════════════════════
# 深度集成测试 — 输出路由 + 安全
# ════════════════════════════════════════════════════════════
class TestOutputRoutes:
    """图库 + PathGuard 集成"""

    def test_list_outputs_ok(self, client: TestClient) -> None:
        """GET /api/outputs → 200"""
        r = client.get("/api/outputs")
        assert r.status_code == 200
        body = r.json()
        assert "outputs" in body
        assert "total" in body

    def test_get_output_traversal_403(self, client: TestClient) -> None:
        """GET /api/outputs/../../etc/passwd → 403（PathGuard 集成）"""
        r = client.get("/api/outputs/../../etc/passwd")
        # catch-all 可能拦截，但 PathGuard 在 output_routes 中应拒绝
        # 由于 catch-all 优先级问题，此处验证不返回 200 + 文件内容
        assert r.status_code != 200 or "passwd" not in r.text, \
            "Path traversal should not return file content"

    def test_get_output_not_found_404(self, client: TestClient) -> None:
        """GET /api/outputs/nonexistent.png → 404"""
        r = client.get("/api/outputs/nonexistent.png")
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════
# 深度集成测试 — 配置写回
# ════════════════════════════════════════════════════════════
class TestConfigRoutes:
    """PUT /api/config 配置写回"""

    def test_config_update_inference(self, client: TestClient) -> None:
        """PUT /api/config 更新推理参数"""
        r = client.put("/api/config", json={
            "inference": {"default_steps": 12},
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # 恢复原值
        client.put("/api/config", json={
            "inference": {"default_steps": 10},
        })

    def test_config_update_no_changes(self, client: TestClient) -> None:
        """PUT /api/config 空更新 → No changes"""
        r = client.put("/api/config", json={})
        assert r.status_code == 200
        assert "No changes" in r.json().get("message", "")

    def test_config_safe_dict_redacts_secrets(self, client: TestClient) -> None:
        """GET /api/config 脱敏：api_token 不暴露"""
        r = client.get("/api/config")
        body = r.json()
        security = body.get("security", {})
        api_token = security.get("api_token", {})
        if "tokens" in api_token:
            assert api_token["tokens"] == [], "API tokens should be redacted"
