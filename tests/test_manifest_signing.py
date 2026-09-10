"""tests/test_manifest_signing.py — 完整性清单签名 + enforce 专项测试（任务书 P0）

覆盖任务书阶段一验收：
- 签名后回验 PASS + 公钥一致性闸门生效；
- 篡改清单 → 验签失败；enforce 下拒绝启动（RuntimeError）；
- 篡改代码哈希 → enforce 拒绝启动；
- HMAC 回退签名（开发机无 Ed25519 私钥时）；
- 行尾归一化未回归（Windows CRLF / Linux LF 哈希一致）；
- 密钥权限自愈（POSIX 0600；Windows 临时目录跳过 icacls）。

测试护栏：全部在 tmp_path 内构造清单/签名，不触碰仓库真实清单与签名文件。
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── 工具函数 ─────────────────────────────────────────────
def _load_selfcheck_module():
    import importlib.util

    path = PROJECT_ROOT / "app" / "integrated_app" / "security" / "integrity_selfcheck.py"
    spec = importlib.util.spec_from_file_location("_test_imm_selfcheck", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_secret_key_module():
    import importlib.util

    path = PROJECT_ROOT / "app" / "integrated_app" / "security" / "secret_key.py"
    spec = importlib.util.spec_from_file_location("_test_imm_secret_key", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_real_manifest(tmp_path: Path) -> Path:
    """复制仓库真实清单到 tmp（files 哈希仍指向真实代码，供 enforce 通过路径）。"""
    src = PROJECT_ROOT / "app" / "integrated_app" / "security" / "integrity_manifest.json"
    dst = tmp_path / "integrity_manifest.json"
    dst.write_bytes(src.read_bytes())
    return dst


@pytest.fixture
def sk_with_private_key():
    """提供 secret_key 模块；签发机私钥缺失时跳过（CI 没有私钥，属设计如此）。

    真实 Ed25519 签名（sign_manifest_ed25519 / _public_key_consistency_ok）依赖
    签发机私钥 `data/.manifest_signing_key` —— 它不得进入 CI checkout（否则攻击者
    拿到私钥就破解了完整性防线）。因此这些用例只在有能力签名的环境（本机/签发机/自托管）
    执行；CI 上跳过而非失败。其余用例（篡改后拒签、缺失清单、HMAC 回退、行尾归一化、
    权限自愈）不依赖私钥，照常全跑。
    """
    sk = _load_secret_key_module()
    if not sk.manifest_private_key_path().exists():
        pytest.skip(
            "清单签名私钥(data/.manifest_signing_key)仅签发机持有，未入库："
            "真实签名路径在具备私钥的环境验证，CI 跳过。"
        )
    return sk


# ── Ed25519 签名 / 验签 ──────────────────────────────────
class TestEd25519SignVerify:
    def test_sign_then_verify_roundtrip(self, tmp_path, sk_with_private_key):
        """真实私钥签名 → 内置公钥回验 PASS（构建期回验闸门）。"""
        sk = sk_with_private_key
        manifest = _copy_real_manifest(tmp_path)

        sig_path = sk.sign_manifest_ed25519(manifest)
        assert sig_path is not None and sig_path.exists()
        assert sk.verify_manifest_signature_ed25519(manifest) is True

    def test_tampered_manifest_verify_fails(self, tmp_path, sk_with_private_key):
        """篡改清单任意字节 → 验签失败（无私钥无法重签）。"""
        sk = sk_with_private_key
        manifest = _copy_real_manifest(tmp_path)
        sk.sign_manifest_ed25519(manifest)

        # 篡改：在 JSON 末尾追加空格（内容变化即哈希变化）
        original = manifest.read_bytes()
        manifest.write_bytes(original + b" ")
        assert sk.verify_manifest_signature_ed25519(manifest) is False
        # 还原后仍可验签（确认是内容变化导致）
        manifest.write_bytes(original)
        assert sk.verify_manifest_signature_ed25519(manifest) is True

    def test_sign_and_code_tamper_both_blocked(self, tmp_path, monkeypatch):
        """攻击者同时改代码 + 清单 → 无私钥无法重签 → enforce 拒绝启动（验收 ②）。"""
        selfcheck = _load_selfcheck_module()
        sk = _load_secret_key_module()

        # 构造"被同步篡改"的清单：哈希改为垃圾值（模拟代码+清单都被改，攻击者无密钥重签）
        manifest = tmp_path / "integrity_manifest.json"
        data = json.loads(
            (PROJECT_ROOT / "app" / "integrated_app" / "security" / "integrity_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        for k in data["files"]:
            data["files"][k] = "0" * 64
        manifest.write_text(json.dumps(data), encoding="utf-8")
        # 不签名（攻击者无私钥，无法重签）→ 验签失败 + 哈希失败双防线

        monkeypatch.setattr(selfcheck, "_get_manifest_path", lambda: manifest)
        with pytest.raises(RuntimeError, match="拒绝启动"):
            selfcheck.run_startup_selfcheck(enforce=True)

    def test_public_key_consistency_gate(self, sk_with_private_key):
        """公钥一致性闸门：私钥派生公钥 == 仓库内置公钥（GOTCHAS #97）。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_test_sign_script",
            PROJECT_ROOT / "scripts" / "sign_integrity_manifest.py",
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._public_key_consistency_ok() is True


