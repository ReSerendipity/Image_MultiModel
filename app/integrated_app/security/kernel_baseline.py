"""
security/kernel_baseline.py — vendored ComfyUI 内核完整性基线（M-04）

与 integrity_selfcheck.py 互补：
- integrity_selfcheck 守护「自研核心模块」不被篡改；
- 本模块守护「vendor 进来的 comfy_kernel 源码」基线不被静默改动。

设计取舍（对齐 AGENTS.md §禁区目录：comfy_kernel 为 vendored 上游）：
- **fail-open**：comfy_kernel 允许随上游更新（保留 patch 文件、记录 ADR），
  因此基线不一致时仅告警、不阻断加载；基线文件缺失时直接跳过（零开销）。
- 基线文件由 scripts/generate_comfy_kernel_baseline.py 在构建/发版阶段生成，
  不随仓库默认提供 → 默认启动零成本、不影响测试套件。
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 默认基线文件路径（相对项目根）；缺失即跳过校验。
_DEFAULT_BASELINE = "app/integrated_app/security/comfy_kernel_baseline.json"

# 纳入基线的源码后缀；排除缓存与构建产物。
_INCLUDE_SUFFIXES = (".py", ".json", ".yaml", ".yml")
_SKIP_DIRS = {"__pycache__", ".git", "node_modules", "build", "dist"}


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in _INCLUDE_SUFFIXES:
            continue
        files.append(p)
    return files


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_kernel_baseline(root: str | Path, baseline_path: str | Path | None = None) -> dict[str, Any]:
    """生成 comfy_kernel 目录的 SHA256 基线清单并写入磁盘。

    Args:
        root: comfy_kernel 源码根目录。
        baseline_path: 输出清单路径；None 时使用默认路径。相对路径
            相对项目根解析。

    Returns:
        写入的清单 dict（含 file_count / generated_at / files）。
    """
    root = Path(root).resolve()
    project_root = Path(__file__).resolve().parents[3]
    if baseline_path:
        bp = Path(baseline_path)
        out = bp if bp.is_absolute() else project_root / bp
    else:
        out = project_root / _DEFAULT_BASELINE

    files: dict[str, str] = {}
    for p in _iter_source_files(root):
        rel = str(p.relative_to(root))
        files[rel] = _sha256(p)

    manifest = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "file_count": len(files),
        "files": files,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    logger.info("[KERNEL-BASELINE] 生成基线: %s (%d 文件)", out, len(files))
    return manifest


def verify_kernel_baseline(
    root: str | Path,
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    """校验 comfy_kernel 目录与基线清单是否一致（fail-open）。

    Args:
        root: comfy_kernel 源码根目录。
        baseline_path: 基线清单路径；None 时使用默认路径。

    Returns:
        dict：{"skipped": bool, "checked": int, "mismatched": int,
               "missing": int, "extra": int, "ok": bool}
        基线缺失时 skipped=True（不告警）；不一致时仅记录 warning。
    """
    root = Path(root).resolve()
    if baseline_path:
        bp = Path(baseline_path)
        if not bp.is_absolute():
            bp = Path(__file__).resolve().parents[3] / bp
    else:
        bp = Path(__file__).resolve().parents[3] / _DEFAULT_BASELINE

    if not bp.is_file():
        logger.debug("[KERNEL-BASELINE] 基线文件缺失，跳过校验: %s", bp)
        return {"skipped": True, "checked": 0, "mismatched": 0, "missing": 0, "extra": 0, "ok": True}

    try:
        manifest = json.loads(bp.read_text(encoding="utf-8"))
        expected: dict[str, str] = manifest.get("files", {})
    except Exception as e:  # noqa: BLE001
        logger.warning("[KERNEL-BASELINE] 基线文件损坏，跳过校验: %s (%s)", bp, e)
        return {"skipped": True, "checked": 0, "mismatched": 0, "missing": 0, "extra": 0, "ok": True}

    mismatched = 0
    missing = 0
    present: set[str] = set()
    for rel, exp_hash in expected.items():
        fp = root / rel
        if not fp.is_file():
            missing += 1
            continue
        present.add(rel)
        try:
            if _sha256(fp) != exp_hash:
                mismatched += 1
                logger.warning("[KERNEL-BASELINE] 文件哈希不一致: %s", rel)
        except Exception as e:  # noqa: BLE001
            logger.warning("[KERNEL-BASELINE] 读取失败跳过: %s (%s)", rel, e)

    extra = len([p for p in _iter_source_files(root) if str(p.relative_to(root)) not in present])

    ok = (mismatched == 0 and missing == 0)
    if not ok:
        # fail-open：仅告警，不抛异常、不阻断加载
        logger.warning(
            "[KERNEL-BASELINE] vendored 内核与基线不符（mismatched=%d missing=%d extra=%d），"
            "请确认是否来自预期的上游更新。",
            mismatched, missing, extra,
        )
    else:
        logger.info("[KERNEL-BASELINE] 内核基线校验通过（%d 文件）", len(expected))
    return {
        "skipped": False,
        "checked": len(expected),
        "mismatched": mismatched,
        "missing": missing,
        "extra": extra,
        "ok": ok,
    }
