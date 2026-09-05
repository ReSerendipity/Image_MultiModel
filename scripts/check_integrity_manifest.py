#!/usr/bin/env python
"""scripts/check_integrity_manifest.py — 完整性清单新鲜度 CI 门禁（GOTCHAS #15 防复发）

背景：2026-09-05 事故——81910d2 在同一提交中先重生成 integrity_manifest.json
（13:01，按当时代码树）、后改动 4 个核心模块（13:07-08）、最后一起 commit（13:09），
清单入库即过期；且该提交此前从未单独 push，「清单-代码失配」只存在于本地全量测试中。
本门禁在 CI 中按**检出代码**重算哈希并与入库清单对账，不一致即 fail，
确保「清单过期」永远不能静默入库。

实现说明：直接复用 integrity_selfcheck.run_startup_selfcheck()（单一事实源，
避免第二套哈希实现漂移）；该模块仅依赖 stdlib，故本门禁在裸 CI 环境可运行。
用 importlib 按文件路径加载，绕开 app 包 __init__ 的导入副作用。

用法:
    python scripts/check_integrity_manifest.py

退出码: 0 = 清单与检出代码一致；1 = 失配 / 模块缺失 / 清单不可读 / 自检异常。
修复指引见文末输出。
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SELFCHECK_PATH = REPO_ROOT / "app" / "integrated_app" / "security" / "integrity_selfcheck.py"


def _load_selfcheck(path: Path):
    spec = importlib.util.spec_from_file_location("_imm_integrity_selfcheck", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="完整性清单新鲜度门禁（GOTCHAS #15）")
    parser.add_argument(
        "--selfcheck",
        type=Path,
        default=DEFAULT_SELFCHECK_PATH,
        help="integrity_selfcheck.py 路径（默认仓库内标准位置；供测试重定向）",
    )
    args = parser.parse_args(argv)

    if not args.selfcheck.exists():
        print(f"[FAIL] 自检模块不存在: {args.selfcheck}")
        return 1

    try:
        selfcheck = _load_selfcheck(args.selfcheck)
        result = selfcheck.run_startup_selfcheck()
    except Exception as exc:  # noqa: BLE001 - 门禁需把任何异常转为明确失败
        print(f"[FAIL] 自检执行异常: {exc!r}")
        return 1

    total = result.get("total", 0)
    passed = result.get("passed", 0)
    failed = result.get("failed", 0)
    skipped = result.get("skipped", 0)
    failed_files = result.get("failed_files", [])

    if failed == 0 and skipped == 0 and total > 0 and passed == total:
        print(f"[PASS] 完整性清单与检出代码一致（{passed}/{total} 模块）")
        return 0

    print(f"[FAIL] 完整性清单与检出代码不一致: total={total} passed={passed} failed={failed} skipped={skipped}")
    for name in failed_files:
        print(f"  - 哈希失配: {name}")
    if skipped:
        print("  - 有核心模块文件缺失（skipped>0），检查工作树完整性")
    if failed == 0 and (skipped or total == 0):
        print("  - 清单覆盖面异常（无失败但未全覆盖），运行 generate 脚本核对 _CORE_MODULES")
    print()
    print("修复: 确保同一提交的全部代码改动完成后，最后一步运行")
    print("      python scripts/generate_integrity_manifest.py")
    print("      再 git add app/integrated_app/security/integrity_manifest.json 并提交。")
    print("根因记录: docs/agents/GOTCHAS.md #15")
    return 1


if __name__ == "__main__":
    sys.exit(main())
