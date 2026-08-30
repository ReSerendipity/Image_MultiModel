"""
workflow_schema.py — 工作流 JSON Schema 版本化与加载时校验（MLOps P2·治理）

对应审计反模式 #1（No workflow version control）与 #6（手动编辑破坏 schema）：
- 落地 JSON Schema 于 ``comfy/schemas/workflow_schema.json``（单一事实来源）
- 提供 ``validate_workflow`` / ``load_workflow_file`` 在加载时校验，拦截结构损坏
- ``schema_version`` 字段用于可复现性与向后兼容

校验器为自包含实现（不依赖 jsonschema 第三方库），保证离线 / CI 环境可单测。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "comfy" / "schemas" / "workflow_schema.json"


def _load_schema() -> dict[str, Any]:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


try:
    _SCHEMA = _load_schema()
    SCHEMA_VERSION: str = _SCHEMA["properties"]["schema_version"]["enum"][0]
    SUPPORTED_VERSIONS: list[str] = list(_SCHEMA["properties"]["schema_version"]["enum"])
except Exception as e:  # pragma: no cover - schema 文件缺失
    logger.error("Workflow schema 加载失败: %s", e)
    SCHEMA_VERSION = "1.0.0"
    SUPPORTED_VERSIONS = ["1.0.0"]


def validate_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    """校验工作流 dict 是否符合当前 schema。

    Returns:
        ``{"valid": bool, "errors": list[str], "schema_version": str}``
    """
    errors: list[str] = []
    if not isinstance(workflow, dict):
        return {"valid": False, "errors": ["workflow must be a JSON object"], "schema_version": ""}

    sv = workflow.get("schema_version")
    if not isinstance(sv, str):
        errors.append("missing or invalid 'schema_version' (string required)")
    elif sv not in SUPPORTED_VERSIONS:
        errors.append(f"unsupported schema_version '{sv}' (supported: {SUPPORTED_VERSIONS})")

    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        errors.append("missing or invalid 'nodes' (array required)")
    else:
        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(f"nodes[{i}] must be an object")
                continue
            if "id" not in node:
                errors.append(f"nodes[{i}] missing required field 'id'")
            elif not isinstance(node["id"], (str, int)):
                errors.append(f"nodes[{i}].id must be string or integer")
            if "type" not in node:
                errors.append(f"nodes[{i}] missing required field 'type'")
            elif not isinstance(node["type"], str):
                errors.append(f"nodes[{i}].type must be string")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "schema_version": sv if isinstance(sv, str) else "",
    }


def load_workflow_file(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """加载并校验工作流文件（加载时校验，反模式 #6 防护）。

    Args:
        path: 工作流 JSON 路径

    Returns:
        ``(workflow_dict, validation_result)``

    Raises:
        FileNotFoundError / json.JSONDecodeError: 文件读取/解析失败
    """
    p = Path(path)
    with open(p, encoding="utf-8") as f:
        workflow = json.load(f)
    result = validate_workflow(workflow)
    if not result["valid"]:
        logger.warning("工作流 %s 校验未通过: %s", p, result["errors"])
    return workflow, result


__all__ = [
    "SCHEMA_VERSION",
    "SUPPORTED_VERSIONS",
    "validate_workflow",
    "load_workflow_file",
]
