#!/usr/bin/env python3
"""为核心模块完整性清单生成/校验签名（任务书 P0：Ed25519 优先，HMAC 兼容）。

背景：integrity_manifest.json 与被校验代码同目录，攻击者若能改代码就能
同步改清单，"启动自检"即被绕过。签名把信任根外移：
- 发布版（推荐）：签发机用 Ed25519 私钥（data/.manifest_signing_key）签发，
  发布包内置公钥验证（用户端可验签、不持有私钥，enforce 才能成立）；
- 开发机：无 Ed25519 私钥时回退 HMAC-SHA256（data/.imm_secret）。

签名后立即用内置公钥回验，错配即 fail（GOTCHAS #97 密钥配套闸门）；
构建期断言 payload 公钥 == 仓库公钥 SHA256 一致。

用法：
    # 首次（签发机）：生成密钥对（私钥不进包，公钥内置）
    python scripts/generate_manifest_signing_key.py

    # 代码更新后：重新生成清单 → 签名
    python scripts/generate_integrity_manifest.py
    python scripts/sign_integrity_manifest.py

    # 校验（CI / 运维巡检）
    python scripts/sign_integrity_manifest.py --verify

退出码：
    0 成功；1 校验失败或文件缺失。
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        with contextlib.suppress(OSError, ValueError):
            _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.integrated_app.security.secret_key import (  # noqa: E402
    get_secret_key,
    manifest_private_key_path,
    manifest_public_key_path,
    sign_file,
    sign_manifest_ed25519,
    signature_path_for,
    verify_file_signature,
    verify_manifest_signature_ed25519,
)

MANIFEST_PATH = os.path.join("app", "integrated_app", "security", "integrity_manifest.json")


def _public_key_consistency_ok() -> bool:
    """构建期断言：私钥派生的公钥 == 仓库内置公钥（SHA256 一致）。

    GOTCHAS #97 配套闸门：密钥配套是双向的，光有"能签名"不够，要证明
    "签出来能被自己的公钥验过"。私钥派生公钥与内置公钥文件哈希一致，
    错配直接 fail（CI Secret 里的私钥与仓库公钥不是一对时立即暴露）。
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] Ed25519 依赖不可用，无法做公钥一致性断言: {e}")
        return False

    priv_path = manifest_private_key_path()
    pub_path = manifest_public_key_path()
    if not priv_path.exists() or not pub_path.exists():
        print("[FAIL] 私钥或内置公钥缺失，无法做一致性断言")
        return False

    try:
        private_key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            print("[FAIL] 私钥非 Ed25519")
            return False
        # 用 DER 公钥比对（绕开 PEM 行尾/编码差异）：Windows 文本模式写出的
        # 公钥 PEM 可能是 CRLF，字节级 SHA256 会因行尾漂移误报不配套
        derived_der = private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        repo_key = serialization.load_pem_public_key(pub_path.read_bytes())
        if not isinstance(repo_key, ed25519.Ed25519PublicKey):
            print("[FAIL] 仓库公钥非 Ed25519")
            return False
        repo_der = repo_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        ok = derived_der == repo_der
        if not ok:
            print("[FAIL] 公钥一致性闸门：私钥派生公钥与仓库内置公钥不一致（密钥不配套）")
        return ok
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] 公钥一致性断言异常: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="完整性清单签名 / 校验")
    parser.add_argument("--manifest", default=MANIFEST_PATH, help="清单文件路径")
    parser.add_argument("--verify", action="store_true", help="校验模式（默认签名模式）")
    args = parser.parse_args()

    if not os.path.exists(args.manifest):
        print(f"[FAIL] 清单文件不存在: {args.manifest}")
        print("       先运行 `python scripts/generate_integrity_manifest.py` 生成")
        return 1

    if args.verify:
        if verify_manifest_signature_ed25519(args.manifest):
            print(f"[PASS] 清单 Ed25519 签名有效: {args.manifest}")
            return 0
        if verify_file_signature(args.manifest):
            print(f"[PASS] 清单 HMAC 签名有效: {args.manifest}")
            return 0
        sig_ed = f"{args.manifest}.sig.ed25519"
        sig_hmac = signature_path_for(args.manifest)
        if not os.path.exists(sig_ed) and not os.path.exists(sig_hmac):
            print(f"[FAIL] 缺少签名文件（{sig_ed} 或 {sig_hmac}），请先执行签名")
        else:
            print(f"[FAIL] 清单签名无效（内容已变更或密钥不匹配）: {args.manifest}")
        return 1

    # 签名模式：Ed25519 优先（发布版），无私钥回退 HMAC（开发机）
    if manifest_private_key_path().exists():
        # 公钥一致性闸门先行：CI Secret 私钥与仓库公钥不配套时立即 fail
        if not _public_key_consistency_ok():
            return 1
        sig_path = sign_manifest_ed25519(args.manifest)
        if sig_path is None:
            print("[FAIL] Ed25519 签名写入失败")
            return 1
        # 签名后立即用内置公钥回验——密钥错配或签名写入异常在构建期立刻暴露
        if not verify_manifest_signature_ed25519(args.manifest):
            print("[FAIL] Ed25519 签名回验失败：私钥与内置公钥不匹配或签名文件异常")
            print("       请检查 data/.manifest_signing_key 与 security/manifest_signing_public_key.pem 是否配套")
            return 1
        print(f"[OK] 已签名(Ed25519): {args.manifest} -> {sig_path}")
        return 0

    key = get_secret_key()
    if not key:
        print("[FAIL] 无法获取签名密钥（Ed25519 私钥或 HMAC 密钥均不可用）")
        return 1

    sig_path = sign_file(args.manifest, key)
    if not sig_path:
        print("[FAIL] 签名写入失败")
        return 1
    print(f"[OK] 已签名(HMAC，开发模式): {args.manifest} -> {sig_path}")
    print("    提示：发布构建请先生成 Ed25519 密钥对（scripts/generate_manifest_signing_key.py）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
