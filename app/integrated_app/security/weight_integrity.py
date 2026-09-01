"""
security/weight_integrity.py — LoRA/checkpoint 权重加载前完整性校验

对应 MLOps 审计报告 P0-1: 在加载 ``.safetensors`` / ``.pt`` / ``.bin`` 权重前做:
1. **格式白名单**: ``only_safetensors`` 时拒绝非 safetensors 文件
2. **结构合法性**: 解析 safetensors 头（8 字节 length + JSON），失败即视为损坏
3. **危险载荷探测**: 探测 pickle/可疑二进制头部（CWE-502 反序列化防护）
4. **可选 SHA256 比对**: 与权重清单（manifest）或 config 中登记的期望值比对

设计原则（与 AGENTS.md 硬约束 #2「路由层不写推理逻辑」不冲突，本模块只做
文件级校验，不触碰 torch.* / 推理；native 层在加载前调用）:
- 校验**仅对实际存在的文件生效**；文件缺失由调用方既有逻辑处理（告警并跳过）。
- 默认 ``fail_closed=False``: 校验失败时记录告警并跳过该层，不阻断主推理
  （与现有 LoRA 静默跳过行为一致）；配置 ``fail_closed_on_corrupt_weight=True``
  时升级为 fail-closed，抛 ``WeightIntegrityError``。
"""

from __future__ import annotations

import hashlib
import json
import logging
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# pickle 协议魔数（用于危险载荷探测）
_PICKLE_MAGICS = (b"\x80\x02", b"\x80\x03", b"\x80\x04", b"\x80\x05")
# torch >=1.6 的 .pt/.bin 通常为 ZIP（PK\x03\x04），这里仅标记"非 safetensors 已知安全格式"
_ZIP_MAGIC = b"PK\x03\x04"
_SAFETENSORS_EXT = ".safetensors"


class WeightIntegrityError(Exception):
    """权重完整性校验失败（fail-closed 模式下抛出）。"""


@dataclass
class WeightCheckResult:
    """单次权重校验结果。"""

    path: str
    ok: bool
    sha256: str = ""
    size_bytes: int = 0
    fmt: str = "unknown"  # safetensors | zip | pickle | unknown
    tensor_count: int = 0
    error: str = ""


