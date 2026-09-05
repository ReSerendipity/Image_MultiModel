"""tests/test_integrity_manifest_gate.py — 完整性清单新鲜度门禁测试（GOTCHAS #15）

门禁脚本 ``scripts/check_integrity_manifest.py`` 的行为锁定：
1. 当前仓库清单与检出代码一致 → exit 0；
2. 自检模块不可用 / 异常 → exit 1（fail-closed，绝不静默放行）。

负向「哈希失配」路径不在这里对真实清单做篡改演练（避免测试崩溃时留下
损坏的 tracked 清单），由 CI 门禁步骤本身承担该职责；此处只锁定门禁的
接口契约与 fail-closed 语义。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "scripts" / "check_integrity_manifest.py"


def _run(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *extra],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO_ROOT,
    )


def test_gate_passes_on_current_tree():
    """仓库当前清单必须与检出代码一致（清单过期入库即在此拦截）。"""
    r = _run()
    assert r.returncode == 0, f"门禁应 PASS: {r.stdout}\n{r.stderr}"
    assert "[PASS]" in r.stdout
    assert "33/33" in r.stdout


def test_gate_fails_closed_when_selfcheck_missing():
    """自检模块不存在时必须 fail-closed（exit 1），不得静默放行。"""
    r = _run("--selfcheck", str(REPO_ROOT / "scripts" / "__no_such_selfcheck__.py"))
    assert r.returncode == 1
    assert "[FAIL]" in r.stdout


def test_gate_fails_closed_on_broken_selfcheck(tmp_path: Path):
    """自检模块语法损坏时必须 fail-closed（exit 1）。"""
    broken = tmp_path / "integrity_selfcheck.py"
    broken.write_text("raise RuntimeError('broken selfcheck')\n", encoding="utf-8")
    r = _run("--selfcheck", str(broken))
    assert r.returncode == 1
    assert "[FAIL]" in r.stdout
