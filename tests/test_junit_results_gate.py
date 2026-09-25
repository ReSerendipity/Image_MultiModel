"""tests/test_junit_results_gate.py — junit 反假绿门禁的行为锁定。

门禁脚本 ``scripts/check_junit_results.py`` 负责把「pytest 退出码 0 但其实
什么都没测」报成红色，它自身必须可靠：
1. 有足量用例真正执行出结论 → exit 0；
2. 执行数为 0（整目录 skip / marker 筛空）→ exit 1；
3. 未登记的 skip 原因、超出配额的 skip、含 failure/error 节点 → exit 1；
4. junit 文件缺失（测试步骤没产出）→ exit 1，不得静默放行。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "scripts" / "check_junit_results.py"


def _junit(tmp_path: Path, cases: list[tuple[str, str]]) -> str:
    """按 pytest 的 junit 形状写一份 XML，返回文件路径字符串。

    Args:
        tmp_path: pytest 临时目录。
        cases: ``(用例名, 状态)`` 列表，状态取 ``pass`` / ``skip:<原因>`` /
            ``fail`` / ``error``。
    """
    parts: list[str] = []
    for i, (name, state) in enumerate(cases):
        if state == "pass":
            parts.append(f'<testcase classname="g.{i}" name="{name}" time="0.1" />')
        elif state.startswith("skip:"):
            reason = state.split(":", 1)[1]
            parts.append(
                f'<testcase classname="g.{i}" name="{name}" time="0.1">'
                f'<skipped type="pytest.skip" message="{reason}">{reason}</skipped></testcase>'
            )
        elif state == "fail":
            parts.append(
                f'<testcase classname="g.{i}" name="{name}" time="0.1">'
                f'<failure message="assert 1 == 2">boom</failure></testcase>'
            )
        else:
            parts.append(
                f'<testcase classname="g.{i}" name="{name}" time="0.1">'
                f'<error message="collection failure">boom</error></testcase>'
            )
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites name="pytest tests"><testsuite name="pytest" '
        f'tests="{len(cases)}" failures="0" errors="0" skipped="0" time="1.0">'
        f"{''.join(parts)}</testsuite></testsuites>"
    )
    path = tmp_path / "result.xml"
    path.write_text(xml, encoding="utf-8")
    return str(path)


def _run(*extra: str) -> subprocess.CompletedProcess[str]:
    # PYTHONUTF8=1：门禁输出含中文，Windows 子进程默认按本地代码页(cp936)写管道，
    # 父进程按 utf-8 解码会抛 UnicodeDecodeError 并把 stdout 变成 None。
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, str(GATE), *extra],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        cwd=REPO_ROOT,
    )


def test_gate_passes_when_cases_actually_ran(tmp_path: Path):
    """20 个用例执行出结论 + 1 条登记过的 skip → PASS。"""
    junit = _junit(
        tmp_path,
        [(f"test_{i}", "pass") for i in range(20)]
        + [("test_baseline", "skip:基线快照已写入：homepage.linux-chromium.png")],
    )
    r = _run("--junit", junit, "--min-executed", "20", "--allow-skip", "基线快照已写入=1")
    assert r.returncode == 0, f"应 PASS: {r.stdout}\n{r.stderr}"
    assert "[PASS]" in r.stdout
    assert "21 用例 / 20 执行出结论 / 1 skip" in r.stdout


def test_gate_fails_when_nothing_executed(tmp_path: Path):
    """整目录被 skip（依赖缺失那类）→ 执行数为 0，必须红。"""
    junit = _junit(tmp_path, [(f"test_{i}", "skip:pytest-playwright not installed") for i in range(25)])
    r = _run("--junit", junit, "--min-executed", "20", "--allow-skip", "基线快照已写入=1")
    assert r.returncode == 1, f"零执行应被拦截: {r.stdout}"
    assert "执行出结论的用例 0 < 下限 20" in r.stdout


def test_gate_fails_on_unregistered_skip_reason(tmp_path: Path):
    """新增的 pytest.skip 原因未登记 → 红（强制一次显式决策）。"""
    junit = _junit(
        tmp_path,
        [("test_a", "pass")] * 20 + [("test_b", "skip:临时想找个理由不测")],
    )
    r = _run("--junit", junit, "--min-executed", "20", "--allow-skip", "基线快照已写入=1")
    assert r.returncode == 1, f"未登记 skip 应被拦截: {r.stdout}"
    assert "未登记的 skip 原因" in r.stdout


def test_gate_fails_when_skip_quota_exceeded(tmp_path: Path):
    """登记原因但条数超过配额（基线在多个用例上重生）→ 红。"""
    junit = _junit(
        tmp_path,
        [("test_a", "pass")] * 20
        + [("test_b", "skip:基线快照已写入：a.png"), ("test_c", "skip:基线快照已写入：b.png")],
    )
    r = _run("--junit", junit, "--min-executed", "20", "--allow-skip", "基线快照已写入=1")
    assert r.returncode == 1, f"超配额应被拦截: {r.stdout}"
    assert "skip 原因超出配额：2 > 1" in r.stdout


def test_gate_fails_on_failure_or_error_node(tmp_path: Path):
    """junit 里有 failure/error 节点 → 红（挡住将来给测试步骤补 || true）。"""
    junit = _junit(tmp_path, [("test_a", "pass")] * 20 + [("test_b", "fail"), ("test_c", "error")])
    r = _run("--junit", junit, "--min-executed", "20", "--allow-skip", "基线快照已写入=1")
    assert r.returncode == 1, f"有失败节点应被拦截: {r.stdout}"
    assert "2 个用例失败/报错" in r.stdout


def test_gate_fails_when_junit_missing(tmp_path: Path):
    """测试步骤没产出 junit（被 kill / 路径写错）→ 红，不静默放行。"""
    r = _run("--junit", str(tmp_path / "nope.xml"), "--min-executed", "20")
    assert r.returncode == 1, f"缺 junit 应被拦截: {r.stdout}"
    assert "不存在" in r.stdout


# ── --ledger 精确相等口径（主 test job 用的那套）──────────────────────
def _ledger(tmp_path: Path, reasons: list[dict], total: int | None = None, min_executed: int = 1) -> str:
    data = {
        "total_skips_expected": total if total is not None else sum(r["count"] for r in reasons),
        "min_executed": min_executed,
        "reasons": reasons,
    }
    f = tmp_path / "ledger.json"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(f)


R_A = {"key": "原生引擎栈不可用", "count": 2}
R_B = {"key": "ComfyUI 不在线", "count": 1}


def test_ledger_passes_on_exact_match(tmp_path: Path):
    junit = _junit(
        tmp_path,
        [
            ("test_p1", "pass"),
            ("test_p2", "pass"),
            ("test_s1", "skip:原生引擎栈不可用（缺 comfy_aimdo）"),
            ("test_s2", "skip:原生引擎栈不可用（另一模块）"),
            ("test_s3", "skip:ComfyUI 不在线，跳过前向路径集成测试"),
        ],
    )
    r = _run("--junit", junit, "--ledger", _ledger(tmp_path, [R_A, R_B]))
    assert r.returncode == 0, f"精确一致应 PASS: {r.stdout}"
    assert "逐条与台账一致" in r.stdout


def test_ledger_fails_when_skip_grew(tmp_path: Path):
    """多一条 skip = 新增未登记，必须红。"""
    junit = _junit(
        tmp_path,
        [
            ("test_p1", "pass"),
            ("test_s1", "skip:原生引擎栈不可用"),
            ("test_s2", "skip:原生引擎栈不可用"),
            ("test_s3", "skip:原生引擎栈不可用"),
            ("test_s4", "skip:ComfyUI 不在线"),
        ],
    )
    r = _run("--junit", junit, "--ledger", _ledger(tmp_path, [R_A, R_B]))
    assert r.returncode == 1, f"skip 变多应被拦: {r.stdout}"
    assert "skip 总数 4 ≠ 台账期望 3" in r.stdout


def test_ledger_fails_when_skip_shrank(tmp_path: Path):
    """少一条 skip 同样红：已登记的 skip 悄悄消失也是台账失真（双向防漂移）。"""
    junit = _junit(
        tmp_path,
        [
            ("test_p1", "pass"),
            ("test_p2", "pass"),
            ("test_p3", "pass"),
            ("test_s1", "skip:原生引擎栈不可用"),
            ("test_s2", "skip:ComfyUI 不在线"),
        ],
    )
    r = _run("--junit", junit, "--ledger", _ledger(tmp_path, [R_A, R_B]))
    assert r.returncode == 1, f"skip 变少也应被拦: {r.stdout}"
    assert "skip 总数 2 ≠ 台账期望 3" in r.stdout
    assert "已登记的 skip 消失" in r.stdout


def test_ledger_fails_on_per_key_drift_with_same_total(tmp_path: Path):
    """总数刚好抵消（A 少一条、B 多一条）也要红——只看总数会被抹平。"""
    junit = _junit(
        tmp_path,
        [
            ("test_p1", "pass"),
            ("test_s1", "skip:原生引擎栈不可用"),
            ("test_s2", "skip:ComfyUI 不在线"),
            ("test_s3", "skip:ComfyUI 不在线"),
        ],
    )
    r = _run("--junit", junit, "--ledger", _ledger(tmp_path, [R_A, R_B]))
    assert r.returncode == 1, f"逐条漂移应被拦: {r.stdout}"
    assert "条数与台账不符" in r.stdout


def test_ledger_fails_on_unregistered_reason(tmp_path: Path):
    junit = _junit(
        tmp_path,
        [
            ("test_p1", "pass"),
            ("test_p2", "pass"),
            ("test_s1", "skip:原生引擎栈不可用"),
            ("test_s2", "skip:原生引擎栈不可用"),
            ("test_s3", "skip:冒出来的新理由"),
        ],
    )
    r = _run("--junit", junit, "--ledger", _ledger(tmp_path, [R_A, R_B]))
    assert r.returncode == 1, f"未登记原因应被拦: {r.stdout}"
    assert "未登记的 skip 原因" in r.stdout
    assert '"count": 1' in r.stdout  # 失败时打印可直接粘的更新表


def test_ledger_rejects_self_inconsistent_totals(tmp_path: Path):
    """台账自己前后矛盾（总数 ≠ 逐条之和）时不许静默按某一个跑。"""
    junit = _junit(tmp_path, [("test_p1", "pass"), ("test_s1", "skip:原生引擎栈不可用")])
    r = _run("--junit", junit, "--ledger", _ledger(tmp_path, [R_A], total=99))
    assert r.returncode != 0, f"自相矛盾台账应拒跑: {r.stdout}{r.stderr}"
    assert "自相矛盾" in (r.stdout + r.stderr)


def test_ledger_enforces_min_executed(tmp_path: Path):
    junit = _junit(
        tmp_path,
        [
            ("test_p1", "pass"),
            ("test_s1", "skip:原生引擎栈不可用"),
            ("test_s2", "skip:原生引擎栈不可用"),
            ("test_s3", "skip:ComfyUI 不在线"),
        ],
    )
    r = _run("--junit", junit, "--ledger", _ledger(tmp_path, [R_A, R_B], min_executed=50))
    assert r.returncode == 1, f"executed 不足应红: {r.stdout}"
    assert "执行出结论的用例 1 < 下限 50" in r.stdout