def compute_file_sha256(path: str | Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    """分块计算文件 SHA256（与 integrity_selfcheck 同实现，避免大文件占用内存）。"""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def _read_safetensors_header(path: Path) -> dict | None:
    """读取并解析 safetensors 头，返回 header dict；解析失败返回 None。"""
    try:
        with open(path, "rb") as f:
            magic = f.read(8)
            if len(magic) < 8:
                return None
            header_len = struct.unpack("<Q", magic)[0]
            if header_len <= 0 or header_len > 100 * 1024 * 1024:
                return None
            header_bytes = f.read(header_len)
        if len(header_bytes) < header_len:
            return None
        return json.loads(header_bytes)
    except Exception as e:  # noqa: BLE001 - 解析异常即视为损坏
        logger.debug("safetensors header parse failed for %s: %s", path, e)
        return None


def _peek_format(path: Path) -> str:
    """粗略判断文件格式（用于报告与危险载荷探测）。"""
    try:
        with open(path, "rb") as f:
            head = f.read(8)
    except OSError:
        return "unknown"
    if head[:2] in _PICKLE_MAGICS:
        return "pickle"
    if head[:4] == _ZIP_MAGIC:
        return "zip"
    if path.suffix.lower() == _SAFETENSORS_EXT and head[:8] and _read_safetensors_header(path):
        return "safetensors"
    return "unknown"


def _cfg_warn_if_pickle_found() -> bool:
    """读取 ``security.model_format.warn_if_pickle_found``（默认 True）。

    该开关此前只声明在 config.yaml / config_models.py 中、无任何代码消费
    （配置-实现错配）。现由 pickle 探测分支真正读取并据此告警。
    """
    try:
        from ..config import get_config

        return bool(get_config().security.model_format.warn_if_pickle_found)
    except Exception:  # noqa: BLE001 - 配置不可用时采用安全默认值
        return True


def validate_weight_file(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
    allow_non_safetensors: bool = False,
    warn_if_pickle_found: bool | None = None,
) -> WeightCheckResult:
    """对单个权重文件做完整性校验。

    Args:
        path: 权重文件路径
        expected_sha256: 期望的 SHA256（来自 manifest 或 config）；为空则不比对 hash
        allow_non_safetensors: 是否允许非 safetensors 格式（对应 ``only_safetensors=False``）
        warn_if_pickle_found: 检测到 pickle 载荷时是否告警；None 时读取
            ``security.model_format.warn_if_pickle_found`` 配置

    Returns:
        WeightCheckResult: ``ok`` 为 True 表示通过校验
    """
    p = Path(path)
    result = WeightCheckResult(path=str(p), ok=False, sha256="", size_bytes=0, fmt="unknown")

    if not p.exists() or not p.is_file():
        result.error = "file_not_found"
        result.ok = False
        return result

    try:
        result.size_bytes = p.stat().st_size
    except OSError:
        pass

    fmt = _peek_format(p)
    result.fmt = fmt
    is_safetensors_ext = p.suffix.lower() == _SAFETENSORS_EXT

    if fmt == "pickle":
        result.ok = False
        result.error = "pickle_payload_detected (potential CWE-502 deserialization risk)"
        if warn_if_pickle_found is None:
            warn_if_pickle_found = _cfg_warn_if_pickle_found()
        if warn_if_pickle_found:
            logger.warning(
                "[WEIGHT-INTEGRITY] 检测到 pickle 载荷（CWE-502 反序列化风险）: %s", p
            )
        return result

    if is_safetensors_ext:
        result.fmt = "safetensors"
        header = _read_safetensors_header(p)
        if header is None:
            result.ok = False
            result.error = "invalid_safetensors_header (corrupted)"
            return result
        # 统计张量数量（排除元数据键）
        result.tensor_count = sum(1 for k in header if k != "__metadata__")
    elif not allow_non_safetensors:
        result.ok = False
        result.error = f"non-safetensors format rejected (only_safetensors=true, got {fmt})"
        return result

    # SHA256 比对（可选）
    if expected_sha256:
        actual = compute_file_sha256(p)
        result.sha256 = actual
        if actual.lower() != expected_sha256.lower():
            result.ok = False
            result.error = "sha256_mismatch"
            return result
    else:
        # 仍记录 hash 便于审计
        try:
            result.sha256 = compute_file_sha256(p)
        except OSError:
            pass

    result.ok = True
    return result


def load_weight_manifest(manifest_file: str | Path) -> dict[str, Any]:
    """加载权重 SHA256 清单。

    manifest 格式（与 integrity_manifest.json 对齐）::

        {"generated_at": "...", "files": {"loras/foo.safetensors": "abc..."}}

    Returns:
        清单 dict；文件缺失/损坏时返回空 dict（调用方按"不比对"处理）
    """
    p = Path(manifest_file)
    if not p.exists():
        logger.info("[WEIGHT-INTEGRITY] 权重清单不存在: %s，跳过 hash 比对", p)
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[WEIGHT-INTEGRITY] 权重清单读取失败: %s", e)
        return {}
    files = data.get("files", {})
    if not isinstance(files, dict):
        return {}
    return files


def manifest_hash_for_path(
    manifest: dict[str, str],
    abs_path: str | Path,
    project_root: str | Path = "",
) -> str | None:
    """从清单中查某绝对路径对应的期望 hash。

    支持绝对路径键与相对项目根的相对路径键两种形态。
    """
    abs_s = str(Path(abs_path)).replace("\\", "/")
    if abs_s in manifest:
        return manifest[abs_s]
    if project_root:
        try:
            rel = str(Path(abs_path).resolve().relative_to(Path(project_root).resolve())).replace("\\", "/")
            if rel in manifest:
                return manifest[rel]
        except ValueError:
            pass
    return None


def verify_weights_against_manifest(
    manifest: dict[str, str],
    project_root: str | Path = "",
) -> dict[str, Any]:
    """批量校验清单中权重与登记 hash 的一致性（用于启动自检 / CLI）。

    Args:
        manifest: ``{"relative/or/abs/path": "sha256", ...}``
        project_root: 项目根；当 manifest 键为相对路径时用于解析绝对路径

    Returns:
        {"total", "passed", "failed", "missing", "failed_files": [...]}
    """
    total = passed = failed = missing = 0
    failed_files: list[str] = []
    for rel, expected in manifest.items():
        if project_root and not Path(rel).is_absolute():
            full = str((Path(project_root) / rel).resolve())
        else:
            full = str(Path(rel).resolve())
        p = Path(full)
        if not p.exists():
            missing += 1
            continue
        total += 1
        res = validate_weight_file(p, expected_sha256=expected)
        if res.ok:
            passed += 1
        else:
            failed += 1
            failed_files.append(rel)
            logger.error("[WEIGHT-INTEGRITY] 校验失败: %s (%s)", rel, res.error)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "missing": missing,
        "failed_files": failed_files,
    }


def verify_weight_before_load(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
    allow_non_safetensors: bool = False,
) -> WeightCheckResult:
    """加载前便捷封装：对存在的文件做校验，缺失则交给调用方既有逻辑。"""
    p = Path(path)
    if not p.exists():
        return WeightCheckResult(path=str(p), ok=False, error="file_not_found")
    return validate_weight_file(
        p,
        expected_sha256=expected_sha256,
        allow_non_safetensors=allow_non_safetensors,
    )


__all__ = [
    "WeightIntegrityError",
    "WeightCheckResult",
    "compute_file_sha256",
    "validate_weight_file",
    "load_weight_manifest",
    "manifest_hash_for_path",
    "verify_weights_against_manifest",
    "verify_weight_before_load",
]
