"""
test_workflow_schema.py — 工作流 Schema 版本化与加载校验（MLOps P2·治理）单测
"""

from __future__ import annotations

import json

import pytest

from integrated_app import workflow_schema as ws


VALID_WORKFLOW = {
    "schema_version": "1.0.0",
    "name": "smoke",
    "nodes": [
        {"id": 1, "type": "CLIPTextEncode", "inputs": {"text": "a cat"}},
        {"id": "2", "type": "KSampler"},
    ],
    "edges": [{"from": 1, "to": "2"}],
}


def test_schema_version_constant() -> None:
    assert ws.SCHEMA_VERSION == "1.0.0"
    assert "1.0.0" in ws.SUPPORTED_VERSIONS


def test_validate_valid_workflow() -> None:
    res = ws.validate_workflow(VALID_WORKFLOW)
    assert res["valid"] is True
    assert res["errors"] == []
    assert res["schema_version"] == "1.0.0"


def test_validate_missing_schema_version() -> None:
    wf = {"nodes": [{"id": 1, "type": "X"}]}
    res = ws.validate_workflow(wf)
    assert res["valid"] is False
    assert any("schema_version" in e for e in res["errors"])


def test_validate_unsupported_version() -> None:
    wf = {"schema_version": "9.9.9", "nodes": [{"id": 1, "type": "X"}]}
    res = ws.validate_workflow(wf)
    assert res["valid"] is False
    assert any("unsupported schema_version" in e for e in res["errors"])


def test_validate_missing_nodes() -> None:
    wf = {"schema_version": "1.0.0"}
    res = ws.validate_workflow(wf)
    assert res["valid"] is False
    assert any("nodes" in e for e in res["errors"])


def test_validate_node_missing_fields() -> None:
    wf = {"schema_version": "1.0.0", "nodes": [{"id": 1}, {"type": "X"}]}
    res = ws.validate_workflow(wf)
    assert res["valid"] is False
    assert any("nodes[0]" in e and "type" in e for e in res["errors"])
    assert any("nodes[1]" in e and "id" in e for e in res["errors"])


def test_load_workflow_file_valid(tmp_path) -> None:
    p = tmp_path / "wf.json"
    p.write_text(json.dumps(VALID_WORKFLOW), encoding="utf-8")
    wf, res = ws.load_workflow_file(p)
    assert wf["name"] == "smoke"
    assert res["valid"] is True


def test_load_workflow_file_invalid(tmp_path) -> None:
    bad = {"nodes": [{"type": "X"}]}  # 缺 schema_version
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    _wf, res = ws.load_workflow_file(p)
    assert res["valid"] is False
