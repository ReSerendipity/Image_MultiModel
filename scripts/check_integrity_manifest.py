#!/usr/bin/env python
"""scripts/check_integrity_manifest.py — 完整性清单新鲜度 CI 门禁（GOTCHAS #15 防复发）

背景：2026-09-05 事故——81910d2 在同一提交中先重生成 integrity_manifest.json
（13:01，按当时代码树）、后改动 4 个核心模块（13:07-08）、最后一起 commit（13:09），
清单入库即过期；且该提交此前从未单独 push，「清单-代码失配」只存在于本地全量测试中。
本门禁在 CI 中按**检出代码**重算哈希并与入库清单对账，不一致即 fail，
确保「清单过期」永远不能静默入库。同时要求清单**带有效 Ed25519 签名**：
自检在 enforce=false 时把验签失败只记为告警、不计入 failed，若本门禁不单独
检查 `manifest_signed`，未签名清单就能通过 CI，而运行时（config.yaml
security.integrity_selfcheck.enforce=true）会拒绝启动——两者必须同口径。

实现说明：直接复用 integrity_selfcheck.run_startup_selfcheck()（单一事实源，
避免第二套哈希实现漂移）。用 importlib 按文件路径加载，绕开 app 包 __init__ 的导入副作用。

用法:
    python scripts/check_integrity_manifest.py

退出码: 0 = 清单与检出代码一致且签名有效；1 = 失配 / 未签名或验签器不可用 /
模块缺失 / 清单不可读 / 自检异常。

依赖边界（2026-09-24 更正）：哈希对账只需 stdlib，但清单**验签**走
security/secret_key.py 的 Ed25519 分支，那里是函数内 import cryptography。
本文件原先写着“仅依赖 stdlib，故裸 CI 可运行”，正是这句让调用方 job 只装了
pyyaml，使门禁在 CI 恒红并报成“清单缺少有效签名”，把排查引向错误方向。
缺依赖与未签名是两件事，下面分开报。
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
    signed = bool(result.get("manifest_signed", False))

    if failed == 0 and skipped == 0 and total > 0 and passed == total and signed:
        print(f"[PASS] 完整性清单与检出代码一致（{passed}/{total} 模块）且 Ed25519 签名有效")
        return 0

    print(
        f"[FAIL] 完整性清单门禁未通过: total={total} passed={passed} failed={failed} skipped={skipped} signed={signed}"
    )
    for name in failed_files:
        print(f"  - 哈希失配: {name}")
    if skipped:
        print("  - 有核心模块文件缺失（skipped>0），检查工作树完整性")
    if failed == 0 and (skipped or total == 0):
        print("  - 清单覆盖面异常（无失败但未全覆盖），运行 generate 脚本核对 _CORE_MODULES")
    if not signed:
        import importlib.util

        if importlib.util.find_spec("cryptography") is None:
            print("  - 无法判定签名：本环境未安装 cryptography，Ed25519 验签分支不可用；")
            print("    而 HMAC 回退需要本机 data/.imm_secret（CI 里没有），故 verify_manifest_signature()")
            print("    返回 False。这是门禁运行环境缺依赖，不是清单问题——给该 job 补 pip install cryptography。")
        else:
            print("  - 清单缺少有效 Ed25519 签名。自检在 enforce=false 时只告警不计入 failed，")
            print("    而运行时 config.yaml security.integrity_selfcheck.enforce=true 会据此拒绝启动；")
            print("    CI 与 release 门禁不得放行未签名或签名已过期的清单。")

    print()
    print("修复: 确保同一提交的全部代码改动完成后，最后一步依次运行")
    print("      python scripts/generate_integrity_manifest.py")
    print("      python scripts/sign_integrity_manifest.py")
    print("      再 git add integrity_manifest.json 与 integrity_manifest.json.sig.ed25519 并提交。")
    print("根因记录: 本地 AI 规范坑点集 GOTCHAS #15（未随仓库发布）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
