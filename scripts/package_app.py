#!/usr/bin/env python3
"""桌面增量更新应用包打包脚本（任务书 P1-3.5 发布侧支撑，报告1 阶段5）。

将 L2 应用代码（分层定案 docs/桌面分发分层定案-20260910.md）打包为
`app-v{version}.zip`（zip 根即 app/ 内容，供 updater.rs 解压到 app.new/），
同时生成 `app/version.json`（增量更新版本依据）、`app-v{version}.zip.sha256`
与 Ed25519 签名 `app-v{version}.zip.sig.ed25519`（复用清单签名密钥对）。

用法:
    python scripts/package_app.py                 # 默认打包到 release/packages/
    python scripts/package_app.py --out-dir dist  # 指定输出目录

打包范围（决策留痕于《执行对照表》P1-3.5）：
- 含：app/integrated_app、app/static、app/templates、config.yaml、bin/、
  requirements*.txt、LICENSE/NOTICE/SECURITY/PRIVACY_POLICY/USER_AGREEMENT/THIRD_PARTY_NOTICES.md
- 排除：data/ model/ logs/ outputs/ pretrained_models/ comfy_kernel/ desktop/ docs/ tests/
  release/ backups/ demo/ screenshots/ .venv/ 缓存/密钥（.watermark_key .env
  data/.manifest_signing_key）/ 构建产物
- 不打包 scripts/（运行时非必需；诊断脚本由仓库/发布附随提供）
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.integrated_app.security.secret_key import sign_manifest_ed25519  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

EXCLUDE_DIRS = {
    "data",
    "model",
    "logs",
    "outputs",
    "pretrained_models",
    "comfy_kernel",
    "desktop",
    "docs",
    "tests",
    "release",
    "backups",
    "demo",
    "screenshots",
    ".venv",
    "__pycache__",
    ".git",
    ".github",
    ".githooks",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hypothesis",
    ".pytest_tmp",
    ".workbuddy",
    ".workbuddy-ai",
    ".zcode",
    ".trae",
}
EXCLUDE_FILES = {
    ".watermark_key",
    ".env",
    "coverage.xml",
    ".dockerignore",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

# 根级额外包含项（不在 app/ 下的运行时必需）
ROOT_EXTRA = [
    "config.yaml",
    "requirements.txt",
    "requirements-lock.txt",
    "LICENSE",
    "NOTICE",
    "SECURITY.md",
    "PRIVACY_POLICY.md",
    "USER_AGREEMENT.md",
    "THIRD_PARTY_NOTICES.md",
]


def app_version() -> str:
    import yaml

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    v = cfg.get("version")
    if not isinstance(v, str) or not v:
        raise SystemExit(f"config.yaml 缺少权威版本位 version（当前: {v!r}）")
    return v


def _collect(root: Path, exclude_dirs: set[str]) -> list[Path]:
    """收集 root 下所有应打包文件（相对路径）。"""
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(root)
        parts = rel.parts
        if any(part in exclude_dirs for part in parts[:-1]):
            continue
        if rel.name in EXCLUDE_FILES or p.suffix in EXCLUDE_SUFFIXES:
            continue
        files.append(p)
    return files


def build_payload(tmp: Path) -> None:
    """把 L2 内容组装到 tmp/（zip 根目录）。"""
    # 1. app/ 下的 Python 包（integrated_app 内含 static/templates 前端）
    src = APP / "integrated_app"
    if not src.exists():
        raise SystemExit(f"缺少必需目录: {src}")
    _copy_tree(src, tmp / "integrated_app")

    # 2. bin/（clean_launch.py 启动器）
    if (ROOT / "bin").exists():
        _copy_tree(ROOT / "bin", tmp / "bin")

    # 3. 根级合规/配置文本
    for name in ROOT_EXTRA:
        src = ROOT / name
        if src.is_file():
            import shutil

            shutil.copy2(src, tmp / name)

    # 4. version.json（config.yaml 权威位）
    v = app_version()
    (tmp / "version.json").write_text(
        __import__("json").dumps(
            {
                "version": v,
                "release_date": __import__("datetime").date.today().isoformat(),
                "minimum_shell_version": "1.0.0",
                "changelog": "桌面增量更新",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _copy_tree(src: Path, dst: Path) -> None:
    import shutil

    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def make_zip(tmp: Path, out: Path) -> Path:
    """zip 根即 tmp 内容（增量更新解压到 app.new/ 的形态）。"""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(tmp.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(tmp))
    return out


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="增量更新应用包打包（L2 app/）")
    ap.add_argument("--out-dir", default=str(ROOT / "release" / "packages"))
    ap.add_argument("--keep-tmp", action="store_true", help="保留组装中间目录（调试）")
    ap.add_argument(
        "--no-sign",
        action="store_true",
        help="跳过 Ed25519 签名（仅调试用；发布物必须签名）",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    v = app_version()

    tmp = ROOT / ".package_tmp"
    import shutil

    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        build_payload(tmp)
        zip_path = out_dir / f"app-v{v}.zip"
        make_zip(tmp, zip_path)
        digest = sha256_of(zip_path)
        (out_dir / f"app-v{v}.zip.sha256").write_text(f"{digest}  app-v{v}.zip\n", encoding="utf-8")
        if args.no_sign:
            print("[package] 跳过 Ed25519 签名（--no-sign，调试模式）")
        else:
            sig_path = sign_manifest_ed25519(zip_path)
            if sig_path is None:
                print(
                    "[package] FAIL: Ed25519 签名未生成（私钥/依赖缺失），发布物必须签名",
                    file=sys.stderr,
                )
                return 2
            print(f"[package] Ed25519 签名: {sig_path.name}（{sig_path.stat().st_size} B）")
        n = sum(1 for _ in tmp.rglob("*") if _.is_file())
        print(f"[package] {zip_path.name}  {zip_path.stat().st_size / 1024 / 1024:.2f} MB（{n} 文件）")
        print(f"[package] SHA256: {digest}")
        print(f"[package] 版本: {v}（config.yaml 权威位）")
    finally:
        if not args.keep_tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
