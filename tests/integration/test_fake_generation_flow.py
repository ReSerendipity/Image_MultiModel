"""
tests/integration/test_fake_generation_flow.py — 无 GPU 的完整生成链路集成测试

对应测试体系评估 P0-2：E2E / 集成生成流程去 GPU 化。

通过环境变量 IMM_FAKE_ENGINE=1 让 model_registry 返回 FakeEngine（不触发任何
GPU 推理），从而在无 GPU 的 CI 环境中也能跑通：
    prompt 提交 → 任务入队 → worker 执行 → 进度回调 → 输出落盘 → 历史可读
覆盖需求「用户旅程从 prompt 到 output」，且可复现、不 flaky。
真实 GPU 推理仅保留为 @pytest.mark.slow 的人工冒烟（见 tests/integration 下的
前向路径测试，需 ComfyUI/原生引擎在线）。
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.integrated_app.app_server import create_app  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def fake_client():
    """启用假引擎的 TestClient（进程级环境变量，worker 运行期读取）。"""
    import os

    os.environ["IMM_FAKE_ENGINE"] = "1"
    with TestClient(create_app()) as c:
        # 取 CSRF token（CSRF 中间件默认开启）
        health = c.get("/api/health")
        token = health.headers.get("X-CSRF-Token", "")
        if token:
            c.headers["X-CSRF-Token"] = token
        yield c
    os.environ.pop("IMM_FAKE_ENGINE", "")


def _wait_terminal(client: TestClient, task_id: str, timeout_s: float = 10.0) -> dict:
    deadline = time.time() + timeout_s
    d: dict = {}
    while time.time() < deadline:
        d = client.get(f"/api/tasks/{task_id}").json()
        if d.get("status") in ("completed", "failed", "cancelled"):
            return d
        time.sleep(0.05)
    pytest.fail(f"任务 {task_id} 超时（{timeout_s}s），最后状态 {d.get('status')}")


def test_prompt_to_output_journey(fake_client: TestClient) -> None:
    """prompt 提交 → completed → 输出数量 == batch_size → 历史可读。"""
    payload = {
        "positive_prompt": "一只橘猫坐在窗台上，午后阳光",
        "negative_prompt": "",
        "cfg": 1.0, "steps": 8, "width": 512, "height": 512,
        "seed": 42, "batch_size": 2,
        "engine_name": "z_image_turbo_native",
    }
    r = fake_client.post("/api/generate", json=payload)
    assert r.status_code == 200, f"POST /api/generate -> {r.status_code}: {r.text[:200]}"
    tid = r.json()["task_id"]

    # 任务已入队（pending/processing 之一）
    initial = fake_client.get(f"/api/tasks/{tid}").json()
    assert initial.get("status") in ("pending", "processing", "completed")

    d = _wait_terminal(fake_client, tid)
    assert d["status"] == "completed", d.get("error")
    assert d.get("output_count", 0) == 2, f"期望 2 张输出，实际 {d.get('output_count')}"

    # 输出列表可读（证明输出已落盘并登记）
    outs = fake_client.get("/api/outputs?page=1&page_size=20").json()
    assert outs.get("total", 0) >= 1, "输出列表应为非空"


def test_generation_marks_history_entry(fake_client: TestClient) -> None:
    """生成完成后历史任务存在且状态一致。"""
    payload = {
        "positive_prompt": "test history entry",
        "cfg": 1.0, "steps": 4, "width": 256, "height": 256,
        "seed": 7, "batch_size": 1,
        "engine_name": "z_image_turbo_native",
    }
    r = fake_client.post("/api/generate", json=payload)
    assert r.status_code == 200
    tid = r.json()["task_id"]
    d = _wait_terminal(fake_client, tid)
    assert d["status"] == "completed"

    detail = fake_client.get(f"/api/tasks/{tid}").json()
    assert detail["task_id"] == tid
    assert detail.get("status") == "completed"


def test_cancel_endpoint_accepts(fake_client: TestClient) -> None:
    """取消接口可达且返回 2xx/404（真实取消链路在 slow 冒烟中验证）。"""
    payload = {
        "positive_prompt": "test cancel",
        "cfg": 1.0, "steps": 4, "width": 256, "height": 256,
        "seed": 1, "batch_size": 1,
        "engine_name": "z_image_turbo_native",
    }
    r = fake_client.post("/api/generate", json=payload)
    assert r.status_code == 200
    tid = r.json()["task_id"]
    cr = fake_client.post(f"/api/tasks/{tid}/cancel")
    assert cr.status_code in (200, 404, 409), f"cancel -> {cr.status_code}"
    d = _wait_terminal(fake_client, tid, timeout_s=5)
    assert d.get("status") in ("completed", "cancelled", "failed")
