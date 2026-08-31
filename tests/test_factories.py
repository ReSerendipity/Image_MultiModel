"""
tests/test_factories.py — 测试数据工厂自检（对应测试体系评估 P3-10）

验证扩展后的工厂可正确构建对象 / dict，避免「工厂仅 2 个、覆盖不足」的回归。
"""

from __future__ import annotations

from factories import (
    EngineConfigFactory,
    GenerationConfigFactory,
    HistoryTaskDataFactory,
    LoraFactory,
    PresetFactory,
    TaskFactory,
)

from integrated_app.engine_interface import GenerationConfig


def test_generation_config_factory() -> None:
    cfg = GenerationConfigFactory()
    assert isinstance(cfg, GenerationConfig)
    assert cfg.engine_name == "z_image_turbo_native"
    assert cfg.batch_size == 1


def test_large_batch_factory() -> None:
    from factories import LargeBatchConfigFactory

    cfg = LargeBatchConfigFactory()
    assert cfg.batch_size == 16


def test_task_factory() -> None:
    t = TaskFactory()
    assert t.task_id.startswith("factory-task-")
    assert t.engine == "z_image_turbo_native"
    assert isinstance(t.config, dict)


def test_preset_factory() -> None:
    p = PresetFactory()
    assert isinstance(p, dict)
    assert "positive_prompt" in p
    assert PresetFactory()["name"] != p["name"]  # Sequence 唯一


def test_lora_factory() -> None:
    lora = LoraFactory()
    assert isinstance(lora, dict)
    assert lora["path"].endswith(".safetensors")
    assert 0.0 <= lora["strength"] <= 1.0


def test_engine_config_factory() -> None:
    e = EngineConfigFactory()
    assert isinstance(e, dict)
    assert e["backend"] == "native"
    assert e["vram_gb"] > 0


def test_history_task_data_factory() -> None:
    h = HistoryTaskDataFactory()
    assert isinstance(h, dict)
    assert h["task_id"].startswith("hist-")
    assert h["status"] == "completed"
