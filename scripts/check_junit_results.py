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
    args = ap.parse_args(argv)

    if not args.junit.is_file():
        print(f"::error::{args.junit} 不存在 —— 测试步骤没产出 junit，等于没测")
        return 1

    cases = _parse(args.junit)
    total = len(cases)
    failed = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
    skipped = [c for c in cases if c.find("skipped") is not None]
    executed = total - len(skipped)
    quotas = dict(args.allow_skip)

    print(f"junit: {total} 用例 / {executed} 执行出结论 / {len(skipped)} skip / {len(failed)} 失败")

    reasons: Counter[str] = Counter()
    for case in skipped:
        reason = _skip_reason(case) or "(无原因)"
        label = next((r for r in quotas if r in reason), None)
        reasons[label or reason] += 1

    print("skip 原因分布：")
    if not reasons:
        print("  (无 skip)")
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        if reason not in quotas:
            print(f"  [未登记] {count} 条: {reason}")
        else:
            flag = "OK" if count <= quotas[reason] else "超配额"
            print(f"  [{flag}] {count}/{quotas[reason]} 条: {reason}")

    problems: list[str] = []
    if failed:
        names = ", ".join(f"{c.get('classname', '?')}::{c.get('name', '?')}" for c in failed[:5])
        problems.append(f"{len(failed)} 个用例失败/报错（junit 里有 failure/error 节点）：{names}")
    if executed < args.min_executed:
        problems.append(
            f"执行出结论的用例 {executed} < 下限 {args.min_executed} —— "
            f"总收集 {total}、skip {len(skipped)}：极可能是收集为空或整体被 skip"
        )
    for reason, count in reasons.items():
        if reason not in quotas:
            problems.append(f"未登记的 skip 原因（新增 pytest.skip 需先加入 --allow-skip）：{reason}")
        elif count > quotas[reason]:
            problems.append(f"skip 原因超出配额：{count} > {quotas[reason]} —— {reason}")

    if problems:
        for p in problems:
            print(f"::error::{p}")
        return 1
    print(f"[PASS] junit 门禁通过：{executed} 个用例真正执行出结论，skip 均在白名单配额内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
