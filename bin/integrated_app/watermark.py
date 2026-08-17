"""
watermark.py — DCT 频域不可感知数字水印（PRD §8.6 / 附录 E）

嵌入 product_id + task_id + timestamp 溯源信息到图像 DCT 中频系数，
提取时可还原。仅依赖 numpy（DCT 用纯 numpy 实现，不依赖 scipy/pillow）。

设计：
- 将图像视为 2D float 数组（调用方负责 PNG↔array 转换，可用 pillow 或任意解码器）
- 每 1 bit 占用一个 8x8 块的中频系数 (4,3)，按量化步长 q 加性嵌入（符号编码）
- 提取时读取该系数符号还原 bit

不可感知性：q 取块能量的较小比例，视觉差异 < 1/255 量级。
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import math
import os
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ── 水印参数 ─────────────────────────────────────────────
BLOCK = 8                 # DCT 块大小
COEF_RC = (4, 3)          # 中频嵌入系数位置
QUANT_RATIO = 0.05        # 量化步长相对块能量比例（越小越不可感知）
MIN_Q = 8.0               # 量化步长下限（≥8 才能在 uint8/PNG 量化噪声下保持符号稳定）
MAX_Q = 16.0              # 量化步长上限（约束像素扰动，保证不可感知）


# ── DCT-II 基矩阵（8x8）─────────────────────────────────
def _dct_matrix(n: int = BLOCK) -> np.ndarray:
    c = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(n):
            if i == 0:
                c[i, j] = math.sqrt(1.0 / n)
            else:
                c[i, j] = math.sqrt(2.0 / n) * math.cos(math.pi * (2 * j + 1) * i / (2 * n))
    return c


_D = _dct_matrix()
_DT = _D.T


def _dct2(block: np.ndarray) -> np.ndarray:
    return _D @ block @ _DT


def _idct2(coef: np.ndarray) -> np.ndarray:
    return _DT @ coef @ _D


# ── 比特编解码 ──────────────────────────────────────────
def _str_to_bits(s: str) -> list[int]:
    bits: list[int] = []
    for ch in s.encode("utf-8"):
        for i in range(7, -1, -1):
            bits.append((ch >> i) & 1)
    return bits


def _bits_to_str(bits: list[int]) -> str:
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        out.append(byte)
    return out.decode("utf-8", errors="replace")


def _payload_string(product_id: str, task_id: str, ts: float) -> str:
    return f"{product_id}|{task_id}|{int(ts)}"


# ── 密钥签名（v2）────────────────────────────────────────
# 载荷格式（签名版）: "<product_id>|<task_id>|<ts>|<hmac-sha256 hex>"
# 未配置密钥时嵌入未签名载荷（兼容旧版验证）；配置密钥后仅持钥者可伪造通过验证的水印。
_WATERMARK_KEY_ENV = "IMAGE_MULTIMODEL_WATERMARK_KEY"
_WATERMARK_KEY_FILE = Path(__file__).resolve().parent.parent.parent / ".watermark_key"
_SIG_LEN = 64  # sha256 hex 长度


def _load_secret_key() -> bytes | None:
    """加载水印签名密钥（环境变量优先，其次项目根 .watermark_key 文件）。"""
    env_key = os.environ.get(_WATERMARK_KEY_ENV, "").strip()
    if env_key:
        return env_key.encode("utf-8")
    try:
        if _WATERMARK_KEY_FILE.exists():
            key = _WATERMARK_KEY_FILE.read_text(encoding="utf-8").strip()
            if key:
                return key.encode("utf-8")
    except Exception as e:
        logger.debug(f"读取水印密钥文件失败: {e}")
    return None


def _sign_payload(payload: str, key: bytes) -> str:
    """对水印载荷附加 HMAC-SHA256 签名。"""
    digest = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}|{digest}"


def _verify_signed(signed_payload: str, key: bytes) -> str | None:
    """验证签名载荷，返回原始载荷；签名缺失或无效返回 None。

    提取噪声可能产生非 ASCII 字符，digest 必须为 64 位 hex 才参与比对。
    """
    if len(signed_payload) < _SIG_LEN + 1:
        return None
    payload, digest = signed_payload[:-_SIG_LEN - 1], signed_payload[-_SIG_LEN:]
    if not digest.isascii() or any(c not in "0123456789abcdefABCDEF" for c in digest):
        return None
    expected = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, digest):
        return payload
    return None


# ── 嵌入 / 提取 ─────────────────────────────────────────
def embed_watermark(
    image: np.ndarray,
    product_id: str,
    task_id: str,
    timestamp: float | None = None,
) -> np.ndarray:
    """
    将溯源水印嵌入 2D/3D 图像数组，返回新数组（不修改输入）。

    对 3D (H,W,C) 图像，仅嵌入到第一通道（亮度主导），其余通道不变。
    优先尝试 GPU 加速（cupy 批量向量化 DCT），失败时自动回退 CPU。
    """
    # 优先尝试 GPU 加速（优雅降级：cupy 不可用时回退 CPU）
    try:
        from .watermark_gpu import embed_watermark_gpu, is_gpu_available
        if is_gpu_available():
            result = embed_watermark_gpu(image, product_id, task_id, timestamp)
            if result is not None:
                logger.debug("Watermark embedded via GPU (cupy)")
                return result
            logger.debug("GPU watermark returned None, falling back to CPU")
    except Exception as e:
        logger.debug(f"GPU watermark failed, falling back to CPU: {e}")
    
    # CPU 实现（原有路径）
    ts = timestamp if timestamp is not None else time.time()
    payload = _payload_string(product_id, task_id, ts)
    key = _load_secret_key()
    if key is not None:
        payload = _sign_payload(payload, key)
    else:
        logger.warning(
            "未配置水印签名密钥，将嵌入未签名水印（不可证伪归属）。"
            "请运行 scripts/init_watermark_key.py 生成密钥"
        )
    bits = _str_to_bits(payload)

    arr = np.asarray(image, dtype=np.float64)
    single = arr.ndim == 2
    work = arr if single else arr[:, :, 0]

    h, w = work.shape
    need = len(bits)
    cols_blocks = w // BLOCK
    rows_blocks = h // BLOCK
    capacity = rows_blocks * cols_blocks
    if need > capacity:
        raise ValueError(f"Image too small for payload: need {need} blocks, have {capacity}")

    out = work.copy()
    r, c = COEF_RC
    idx = 0
    for bi in range(rows_blocks):
        for bj in range(cols_blocks):
            if idx >= need:
                break
            y, x = bi * BLOCK, bj * BLOCK
            block = out[y:y + BLOCK, x:x + BLOCK]
            coef = _dct2(block)
            energy = float(np.abs(coef).sum()) + 1e-6
            q = min(max(energy * QUANT_RATIO, MIN_Q), MAX_Q)
            bit = bits[idx]
            # 符号编码：bit=1 → +q, bit=0 → -q
            coef[r, c] = q if bit == 1 else -q
            out[y:y + BLOCK, x:x + BLOCK] = _idct2(coef)
            idx += 1
        if idx >= need:
            break

    if single:
        return out
    result = arr.copy()
    result[:, :, 0] = out
    return result


def extract_watermark(image: np.ndarray, n_bits: int) -> list[int]:
    """提取前 n_bits 个水印比特"""
    arr = np.asarray(image, dtype=np.float64)
    work = arr if arr.ndim == 2 else arr[:, :, 0]
    h, w = work.shape
    rows_blocks, cols_blocks = h // BLOCK, w // BLOCK
    r, c = COEF_RC
    bits: list[int] = []
    idx = 0
    for bi in range(rows_blocks):
        for bj in range(cols_blocks):
            if idx >= n_bits:
                break
            y, x = bi * BLOCK, bj * BLOCK
            coef = _dct2(work[y:y + BLOCK, x:x + BLOCK])
            bits.append(1 if coef[r, c] > 0 else 0)
            idx += 1
        if idx >= n_bits:
            break
    return bits


def verify(image: np.ndarray, product_id: str, task_id: str, timestamp: float) -> bool:
    """校验水印是否可正确还原。

    - 配置了密钥时（推荐）：严格验证 HMAC 签名，仅持有密钥嵌入的水印通过；
      旧版未签名水印将验证失败（无法证明真伪）。
    - 未配置密钥时：回退旧版位级比对（弱验证）。
    """
    payload = _payload_string(product_id, task_id, timestamp)
    key = _load_secret_key()
    if key is not None:
        signed = _sign_payload(payload, key)
        bits = _str_to_bits(signed)
        got = extract_watermark(image, len(bits))
        extracted = _bits_to_str(got)
        return _verify_signed(extracted, key) is not None
    bits = _str_to_bits(payload)
    got = extract_watermark(image, len(bits))
    return got == bits
