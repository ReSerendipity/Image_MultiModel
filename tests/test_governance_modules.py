"""
test_governance_modules.py — 数据治理评估落地（中期/长期）模块验证

覆盖：
- workflow_governance.validate_configured_workflows（启动期准入校验）
- metrics_quality.compute_quality_metrics（业务指标单一聚合）
- model_compat.validate_compatibility_matrix / is_lora_compatible（兼容性矩阵消费）
- native.preview.assess_image_quality（基础质量/artifact 检测）
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from integrated_app.history_db import HistoryDB
from integrated_app.metrics_quality import compute_quality_metrics
from integrated_app.model_compat import is_lora_compatible, validate_compatibility_matrix
from integrated_app.native.preview import assess_image_quality
from integrated_app.workflow_governance import validate_configured_workflows


# ── workflow_governance ──────────────────────────────────────────────
class _Engine:
    def __init__(self, workflow_file: str, name: str = "eng") -> None:
        self.workflow_file = workflow_file
        self.name = name


class _Models:
    def __init__(self, engines: dict) -> None:
        self.engines = engines


class _Cfg:
    def __init__(self, engines: dict, root: Path) -> None:
        self.models = _Models(engines)
        self.project_root = root


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="gov_mod_"))


def test_workflow_governance_valid_and_missing() -> None:
    d = _tmp()
    good = d / "good.json"
    good.write_text(json.dumps({"schema_version": "1.0.0", "nodes": [{"id": 1, "type": "X"}]}), encoding="utf-8")
    bad = d / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")

    cfg = _Cfg(
        {
            "ok_engine": _Engine("good.json", "ok_engine"),
            "missing_engine": _Engine("nope.json", "missing_engine"),
            "corrupt_engine": _Engine("bad.json", "corrupt_engine"),
        },
        d,
    )
    results = {r["engine"]: r for r in validate_configured_workflows(cfg)}
    assert results["ok_engine"]["ok"] is True
    assert results["missing_engine"]["ok"] is False
    assert any("missing" in e for e in results["missing_engine"]["errors"])
    assert results["corrupt_engine"]["ok"] is False
    assert any("parse" in e for e in results["corrupt_engine"]["errors"])


def test_workflow_governance_no_version_warns_only() -> None:
    d = _tmp()
    nov = d / "nov.json"
    nov.write_text(json.dumps({"nodes": [{"id": 1, "type": "X"}]}), encoding="utf-8")
    cfg = _Cfg({"e": _Engine("nov.json", "e")}, d)
    res = validate_configured_workflows(cfg)
    assert res[0]["ok"] is True
    assert any("schema_version" in w for w in res[0]["warnings"])


# ── metrics_quality ─────────────────────────────────────────────────
def test_compute_quality_metrics() -> None:
    d = _tmp()
    db = HistoryDB(d / "history.db")
    db.create_task("t1", "eng", generation_config={"seed": 1}, lora_checksums=[{"name": "lora_a", "strength": 0.7, "sha256": "x"}])
    db.update_task_status("t1", "completed", processing_time_s=2.0)
    db.create_task("t2", "eng", lora_checksums=[{"name": "lora_a", "strength": 0.5, "sha256": "y"}])
    db.update_task_status("t2", "completed", processing_time_s=4.0)
    db.create_task("t3", "eng", lora_checksums=[{"name": "lora_b", "strength": 1.0, "sha256": "z"}])
    db.update_task_status("t3", "failed", error="oom", error_code="OOM_VRAM")

    m = compute_quality_metrics(db)
    assert m["total_attempts"] == 3
    assert m["successful_generations"] == 2
    assert m["failed_generations"] == 1
    assert abs(m["success_rate"] - 2 / 3) < 1e-9
    assert abs(m["avg_generation_time_s"] - 3.0) < 1e-9
    assert m["lora_usage_frequency"] == {"lora_a": 2, "lora_b": 1}
    db.close()


# ── model_compat ────────────────────────────────────────────────────
def test_validate_compatibility_matrix() -> None:
    class E:
        name = "z"
        compatibility_matrix = {"lora_a": "not-a-list"}

    errs = validate_compatibility_matrix(E())
    assert errs  # 结构非法

    E.compatibility_matrix = {"lora_a": ["z", "other"]}
    assert validate_compatibility_matrix(E()) == []


def test_is_lora_compatible() -> None:
    class E:
        name = "z"
        compatibility_matrix = {"lora_a": ["z"], "lora_b": ["other_engine"]}

    assert is_lora_compatible(E(), "lora_a") is True
    assert is_lora_compatible(E(), "lora_b") is False
    assert is_lora_compatible(E(), "undeclared") is True  # 未声明默认兼容


# ── preview.assess_image_quality ────────────────────────────────────
def test_assess_image_quality_flags() -> None:
    assert assess_image_quality(np.zeros((100, 100, 3), dtype="uint8"))["all_black"] is True
    assert assess_image_quality(np.full((100, 100, 3), 255, dtype="uint8"))["all_white"] is True
    gray = np.full((100, 100, 3), 128, dtype="uint8")
    flags = assess_image_quality(gray)
    assert flags["low_contrast"] and flags["uniform"]
    normal = (np.random.rand(100, 100, 3) * 255).astype("uint8")
    nf = assess_image_quality(normal)
    assert not any(nf.values())
    assert assess_image_quality(np.zeros((32, 32, 3), dtype="uint8"))["tiny"] is True
