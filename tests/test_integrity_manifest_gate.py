"""tests/test_integrity_manifest_gate.py — 完整性清单新鲜度门禁测试（GOTCHAS #15）

门禁脚本 ``scripts/check_integrity_manifest.py`` 的行为锁定：
1. 当前仓库清单与检出代码一致且签名有效 → exit 0；
2. 自检模块不可用 / 异常 → exit 1（fail-closed，绝不静默放行）；
3. 哈希全对但清单未签名 → exit 1（与运行时 enforce=true 的拒绝启动口径一致）。

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


def test_gate_fails_when_manifest_hash_ok_but_unsigned(tmp_path: Path):
    """哈希全对、但清单未签名 → 仍必须 exit 1。

    自检在 enforce=false 时只把验签失败记为告警、不计入 failed，所以门禁若
    只看 total/passed/failed/skipped 就会放行未签名清单；而运行时
    config.yaml security.integrity_selfcheck.enforce=true 会拒绝启动。
    本用例锁定 CI 门禁与运行时口径一致（防「同步篡改代码与清单」的投毒路径）。
    """
    fake = tmp_path / "integrity_selfcheck.py"
    fake.write_text(
        "def run_startup_selfcheck(*args, **kwargs):\n"
        "    return {\n"
        "        'total': 33,\n"
        "        'passed': 33,\n"
        "        'failed': 0,\n"
        "        'skipped': 0,\n"
        "        'failed_files': [],\n"
        "        'manifest_signed': False,\n"
        "    }\n",
        encoding="utf-8",
    )
    r = _run("--selfcheck", str(fake))
    assert r.returncode == 1, f"未签名清单应被拦截: {r.stdout}"
    assert "signed=False" in r.stdout
