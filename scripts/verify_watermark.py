"""
scripts/verify_watermark.py — 输出数字水印溯源验证（PRD §8.6 / §10.5 STEP 6）

用法:
    python scripts/verify_watermark.py outputs/xxx.png            # PNG 需 pillow
    python scripts/verify_watermark.py path/to/array.npy          # numpy 数组
    python scripts/verify_watermark.py -p product_id 图像路径     # 校验指定 product_id

提取的 payload 格式: {product_id}|{task_id}|{timestamp}
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bin.integrated_app import watermark  # noqa: E402

# Windows 控制台默认 GBK 无法编码 ✅/❌ → 强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_array(path: str) -> np.ndarray:
    p = Path(path)
    if p.suffix.lower() in (".npy",):
        return np.load(p)
    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
        try:
            from PIL import Image  # pillow
        except ImportError as e:
            raise SystemExit("需安装 pillow 才能读取图片: pip install Pillow") from e
        img = Image.open(p).convert("RGB")
        return np.asarray(img, dtype=np.float64)
    raise SystemExit(f"不支持的输入格式: {p.suffix}")


def decode_payload(bits: list[int]) -> str:
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        out.append(byte)
    return out.decode("utf-8", errors="replace").rstrip("\x00")


def main() -> int:
    ap = argparse.ArgumentParser(description="验证 Image MultiModel 输出数字水印")
    ap.add_argument("image", help="图片/数组路径")
    ap.add_argument("-p", "--product-id", default="img_multimodel", help="期望的 product_id")
    ap.add_argument("-n", "--n-bits", type=int, default=400, help="尝试提取的比特数（默认 400，覆盖完整载荷 ~368bit）")
    args = ap.parse_args()

    arr = load_array(args.image)
    bits = watermark.extract_watermark(arr, args.n_bits)
    payload = decode_payload(bits)

    print("=== 水印溯源验证 ===")
    print(f"输入     : {args.image}")
    print(f"载荷     : {payload}")
    if "|" in payload:
        pid, task_id, ts = payload.split("|", 2)
        print(f"product_id: {pid}")
        print(f"task_id   : {task_id}")
        print(f"timestamp : {ts}")
        ok = pid == args.product_id
        print("校验     : ✅ 匹配 product_id" if ok else "校验     : ❌ product_id 不匹配")
        return 0 if ok else 1
    print("校验     : ❌ 未提取到有效载荷")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
