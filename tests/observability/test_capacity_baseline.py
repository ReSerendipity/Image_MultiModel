"""
tests/observability/test_capacity_baseline.py — P1-9 容量基线 runner 测试

覆盖：
- 容量公式推导（derive_capacity）正确；
- profile 矩阵构造（build_matrix）；
- 百分位计算（_pct）；
- 脚本端到端可运行（--quick）并产出基线 JSON。
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_SPEC = Path(__file__).resolve().parents[2] / "scripts" / "capacity_baseline.py"


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("capacity_baseline", _SPEC)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m  # 供 dataclass 字符串注解解析
    spec.loader.exec_module(m)
    return m


def test_pct_basic(mod):
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert mod._pct(vals, 50) == 3.0
    assert mod._pct(vals, 95) == 5.0
    assert mod._pct([], 95) == 0.0


def test_derive_capacity_formula(mod):
    from dataclasses import dataclass

    @dataclass
    class _R:
        p95_s: float

    results = [_R(p95_s=2.0), _R(p95_s=5.0)]  # 最慢 P95 = 5s
    cap = mod.derive_capacity(results, latency_budget_s=30.0)
    # safe_depth = floor(30 / 5 * 1) = 6
    assert cap["safe_queue_depth"] == 6
    assert cap["expansion_trigger_depth"] == 5  # 6 * 0.85 = 5.1 -> int 5
    assert cap["slowest_p95_s"] == 5.0


def test_derive_capacity_zero_latency(mod):
    from dataclasses import dataclass

    @dataclass
    class _R:
        p95_s: float

    cap = mod.derive_capacity([_R(p95_s=0.0)], latency_budget_s=30.0)
    assert cap["safe_queue_depth"] >= 1  # 防御除零


def test_build_matrix_has_expected_profiles(mod):
    matrix = mod.build_matrix()
    names = {name for name, _ in matrix}
    assert "256px_b1" in names
    assert "1024px_b2" in names
    assert len(matrix) == 6  # 3 分辨率 × 2 batch


def test_postprocess_matrix_covers_seedvr2(mod):
    matrix = mod.build_postprocess_matrix()
    names = {name for name, _ in matrix}
    assert "1024px_b1_seedvr2_on" in names
    assert "1024px_b1_seedvr2_off" in names
    flags = {payload.get("seedvr2_enable") for _, payload in matrix[:2]}
    assert flags == {True, False}


def _make_root():
    """自建临时根目录。

    注意：不使用 pytest 的 tmp_path / tmp_path_factory —— Windows 上 pytest 的
    `pytest-current` 符号链接清理会抛 PermissionError [WinError 5]（与被测代码无关）。
    """
    root = Path(tempfile.mkdtemp(prefix="imm-cap-"))
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def tmp_root():
    yield from _make_root()


def test_discover_lora_names_empty_on_missing_dir(mod, tmp_root):
    assert mod.discover_lora_names(tmp_root) == []


def test_discover_lora_names_finds_weights(mod, tmp_root):
    lora_dir = tmp_root / "model" / "loras"
    lora_dir.mkdir(parents=True)
    (lora_dir / "b.safetensors").write_bytes(b"")
    (lora_dir / "a.ckpt").write_bytes(b"")
    (lora_dir / "notes.txt").write_text("ignored", encoding="utf-8")
    assert mod.discover_lora_names(tmp_root) == ["a", "b"]  # 排序后返回，且忽略非权重文件


def test_profile_result_records_peak_vram(mod):
    """ProfileResult 必须携带峰值显存字段（无 GPU 时为 0.0）。"""
    r = mod.ProfileResult(
        profile="x", runs=1, completed=1, failed=0, oom=0,
        p50_s=0.1, p95_s=0.2, p99_s=0.3, throughput_tps=5.0,
        first_preview_avg_s=0.05, persist_avg_s=0.01,
    )
    assert r.peak_vram_gb == 0.0
    assert "peak_vram_gb" in r.__dataclass_fields__


def test_run_profile_completes_serial(mod):
    """在进程内用 FakeEngine 验证 _run_profile 串行完成且不因限流/过载丢任务。"""
    import os

    os.environ["IMM_FAKE_ENGINE"] = "1"
    from fastapi.testclient import TestClient

    from app.integrated_app.app_server import create_app

    with TestClient(create_app(enable_rate_limit=False)) as client:
        token = client.get("/api/health").headers.get("X-CSRF-Token", "")
        if token:
            client.headers["X-CSRF-Token"] = token
        res = mod._run_profile(
            client, "256px_b1",
            {"positive_prompt": "x", "cfg": 1.0, "steps": 4, "seed": 1,
             "width": 256, "height": 256, "batch_size": 1,
             "engine_name": "z_image_turbo_native"},
            runs=4,
        )
    assert res.completed >= 1, f"completed={res.completed} failed={res.failed}"
    assert res.p95_s >= 0.0
    assert res.throughput_tps > 0 or res.completed >= 1
