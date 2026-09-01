"""
tests/release/test_post_deploy_smoke.py — P2-11 post-deploy smoke 测试

使用一个 FakeSmokeClient 把每个检查的 HTTP 交互固定下来，验证：
- 健康检查通过 / 失败的判定；
- 引擎列表 / 配置 / SSE 探测 / Prometheus 端点的判定；
- generation 检查能在超时内正确判定 completed/failed；
- run() 汇总报告；main 失败时退出码非零。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

_SPEC = Path(__file__).resolve().parents[2] / "scripts" / "post_deploy_smoke.py"


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("post_deploy_smoke", _SPEC)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


# ────────────────────────── Fake 客户端 ──────────────────────────
class FakeResponse:
    def __init__(self, status: int, payload: str = ""):
        self.status = status
        self._payload = payload.encode("utf-8")
        self.headers: dict[str, str] = {}

    def read(self, n: int = -1) -> bytes:
        if n < 0 or n >= len(self._payload):
            data, self._payload = self._payload, b""
            return data
        data, self._payload = self._payload[:n], self._payload[n:]
        return data

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeSmokeClient:
    """替代 SmokeClient 的最小桩：直接接收预编排的响应序列。"""

    def __init__(self, scripts: list[FakeResponse]):
        self._scripts = list(scripts)
        self._cursor = 0
        self.base_url = "http://test"
        self.timeout = 5.0
        self.csrf_token = ""

    def _next(self, method: str, path: str) -> FakeResponse:
        if self._cursor >= len(self._scripts):
            raise AssertionError(f"unexpected request {method} {path}")
        self._cursor += 1
        return self._scripts[self._cursor - 1]

    @contextmanager
    def _request(self, method, path, body=None, headers=None, stream=False):
        yield self._next(method, path)

    def read_request_count(self) -> int:
        return self._cursor


def _make_real_client(mod, scripts: list[FakeResponse]):
    """构造一个 mod.SmokeClient，但把 _request 替换成读取预编排的响应。"""
    c = mod.SmokeClient(base_url="http://test", timeout=5.0)
    cursor = {"i": 0}

    @contextmanager
    def fake(method, path, body=None, headers=None, stream=False):
        if cursor["i"] >= len(scripts):
            raise AssertionError(f"unexpected request {method} {path}")
        resp = scripts[cursor["i"]]
        cursor["i"] += 1
        yield resp

    c._request = fake
    return c, cursor


# ────────────────────────── 各检查 ──────────────────────────
def test_check_health_ok(mod):
    c, _ = _make_real_client(mod, [FakeResponse(200, json.dumps({"status": "ok", "queue": {"total": 0}}))])
    r = mod.check_health(c, {})
    assert r.ok
    assert r.extras["status"] == "ok"


def test_check_health_bad_status_field(mod):
    c, _ = _make_real_client(mod, [FakeResponse(200, json.dumps({"status": "down"}))])
    r = mod.check_health(c, {})
    assert not r.ok


@pytest.mark.parametrize(
    "scripts,ok,detail_match",
    [
        (
            [FakeResponse(200, json.dumps({"runtime": {"task_queue": {"maxsize": 100}}}))],
            True,
            "maxsize=100",
        ),
        (
            [FakeResponse(200, json.dumps({"runtime": {}}))],
            False,  # maxsize 缺失视为异常
            "maxsize=None",
        ),
        (
            [FakeResponse(500, "")],
            False,
            "HTTP 500",
        ),
    ],
)
def test_check_config(mod, scripts, ok, detail_match):
    c, _ = _make_real_client(mod, scripts)
    r = mod.check_config(c, {})
    assert r.ok is ok
    assert detail_match in r.detail


def test_check_engines_contains_zimage(mod):
    body = json.dumps({"engines": [{"name": "z_image_turbo_native", "state": "ready"}]})
    c, _ = _make_real_client(mod, [FakeResponse(200, body)])
    r = mod.check_engines(c, {})
    assert r.ok
    assert "z_image_turbo_native" in r.extras["engine_names"]


def test_check_engines_missing_target(mod):
    c, _ = _make_real_client(mod, [FakeResponse(200, json.dumps({"engines": [{"name": "other"}]}))])
    r = mod.check_engines(c, {})
    assert not r.ok


def test_check_queue_protection_ok(mod):
    text = "# HELP queue_depth ...\nqueue_depth 0\nqueue_rejected_total 0\n"
    body_cfg = json.dumps({"runtime": {"task_queue": {"maxsize": 64}}})
    c, _ = _make_real_client(mod, [FakeResponse(200, text), FakeResponse(200, body_cfg)])
    r = mod.check_queue_protection(c, {})
    assert r.ok
    assert r.extras["maxsize"] == 64


def test_check_queue_protection_missing_metric(mod):
    body_cfg = json.dumps({"runtime": {"task_queue": {"maxsize": 64}}})
    c, _ = _make_real_client(mod, [FakeResponse(200, "# empty\n"), FakeResponse(200, body_cfg)])
    r = mod.check_queue_protection(c, {})
    assert not r.ok
    assert r.extras["has_depth"] is False


def test_check_generation_completes(mod):
    submit = FakeResponse(200, json.dumps({"task_id": "abc123"}))
    polled = FakeResponse(200, json.dumps({"status": "completed"}))
    c, _ = _make_real_client(mod, [submit, polled])
    r = mod.check_generation(c, {"generation_timeout_s": 5.0})
    assert r.ok
    assert r.name == "generation_completed"


def test_check_generation_submit_fails(mod):
    c, _ = _make_real_client(mod, [FakeResponse(503, "boom")])
    r = mod.check_generation(c, {"generation_timeout_s": 1.0})
    assert not r.ok
    assert r.name == "generation_submit"


def test_check_generation_failed_status(mod):
    submit = FakeResponse(200, json.dumps({"task_id": "abc123"}))
    polled = FakeResponse(200, json.dumps({"status": "failed", "error": "OOM"}))
    c, _ = _make_real_client(mod, [submit, polled])
    r = mod.check_generation(c, {"generation_timeout_s": 1.0})
    assert not r.ok
    assert "OOM" in r.detail


def test_run_aggregates_pass_and_fail(mod):
    """SmokeReport 汇总：所有检查都返回汇总结果。"""
    scripts = [
        FakeResponse(200, json.dumps({"status": "ok"})),
        FakeResponse(200, json.dumps({"runtime": {"task_queue": {"maxsize": 32}}})),
        FakeResponse(200, json.dumps({"engines": [{"name": "z_image_turbo_native"}]})),
    ]
    c, _ = _make_real_client(mod, scripts)
    # 直接绕过 client.run 调用各 check
    results = [
        mod.check_health(c, {}),
        mod.check_config(c, {}),
        mod.check_engines(c, {}),
    ]
    report = mod.SmokeReport(base_url="x", started_at=0.0, results=results, finished_at=1.0)
    assert report.passed is True
    assert report.failed_checks == []


def test_check_sse_receives_chunk(mod):
    """SSE 探测：注入 urllib.request.urlopen 返回带内容的 FakeResponse。"""
    c = mod.SmokeClient(base_url="http://test", timeout=2.0)
    import urllib.request as ur

    real = ur.urlopen

    def fake_urlopen(req, timeout=None):
        return FakeResponse(200, ": ping\n\n")

    ur.urlopen = fake_urlopen
    try:
        r = mod.check_sse(c, {})
    finally:
        ur.urlopen = real
    assert r.ok
    assert "first chunk" in r.detail


def test_check_sse_no_bytes_fails(mod):
    """SSE 端点可达但 0 字节：标记失败。"""
    c = mod.SmokeClient(base_url="http://test", timeout=1.0)
    import urllib.request as ur

    real = ur.urlopen

    def empty_urlopen(req, timeout=None):
        return FakeResponse(200, "")

    ur.urlopen = empty_urlopen
    try:
        r = mod.check_sse(c, {})
    finally:
        ur.urlopen = real
    assert not r.ok
    assert "no bytes" in r.detail or "first chunk" in r.detail or r.detail.startswith("connected")


def test_main_returns_nonzero_when_failed(mod, monkeypatch):
    """main() 在 smoke 失败时退出码 1（用于 CI 门禁）。

    注意：不使用 pytest 的 tmp_path —— Windows 上 pytest 会话结束时清理
    `pytest-current` 符号链接会抛 PermissionError [WinError 5]（与被测代码无关）。
    """
    import shutil
    import tempfile

    out_dir = Path(tempfile.mkdtemp(prefix="imm-smoke-"))
    out_json = out_dir / "smoke.json"

    def boom(client, cfg):
        return mod.CheckResult("any", False, "mocked fail")

    monkeypatch.setattr(mod, "check_health", boom)
    monkeypatch.setattr(mod, "check_config", boom)
    monkeypatch.setattr(mod, "check_engines", boom)
    monkeypatch.setattr(mod, "check_generation", boom)
    monkeypatch.setattr(mod, "check_queue_protection", boom)
    monkeypatch.setattr(mod, "check_sse", boom)

    sys_argv_backup = sys.argv[:]
    sys.argv = ["post_deploy_smoke", "--output", str(out_json)]
    try:
        rc = mod.main()
    finally:
        sys.argv = sys_argv_backup
    assert rc == 1
    try:
        saved = json.loads(out_json.read_text(encoding="utf-8"))
        assert saved["passed"] is False
        assert "any" in saved["failed"]
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