# ── enforce 拒绝启动语义 ─────────────────────────────────
class TestEnforceSemantics:
    def test_enforce_passes_on_signed_clean_manifest(self, tmp_path, monkeypatch, sk_with_private_key):
        """签名有效 + 哈希一致 → enforce 不抛（发布版正常启动路径）。"""
        selfcheck = _load_selfcheck_module()
        sk = sk_with_private_key

        manifest = _copy_real_manifest(tmp_path)
        sk.sign_manifest_ed25519(manifest)
        monkeypatch.setattr(selfcheck, "_get_manifest_path", lambda: manifest)

        result = selfcheck.run_startup_selfcheck(enforce=True)
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert result["manifest_signed"] is True

    def test_enforce_rejects_unsigned_manifest(self, tmp_path, monkeypatch):
        """清单未签名 → enforce 拒绝启动（无签名 = 信任根不可信）。"""
        selfcheck = _load_selfcheck_module()
        manifest = _copy_real_manifest(tmp_path)  # 不签名
        monkeypatch.setattr(selfcheck, "_get_manifest_path", lambda: manifest)

        with pytest.raises(RuntimeError, match="缺少有效签名"):
            selfcheck.run_startup_selfcheck(enforce=True)

    def test_enforce_rejects_missing_manifest(self, tmp_path, monkeypatch):
        """清单缺失 → enforce 拒绝启动（不允许 skipped 裸奔）。"""
        selfcheck = _load_selfcheck_module()
        missing = tmp_path / "no_such_manifest.json"
        monkeypatch.setattr(selfcheck, "_get_manifest_path", lambda: missing)

        with pytest.raises(RuntimeError, match="拒绝启动"):
            selfcheck.run_startup_selfcheck(enforce=True)

    def test_enforce_rejects_hash_mismatch(self, tmp_path, monkeypatch):
        """哈希失配（代码被篡改 1 字节语义）→ enforce 拒绝启动。"""
        selfcheck = _load_selfcheck_module()
        sk = _load_secret_key_module()

        manifest = _copy_real_manifest(tmp_path)
        sk.sign_manifest_ed25519(manifest)
        # 篡改清单中某文件哈希（模拟代码被改后攻击者无法同步改已签名清单）
        data = json.loads(manifest.read_text(encoding="utf-8"))
        first = next(iter(data["files"]))
        data["files"][first] = "1" * 64
        manifest.write_text(json.dumps(data), encoding="utf-8")
        # 篡改后签名失效，但验签失败已被 enforce 拦截；此处再确认哈希路径同样拦
        monkeypatch.setattr(selfcheck, "_get_manifest_path", lambda: manifest)
        with pytest.raises(RuntimeError):
            selfcheck.run_startup_selfcheck(enforce=True)

    def test_non_enforce_warns_but_does_not_raise(self, tmp_path, monkeypatch):
        """enforce=False（开发/CI）时验签失败仅告警不阻断（兼容裸 CI）。"""
        selfcheck = _load_selfcheck_module()
        manifest = _copy_real_manifest(tmp_path)  # 不签名
        monkeypatch.setattr(selfcheck, "_get_manifest_path", lambda: manifest)

        result = selfcheck.run_startup_selfcheck(enforce=False)
        assert result["manifest_signed"] is False


