"""
workflow_governance.py — 配置化 workflow 文件的启动期准入校验（数据治理 §4.4 / 中期 Schema 治理）

将 ``workflow_schema.validate_workflow`` 接入「加载链路」：在应用启动时对每个引擎
声明的 ``workflow_file`` 做存在性 + JSON 可解析 + schema_version 校验。

注意：原生引擎（native）在代码中构建推理图，并不直接读取 workflow 文件的节点结构；
此处校验的目标是「治理准入」——拦截缺失/损坏文件、强制 workflow 携带版本指纹，
而非替代引擎内部构图。缺 ``schema_version`` 仅告警（不阻断启动），以保证既有
ComfyUI API 格式文件平滑兼容。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .workflow_schema import validate_workflow

logger = logging.getLogger(__name__)


def validate_configured_workflows(config: Any) -> list[dict[str, Any]]:
    """校验所有引擎配置的 workflow 文件。

    Args:
        config: AppConfig 实例。

    Returns:
        每引擎一条 ``{"engine", "workflow_file", "ok", "errors", "warnings"}``。
        ``ok=False`` 表示文件缺失或 JSON 损坏或 schema_version 不被支持（应上线前修复）。
    """
    results: list[dict[str, Any]] = []
    for name, ecfg in config.models.engines.items():
        wf = getattr(ecfg, "workflow_file", "") or ""
        if not wf:
            continue
        p = Path(config.project_root) / wf
        rec: dict[str, Any] = {
            "engine": name,
            "workflow_file": wf,
            "ok": True,
            "errors": [],
            "warnings": [],
        }
        if not p.exists():
            rec["ok"] = False
            rec["errors"].append(f"workflow file missing: {p}")
            results.append(rec)
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            rec["ok"] = False
            rec["errors"].append(f"workflow JSON parse failed: {e}")
            results.append(rec)
            continue

        sv = data.get("schema_version")
        if not sv:
            rec["warnings"].append(
                "workflow has no 'schema_version' field (not version-controlled; "
                "add \"schema_version\": \"1.0.0\" for reproducible lineage)"
            )
        else:
            vr = validate_workflow(data)
            if not vr["valid"]:
                rec["ok"] = False
                rec["errors"].extend(vr["errors"])
        results.append(rec)
    return results
