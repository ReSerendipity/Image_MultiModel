"""
test_lora_vram_estimation.py — 多 LoRA 叠加 VRAM 增量估算（MLOps P0-2）单测

覆盖: safetensors 头解析字节统计、单/多 LoRA 增量、preflight 透传、with_loras 封装。
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from integrated_app.gpu_utils import GPUInfo, preflight_vram, preflight_vram_with_loras
from integrated_app.native import vram as nvram


def _make_safetensors(path: Path, *, params_mb: float = 5.0) -> None:
    """构造含给定参数字节量的最小 safetensors（单张量占位）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    nbytes = int(params_mb * 1024 * 1024)
    header = {
        "weight": {"dtype": "F32", "shape": [nbytes // 4], "data_offsets": [0, nbytes]},
    }
    header_bytes = json.dumps(header).encode()
    blob = struct.pack("<Q", len(header_bytes)) + header_bytes + b"\x00" * nbytes
    path.write_bytes(blob)


def test_estimate_lora_increment_from_header(tmp_path: Path) -> None:
    f = tmp_path / "lora.safetensors"
    _make_safetensors(f, params_mb=5.0)
    # 5MB * 2 bytes/param = 10MB ≈ 0.0093 GB
    inc = nvram.estimate_lora_vram_increment(str(f), strength=1.0)
    assert 0.008 < inc < 0.012


def test_estimate_lora_increment_strength_scales(tmp_path: Path) -> None:
    f = tmp_path / "lora.safetensors"
    _make_safetensors(f, params_mb=10.0)
    base = nvram.estimate_lora_vram_increment(str(f), strength=1.0)
    strong = nvram.estimate_lora_vram_increment(str(f), strength=1.5)
    # strength 仅做 max(0.1,|s|) 轻微修正，不应改变量级
    assert strong > base
    assert strong < base * 1.6


def test_estimate_lora_increment_missing_file_uses_default(tmp_path: Path) -> None:
    inc = nvram.estimate_lora_vram_increment(str(tmp_path / "ghost.safetensors"), strength=1.0)
    assert inc == nvram._DEFAULT_LORA_INCREMENT_GB


def test_estimate_lora_stack_vram_sums(tmp_path: Path) -> None:
    a = tmp_path / "a.safetensors"
    b = tmp_path / "b.safetensors"
    _make_safetensors(a, params_mb=5.0)
    _make_safetensors(b, params_mb=15.0)
    total = nvram.estimate_lora_stack_vram([(str(a), 1.0), (str(b), 1.0)])
    # a≈0.0093 + b≈0.0279 ≈ 0.037
    assert 0.03 < total < 0.045


def test_estimate_lora_stack_from_stack_resolves_paths(tmp_path: Path) -> None:
    a = tmp_path / "a.safetensors"
    _make_safetensors(a, params_mb=5.0)
    stack = [{"name": "a", "strength": 1.0}]
    lora_paths = {"a": str(a)}
    inc = nvram.estimate_lora_stack_vram_from_stack(stack, lora_paths)
    assert inc > 0.008


def test_preflight_includes_lora_extra() -> None:
    gpu = GPUInfo(total_vram_gb=24.0, used_vram_gb=2.0, free_vram_gb=22.0, backend="cuda")
    base = preflight_vram(16.0, 1024, 1024, 1, gpu_info=gpu)
    with_lora = preflight_vram(16.0, 1024, 1024, 1, gpu_info=gpu, lora_extra_vram_gb=4.0)
    assert with_lora.needed_vram_gb == pytest.approx(base.needed_vram_gb + 4.0)
    assert with_lora.lora_increment_gb == 4.0


def test_preflight_with_loras_convenience(tmp_path: Path) -> None:
    a = tmp_path / "a.safetensors"
    b = tmp_path / "b.safetensors"
    _make_safetensors(a, params_mb=5.0)
    _make_safetensors(b, params_mb=5.0)
    gpu = GPUInfo(total_vram_gb=24.0, used_vram_gb=2.0, free_vram_gb=22.0, backend="cuda")
    est = preflight_vram_with_loras(
        10.0,
        [{"name": "a", "strength": 1.0}, {"name": "b", "strength": 1.0}],
        width=1024, height=1024, batch_size=1,
        lora_paths={"a": str(a), "b": str(b)},
        gpu_info=gpu,
    )
    assert est.lora_increment_gb > 0
    assert est.needed_vram_gb > 10.0 * 1.5  # 含 base + lora 增量 + headroom
