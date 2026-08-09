#!/usr/bin/env python3
"""生成核心安全模块的 SHA256 完整性清单（P1-1: 来源 Seedvr2）。

使用方式:
    python scripts/generate_integrity_manifest.py

输出文件: bin/integrated_app/security/integrity_manifest.json

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
import os
import sys
from pathlib import Path


# 核心安全模块清单 (相对于 bin/integrated_app/)
CORE_MODULES = [
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
    """生成完整性清单。"""
    project_root = Path(__file__).resolve().parent.parent
    app_dir = project_root / "bin" / "integrated_app"
    manifest_path = app_dir / "security" / "integrity_manifest.json"

    files: dict[str, str] = {}
    for module_rel in CORE_MODULES:
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
