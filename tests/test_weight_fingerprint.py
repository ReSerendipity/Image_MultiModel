"""
test_weight_fingerprint.py — 数据治理报告 P2-2：权重 sha256/version 登记

覆盖：
- compute_engine_weight_fingerprint：聚合指纹确定性、内容敏感、无权重返回空
- register_weight_fingerprint：空缺填充、手工登记不覆盖、无权重 no-op
- build_model_card 联动：登记后 is_complete 的 sha256/version 字段非空
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from integrated_app.model_card import (
    build_model_card,
    compute_engine_weight_fingerprint,
    register_weight_fingerprint,
)


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="wfp_test_"))


def _mk_weights(root: Path, n: int = 2) -> Path:
    """构造 fake 权重树：<root>/model/{text_encoders,unet,vae}/*.safetensors"""
    base = root / "model"
    for sub in ("text_encoders", "unet", "vae"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    (base / "text_encoders" / "te.safetensors").write_bytes(b"TE-WEIGHTS" * 10)
    (base / "unet" / "unet.safetensors").write_bytes(b"UNET-WEIGHTS" * 10)
    for i in range(n):
        (base / "vae" / f"vae_{i}.safetensors").write_bytes(b"VAE" * 10)
    return base


class _Portable:
    internal_models_dir = "model"
    sub_dirs = {"lora": "loras"}


class _Models:
    portable = _Portable()


def test_fingerprint_deterministic_and_content_sensitive() -> None:
    root = _tmp()
    _mk_weights(root)
    fp1 = compute_engine_weight_fingerprint(_Models(), root)
    fp2 = compute_engine_weight_fingerprint(_Models(), root)
    assert fp1 and len(fp1) == 64
    assert fp1 == fp2, "内容不变指纹必须稳定"
    # 内容变化 → 指纹变化
    (root / "model" / "unet" / "unet.safetensors").write_bytes(b"TAMPERED" * 10)
    fp3 = compute_engine_weight_fingerprint(_Models(), root)
    assert fp3 != fp1, "权重被篡改后指纹必须改变"


def test_fingerprint_empty_when_no_weights() -> None:
    root = _tmp()
    assert compute_engine_weight_fingerprint(_Models(), root) == ""


def test_register_fills_empty_fields() -> None:
    root = _tmp()
    _mk_weights(root)
    ecfg = SimpleNamespace(
        name="e1",
        weight_sha256="",
        weight_version="",
        display_name="E1",
        backend="native",
        training_data_source="",
        license="",
        compatibility_matrix={},
        vram_gb=0.0,
    )
    fp = register_weight_fingerprint(ecfg, _Models(), root)
    assert fp == ecfg.weight_sha256
    assert ecfg.weight_version.startswith("auto-sha256:")
    assert len(ecfg.weight_version) == len("auto-sha256:") + 12


def test_register_respects_manual_values() -> None:
    root = _tmp()
    _mk_weights(root)
    ecfg = SimpleNamespace(
        name="e1",
        weight_sha256="manual",
        weight_version="v9",
        display_name="",
        backend="native",
        training_data_source="",
        license="",
        compatibility_matrix={},
        vram_gb=0.0,
    )
    register_weight_fingerprint(ecfg, _Models(), root)
    assert ecfg.weight_sha256 == "manual", "手工登记值不得被覆盖"
    assert ecfg.weight_version == "v9"


def test_fingerprint_file_cap_bounded() -> None:
    """成本护栏：文件数超上限不炸、不失控（启动期有界快速指纹）。"""
    root = _tmp()
    base = root / "model" / "vae"
    base.mkdir(parents=True, exist_ok=True)
    for i in range(250):  # > _MAX_FILES(200)
        (base / f"w_{i:03d}.safetensors").write_bytes(b"W" * 16)
    fp = compute_engine_weight_fingerprint(_Models(), root)
    assert fp and len(fp) == 64, "超限时应产出部分指纹而非失败"


def test_model_card_sees_registered_fingerprint() -> None:
    root = _tmp()
    _mk_weights(root)
    ecfg = SimpleNamespace(
        name="e1",
        weight_sha256="",
        weight_version="",
        display_name="E1",
        backend="native",
        training_data_source="synthetic",
        license="Apache-2.0",
        compatibility_matrix={},
        vram_gb=0.0,
    )
    register_weight_fingerprint(ecfg, _Models(), root)
    card = build_model_card(ecfg)
    assert card.weight_sha256
    assert card.weight_version
    assert "weight_sha256" not in card.missing_fields()
