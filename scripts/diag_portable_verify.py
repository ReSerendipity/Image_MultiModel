#!/usr/bin/env python3
"""桌面安装环境诊断脚本（任务书 P2 诊断，参考 SeedVR2 diag_portable_verify.py）。

在安装/便携目录内直接调用与服务器启动自检相同的验签与完整性检查链路，
逐环节打印：
- cryptography 是否可 import 及版本；
- 清单 / Ed25519 签名 / 公钥文件是否存在；
- 清单验签结果（Ed25519→HMAC 回退语义）；
- 完整性自检全量结果（failed 数 / manifest_signed / skipped）；
- enforce 配置是否生效（config.yaml security.integrity_selfcheck.enforce）。

用法:
    <python> scripts/diag_portable_verify.py [--app-dir <安装目录/app>]
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import os
import sys

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        with contextlib.suppress(OSError, ValueError):
            _stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="桌面安装环境验签/完整性诊断")
    parser.add_argument(
        "--app-dir",
        default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        help="应用代码根（默认本仓库根；安装环境为 <安装目录>/app）",
    )
    args = parser.parse_args()

    app_dir = os.path.abspath(args.app_dir)
    sys.path.insert(0, app_dir)
    sec = os.path.join(app_dir, "app", "integrated_app", "security")
    manifest = os.path.join(sec, "integrity_manifest.json")
    sig = manifest + ".sig.ed25519"
    pub = os.path.join(sec, "manifest_signing_public_key.pem")
    config_yaml = os.path.join(app_dir, "config.yaml")

    try:
        import cryptography

        print(f"[diag] cryptography {cryptography.__version__} import OK")
    except Exception as e:  # noqa: BLE001
        print(f"[diag] cryptography import FAIL: {e!r}")
        return 1

    for label, path in (("manifest", manifest), ("sig", sig), ("pub", pub)):
        print(f"[diag] {label} exists={os.path.exists(path)} path={path}")

    try:
        from app.integrated_app.security.secret_key import (  # noqa: PLC0415
            verify_manifest_signature_ed25519,
        )

        result = verify_manifest_signature_ed25519(manifest)
        print(f"[diag] MANIFEST_VERIFY={result}")
        if not result:
            return 2
    except Exception as e:  # noqa: BLE001
        print(f"[diag] VERIFY_EXC: {type(e).__name__}: {e!r}")
        return 3

    # 完整性自检全量（与启动 selfcheck 同链路）
    try:
        from app.integrated_app.security.integrity_selfcheck import run_startup_selfcheck  # noqa: PLC0415

        report = run_startup_selfcheck(enforce=False)
        print(
            "[diag] SELFCHECK failed={} skipped={} manifest_signed={}".format(
                report.get("failed"),
                report.get("skipped"),
                report.get("manifest_signed"),
            )
        )
    except Exception as e:  # noqa: BLE001
        print(f"[diag] SELFCHECK_EXC: {type(e).__name__}: {e!r}")
        return 4

    # enforce 配置
    try:
        import yaml

        with open(config_yaml, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        enforce = (cfg or {}).get("security", {}).get("integrity_selfcheck", {}).get("enforce")
        print(f"[diag] ENFORCE_CONFIG={enforce!r}（True=签名/哈希失败拒启动）")
    except Exception as e:  # noqa: BLE001
        print(f"[diag] CONFIG_READ_EXC: {type(e).__name__}: {e!r}")
        return 5

    # 增量包 Ed25519 签名（收口项：发布门禁外的便携诊断第二道）
    pkgs_dir = os.path.join(app_dir, "release", "packages")
    zips = sorted(glob.glob(os.path.join(pkgs_dir, "app-v*.zip")))
    if not zips:
        print(f"[diag] PACKAGE_SIG: 无增量包（{pkgs_dir}），跳过")
    else:
        bad = 0
        for z in zips:
            s = z + ".sig.ed25519"
            name = os.path.basename(z)
            if not os.path.exists(s):
                print(f"[diag] PACKAGE_SIG: {name} FAIL（缺少 .sig.ed25519）")
                bad += 1
                continue
            try:
                ok = verify_manifest_signature_ed25519(z)
            except Exception as e:  # noqa: BLE001
                print(f"[diag] PACKAGE_SIG: {name} 验签异常 {type(e).__name__}: {e!r}")
                bad += 1
                continue
            print(f"[diag] PACKAGE_SIG: {name} {'PASS' if ok else 'FAIL'}")
            if not ok:
                bad += 1
        if bad:
            print("[diag] PACKAGE_SIG_FAIL")
            return 6

    print("[diag] ALL_CHECKS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
