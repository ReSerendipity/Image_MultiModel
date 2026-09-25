#!/usr/bin/env python3
"""scripts/check_junit_results.py — junit 结果门禁：拦掉「绿色但没真测」。

pytest 退出码 0 只说明它没报错，不说明它真的比对过什么。本脚本只解析
pytest --junitxml 的产物（纯 stdlib，不装 pytest），拦三类静默退化：

1. 零执行：非 skip 用例数为 0。marker 表达式写错筛空、收集目录改名、
   依赖缺失导致整目录 pytest.skip —— 这些在 pytest 侧都是"通过"。
2. 未知 skip：skip 原因不在白名单内，或同一原因的条数超过配额。
   新增一条 pytest.skip 必须先在这里登记，逼一次显式决策。
3. 失败被吞：junit 里存在 failure/error 节点（防止将来有人补 `|| true`）。

用法：
    python scripts/check_junit_results.py --junit e2e-junit.xml \
        --min-executed 20 --allow-skip "基线快照已写入=1"
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def _skip_reason(case: ET.Element) -> str:
    """取 skipped 节点的原因文本（pytest 把原因放在 message 属性里）。"""
    node = case.find("skipped")
    if node is None:
        return ""
    return (node.get("message") or (node.text or "")).strip()


def _parse(junit: Path) -> list[ET.Element]:
    root = ET.parse(junit).getroot()
    if root.tag == "testsuite":
        return list(root.iter("testcase"))
    return list(root.iter("testcase"))


def _parse_allow(raw: str) -> tuple[str, int]:
    reason, _, quota = raw.rpartition("=")
    if not reason or not quota.isdigit():
        raise argparse.ArgumentTypeError(f'--allow-skip 需要 "原因关键字=配额"，收到 {raw!r}')
    return reason, int(quota)


def _load_ledger(path: Path) -> tuple[dict[str, int], int, int]:
    """读 skip 台账，返回 (原因→应有条数, skip 总数期望, executed 下限)。

    台账语义是**精确相等**而不是上限：条数变多 = 新增了没人登记的 skip；
    条数变少 = 登记过的 skip 悄悄消失（环境变了、用例被删、断言失效）。
    两者都是台账失真，都必须走"改台账"的 PR，不许就地放宽成 warning。
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    reasons: dict[str, int] = {}
    for item in data.get("reasons", []):
        key, count = item["key"], int(item["count"])
        if key in reasons:
            raise SystemExit(f"台账 {path} 原因键重复：{key!r}")
        reasons[key] = count
    per_key = sum(reasons.values())
    total = int(data.get("total_skips_expected", per_key))
    if total != per_key:
        raise SystemExit(f"台账自相矛盾：total_skips_expected={total} 但逐条之和={per_key}（{path}）")
    return reasons, total, int(data.get("min_executed", 1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="解析 pytest junit 产物并做反假绿门禁")
    ap.add_argument("--junit", required=True, type=Path, help="pytest --junitxml 产出的 XML")
    ap.add_argument(
        "--min-executed",
        type=int,
        default=1,
        help="至少多少个用例真正执行出结论（passed/failed/error，不含 skipped）",
    )
    ap.add_argument(
        "--allow-skip",
        action="append",
        type=_parse_allow,
        default=[],
        metavar="'原因关键字=配额'",
        help="允许的 skip 原因及其最大条数，可重复；未登记的 skip 原因一律失败",
    )
    ap.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help="skip 台账 JSON：逐原因条数与 skip 总数按精确相等判定（双向防漂移）；"
        "给了它就覆盖 --allow-skip / --min-executed 的口径",
    )
    args = ap.parse_args(argv)

    if not args.junit.is_file():
        print(f"::error::{args.junit} 不存在 —— 测试步骤没产出 junit，等于没测")
        return 1

    cases = _parse(args.junit)
    total = len(cases)
    failed = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
    skipped = [c for c in cases if c.find("skipped") is not None]
    executed = total - len(skipped)

    if args.ledger is not None:
        quotas, expected_skips, min_executed = _load_ledger(args.ledger)
        exact = True
        print(
            f"台账 {args.ledger}：{len(quotas)} 条登记原因，"
            f"期望 skip 总数 {expected_skips}，executed 下限 {min_executed}"
        )
    else:
        quotas, expected_skips, min_executed, exact = dict(args.allow_skip), -1, args.min_executed, False

    print(f"junit: {total} 用例 / {executed} 执行出结论 / {len(skipped)} skip / {len(failed)} 失败")

    reasons: Counter[str] = Counter()
    for case in skipped:
        reason = _skip_reason(case) or "(无原因)"
        label = next((r for r in quotas if r in reason), None)
        reasons[label or reason] += 1

    print("skip 原因分布：")
    if not reasons:
        print("  (无 skip)")
    for reason, count in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0])):
        if reason not in quotas:
            print(f"  [未登记] {count} 条: {reason}")
        elif exact:
            print(f"  [{'OK' if count == quotas[reason] else '漂移'}] {count}/{quotas[reason]} 条: {reason}")
        else:
            print(f"  [{'OK' if count <= quotas[reason] else '超配额'}] {count}/{quotas[reason]} 条: {reason}")

    problems: list[str] = []
    if failed:
        names = ", ".join(f"{c.get('classname', '?')}::{c.get('name', '?')}" for c in failed[:5])
        problems.append(f"{len(failed)} 个用例失败/报错（junit 里有 failure/error 节点）：{names}")
    if executed < min_executed:
        problems.append(
            f"执行出结论的用例 {executed} < 下限 {min_executed} —— "
            f"总收集 {total}、skip {len(skipped)}：极可能是收集为空或整体被 skip"
        )
    if exact and len(skipped) != expected_skips:
        problems.append(
            f"skip 总数 {len(skipped)} ≠ 台账期望 {expected_skips}（"
            f"{'新增未登记 skip' if len(skipped) > expected_skips else '已登记的 skip 消失：环境变化或用例被删'}）"
            "—— 两种都是台账失真，要改台账而不是放宽门禁"
        )
    for reason, count in sorted(reasons.items()):
        if reason not in quotas:
            problems.append(f"未登记的 skip 原因（新增 pytest.skip 需先入台账）：{reason}")
        elif exact and count != quotas[reason]:
            problems.append(f"skip 条数与台账不符：{count} ≠ {quotas[reason]} —— {reason}")
        elif not exact and count > quotas[reason]:
            problems.append(f"skip 原因超出配额：{count} > {quotas[reason]} —— {reason}")

    if problems:
        for p in problems:
            print(f"::error::{p}")
        if exact and reasons:
            print("按本次实况更新台账的原因表（仍需人工核对归属，别直接粘贴了事）：")
            for reason, count in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0])):
                print(f'  {{"key": {json.dumps(reason, ensure_ascii=False)}, "count": {count}}},')
        return 1
    mode = "逐条与台账一致" if exact else "均在白名单配额内"
    print(f"[PASS] junit 门禁通过：{executed} 个用例真正执行出结论，{len(skipped)} 条 skip {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
