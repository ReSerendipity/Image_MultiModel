"""
test_comfy_patcher_snapshot.py — 4 大开关 on/off 组合快照比对

对应 AUDIT_REPORT_2.0 Y2: test_comfy_patcher_snapshot.py
4 大开关: LoRA / SeedVR2 / Eses / VRAM on/off → patch 后 JSON 快照比对
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from integrated_app.comfy.workflow import WorkflowManager
from integrated_app.engine_interface import GenerationConfig


@pytest.fixture
def flux_workflow():
    wf_path = PROJECT_ROOT / "workflows" / "Flux.2_Klein-9B-Distilled.json"
    schema_path = PROJECT_ROOT / "bin/integrated_app/comfy/schemas/flux2_klein_9b_distilled.yaml"
    return WorkflowManager(
        workflow_path=str(wf_path),
        schema_path=str(schema_path),
        project_root=str(PROJECT_ROOT),
    )


def get_node_mode(wf, node_type):
    """获取指定类型节点的 mode 值列表"""
    all_nodes = flux_workflow_all_nodes(wf)
    return [n.get("mode", 0) for n in all_nodes if n.get("type") == node_type]


def flux_workflow_all_nodes(wf):
    """获取工作流中的所有节点"""
    nodes = list(wf.get("nodes", []))
    for sub in wf.get("definitions", {}).get("subgraphs", []):
        nodes.extend(sub.get("nodes", []))
    return nodes


class TestPatcherSnapshot:
    """4 大开关 on/off 组合快照比对"""

    @pytest.mark.parametrize("seedvr2,eses,vram", [
        (True,  True,  True),   # 全开
        (False, True,  True),   # 关 SeedVR2
        (True,  False, True),   # 关 Eses
        (True,  True,  False),  # 关 VRAM
        (False, False, False),  # 全关
    ])
    def test_switch_combinations(self, flux_workflow, seedvr2, eses, vram):
        """4 大开关 on/off 组合 → patch 后验证节点 mode"""
        config = GenerationConfig(
            seedvr2_enable=seedvr2,
            eses_enable=eses,
            vram_enable=vram,
        )
        wf = flux_workflow.patch(config)
        all_nodes = flux_workflow_all_nodes(wf)

        # SeedVR2 节点
        seedvr2_types = ("SeedVR2LoadVAEModel", "SeedVR2VideoUpscaler", "SeedVR2LoadDiTModel")
        for node in all_nodes:
            if node.get("type") in seedvr2_types:
                expected_mode = 0 if seedvr2 else 4
                assert node.get("mode") == expected_mode, \
                    f"SeedVR2 node {node.get('id')} mode={node.get('mode')}, expected {expected_mode}"

        # Eses 节点
        for node in all_nodes:
            if node.get("type") == "EsesImageCompare":
                expected_mode = 0 if eses else 4
                assert node.get("mode") == expected_mode, \
                    f"Eses node mode={node.get('mode')}, expected {expected_mode}"

        # VRAM 节点
        for node in all_nodes:
            if node.get("type") == "ReservedVRAMSetter":
                expected_mode = 0 if vram else 4
                assert node.get("mode") == expected_mode, \
                    f"VRAM node mode={node.get('mode')}, expected {expected_mode}"

    def test_lora_always_mode_0(self, flux_workflow):
        """LoRA 节点无论开关组合如何，mode 始终为 0（提交前强制）"""
        for seedvr2 in [True, False]:
            for eses in [True, False]:
                config = GenerationConfig(seedvr2_enable=seedvr2, eses_enable=eses)
                wf = flux_workflow.patch(config)
                all_nodes = flux_workflow_all_nodes(wf)
                for node in all_nodes:
                    if node.get("type") == "LoraLoaderModelOnly":
                        assert node.get("mode") == 0, \
                            f"LoRA node {node.get('id')} mode should always be 0"

    def test_workflow_integrity_after_patch(self, flux_workflow):
        """patch 后工作流结构完整：nodes/links/definitions 都存在"""
        config = GenerationConfig()
        wf = flux_workflow.patch(config)
        assert "nodes" in wf
        assert "links" in wf
        assert "definitions" in wf
        assert len(wf["nodes"]) > 0

    def test_seed_persistence(self, flux_workflow):
        """相同 seed → patch 后 RandomNoise 的 seed 一致"""
        config1 = GenerationConfig(seed=12345)
        wf1 = flux_workflow.patch(config1)
        nodes1 = flux_workflow_all_nodes(wf1)

        config2 = GenerationConfig(seed=12345)
        wf2 = flux_workflow.patch(config2)
        nodes2 = flux_workflow_all_nodes(wf2)

        for n1, n2 in zip(nodes1, nodes2):
            if n1.get("type") == "RandomNoise" and n2.get("type") == "RandomNoise":
                wv1 = n1.get("widgets_values", [])
                wv2 = n2.get("widgets_values", [])
                assert wv1[0] == wv2[0], "Seed not persistent across patches"
