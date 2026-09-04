#!/usr/bin/env python3
"""生成模型权重（LoRA / checkpoint 等）的 SHA256 完整性清单。

对应 MLOps 审计报告 P0-1: 为 ``.safetensors`` 权重生成可审计的 hash 清单，
供 ``security/weight_integrity.py`` 在加载前做 SHA256 比对（防供应链投毒 / 静默损坏）。

使用方式:
    python scripts/generate_weight_manifest.py
    python scripts/generate_weight_manifest.py --dir model/loras --out app/integrated_app/security/weight_manifest.json

输出格式（与 integrity_manifest.json 对齐）:
    {
        "generated_at": "2026-08-30T...",
        "generator": "scripts/generate_weight_manifest.py",
        "description": "模型权重 SHA256 完整性清单",
        "base_dir": "model/loras",
        "files": {"loras/foo.safetensors": "abc123..."}
    }
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from integrated_app.security.weight_integrity import compute_file_sha256  # noqa: E402

WEIGHT_EXTS = (".safetensors", ".pt", ".bin", ".ckpt")


def scan_weights(base_dir: Path) -> list[Path]:
    """递归扫描权重文件。"""
    if not base_dir.exists() or not base_dir.is_dir():
        return []
    result: list[Path] = []
    for root, _dirs, files in __import__("os").walk(base_dir, followlinks=True):
        for f in files:
            if f.lower().endswith(WEIGHT_EXTS):
                result.append(Path(root, f))
    return sorted(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成模型权重 SHA256 清单")
    parser.add_argument(
        "--dir",
        nargs="+",
        default=["model/loras"],
        help="权重根目录（相对项目根；可传多个，默认 model/loras）",
    )
    parser.add_argument(
        "--out",
        default="app/integrated_app/security/weight_manifest.json",
        help="输出清单路径",
    )
    parser.add_argument("--project-root", default=None, help="项目根（默认脚本上级目录）")
    args = parser.parse_args()

    project_root = Path(args.project_root) if args.project_root else Path(__file__).resolve().parent.parent
    base_dirs = [(project_root / d).resolve() for d in args.dir]

    files: dict[str, str] = {}
    for base_dir in base_dirs:
        for path in scan_weights(base_dir):
            rel = str(path.relative_to(project_root)).replace("\\", "/")
            sha = compute_file_sha256(path)
            files[rel] = sha
            print(f"  [OK] {rel}: {sha[:16]}...")

    manifest = {
        "generated_at": datetime.datetime.now().isoformat(),
        "generator": "scripts/generate_weight_manifest.py",
        "description": "模型权重 SHA256 完整性清单，供加载前校验",
        "base_dir": args.dir,
        "files": files,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n权重清单已生成: {out_path}")
    print(f"共 {len(files)} 个权重文件 (base: {args.dir})")


if __name__ == "__main__":
    main()
