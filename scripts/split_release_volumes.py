#!/usr/bin/env python3
"""GitHub Release 分卷切片脚本（任务书 P1-3.4）。

将单个大型发布归档（.7z/.zip）按字节顺序切分为 `<name>.001 / .002 / ...` 分卷，
按序拼接即可还原原文件；每卷写入后立即校验字节数；输出 `SHA256SUMS.txt`
全覆每卷哈希（格式 `{sha256}  {name}`，与 GNU sha256sum 兼容）。

用法:
    python scripts/split_release_volumes.py --input ImageMultiModel-Data.7z
    python scripts/split_release_volumes.py --input X.7z --max-bytes 900MB --out-dir dist
    python scripts/split_release_volumes.py --verify --input-dir dist

设计约束（对齐 SeedVR2 portable_bundle_lib.ps1）：
- GitHub Release 单文件硬上限 2 GiB；分卷名统一 `<archive>.001` 起，按序拼接还原。
- 只依赖 Python 3 标准库（hashlib/os/argparse），不引入新依赖（范围铁律）。
- 默认 900MB/卷（任务书要求 ≤900MB）；`--max-bytes` 支持 MB/GB 后缀。
- `--verify` 模式重新逐卷计算哈希并与 SHA256SUMS.txt 比对，发布后回读验证。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

CHUNK = 64 * 1024
DEFAULT_MAX_BYTES = 900 * 1024 * 1024  # 900MB


def parse_size(text: str) -> int:
    """解析体积参数：纯数字=字节；支持 KB/MB/GB 后缀（大小写不敏感）。"""
    t = text.strip().upper()
    mult = 1
    for suffix, m in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if t.endswith(suffix):
            mult = m
            t = t[: -len(suffix)].strip()
            break
    try:
        n = int(t)
    except ValueError:
        raise SystemExit(f"无法解析体积参数: {text!r}（支持 KB/MB/GB 后缀）")
    if n <= 0:
        raise SystemExit(f"体积参数必须为正数: {text!r}")
    return n * mult


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def split_volumes(src: Path, max_bytes: int, out_dir: Path) -> list[Path]:
    """顺序字节切片；每卷写完即校验字节数。返回分卷路径列表（.001 起）。"""
    if max_bytes < 1 * 1024 * 1024:
        raise SystemExit(f"--max-bytes 过小（{max_bytes}），至少 1MB")
    total = src.stat().st_size
    volumes: list[Path] = []
    idx = 1
    with open(src, "rb") as f:
        while True:
            vol = out_dir / f"{src.name}.{idx:03d}"
            remain = total - f.tell()
            if remain <= 0:
                break
            this = min(max_bytes, remain)
            written = 0
            with open(vol, "wb") as out:
                while written < this:
                    b = f.read(min(CHUNK, this - written))
                    if not b:
                        break
                    out.write(b)
                    written += len(b)
            if written != this:
                raise SystemExit(f"分卷 {vol.name} 写入不完整（{written}/{this} 字节）")
            volumes.append(vol)
            print(f"[split] {vol.name}  {written} 字节")
            idx += 1
    return volumes


def write_sums(volumes: list[Path], sums_file: Path) -> None:
    lines = []
    for v in volumes:
        lines.append(f"{sha256_of(v)}  {v.name}")
    sums_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[split] 已写入 {sums_file.name}（{len(lines)} 条）")


def verify_sums(in_dir: Path, sums_file: Path) -> bool:
    """逐卷重算哈希并与 SHA256SUMS.txt 比对；全部一致返回 True。"""
    if not sums_file.exists():
        print(f"[verify] 缺少 {sums_file.name}，无法校验")
        return False
    expected: dict[str, str] = {}
    for line in sums_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            print(f"[verify] 跳过异常行: {line!r}")
            continue
        expected[parts[1]] = parts[0].lower()
    if not expected:
        print("[verify] SHA256SUMS.txt 无有效条目")
        return False
    ok = True
    for name, want in sorted(expected.items()):
        p = in_dir / name
        if not p.exists():
            print(f"[verify] FAIL 缺失: {name}")
            ok = False
            continue
        got = sha256_of(p)
        if got == want:
            print(f"[verify] OK   {name}")
        else:
            print(f"[verify] FAIL {name}: 期望 {want[:16]}… 实际 {got[:16]}…")
            ok = False
    # 额外检查：目录中未被 sums 覆盖的分卷（防漏）
    for p in sorted(in_dir.iterdir()):
        if p.suffix.lstrip(".").isdigit() and p.name not in expected:
            print(f"[verify] WARN 未在 sums 中: {p.name}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description="GitHub Release 分卷切片与校验")
    ap.add_argument("--input", help="待分卷的归档文件（.7z/.zip）")
    ap.add_argument("--input-dir", help="verify 模式：分卷所在目录")
    ap.add_argument("--max-bytes", default="900MB", help="单卷上限（默认 900MB，支持 KB/MB/GB）")
    ap.add_argument("--out-dir", help="输出目录（默认与输入同目录）")
    ap.add_argument("--verify", action="store_true", help="校验模式：重算哈希比对 SHA256SUMS.txt")
    args = ap.parse_args()

    if args.verify:
        in_dir = Path(args.input_dir or ".")
        sums = in_dir / "SHA256SUMS.txt"
        sys.exit(0 if verify_sums(in_dir, sums) else 1)

    if not args.input:
        ap.error("--input 或 --verify 必须提供其一")
    src = Path(args.input).resolve()
    if not src.is_file():
        raise SystemExit(f"输入文件不存在: {src}")
    max_bytes = parse_size(args.max_bytes)
    out_dir = (Path(args.out_dir) if args.out_dir else src.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 清理同名前缀的旧分卷（幂等重跑）
    for p in out_dir.glob(f"{src.name}.*"):
        if p.suffix.lstrip(".").isdigit():
            p.unlink()

    volumes = split_volumes(src, max_bytes, out_dir)
    write_sums(volumes, out_dir / "SHA256SUMS.txt")
    total = sum(v.stat().st_size for v in volumes)
    print(f"[split] 完成：{len(volumes)} 卷，共 {total / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
