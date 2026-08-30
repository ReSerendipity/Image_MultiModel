"""
test_weight_integrity.py — 权重加载前完整性校验（MLOps P0-1）单测

覆盖: SHA256 计算、safetensors 头解析、pickle 探测、格式白名单、manifest 比对、缺失文件处理。
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from integrated_app.security import weight_integrity as wi


def _make_safetensors(path: Path, *, corrupt: bool = False, pickle: bool = False) -> None:
    """构造一个最小 safetensors 文件（仅头 + 占位数据）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if pickle:
        path.write_bytes(b"\x80\x02" + b"c__builtin__\neval\n(S'x'\ntR." ,)
        return
    if corrupt:
        path.write_bytes(b"not a safetensors file at all!!")
        return
    header = {
        "__metadata__": {"format": "pt"},
        "weight": {"dtype": "F32", "shape": [2, 2], "data_offsets": [0, 16]},
    }
    header_bytes = json.dumps(header).encode()
    blob = struct.pack("<Q", len(header_bytes)) + header_bytes + b"\x00" * 16
    path.write_bytes(blob)


def test_compute_sha256_matches_hashlib(tmp_path: Path) -> None:
    import hashlib

    f = tmp_path / "a.bin"
    data = b"hello world" * 1000
    f.write_bytes(data)
    assert wi.compute_file_sha256(f) == hashlib.sha256(data).hexdigest()


def test_validate_valid_safetensors(tmp_path: Path) -> None:
    f = tmp_path / "lora.safetensors"
    _make_safetensors(f)
    res = wi.validate_weight_file(f)
    assert res.ok is True
    assert res.fmt == "safetensors"
    assert res.tensor_count == 1
    assert res.sha256


def test_validate_corrupt_safetensors(tmp_path: Path) -> None:
    f = tmp_path / "bad.safetensors"
    _make_safetensors(f, corrupt=True)
    res = wi.validate_weight_file(f)
    assert res.ok is False
    assert "invalid_safetensors_header" in res.error


def test_validate_pickle_rejected(tmp_path: Path) -> None:
    f = tmp_path / "evil.pt"
    _make_safetensors(f, pickle=True)
    res = wi.validate_weight_file(f, allow_non_safetensors=True)
    assert res.ok is False
    assert "pickle" in res.error


def test_validate_non_safetensors_rejected_by_default(tmp_path: Path) -> None:
    f = tmp_path / "model.bin"
    f.write_bytes(b"PK\x03\x04 some zip-ish bytes")
    res = wi.validate_weight_file(f, allow_non_safetensors=False)
    assert res.ok is False
    assert "non-safetensors" in res.error


def test_validate_non_safetensors_allowed(tmp_path: Path) -> None:
    f = tmp_path / "model.bin"
    f.write_bytes(b"PK\x03\x04 some zip-ish bytes")
    res = wi.validate_weight_file(f, allow_non_safetensors=True)
    # zip 格式被允许（不视为损坏），但非 safetensors 故 tensor_count=0
    assert res.ok is True
    assert res.fmt == "zip"


def test_validate_sha256_mismatch(tmp_path: Path) -> None:
    f = tmp_path / "lora.safetensors"
    _make_safetensors(f)
    res = wi.validate_weight_file(f, expected_sha256="deadbeef" * 8)
    assert res.ok is False
    assert res.error == "sha256_mismatch"


def test_validate_sha256_match(tmp_path: Path) -> None:
    f = tmp_path / "lora.safetensors"
    _make_safetensors(f)
    expected = wi.compute_file_sha256(f)
    res = wi.validate_weight_file(f, expected_sha256=expected)
    assert res.ok is True


def test_missing_file_result(tmp_path: Path) -> None:
    res = wi.validate_weight_file(tmp_path / "ghost.safetensors")
    assert res.ok is False
    assert res.error == "file_not_found"


def test_manifest_hash_lookup_absolute_and_relative(tmp_path: Path) -> None:
    f = tmp_path / "loras" / "foo.safetensors"
    _make_safetensors(f)
    sha = wi.compute_file_sha256(f)
    manifest = {str(f).replace("\\", "/"): sha, "loras/bar.safetensors": "abc"}
    # 绝对路径命中
    assert wi.manifest_hash_for_path(manifest, f, project_root=tmp_path) == sha
    # 相对路径命中
    rel = "loras/foo.safetensors"
    manifest2 = {rel: sha}
    assert wi.manifest_hash_for_path(manifest2, f, project_root=tmp_path) == sha


def test_load_weight_manifest_missing_returns_empty(tmp_path: Path) -> None:
    assert wi.load_weight_manifest(tmp_path / "nope.json") == {}


def test_verify_weights_against_manifest(tmp_path: Path) -> None:
    loras_dir = tmp_path / "loras"
    f = loras_dir / "foo.safetensors"
    _make_safetensors(f)
    sha = wi.compute_file_sha256(f)
    manifest = {"loras/foo.safetensors": sha}
    report = wi.verify_weights_against_manifest(manifest=manifest, project_root=tmp_path)
    assert report["total"] == 1
    assert report["passed"] == 1
    assert report["failed"] == 0
