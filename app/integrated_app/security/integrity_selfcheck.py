"""
security/integrity_selfcheck.py — 启动时核心模块完整性自检

P1-1 改造（来源：Seedvr2）：在应用启动时计算核心安全模块的 SHA256 哈希值
并与预期值比对，检测文件是否被篡改或注入后门 (CWE-912 供应链投毒防御)。

使用方式:
    from .security.integrity_selfcheck import run_startup_selfcheck

    results = run_startup_selfcheck()
    if results["failed"]:
        logger.error("WARNING: 核心模块完整性校验失败！")

哈希清单文件:
    哈希值存储在 ``app/integrated_app/security/integrity_manifest.json`` 中。
    首次运行或代码更新后，运行 ``python scripts/generate_integrity_manifest.py`` 重新生成。
    若清单文件不存在，自检跳过并提示生成命令。
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

# 核心安全模块清单 (相对于 app/integrated_app/)
_CORE_MODULES = [
    "app_server.py",
    "config.py",
    "config_models.py",
    "engine_interface.py",
    "model_manager.py",
    "model_registry.py",
    "task_queue.py",
    "history_db.py",
    "lineage.py",
    "i18n.py",
    "gpu_utils.py",
    "sse.py",
    "watermark.py",
    "checkpoint.py",
    "security/path_guard.py",
    "security/magic_check.py",
    "security/integrity_selfcheck.py",
    "security/weight_integrity.py",
    "security/content_filter.py",
    "security/kernel_baseline.py",
    "middleware/csrf.py",
    "middleware/rate_limit.py",
    "middleware/request_id.py",
    "middleware/auth.py",
    "middleware/security_headers.py",
    "routes/config_routes.py",
    "routes/system_routes.py",
    "routes/generate_routes.py",
    "routes/task_routes.py",
    "routes/output_routes.py",
    "routes/preset_routes.py",
    "routes/engine_routes.py",
    "mcp_server.py",
]

# 清单文件路径
_MANIFEST_FILENAME = "integrity_manifest.json"


class SelfCheckResult(NamedTuple):
    """自检结果。"""

    total: int
    passed: int
    failed: int
    skipped: int
    failed_files: list[str]


def _get_manifest_path() -> Path:
    """获取清单文件路径。

    优先采用 ``security.integrity_selfcheck.manifest_file`` 配置（此前该配置
    只声明、无代码消费）；未配置或读取失败时回退到模块同目录默认清单。
    """
    try:
        from ..config import get_config

        configured = get_config().security.integrity_selfcheck.manifest_file
        if configured:
            p = Path(configured)
            if not p.is_absolute():
                # 相对路径相对项目根解析（security/ -> integrated_app/ -> app/ -> 项目根）
                p = Path(__file__).resolve().parents[3] / p
            return p
    except Exception:  # noqa: BLE001 - 配置不可用时回退默认
        pass
    return Path(__file__).parent / _MANIFEST_FILENAME


def _compute_file_sha256(filepath: Path) -> str:
    """计算文件 SHA256。"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def run_startup_selfcheck() -> dict:
    """执行启动时核心模块完整性自检。

    流程:
        1. 读取 integrity_manifest.json 清单文件
        2. 若清单不存在，跳过自检并提示生成命令
        3. 对每个核心模块计算当前 SHA256
        4. 与清单中的预期哈希比对
        5. 不一致的文件记录为失败

    Returns:
        dict: 包含 total/passed/failed/skipped/failed_files 字段。
    """
    manifest_path = _get_manifest_path()
    app_dir = Path(__file__).parent.parent  # app/integrated_app/

    # 读取清单
    if not manifest_path.exists():
        logger.info(
            "[SELF-CHECK] 完整性清单不存在，跳过自检。"
            " 运行 `python scripts/generate_integrity_manifest.py` 生成清单以启用启动自检。"
        )
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": len(_CORE_MODULES),
            "failed_files": [],
        }

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[SELF-CHECK] 清单文件读取失败: {e}")
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": len(_CORE_MODULES),
            "failed_files": [],
        }

    expected_hashes = manifest.get("files", {})
    if isinstance(expected_hashes.get("__dummy__"), str):
        # 旧版 manifest 格式（值为 "core" 等标签而非哈希），跳过自检
        logger.info("[SELF-CHECK] 检测到旧版 manifest 格式，跳过自检。请运行 generate_integrity_manifest.py 更新。")
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": len(_CORE_MODULES),
            "failed_files": [],
        }

    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failed_files: list[str] = []

    for module_rel in _CORE_MODULES:
        module_path = app_dir / module_rel
        if not module_path.exists():
            logger.warning(f"[SELF-CHECK] 核心模块不存在: {module_path}")
            skipped += 1
            continue

        expected = expected_hashes.get(module_rel, "")

        if not expected:
            skipped += 1
            continue

        total += 1

        try:
            actual = _compute_file_sha256(module_path)
        except OSError as e:
            logger.error(f"[SELF-CHECK] 无法读取 {module_path}: {e}")
            failed += 1
            failed_files.append(module_rel)
            continue

        if actual == expected:
            passed += 1
            logger.debug(f"[SELF-CHECK] ✓ {module_rel}")
        else:
            failed += 1
            failed_files.append(module_rel)
            logger.error(
                f"[SECURITY WARNING] 核心模块完整性校验失败: {module_rel}\n"
                f"    期望 SHA256: {expected}\n"
                f"    实际 SHA256: {actual}\n"
                f"    该文件可能已被篡改！请检查代码完整性。"
            )

    # 输出汇总
    if failed > 0:
        logger.error(
            "=" * 60 + "\n"
            "[SECURITY] ⚠️  核心模块完整性自检失败！\n"
            f"    通过: {passed}/{total}, 失败: {failed}, 跳过: {skipped}\n"
            f"    失败文件: {', '.join(failed_files)}\n"
            "    请检查上述文件是否被篡改，或运行 "
            "`python scripts/generate_integrity_manifest.py` 更新清单。\n" + "=" * 60
        )
    elif passed > 0:
        logger.info(f"[SELF-CHECK] 核心模块完整性自检通过: {passed}/{total} ✓")

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failed_files": failed_files,
    }
