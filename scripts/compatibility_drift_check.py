#!/usr/bin/env python3
"""
compatibility_drift_check.py — AI 数据债：LoRA / Checkpoint 兼容性漂移检测（长期-数据债登记）

扫描 ``model/loras`` 与 ``model/checkpoints``（portable 模式），输出：
- 各资源数量与总占用
- 未被任何引擎 compatibility_matrix 引用的 LoRA（潜在僵尸/孤立资产，呼应反模式 #4.7）
- 引用了但实际文件缺失的 LoRA（悬空引用）

运行：python scripts/compatibility_drift_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "app"))

from integrated_app.config import get_config  # noqa: E402
from integrated_app.model_compat import validate_compatibility_matrix  # noqa: E402


def main() -> int:
    cfg = get_config()
    project_root = Path(cfg.project_root)
    lora_dir = (
        project_root / cfg.models.portable.internal_models_dir / cfg.models.portable.sub_dirs.get("lora", "loras")
    )
    ckpt_dir = (
        project_root
        / cfg.models.portable.internal_models_dir
        / cfg.models.portable.sub_dirs.get("checkpoint", "checkpoints")
    )

    lora_files = sorted(lora_dir.glob("*.safetensors")) if lora_dir.exists() else []
    ckpt_files = sorted(ckpt_dir.glob("*.safetensors")) if ckpt_dir.exists() else []

    # 收集所有引擎矩阵中声明的 LoRA 名
    declared: set[str] = set()
    matrix_errors: list[str] = []
    for name, ecfg in cfg.models.engines.items():
        matrix_errors.extend(validate_compatibility_matrix(ecfg))
        for key in getattr(ecfg, "compatibility_matrix", None) or {}:
            declared.add(key)

    orphan_loras = [p.name for p in lora_files if p.stem not in declared]
    referenced_missing = [k for k in declared if not (lora_dir / f"{k}.safetensors").exists()]

    print("=" * 56)
    print("AI 数据债 · 兼容性漂移检测")
    print("=" * 56)
    print(f"LoRA 文件数     : {len(lora_files)}  ({lora_dir})")
    print(f"Checkpoint 文件数: {len(ckpt_files)}  ({ckpt_dir})")
    print(f"矩阵声明 LoRA 数: {len(declared)}")
    if matrix_errors:
        print("\n[ERROR] compatibility_matrix 结构非法:")
        for e in matrix_errors:
            print(f"  - {e}")
    if orphan_loras:
        print(f"\n[WARN] 未在任何兼容性矩阵中声明的 LoRA（{len(orphan_loras)}，潜在僵尸资产）:")
        for n in orphan_loras[:20]:
            print(f"  - {n}")
        if len(orphan_loras) > 20:
            print(f"  ... 其余 {len(orphan_loras) - 20} 个省略")
    if referenced_missing:
        print(f"\n[ERROR] 矩阵引用但文件缺失的 LoRA（{len(referenced_missing)}）:")
        for n in referenced_missing:
            print(f"  - {n}")
    if not orphan_loras and not referenced_missing and not matrix_errors:
        print("\nOK: 无明显的兼容性漂移。")

    # 退出码：有 ERROR 级问题返回 1（供 CI 门禁），仅 WARN 返回 0
    return 1 if (matrix_errors or referenced_missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
