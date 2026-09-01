"""
单元测试：services/generation_service.py（P0-1 服务层 + P3-9/P3-10）

聚焦新增的纯逻辑单元：LoRA 兼容性强制、幂等键、回滚补偿，
避免触发真实推理/CLIP（这些已由路由集成测试覆盖）。
"""

import asyncio

import pytest
from fastapi import HTTPException

from app.integrated_app.services.generation_service import (
    GenerationService,
    _idempotency_get,
    _idempotency_put,
    clear_idempotency_cache,
)


class _FakeHistory:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create_task(self, **kwargs):
        self.created.append(kwargs["task_id"])

    def delete_tasks(self, ids):
        self.deleted.extend(ids)


class _FakeQueue:
    def __init__(self, submit_ok=True, size=0):
        self._submit_ok = submit_ok
        self.queue_size = size
        self.submitted = []
        self._n = 0

    def generate_task_id(self):
        self._n += 1
        return f"task{self._n}"

    async def submit(self, task):
        self.submitted.append(task.task_id)
        return self._submit_ok


@pytest.fixture(autouse=True)
def _reset_idem():
    clear_idempotency_cache()
    yield
    clear_idempotency_cache()


def _make_service(submit_ok=True):
    return GenerationService(_FakeQueue(submit_ok=submit_ok), _FakeHistory(), config=None)


def test_lora_incompatible_rejected():
    svc = _make_service()
    engine = type("E", (), {"name": "e1", "compatibility_matrix": {"bad": ["other"]}})()
    with pytest.raises(HTTPException) as exc:
        svc._validate_lora_compatibility(engine, [{"name": "bad"}])
    assert exc.value.status_code == 422


def test_lora_compatible_ok():
    svc = _make_service()
    engine = type("E", (), {"name": "e1", "compatibility_matrix": {"good": ["e1"]}})()
    # 不兼容声明则不应抛异常；已声明且含当前引擎亦兼容
    svc._validate_lora_compatibility(engine, [{"name": "good"}])
    # 未声明的 LoRA 默认兼容
    svc._validate_lora_compatibility(engine, [{"name": "unknown"}])


def test_idempotency_cache_put_get():
    _idempotency_put("k", "abc")
    assert _idempotency_get("k") == "abc"
    assert _idempotency_get("missing") is None


def test_idempotency_ttl_expiry(monkeypatch):
    import app.integrated_app.services.generation_service as gmod

    _idempotency_put("k", "abc")
    # 篡改缓存时间戳使其过期
    for key in list(gmod._IDEMPOTENCY_CACHE.keys()):
        ts, val = gmod._IDEMPOTENCY_CACHE[key]
        gmod._IDEMPOTENCY_CACHE[key] = (ts - 1000.0, val)
    assert _idempotency_get("k") is None


def test_submit_idempotent_replay_early_returns():
    """幂等命中在引擎校验之前即返回，复用首次 task_id（P3-10）。"""
    svc = _make_service()
    _idempotency_put("replay-key", "first-task")
    from app.integrated_app.services.generation_service import GenerateRequest

    resp = asyncio.run(svc.submit_txt2img(GenerateRequest(idempotency_key="replay-key")))
    assert resp.deduplicated is True
    assert resp.task_id == "first-task"


def test_rollback_on_queue_full():
    """入队失败时补偿删除 history 记录，消除孤儿任务（P2-8）。"""
    svc = GenerationService(_FakeQueue(submit_ok=False), _FakeHistory(), config=None)
    svc._history_db.create_task(task_id="t1", engine="e")
    svc._rollback_task("t1")
    assert "t1" in svc._history_db.deleted
