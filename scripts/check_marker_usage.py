#!/usr/bin/env python3
"""scripts/check_marker_usage.py — pytest marker 声明/使用一致性哨兵。

2026-09-04 测试体系评估建议（§3 必答三问 Q3）：`--strict-markers` 只拦
"未声明就使用"，不拦"声明了却无人使用"。空转 marker 会让 `-m "not X"`
类筛选静默失效，本脚本在 CI 拦住这种退化。

规则：pyproject.toml 声明的每个 marker，必须在 tests/ 内至少被 1 个
文件引用（`@pytest.mark.X` 装饰器或模块级 `pytestmark = pytest.mark.X`），
否则退出码 1 并列出空转 marker。

用法：python scripts/check_marker_usage.py [--tests-dir tests] [--pyproject pyproject.toml]
"""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path


def _declared_markers(pyproject: Path) -> list[str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    markers = (
        data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
    )
    names = []
    for m in markers:
        # 每项形如 "slow: marks tests as slow"，取冒号前的标识符
        name = m.split(":", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            names.append(name)
    return names


def _used_markers(tests_dir: Path) -> dict[str, int]:
    """返回 marker -> 引用文件数。覆盖函数级装饰器与 pytestmark 两种写法。"""
    pattern = re.compile(r"pytest\.mark\.([A-Za-z_][A-Za-z0-9_]*)")
    counts: dict[str, int] = {}
    for py in tests_dir.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in set(pattern.findall(text)):
            counts[m] = counts.get(m, 0) + 1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description="pytest marker 声明/使用一致性哨兵")
    ap.add_argument("--pyproject", default="pyproject.toml")
    ap.add_argument("--tests-dir", default="tests")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    pyproject = Path(args.pyproject)
    if not pyproject.is_absolute():
        pyproject = root / pyproject
    tests_dir = Path(args.tests_dir)
    if not tests_dir.is_absolute():
        tests_dir = root / tests_dir

    declared = _declared_markers(pyproject)
    used = _used_markers(tests_dir)

    unused = [m for m in declared if used.get(m, 0) == 0]
    print("marker 声明/使用对照：")
    for m in declared:
        print(f"  {m:20s} used in {used.get(m, 0)} file(s)")
    # 未声明的 marker 无法在此拦截（--strict-markers 已在 pytest 收集期报错）

    if unused:
        print(f"\n❌ 空转 marker（声明但 0 文件使用，-m 筛选失效）：{unused}")
        print("   处置：补用例并打标，或从 pyproject.toml markers 删除声明。")
        return 1
    print("\n✅ 所有声明 marker 均有使用，筛选语义有效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
