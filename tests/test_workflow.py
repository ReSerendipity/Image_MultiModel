"""
test_workflow.py — Workflow Patcher 6 步 + batch 拆分测试

对应 MASTER_PLAN M1 验收: Mock batch=9999 拆分 + Patcher 快照
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

from integrated_app.comfy.workflow import WorkflowManager
from integrated_app.engine_interface import GenerationConfig
from integrated_app.gpu_utils import recommend_chunk_size


@pytest.fixture
def flux_workflow():
    """FLUX.2 Klein 工作流管理器"""
    wf_path = PROJECT_ROOT / "workflows" / "Flux.2_Klein-9B-Distilled.json"
    schema_path = PROJECT_ROOT / "bin/integrated_app/comfy/schemas/flux2_klein_9b_distilled.yaml"
    return WorkflowManager(
        workflow_path=str(wf_path),
        schema_path=str(schema_path),
        project_root=str(PROJECT_ROOT),
    )


@pytest.fixture
def z_workflow():
    """Z-Image Turbo 工作流管理器"""
    wf_path = PROJECT_ROOT / "workflows" / "Z_image_turbo.json"
    schema_path = PROJECT_ROOT / "bin/integrated_app/comfy/schemas/z_image_turbo.yaml"
    return WorkflowManager(
        workflow_path=str(wf_path),
        schema_path=str(schema_path),
        project_root=str(PROJECT_ROOT),
    )


class TestWorkflowLoading:
    """测试工作流加载"""

    def test_flux_workflow_loaded(self, flux_workflow):
        """FLUX 工作流成功加载"""
        assert flux_workflow._workflow_data is not None
        assert flux_workflow.workflow_sha256 != ""

    def test_z_workflow_loaded(self, z_workflow):
        """Z-Image 工作流成功加载"""
        assert z_workflow._workflow_data is not None
        assert z_workflow.workflow_sha256 != ""

    def test_flux_has_lora_nodes(self, flux_workflow):
        """FLUX 工作流包含 6 个 LoRA 节点"""
        all_nodes = flux_workflow._get_all_nodes(flux_workflow._workflow_data)
        lora_nodes = [n for n in all_nodes if n.get("type") == "LoraLoaderModelOnly"]
        assert len(lora_nodes) == 6, "Expected 6 LoraLoaderModelOnly nodes"

    def test_z_has_lora_nodes(self, z_workflow):
        """Z-Image 工作流包含 6 个 LoRA 节点"""
        all_nodes = z_workflow._get_all_nodes(z_workflow._workflow_data)
        lora_nodes = [n for n in all_nodes if n.get("type") == "LoraLoaderModelOnly"]
        assert len(lora_nodes) == 6, "Expected 6 LoraLoaderModelOnly nodes"


class TestPatcher:
    """测试 Patcher 6 步"""

    def test_patch_basic(self, flux_workflow):
        """基本 patch：参数正确注入"""
        config = GenerationConfig(
            positive_prompt="test positive",
            negative_prompt="test negative",
            cfg=1.5,
            steps=10,
            width=768,
            height=768,
            seed=12345,
            batch_size=1,
        )
        wf = flux_workflow.patch(config)

        assert wf is not None
        assert "nodes" in wf

    def test_lora_mode_fixed(self, flux_workflow):
        """LoRA mode=4 → 0（提交前强制改 0）"""
        config = GenerationConfig()
        wf = flux_workflow.patch(config)

        all_nodes = flux_workflow._get_all_nodes(wf)
        for node in all_nodes:
            if node.get("type") == "LoraLoaderModelOnly":
                assert node.get("mode") == 0, f"LoRA node {node.get('id')} mode should be 0, got {node.get('mode')}"

    def test_seedvr2_disable_bypass(self, flux_workflow):
        """关闭 SeedVR2 时节点被 bypass"""
        config = GenerationConfig(seedvr2_enable=False)
        wf = flux_workflow.patch(config)

        all_nodes = flux_workflow._get_all_nodes(wf)
        for node in all_nodes:
            if node.get("type") in ("SeedVR2LoadVAEModel", "SeedVR2VideoUpscaler", "SeedVR2LoadDiTModel"):
                assert node.get("mode") == 4, f"SeedVR2 node should be bypassed (mode=4)"

    def test_eses_disable_bypass(self, flux_workflow):
        """关闭 Eses 时节点被 bypass"""
        config = GenerationConfig(eses_enable=False)
        wf = flux_workflow.patch(config)

        all_nodes = flux_workflow._get_all_nodes(wf)
        for node in all_nodes:
            if node.get("type") == "EsesImageCompare":
                assert node.get("mode") == 4, f"Eses node should be bypassed"

    def test_vram_disable_bypass(self, flux_workflow):
        """关闭 VRAM 时节点被 bypass"""
        config = GenerationConfig(vram_enable=False)
        wf = flux_workflow.patch(config)

        all_nodes = flux_workflow._get_all_nodes(wf)
        for node in all_nodes:
            if node.get("type") == "ReservedVRAMSetter":
                assert node.get("mode") == 4, f"VRAM node should be bypassed"

    def test_seed_resolved_when_negative_one(self, flux_workflow):
        """seed=-1 时生成实际值"""
        config = GenerationConfig(seed=-1, seedvr2_seed=-1, vram_seed=-1)
        flux_workflow.patch(config)

        assert config.seed > 0, "seed should be resolved to positive value"
        assert config.seedvr2_seed > 0, "seedvr2_seed should be resolved"
        assert config.vram_seed > 0, "vram_seed should be resolved"

    def test_width_height_synced(self, flux_workflow):
        """width/height 在 EmptyLatent + Scheduler 双节点同步"""
        config = GenerationConfig(width=512, height=768)
        wf = flux_workflow.patch(config)

        all_nodes = flux_workflow._get_all_nodes(wf)
        for node in all_nodes:
            ntype = node.get("type", "")
            wv = node.get("widgets_values", [])
            if ntype in ("EmptyFlux2LatentImage", "EmptySD3LatentImage") and len(wv) >= 2:
                assert wv[0] == 512, f"Width not synced in {ntype}: {wv[0]}"
                assert wv[1] == 768, f"Height not synced in {ntype}: {wv[1]}"
            if ntype == "Flux2Scheduler" and len(wv) >= 3:
                assert wv[1] == 512, f"Width not synced in Flux2Scheduler: {wv[1]}"
                assert wv[2] == 768, f"Height not synced in Flux2Scheduler: {wv[2]}"

    def test_lora_strength_patched(self, flux_workflow):
        """LoRA 强度正确 patch"""
        config = GenerationConfig(
            lora_1_strength=0.9,
            lora_2_strength=0.6,
            lora_3_strength=0.4,
            lora_4_strength=0.3,
            lora_5_strength=0.2,
            lora_6_strength=0.1,
        )
        wf = flux_workflow.patch(config)

        all_nodes = flux_workflow._get_all_nodes(wf)
        lora_nodes = sorted(
            [n for n in all_nodes if n.get("type") == "LoraLoaderModelOnly"],
            key=lambda n: n.get("id", 0),
        )
        expected_strengths = [0.9, 0.6, 0.4, 0.3, 0.2, 0.1]
        for i, node in enumerate(lora_nodes):
            wv = node.get("widgets_values", [])
            assert wv[1] == expected_strengths[i], f"LoRA layer {i+1} strength mismatch: {wv[1]} != {expected_strengths[i]}"

    def test_z_workflow_patch(self, z_workflow):
        """Z-Image 工作流 patch"""
        config = GenerationConfig(
            positive_prompt="z test",
            cfg=1.0,
            steps=8,
            width=1024,
            height=1024,
            seed=99999,
        )
        wf = z_workflow.patch(config)
        assert wf is not None


class TestBatchChunk:
    """测试 batch chunk 拆分"""

    def test_chunk_size_no_seedvr2(self):
        """不开超分：chunk=16"""
        chunk = recommend_chunk_size(100, enable_seedvr2=False)
        assert chunk == 16

    def test_chunk_size_with_seedvr2(self):
        """开超分：chunk=4"""
        chunk = recommend_chunk_size(100, enable_seedvr2=True)
        assert chunk == 4

    def test_chunk_size_small_batch(self):
        """小 batch：chunk = batch_size"""
        chunk = recommend_chunk_size(3, enable_seedvr2=False)
        assert chunk == 3

    def test_batch_9999_chunk_count(self, flux_workflow):
        """batch=9999 拆分成正确的 chunk 数"""
        # 不开超分
        config = GenerationConfig(batch_size=9999, seedvr2_enable=False)
        flux_workflow.patch(config)
        chunk_count = flux_workflow.get_chunk_count(config)
        assert chunk_count == 625, f"Expected 625 chunks for batch=9999 (chunk=16), got {chunk_count}"

        # 开超分
        config2 = GenerationConfig(batch_size=9999, seedvr2_enable=True)
        flux_workflow.patch(config2)
        chunk_count2 = flux_workflow.get_chunk_count(config2)
        assert chunk_count2 == 2500, f"Expected 2500 chunks for batch=9999 with SeedVR2 (chunk=4), got {chunk_count2}"

    def test_batch_chunk_batch_size_set(self, flux_workflow):
        """batch chunk 拆分后 batch_size 被正确设置"""
        config = GenerationConfig(batch_size=32, seedvr2_enable=False)
        wf = flux_workflow.patch(config)

        all_nodes = flux_workflow._get_all_nodes(wf)
        for node in all_nodes:
            ntype = node.get("type", "")
            wv = node.get("widgets_values", [])
            if ntype in ("EmptyFlux2LatentImage", "EmptySD3LatentImage") and len(wv) >= 3:
                assert wv[2] == 16, f"batch_size should be chunk size 16, got {wv[2]}"
