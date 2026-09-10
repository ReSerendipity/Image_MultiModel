#!/usr/bin/env python3
"""生成清单签名密钥对（任务书 P0：构建机私钥签发 / 发布包内置公钥验证）。

背景：完整性清单 HMAC 签名要求用户端持有密钥才能验签，而密钥进包即公开
可伪造——发布版 enforce 校验因此无法成立。本脚本生成 Ed25519 密钥对：
- 私钥：data/.manifest_signing_key（仅签发机持有，发布包排除，绝不分发）
- 公钥：app/integrated_app/security/manifest_signing_public_key.pem（随代码内置，
  公开无害，用户端用它验证清单签名）

用法：
    # 首次生成（签发机/CI 签名 job）
    python scripts/generate_manifest_signing_key.py

    # 轮换签发身份（会令旧发布清单验签失败，务必先重签再发布）
    python scripts/generate_manifest_signing_key.py --force

配套（任务书阶段一）：
    1. 私钥 base64 → GitHub Secret MANIFEST_SIGNING_KEY_B64（gh secret set）
    2. 离线备份私钥后，不在多处留存副本
    3. 公钥随仓库入库（security/manifest_signing_public_key.pem）
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.integrated_app.security.secret_key import (  # noqa: E402
    generate_manifest_signing_keypair,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成清单签名密钥对")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的私钥（轮换签发身份）")
    args = parser.parse_args()

    try:
        priv_path, pub_path = generate_manifest_signing_keypair(force=args.force)
    except FileExistsError as e:
        print(f"[FAIL] {e}")
        return 1

    print(f"[OK] 清单签名私钥: {priv_path}")
    print(f"[OK] 内置公钥:     {pub_path}")
    print("注意:")
    print("  1. 私钥仅存签发机 + CI Secret，发布包构建已把它列入排除清单（data/.manifest_signing_key）；")
    print("  2. 请离线备份私钥（丢失后无法重签旧清单、无法维持后续发布验签链）；")
    print("  3. 轮换私钥会令旧发布清单验签失败，需同步重签存量清单再发布。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
