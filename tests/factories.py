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
    engine_name = "flux2_klein_9b_distilled"


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
