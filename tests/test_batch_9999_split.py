"""
test_batch_9999_split.py — Mock batch=9999 → chunk=16/4 拆分次数正确

对应 AUDIT_REPORT_2.0 Y2: test_batch_9999_split.py
"""

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
    wf_path = PROJECT_ROOT / "workflows" / "Flux.2_Klein-9B-Distilled.json"
    schema_path = PROJECT_ROOT / "bin/integrated_app/comfy/schemas/flux2_klein_9b_distilled.yaml"
    return WorkflowManager(
        workflow_path=str(wf_path),
        schema_path=str(schema_path),
        project_root=str(PROJECT_ROOT),
    )


class TestBatchSplit:
    """batch=9999 拆分测试"""

    def test_batch_9999_no_seedvr2_chunk_16(self, flux_workflow):
        """batch=9999, 不开超分 → chunk=16 → 625 次提交"""
        config = GenerationConfig(batch_size=9999, seedvr2_enable=False)
        wf = flux_workflow.patch(config)
        chunk_count = flux_workflow.get_chunk_count(config)
        assert chunk_count == 625, f"Expected 625 chunks (9999/16), got {chunk_count}"
        # 验证 batch_size 被设为 chunk_size
        all_nodes = flux_workflow._get_all_nodes(wf)
        for node in all_nodes:
            if node.get("type") in ("EmptyFlux2LatentImage", "EmptySD3LatentImage"):
                wv = node.get("widgets_values", [])
                assert wv[2] == 16, f"batch_size should be chunk=16, got {wv[2]}"

    def test_batch_9999_with_seedvr2_chunk_4(self, flux_workflow):
        """batch=9999, 开超分 → chunk=4 → 2500 次提交"""
        config = GenerationConfig(batch_size=9999, seedvr2_enable=True)
        wf = flux_workflow.patch(config)
        chunk_count = flux_workflow.get_chunk_count(config)
        assert chunk_count == 2500, f"Expected 2500 chunks (9999/4), got {chunk_count}"

    def test_batch_1_no_split(self, flux_workflow):
        """batch=1 → 1 次提交"""
        config = GenerationConfig(batch_size=1, seedvr2_enable=False)
        chunk_count = flux_workflow.get_chunk_count(config)
        assert chunk_count == 1

    def test_batch_16_boundary(self, flux_workflow):
        """batch=16 → 1 次提交（正好 1 chunk）"""
        config = GenerationConfig(batch_size=16, seedvr2_enable=False)
        chunk_count = flux_workflow.get_chunk_count(config)
        assert chunk_count == 1

    def test_batch_17_boundary(self, flux_workflow):
        """batch=17 → 2 次提交（1 chunk=16 + 1 余）"""
        config = GenerationConfig(batch_size=17, seedvr2_enable=False)
        chunk_count = flux_workflow.get_chunk_count(config)
        assert chunk_count == 2

    def test_batch_100_with_seedvr2(self, flux_workflow):
        """batch=100, 开超分 → chunk=4 → 25 次提交"""
        config = GenerationConfig(batch_size=100, seedvr2_enable=True)
        chunk_count = flux_workflow.get_chunk_count(config)
        assert chunk_count == 25, f"Expected 25 chunks (100/4), got {chunk_count}"

    def test_chunk_recommendation_rules(self):
        """chunk 推荐规则: 不开超分=16, 开超分=4"""
        assert recommend_chunk_size(100, enable_seedvr2=False) == 16
        assert recommend_chunk_size(100, enable_seedvr2=True) == 4
        assert recommend_chunk_size(3, enable_seedvr2=False) == 3  # 小 batch
        assert recommend_chunk_size(3, enable_seedvr2=True) == 3

    def test_all_chunks_cover_full_batch(self, flux_workflow):
        """所有 chunk 之和 == batch_size"""
        for batch_size in [1, 5, 16, 17, 100, 9999]:
            for sv2 in [True, False]:
                config = GenerationConfig(batch_size=batch_size, seedvr2_enable=sv2)
                chunk_size = recommend_chunk_size(batch_size, sv2)
                chunk_count = flux_workflow.get_chunk_count(config)
                # 最后一个 chunk 的大小
                last_chunk = batch_size - (chunk_count - 1) * chunk_size
                assert 1 <= last_chunk <= chunk_size, \
                    f"batch={batch_size} sv2={sv2}: last_chunk={last_chunk} out of range"
                assert (chunk_count - 1) * chunk_size + last_chunk == batch_size, \
                    f"Chunks don't cover full batch: {(chunk_count-1)*chunk_size + last_chunk} != {batch_size}"
