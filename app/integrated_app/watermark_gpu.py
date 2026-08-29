"""
watermark_gpu.py — DCT 频域水印 GPU 加速（可选依赖 cupy）

对应 watermark.py 的 embed_watermark 函数 GPU 版。
使用 cupy 批量向量化所有 8×8 块的 DCT/IDCT 运算，替代逐块 CPU 循环。

优雅降级：
- cupy 不可用时自动回退到 CPU 实现（watermark.py 原有路径）
- GPU 加速不影响水印提取兼容性（算法等价）

性能预期：
- 1024×1024 PNG：CPU ~50ms → GPU ~5ms（cuBLAS 批量 matmul）
- 大批量生成时总耗时减少不明显（瓶颈在模型推理），但水印嵌入不再成为尾部延迟源
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# 尝试导入 cupy（可选依赖）
cupy: Any | None = None
try:
    import cupy as _cp
    cupy = _cp
    logger.debug("cupy available, GPU watermark acceleration enabled")
except ImportError:
    logger.debug("cupy not installed, GPU watermark acceleration disabled")


# DCT-II 基矩阵（与 watermark.py 一致，但用 cupy 数组）
# 8x8 DCT-II basis matrix
_D_CPU = np.array([
    [0.35355339, 0.35355339, 0.35355339, 0.35355339, 0.35355339, 0.35355339, 0.35355339, 0.35355339],
    [0.49039264, 0.41573481, 0.27778512, 0.09754516, -0.09754516, -0.27778512, -0.41573481, -0.49039264],
    [0.46193977, 0.19134172, -0.19134172, -0.46193977, -0.46193977, -0.19134172, 0.19134172, 0.46193977],
    [0.41573481, -0.09754516, -0.49039264, -0.27778512, 0.27778512, 0.49039264, 0.09754516, -0.41573481],
    [0.35355339, -0.35355339, -0.35355339, 0.35355339, 0.35355339, -0.35355339, -0.35355339, 0.35355339],
    [0.27778512, -0.49039264, 0.09754516, 0.41573481, -0.41573481, -0.09754516, 0.49039264, -0.27778512],
    [0.19134172, -0.46193977, 0.46193977, -0.19134172, -0.19134172, 0.46193977, -0.46193977, 0.19134172],
    [0.09754516, -0.27778512, 0.41573481, -0.49039264, 0.49039264, -0.41573481, 0.27778512, -0.09754516],
], dtype=np.float64)
_DT_CPU = _D_CPU.T


# 水印嵌入参数（与 watermark.py 一致）
QUANT_RATIO = 0.03
MIN_Q = 8.0
MAX_Q = 16.0
BLOCK_SIZE = 8


def _str_to_bits(s: str) -> list[int]:
    """把字符串 UTF-8 编码展开为 7-bit 列表（与 watermark.py 一致）。"""
    data = s.encode("utf-8")
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def embed_watermark_gpu(
    image: np.ndarray,
    product_id: str,
    task_id: str,
    timestamp: float | None = None,
) -> np.ndarray | None:
    """GPU 加速版 DCT 水印嵌入（cupy 批量向量化）。

    Args:
        image: numpy 数组 (H, W, 3) 或 (H, W)，[0, 255] uint8 或 float64
        product_id: 产品标识符
        task_id: 任务标识符
        timestamp: 时间戳（None 时使用当前时间）

    Returns:
        嵌入水印后的 numpy 数组 (H, W, 3) [0, 255] uint8，
        或 None（cupy 不可用时，调用方应回退 CPU 实现）
    """
    if cupy is None:
        return None

    ts = timestamp if timestamp is not None else time.time()
    payload = f"{product_id}|{task_id}|{int(ts)}"

    bits = _str_to_bits(payload)
    n_bits = len(bits)

    h, w = image.shape[:2]
    n_blocks_h = h // BLOCK_SIZE
    n_blocks_w = w // BLOCK_SIZE
    capacity = n_blocks_h * n_blocks_w

    if capacity < n_bits:
        logger.debug(
            f"Image too small for watermark: need {n_bits} bits, "
            f"capacity {capacity} blocks ({h}x{w})"
        )
        return None

    # 转到 float64（仅第一通道）
    arr = image.astype(np.float64)
    is_3d = arr.ndim == 3
    if is_3d:
        channel = arr[:, :, 0].copy()
    else:
        channel = arr.copy()

    # 搬运到 GPU
    gpu_arr = cupy.asarray(channel)
    gpu_d = cupy.asarray(_D_CPU)
    gpu_dt = cupy.asarray(_DT_CPU)
    gpu_bits = cupy.asarray(bits, dtype=cupy.float64)

    # 构建所有块的索引 (n_blocks, H, W) → 批量运算
    # 提取所有 8x8 块：(n_blocks_h * n_blocks_w, 8, 8)
    blocks = []
    bit_idx = 0
    for bh in range(n_blocks_h):
        for bw in range(n_blocks_w):
            if bit_idx >= n_bits:
                break
            y0, y1 = bh * BLOCK_SIZE, (bh + 1) * BLOCK_SIZE
            x0, x1 = bw * BLOCK_SIZE, (bw + 1) * BLOCK_SIZE
            block = gpu_arr[y0:y1, x0:x1]
            blocks.append(block)
            bit_idx += 1

    if not blocks:
        return None

    # 堆叠为 (n_used_blocks, 8, 8)
    n_used = len(blocks)
    gpu_blocks = cupy.stack(blocks, axis=0)  # (N, 8, 8)

    # 批量 DCT: coeff = D @ block @ D^T
    # (N, 8, 8) → (N, 8, 8) via batch matmul
    # cupy.matmul(gpu_d, gpu_blocks) → (8, N, 8) 需要转置
    # 更高效：reshape 为 (N*8, 8) 后做两次矩阵乘法
    # 方案：直接循环但用 cupy（比 numpy 快 10 倍，但不如纯批量）
    # 实际测试发现 cupy 对小矩阵 batch matmul 的 overhead 较大，
    # 所以我们用更聪明的方法：先把所有块展平为 (N, 64)，
    # 然后用预计算的 64x64 DCT 变换矩阵做单次矩阵乘法

    # 64x64 DCT 变换矩阵（Kronecker product of D and D^T）
    # DCT2D(vec(block)) = (D ⊗ D^T) @ vec(block)
    # 但 64x64 矩阵乘法比 8x8 批量 matmul 更慢（64^3 vs 8^3 * N）
    # 对小 N（~16000），我们仍用批量循环

    # 最终方案：cupy 批量 matmul（cuBLAS 内部优化）
    # batch_matmul: (N, 8, 8) → (N, 8, 8)
    # 第一次：D @ blocks → (N, 8, 8)
    # cupy 的 matmul 支持广播：(8, 8) @ (N, 8, 8) → (N, 8, 8)
    # 但 cupy matmul 不自动广播，需手动 reshape

    # 最优：einsum
    gpu_coeffs = cupy.einsum("ij,njk->nik", gpu_d, gpu_blocks)  # (N, 8, 8)
    gpu_coeffs = cupy.einsum("ijk,kl->ijl", gpu_coeffs, gpu_dt)  # (N, 8, 8)

    # 计算每块能量和量化步
    gpu_energies = cupy.abs(gpu_coeffs).sum(axis=(1, 2)) + 1e-6
    gpu_q = cupy.clip(gpu_energies * QUANT_RATIO, MIN_Q, MAX_Q)

    # 嵌入：修改 (4, 3) 位置系数
    gpu_coeffs[:, 4, 3] = cupy.where(gpu_bits == 1, gpu_q, -gpu_q)

    # 批量 IDCT: block = D^T @ coeff @ D
    gpu_inv = cupy.einsum("ij,njk->nik", gpu_dt, gpu_coeffs)
    gpu_inv = cupy.einsum("ijk,kl->ijl", gpu_inv, gpu_d)

    # 反量化（clip 回 [0, 255]）
    gpu_inv = cupy.clip(gpu_inv, 0, 255)

    # 写回原数组
    bit_idx = 0
    for bh in range(n_blocks_h):
        for bw in range(n_blocks_w):
            if bit_idx >= n_bits:
                break
            y0, y1 = bh * BLOCK_SIZE, (bh + 1) * BLOCK_SIZE
            x0, x1 = bw * BLOCK_SIZE, (bw + 1) * BLOCK_SIZE
            gpu_arr[y0:y1, x0:x1] = gpu_inv[bit_idx]
            bit_idx += 1

    # 搬回 CPU
    result = cupy.asnumpy(gpu_arr)

    # 放回原通道
    if is_3d:
        arr[:, :, 0] = result
    else:
        arr = result

    return arr.astype(np.uint8)


def is_gpu_available() -> bool:
    """检测 GPU 水印加速是否可用。"""
    return cupy is not None
