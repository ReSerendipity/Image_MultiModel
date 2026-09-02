#!/usr/bin/env python3
"""生成核心安全模块的 SHA256 完整性清单（P1-1: 来源 Seedvr2）。

使用方式:
    python scripts/generate_integrity_manifest.py

输出文件: app/integrated_app/security/integrity_manifest.json

清单格式:
    {
        "generated_at": "2026-08-09T13:00:00",
        "generator": "scripts/generate_integrity_manifest.py",
        "description": "核心安全模块 SHA256 完整性清单",
        "files": {
            "app_server.py": "abc123...",
            "config.py": "def456...",
            ...
        }
    }
"""

import datetime
import hashlib
import json
from pathlib import Path

# 核心安全模块清单 (相对于 app/integrated_app/)。
# 若现有清单已存在，以其 files 的 key 为准，保证模块覆盖范围不被脚本硬编码覆盖。
DEFAULT_CORE_MODULES = [
    "app_server.py",
    "config.py",
    "config_models.py",
    "engine_interface.py",
    "model_manager.py",
    "model_registry.py",
    "task_queue.py",
    "history_db.py",
    "i18n.py",
    "gpu_utils.py",
    "sse.py",
    "watermark.py",
    "checkpoint.py",
    "security/path_guard.py",
    "security/integrity_selfcheck.py",
    "middleware/csrf.py",
    "middleware/rate_limit.py",
    "middleware/request_id.py",
    "comfy/client.py",
    "comfy/engine.py",
    "comfy/workflow.py",
    "routes/config_routes.py",
    "routes/system_routes.py",
    "routes/generate_routes.py",
    "routes/task_routes.py",
    "routes/output_routes.py",
    "routes/preset_routes.py",
    "routes/engine_routes.py",
]

CHUNK_SIZE = 8 * 1024 * 1024  # 8MB


def compute_sha256(filepath: Path) -> str:
    """计算文件 SHA256。"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def main() -> None:
    """生成完整性清单。

    策略：优先以现有清单的 files 键集合为覆盖范围（避免硬编码清单与当前代码不同步），
    缺失的模块回退到 DEFAULT_CORE_MODULES，并跳过磁盘上不存在的模块。
    """
    project_root = Path(__file__).resolve().parent.parent
    app_dir = project_root / "app" / "integrated_app"
    manifest_path = app_dir / "security" / "integrity_manifest.json"

    existing: dict[str, str] = {}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {})
        except (json.JSONDecodeError, OSError):
            existing = {}

    module_set = list(existing.keys()) + [m for m in DEFAULT_CORE_MODULES if m not in existing]

    files: dict[str, str] = {}
    for module_rel in module_set:
        module_path = app_dir / module_rel
        if not module_path.exists():
            print(f"  [SKIP] 核心模块不存在: {module_rel}")
            continue
        sha = compute_sha256(module_path)
        files[module_rel] = sha
        print(f"  [OK] {module_rel}: {sha[:16]}...")

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(),
        "generator": "scripts/generate_integrity_manifest.py",
        "description": "核心安全模块 SHA256 完整性清单，用于启动时自检",
        "files": files,
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n完整性清单已生成: {manifest_path}")
    print(f"共 {len(files)} 个核心模块")


if __name__ == "__main__":
    main()
