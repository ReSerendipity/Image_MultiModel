"""
tests/factories.py — 测试数据工厂

对应 N13: factory-boy 测试数据生成
使用工厂模式生成 GenerationConfig、Task 等测试数据
"""

from __future__ import annotations

import factory
from factory import Faker

from integrated_app.engine_interface import GenerationConfig
from integrated_app.task_queue import Task


class GenerationConfigFactory(factory.Factory):
    """GenerationConfig 工厂"""

    class Meta:
        model = GenerationConfig

    positive_prompt = Faker("sentence", nb_words=6)
    negative_prompt = ""
    cfg = 1.0
    steps = 8
    width = 1024
    height = 1024
    seed = -1
    batch_size = 1
    lora_1_name = ""
    lora_1_strength = 1.0
    lora_2_name = ""
    lora_2_strength = 0.7
    lora_3_name = ""
    lora_3_strength = 0.5
    lora_4_name = ""
    lora_4_strength = 0.4
    lora_5_name = ""
    lora_5_strength = 0.3
    lora_6_name = ""
    lora_6_strength = 0.2
    seedvr2_enable = False
    seedvr2_resolution = 2048
    seedvr2_seed = -1
    seedvr2_color_correction = "lab"
    eses_enable = False
    eses_compare_axis = "horizontal"
    vram_enable = False
    vram_reserved_gb = 0.6
    vram_mode = "auto"
    vram_seed = -1
    output_format = "png"
    output_prefix = "{engine}"
    engine_name = "z_image_turbo_native"


class LargeBatchConfigFactory(GenerationConfigFactory):
    """大 batch 配置工厂"""

    batch_size = 16
    seedvr2_enable = False


class SeedVR2ConfigFactory(GenerationConfigFactory):
    """开超分配置工厂"""

    seedvr2_enable = True
    seedvr2_resolution = 2048
    eses_enable = True
    vram_enable = True


class TaskFactory(factory.Factory):
    """Task 工厂"""

    class Meta:
        model = Task

    task_id = factory.Sequence(lambda n: f"factory-task-{n:04d}")
    engine = "z_image_turbo_native"
    config = factory.LazyAttribute(lambda obj: GenerationConfigFactory().to_dict())
    mode = "txt2img"


# ── 扩展工厂（对应测试体系评估 P3-10：原仅 2 个工厂，覆盖不足）────────
class PresetFactory(factory.Factory):
    """预设（preset）工厂：生成可落库/可序列化的预设 dict。"""

    class Meta:
        model = dict

    name = factory.Sequence(lambda n: f"preset-{n:03d}")
    positive_prompt = Faker("sentence", nb_words=6)
    negative_prompt = ""
    cfg = 1.0
    steps = 8
    width = 1024
    height = 1024
    seed = -1
    batch_size = 1
    engine_name = "z_image_turbo_native"


class LoraFactory(factory.Factory):
    """LoRA 条目工厂：生成 {name, path, strength}。"""

    class Meta:
        model = dict

    name = factory.Sequence(lambda n: f"lora-{n:03d}")
    path = factory.Sequence(lambda n: f"models/loras/lora_{n:03d}.safetensors")
    strength = 0.8


class EngineConfigFactory(factory.Factory):
    """引擎配置工厂：生成引擎 config dict（对齐 config_models.EngineConfig）。"""

    class Meta:
        model = dict

    name = "z_image_turbo_native"
    display_name = "Z-Image Turbo"
    display_name_en = "Z-Image Turbo"
    backend = "native"
    vram_gb = 18.0


class HistoryTaskDataFactory(factory.Factory):
    """历史任务数据工厂：生成 HistoryDB.create_task 所需的 kwargs dict。"""

    class Meta:
        model = dict

    task_id = factory.Sequence(lambda n: f"hist-{n:04d}")
    engine = "z_image_turbo_native"
    prompt = Faker("sentence", nb_words=8)
    status = "completed"
    batch_size = 1
