"""
test_model_card.py — 权重级 Model Card / 元数据注册表（MLOps P2·治理）单测
"""

from __future__ import annotations

from integrated_app.config_models import EngineConfig
from integrated_app.model_card import (
    ModelCard,
    audit_registry,
    build_model_card,
    build_registry,
)


def _engine(**over) -> EngineConfig:
    base = dict(
        name="z_image_turbo_native",
        display_name="Z-Image Turbo",
        backend="native",
        vram_gb=16.0,
    )
    base.update(over)
    return EngineConfig(**base)


def test_build_model_card_from_engine() -> None:
    ecfg = _engine(
        weight_sha256="abc123",
        weight_version="1.2.0",
        training_data_source="internal-curated-v1",
        compatibility_matrix={"lora": ["v1", "v2"]},
        license="Apache-2.0",
    )
    card = build_model_card(ecfg)
    assert isinstance(card, ModelCard)
    assert card.name == "z_image_turbo_native"
    assert card.weight_sha256 == "abc123"
    assert card.compatibility_matrix == {"lora": ["v1", "v2"]}
    assert card.is_complete() is True


def test_model_card_incomplete_when_missing_metadata() -> None:
    ecfg = _engine()  # 无治理元数据
    card = build_model_card(ecfg)
    assert card.is_complete() is False
    assert set(card.missing_fields()) == {"weight_sha256", "weight_version", "training_data_source"}


def test_engine_config_accepts_new_fields() -> None:
    # 验证 config_models 扩展字段可被 pydantic 正确解析
    ecfg = _engine(weight_sha256="deadbeef", weight_version="2.0.0", training_data_source="x")
    assert ecfg.weight_sha256 == "deadbeef"
    assert ecfg.weight_version == "2.0.0"


def test_build_registry_and_audit() -> None:
    class FakeModels:
        engines = {
            "complete": _engine(
                weight_sha256="s1", weight_version="1.0.0", training_data_source="src"
            ),
            "incomplete": _engine(),
        }

    registry = build_registry(FakeModels())
    assert set(registry.keys()) == {"complete", "incomplete"}
    report = audit_registry(registry)
    assert report["total"] == 2
    assert report["complete"] == 1
    assert report["incomplete"] == 1
    assert "incomplete" in report["details"]


def test_model_card_to_dict_roundtrip() -> None:
    card = ModelCard(
        name="x", weight_sha256="h", weight_version="1.0.0", training_data_source="s"
    )
    d = card.to_dict()
    assert d["name"] == "x"
    assert d["weight_sha256"] == "h"
    assert card.is_complete() is True
