#!/usr/bin/env python3
"""生成 vendored ComfyUI 内核（comfy_kernel/）的 SHA256 基线清单。

对应安全评估 M-04：为项目内 vendor 的 comfy_kernel 源码建立完整性基线，
由 native/source.py 在装载内核时（fail-open）比对，检测静默篡改。

用法：
    python scripts/generate_comfy_kernel_baseline.py
    python scripts/generate_comfy_kernel_baseline.py --root comfy_kernel --out app/integrated_app/security/comfy_kernel_baseline.json

注意：基线清单不随仓库默认提供（保持启动零成本、不阻断上游更新）。
仅在需要「内核防篡改」加固的发版/构建阶段生成并随产物分发。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让脚本可直接 import 项目内模块（app/integrated_app）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from integrated_app.security.kernel_baseline import generate_kernel_baseline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 comfy_kernel 完整性基线")
    parser.add_argument("--root", default="comfy_kernel", help="comfy_kernel 源码根目录")
    parser.add_argument(
        "--out",
        default="app/integrated_app/security/comfy_kernel_baseline.json",
        help="输出基线清单路径（相对项目根）",
    )
    args = parser.parse_args()

    root = PROJECT_ROOT / args.root
    if not root.is_dir():
        print(f"[ERR] comfy_kernel 根目录不存在: {root}", file=sys.stderr)
        return 2

    manifest = generate_kernel_baseline(root, args.out)
    out_path = (PROJECT_ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    print(f"[OK] 已生成内核基线: {out_path} ({manifest['file_count']} 文件)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
