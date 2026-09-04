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


# ── 2026-09-04 安全评估 M4/H2：manifest 激活 + 符号链接键回退 + 期望 hash 解析 ──


def test_manifest_hash_lookup_logical_path_through_symlink(tmp_path: Path) -> None:
    """逻辑路径（未 resolve，可能经符号链接）须能命中相对键清单。

    场景：model/ 目录经符号链接指向外部模型库（本仓 portable 部署实况）。
    加载路径传"逻辑绝对路径"，旧实现只查 resolve() 后的物理相对键——
    物理路径落在项目根外导致 relative_to 抛 ValueError，逻辑键永远匹配不上。
    """
    real = tmp_path / "external_model_lib"
    f = real / "Z-image-bf16" / "z.safetensors"
    _make_safetensors(f)
    sha = wi.compute_file_sha256(f)
    # 清单键 = 逻辑相对键（generate_weight_manifest.py 的键形态）
    manifest = {"model/unet/Z-image-bf16/z.safetensors": sha}
    # 加载时的逻辑绝对路径（无需真实符号链接——relative_to 是纯词法操作）
    logical_abs = tmp_path / "model" / "unet" / "Z-image-bf16" / "z.safetensors"
    assert wi.manifest_hash_for_path(manifest, logical_abs, project_root=tmp_path) == sha
    # 物理路径在项目根外时不得崩溃，返回 None（按未登记处理）
    outside = tmp_path / "elsewhere" / "z.safetensors"
    assert wi.manifest_hash_for_path(manifest, outside, project_root=tmp_path) is None


class _CfgStub:
    """resolve_expected_sha256 的最小配置桩（避免依赖全局 get_config）。"""

    def __init__(self, tmp_path: Path, *, manifest_rel: str | None, verify: bool = True):
        self.project_root = str(tmp_path)
        self.security = type(
            "Sec",
            (),
            {
                "model_format": type(
                    "Mfmt",
                    (),
                    {
                        "verify_weights": verify,
                        "weight_manifest_file": manifest_rel or "",
                    },
                )()
            },
        )()


def test_resolve_expected_sha256_registered(tmp_path: Path) -> None:
    f = tmp_path / "model" / "loras" / "foo.safetensors"
    _make_safetensors(f)
    sha = wi.compute_file_sha256(f)
    manifest_path = tmp_path / "data" / "weight_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"files": {"model/loras/foo.safetensors": sha}}), encoding="utf-8"
    )
    cfg = _CfgStub(tmp_path, manifest_rel="data/weight_manifest.json")
    expected, registered = wi.resolve_expected_sha256(f, cfg)
    assert registered is True
    assert expected == sha


def test_resolve_expected_sha256_unregistered(tmp_path: Path) -> None:
    f = tmp_path / "model" / "loras" / "other.safetensors"
    _make_safetensors(f)
    manifest_path = tmp_path / "data" / "weight_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"files": {}}), encoding="utf-8")
    cfg = _CfgStub(tmp_path, manifest_rel="data/weight_manifest.json")
    expected, registered = wi.resolve_expected_sha256(f, cfg)
    assert registered is False
    assert expected is None


def test_resolve_expected_sha256_no_manifest_configured(tmp_path: Path) -> None:
    f = tmp_path / "model" / "loras" / "foo.safetensors"
    _make_safetensors(f)
    cfg = _CfgStub(tmp_path, manifest_rel=None)
    assert wi.resolve_expected_sha256(f, cfg) == (None, False)
    # verify_weights 关闭时同样不解析
    cfg_off = _CfgStub(tmp_path, manifest_rel="data/weight_manifest.json", verify=False)
    assert wi.resolve_expected_sha256(f, cfg_off) == (None, False)


def test_resolve_expected_sha256_manifest_file_missing(tmp_path: Path) -> None:
    f = tmp_path / "model" / "loras" / "foo.safetensors"
    _make_safetensors(f)
    cfg = _CfgStub(tmp_path, manifest_rel="data/weight_manifest.json")  # 文件不存在
    assert wi.resolve_expected_sha256(f, cfg) == (None, False)


def test_validate_hash_mismatch_rejected_even_with_registered_manifest(tmp_path: Path) -> None:
    """清单登记的权重被篡改（内容替换）→ sha256_mismatch → ok=False（fail-closed 拒绝）。"""
    f = tmp_path / "loras" / "tampered.safetensors"
    _make_safetensors(f)
    real_sha = wi.compute_file_sha256(f)
    _make_safetensors(f, corrupt=False)  # 重写（内容相同则无篡改），改为追加字节模拟篡改
    with open(f, "ab") as fh:
        fh.write(b"tampered-bytes")
    tampered_sha = wi.compute_file_sha256(f)
    assert tampered_sha != real_sha
    res = wi.validate_weight_file(f, expected_sha256=real_sha)
    assert res.ok is False
    assert res.error == "sha256_mismatch"