# ── HMAC 回退签名（开发机路径）───────────────────────────
class TestHmacFallback:
    def test_hmac_sign_verify_roundtrip(self, tmp_path):
        sk = _load_secret_key_module()
        payload = tmp_path / "payload.bin"
        payload.write_bytes(b"hello manifest")

        key = b"\x11" * 32
        sig_path = sk.sign_file(payload, key=key)
        assert sig_path is not None and sig_path.exists()
        assert sk.verify_file_signature(payload, key=key) is True

        # 篡改内容 → 校验失败
        payload.write_bytes(b"hello manifest!")
        assert sk.verify_file_signature(payload, key=key) is False

    def test_hmac_wrong_key_fails(self, tmp_path):
        sk = _load_secret_key_module()
        payload = tmp_path / "payload.bin"
        payload.write_bytes(b"data")
        sk.sign_file(payload, key=b"\x01" * 32)
        assert sk.verify_file_signature(payload, key=b"\x02" * 32) is False


# ── 行尾归一化未回归 ─────────────────────────────────────
class TestLineEndingNormalization:
    def test_crlf_lf_same_hash(self, tmp_path):
        """同一内容 CRLF 与 LF 哈希一致（跨平台稳定性资产不得回归）。"""
        selfcheck = _load_selfcheck_module()

        crlf = tmp_path / "a_crlf.py"
        lf = tmp_path / "a_lf.py"
        content = "def f():\n    return 1\n"
        crlf.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))
        lf.write_bytes(content.encode("utf-8"))

        assert selfcheck._compute_file_sha256(crlf) == selfcheck._compute_file_sha256(lf)


# ── 密钥权限自愈 ─────────────────────────────────────────
class TestPermissionSelfHeal:
    def test_harden_posix_permissions(self, tmp_path, monkeypatch):
        """POSIX 路径：宽权限文件收紧为 0600。"""
        sk = _load_secret_key_module()
        if os.name == "nt":
            pytest.skip("POSIX 权限语义仅在非 Windows 生效")

        keyfile = tmp_path / ".test_secret"
        keyfile.write_text("00" * 32, encoding="utf-8")
        os.chmod(keyfile, 0o644)
        assert sk.harden_secret_file_permissions(keyfile) is True
        mode = stat.S_IMODE(keyfile.stat().st_mode)
        assert mode == 0o600

    def test_harden_temp_dir_skips_icacls_windows(self, tmp_path, monkeypatch):
        """Windows 临时目录内跳过 icacls（测试护栏，不破坏 pytest 临时目录回收）。"""
        sk = _load_secret_key_module()
        if os.name != "nt":
            pytest.skip("Windows icacls 语义仅在 Windows 生效")

        keyfile = tmp_path / ".test_secret"
        keyfile.write_text("00" * 32, encoding="utf-8")
        # TEMP 指向 tmp_path 时，icacls 分支被跳过且返回 True（不抛异常）
        monkeypatch.setenv("TEMP", str(tmp_path))
        assert sk.harden_secret_file_permissions(keyfile) is True
