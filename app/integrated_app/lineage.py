"""
lineage.py — 生成血缘辅助（数据治理：workflow 版本 + LoRA 权重 checksum + 错误分类）

提供轻量、无 GPU 依赖的辅助函数，用于在任务创建时记录可追溯元数据：
- ``compute_workflow_version``：对引擎 workflow 文件内容求 sha256（带 mtime 缓存），
  作为该 workflow 的不可变版本指纹（原 workflow JSON 无内置版本字段时的补偿手段）。
- ``compute_lora_checksums``：对 generation_config 中的 LoRA 栈逐层求权重 sha256，
  落库后即使 DB 损坏也能凭 image 的 task_id 反查权重指纹。
- ``classify_error``：把 worker 异常归类为一个稳定 error_code，便于 FAILED 记录聚类。

对应数据治理评估报告 §3.3（血缘）/ §4.1（脏数据 error_code）。
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    """对文件求 sha256（分块读取，避免大权重占内存）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_WORKFLOW_HASH_CACHE: dict[str, tuple[float, str]] = {}


def compute_workflow_version(engine_cfg: Any, project_root: str | Path) -> str:
    """计算引擎 workflow 文件的内容指纹作为版本标识。

    Args:
        engine_cfg: 引擎配置（含 ``workflow_file`` 字段）。
        project_root: 项目根目录，用于拼接 workflow 绝对路径。

    Returns:
        workflow 文件 sha256 十六进制串；文件缺失时回退为 workflow_file 文件名，
        保证 lineage 字段永远有值（不为空）。
    """
    wf = getattr(engine_cfg, "workflow_file", "") or ""
    if not wf:
        return ""
    p = Path(project_root) / wf
    try:
        st = p.stat()
        key = str(p)
        cached = _WORKFLOW_HASH_CACHE.get(key)
        if cached and cached[0] == st.st_mtime:
            return cached[1]
        digest = _sha256(p)
        _WORKFLOW_HASH_CACHE[key] = (st.st_mtime, digest)
        return digest
    except Exception as e:  # noqa: BLE001 - 血缘辅助失败不应阻断业务
        logger.warning("workflow version compute failed (%s): %s", p, e)
        return wf


def compute_lora_checksums(stack: list[dict], cfg: Any) -> list[dict]:
    """对 LoRA 栈逐层计算权重 sha256。

    Args:
        stack: ``GenerationConfig.effective_lora_stack()`` 返回的 ``[{name, strength}]``。
        cfg: AppConfig（用于解析 portable 模式下的 LoRA 资源路径）。

    Returns:
        ``[{"name", "strength", "sha256"}]`` 列表；权重文件缺失时 sha256 为 None。
    """
    from .config_models import scan_resource_files

    result: list[dict] = []
    mapping: dict[str, str] = {}
    if stack:
        try:
            rels = scan_resource_files("lora", cfg.models, cfg.project_root)
            base = (
                Path(cfg.project_root)
                / cfg.models.portable.internal_models_dir
                / cfg.models.portable.sub_dirs.get("lora", "loras")
            )
            mapping = {Path(r).stem: str(base / r) for r in rels}
        except Exception as e:  # noqa: BLE001
            logger.warning("scan lora resources failed: %s", e)
            mapping = {}

    for entry in stack or []:
        entry = entry or {}
        name = entry.get("name") or ""
        if not name:
            continue
        path = mapping.get(name)
        rec = {
            "name": name,
            "strength": float(entry.get("strength", 1.0)),
            "sha256": None,
        }
        if path and Path(path).exists():
            try:
                rec["sha256"] = _sha256(Path(path))
            except Exception as e:  # noqa: BLE001
                logger.warning("lora checksum failed (%s): %s", name, e)
        result.append(rec)
    return result


_ERROR_KEYWORDS: list[tuple[str, str]] = [
    ("OutOfMemory", "OOM_VRAM"),
    ("CUDA", "OOM_VRAM"),
    ("timeout", "TASK_TIMEOUT"),
    ("Timeout", "TASK_TIMEOUT"),
    ("cancelled", "CANCELLED"),
    ("Cancelled", "CANCELLED"),
    ("lora", "LORA_APPLY"),
    ("LoRA", "LORA_APPLY"),
    ("weight", "WEIGHT_INTEGRITY"),
    ("integrity", "WEIGHT_INTEGRITY"),
    ("workflow", "WORKFLOW_LOAD"),
    ("WaterMark", "WATERMARK"),
]


def classify_error(exc: BaseException | str) -> str:
    """把异常归类为一个稳定 error_code（用于 FAILED 记录聚类根因）。

    Args:
        exc: 异常对象或错误字符串。

    Returns:
        形如 ``OOM_VRAM`` / ``TASK_TIMEOUT`` / ``LORA_APPLY`` / ``UNKNOWN`` 的错误码。
    """
    text = str(exc)
    for keyword, code in _ERROR_KEYWORDS:
        if keyword in text:
            return code
    return "UNKNOWN"
