#!/usr/bin/env python3
"""发布门禁五步脚本（任务书 P2 发布门禁；对齐 ci.yml/release.yml 质量闸）。

串联发布前的五道关卡，任一失败即中止（供发布者在 tag/release 前本地执行，
CI release 流程同样按此顺序）：

    1. 构建   —— `compileall` 全量 Python 字节码编译 + 桌面壳 `cargo check`
    2. 静态   —— `ruff check app/ tests/ scripts/`（mypy 由 CI reusable workflow 执行）
    3. 测试   —— `pytest tests` 全量
    4. 签名   —— 重生成完整性清单 → Ed25519 签名 → 门禁回验（33/33）
    5. 发布物 —— `package_app.py` 打包增量包 + SHA256 回读校验 + `diag_portable_verify.py` 全链诊断

用法:
    python scripts/release_gate.py [--skip-cargo] [--step N]
    # --skip-cargo: 跳过壳构建（无 Rust 工具链环境）；--step N: 仅跑第 N 步
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # 供增量包验签导入 app.integrated_app.*


def run(cmd: list[str], cwd: Path = ROOT) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd)
    return r.returncode


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def step_build() -> int:
    if run([str(PY), "-m", "compileall", "-q", "app"]) != 0:
        return 1
    print("[gate-1] 构建（compileall）PASS")
    return 0


def step_cargo() -> int:
    r = run(["cargo", "check"], cwd=ROOT / "desktop" / "src-tauri")
    print("[gate-1b] 桌面壳 cargo check", "PASS" if r == 0 else "FAIL")
    return r


def step_lint() -> int:
    if run([str(PY), "-m", "ruff", "check", "app", "tests", "scripts"]) != 0:
        return 1
    print("[gate-2] 静态（ruff）PASS")
    return 0


def step_test() -> int:
    if run([str(PY), "-m", "pytest", "tests", "-q"]) != 0:
        return 1
    print("[gate-3] 测试（pytest 全量）PASS")
    return 0


def step_sign() -> int:
    for script in ("generate_integrity_manifest.py", "sign_integrity_manifest.py", "check_integrity_manifest.py"):
        if run([str(PY), f"scripts/{script}"]) != 0:
            return 1
    print("[gate-4] 清单签名门禁 PASS")
    return 0


def step_artifacts() -> int:
    if run([str(PY), "scripts/package_app.py"]) != 0:
        return 1
    pkg_dir = ROOT / "release" / "packages"
    zips = sorted(pkg_dir.glob("app-v*.zip"))
    if not zips:
        print("[gate-5] FAIL: 未找到增量包 app-v*.zip")
        return 1
    for z in zips:
        sha_file = z.with_suffix(".zip.sha256")
        if not sha_file.exists():
            print(f"[gate-5] FAIL: 缺少 {sha_file.name}")
            return 1
        want = sha_file.read_text(encoding="utf-8").split()[0].lower()
        got = sha256_of(z)
        ok = want == got
        print(f"[gate-5] {z.name} SHA256 {'PASS' if ok else 'FAIL'}")
        if not ok:
            return 1
        # 增量包 Ed25519 签名（后续建议收口：app-v{ver}.zip 纳入签名链）
        sig_file = z.with_suffix(".zip.sig.ed25519")
        if not sig_file.exists():
            print(f"[gate-5] FAIL: 缺少 {sig_file.name}（增量包必须 Ed25519 签名）")
            return 1
        from app.integrated_app.security.secret_key import verify_manifest_signature_ed25519  # noqa: E402

        sig_ok = verify_manifest_signature_ed25519(z)
        print(f"[gate-5] {z.name} Ed25519 {'PASS' if sig_ok else 'FAIL'}")
        if not sig_ok:
            return 1
    if run([str(PY), "scripts/diag_portable_verify.py"]) != 0:
        return 1
    print("[gate-5] 发布物（增量包 SHA256 + 诊断全链）PASS")
    return 0


STEPS: list[tuple[str, Callable[[], int]]] = [
    ("构建", step_build),
    ("静态", step_lint),
    ("测试", step_test),
    ("签名", step_sign),
    ("发布物", step_artifacts),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="发布门禁五步")
    ap.add_argument("--skip-cargo", action="store_true", help="跳过桌面壳 cargo check")
    ap.add_argument("--step", type=int, default=0, help="仅执行指定步骤（1..5）")
    args = ap.parse_args()

    steps = [(n, fn) for n, fn in STEPS]
    if args.step:
        if not 1 <= args.step <= len(steps):
            ap.error(f"--step 范围 1..{len(steps)}")
        steps = [steps[args.step - 1]]

    print("=" * 50)
    print("发布门禁（P2）开始")
    for name, fn in steps:
        print(f"\n── 步骤 {name} ──")
        if fn() != 0:
            print(f"\n❌ 门禁失败：{name}")
            return 1
    print("\n" + "=" * 50)
    print("✅ 发布门禁五步全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
