"""
native/vram.py — VRAM 预留 + BlockSwap 配置

复用 ``ComfyUI-ReservedVRAM/nodes.py`` 的 ``get_gpu_memory_info()`` /
``set_reserved_vram()`` / ``cleanGPUUsedForce()`` 逻辑（pynvml/torch.cuda 兜底），
并移植 ``ComfyUI-SeedVR2_VideoUpscaler`` 的 BlockSwap 配置入口的最小可用包装。
"""

from __future__ import annotations

import gc
import json
import logging
import struct
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# pynvml 在部分 AMD/Intel 环境导入本身就可能抛异常，故整体 try。
try:
    import pynvml

    pynvml.nvmlInit()
    _pynvml = pynvml
except Exception:  # pragma: no cover - 环境相关
    _pynvml = None


def get_gpu_memory_info() -> tuple[float | None, float | None]:
    """获取 GPU 显存信息（优先 pynvml，torch.cuda.mem_get_info 兜底）。

    Returns:
        ``(total_gb, used_gb)``；两种方式都不可用时返回 ``(None, None)``。
    """
    if _pynvml is not None:
        try:
            handle = _pynvml.nvmlDeviceGetHandleByIndex(0)
            info = _pynvml.nvmlDeviceGetMemoryInfo(handle)
            return info.total / (1024**3), info.used / (1024**3)
        except Exception as e:  # noqa: BLE001
            logger.warning("get_gpu_memory_info via nvml failed: %s", e)

    try:
        import torch

        if torch.cuda.is_available() and hasattr(torch.cuda, "mem_get_info"):
            free, total = torch.cuda.mem_get_info()
            return total / (1024**3), (total - free) / (1024**3)
    except Exception as e:  # noqa: BLE001
        logger.warning("get_gpu_memory_info via torch failed: %s", e)

    return None, None


def set_reserved_vram(reserved_gb: float) -> None:
    """设置 ComfyUI 的 EXTRA_RESERVED_VRAM（预留显存，GB）。

    Args:
        reserved_gb: 预留显存大小（GB），自动取非负。
    """
    reserved_gb = max(0.0, float(reserved_gb))
    reserved_vram = int(reserved_gb * 1024 * 1024 * 1024)
    try:
        import comfy.model_management

        if hasattr(comfy.model_management, "set_extra_reserved_vram"):
            comfy.model_management.set_extra_reserved_vram(reserved_gb)
        else:
            comfy.model_management.EXTRA_RESERVED_VRAM = reserved_vram
    except Exception as e:  # pragma: no cover - 依赖环境相关
        logger.warning("set_reserved_vram failed: %s", e)


def reserve_vram(
    reserved_gb: float,
    mode: str = "auto",
    auto_max_reserved: float = 0.0,
) -> float:
    """预留显存（对齐 ReservedVRAMSetter 的 manual/auto 两模式）。

    Args:
        reserved_gb: 期望预留的显存（GB）
        mode: ``"auto"`` 在已用显存基础上累加预留；``"manual"`` 直接使用给定值
        auto_max_reserved: auto 模式上限（GB，0 表示不限）

    Returns:
        实际设置的预留显存（GB，四舍五入 2 位）。
    """
    final_reserved = 0.0
    if mode == "auto":
        total, used = get_gpu_memory_info()
        if total is not None and used is not None:
            auto = max(0.0, used + float(reserved_gb))
            if auto_max_reserved > 0:
                auto = min(auto, float(auto_max_reserved))
            set_reserved_vram(auto)
            final_reserved = round(auto, 2)
        else:
            manual = max(0.0, float(reserved_gb))
            set_reserved_vram(manual)
            final_reserved = round(manual, 2)
    else:
        manual = max(0.0, float(reserved_gb))
        set_reserved_vram(manual)
        final_reserved = round(manual, 2)
    return final_reserved


def free_vram() -> None:
    """释放显存：gc.collect + unload_all_models + soft_empty_cache。"""
    gc.collect()
    try:
        import comfy.model_management

        comfy.model_management.unload_all_models()
        comfy.model_management.soft_empty_cache()
    except Exception as e:  # pragma: no cover - 依赖环境相关
        logger.warning("free_vram failed: %s", e)


def configure_blockswap(model: Any, blocks_to_swap: int = 0) -> dict[str, Any]:
    """配置 DiT 模型的 BlockSwap（最小可用 offload 逻辑包装）。

    优先复用 ``ComfyUI-SeedVR2_VideoUpscaler`` 的
    ``optimization.blockswap.apply_block_swap_to_dit``；若该模块依赖复杂无法导入，
    则退化为对 ``model.blocks`` 的前 N 块执行 ``.to(offload_device)`` 的简单 offload。

    Args:
        model: 含 ``blocks`` 属性的 DiT 模型
        blocks_to_swap: 需要换出的 transformer block 数（0 表示禁用）

    Returns:
        ``{"applied": bool, "blocks_swapped": int, "mode": str}`` 描述实际配置结果。
    """
    if blocks_to_swap <= 0:
        return {"applied": False, "blocks_swapped": 0, "mode": "disabled"}

    if not hasattr(model, "blocks"):
        logger.warning("configure_blockswap: model has no 'blocks', BlockSwap disabled")
        return {"applied": False, "blocks_swapped": 0, "mode": "no_blocks"}

    total = len(model.blocks)
    effective = min(blocks_to_swap, total)
    offload = getattr(model, "offload_device", "cpu") or "cpu"

    # 优先复用 SeedVR2 原生 BlockSwap（若可导入）
    try:
        _apply_reused_blockswap(model, effective, offload)
        return {"applied": True, "blocks_swapped": effective, "mode": "seedvr2"}
    except Exception as e:  # noqa: BLE001 - 退化为最小 offload
        logger.debug("seedvr2 blockswap unavailable (%s), using minimal offload", e)

    # 最小可用 offload：把前 N 块移到 offload device
    try:
        for b, block in enumerate(model.blocks):
            if b < effective:
                block.to(offload)
        model.blocks_to_swap = effective - 1
        model.main_device = getattr(model, "main_device", "cuda")
        model.offload_device = offload
        return {"applied": True, "blocks_swapped": effective, "mode": "minimal"}
    except Exception as e:  # pragma: no cover - 环境相关
        logger.warning("minimal blockswap offload failed: %s", e)
        return {"applied": False, "blocks_swapped": 0, "mode": "error"}


def _apply_reused_blockswap(model: Any, effective: int, offload: Any) -> None:
    """尝试复用 SeedVR2 的 ``apply_block_swap_to_dit``。

    要求 ``model`` 的 Runner 已挂载 ``debug``（SeedVR2 内部强依赖），否则抛异常
    让调用方退化为最小 offload。依赖不可导入时同样抛异常。
    """
    import torch
    from optimization.blockswap import (  # type: ignore  # noqa
        apply_block_swap_to_dit,
    )

    debug = getattr(model, "_seedvr_debug", None)
    if debug is None:
        raise RuntimeError("seedvr2 blockswap requires a runner.debug instance")

    runner = type("_Runner", (), {"dit": model, "debug": debug, "_blockswap_active": False})()
    config = {
        "blocks_to_swap": effective,
        "swap_io_components": False,
        "offload_device": torch.device(offload) if not isinstance(offload, torch.device) else offload,
    }
    apply_block_swap_to_dit(runner, config, debug)


# ──────────────────────────────────────────────────────────────
#  MLOps P0-2: 多 LoRA 叠加 VRAM 增量估算
# ──────────────────────────────────────────────────────────────
_DEFAULT_LORA_INCREMENT_GB = 0.15  # 读取不到 header 时的保守默认（典型小 LoRA）
_BYTES_PER_PARAM = 2  # 推理时 LoRA 权重以 fp16 驻留


def _read_safetensors_tensor_bytes(adapter_path: str | Path) -> int | None:
    """读取 safetensors 头，返回所有张量数据区字节总量；失败返回 None。"""
    try:
        with open(adapter_path, "rb") as f:
            magic = f.read(8)
            if len(magic) < 8:
                return None
            header_len = struct.unpack("<Q", magic)[0]
            if header_len <= 0 or header_len > 100 * 1024 * 1024:
                return None
            header = json.loads(f.read(header_len))
        total = 0
        for key, meta in header.items():
            if key == "__metadata__" or not isinstance(meta, dict):
                continue
            offs = meta.get("data_offsets")
            if offs and len(offs) == 2:
                total += max(0, offs[1] - offs[0])
        return total
    except Exception as e:  # noqa: BLE001 - 解析失败即视为不可估算
        logger.debug("safetensors tensor-byte read failed for %s: %s", adapter_path, e)
        return None


def estimate_lora_vram_increment(adapter_path: str | Path, strength: float = 1.0) -> float:
    """估算单个 LoRA 叠加带来的增量显存（GB）。

    依据：LoRA 权重以 fp16 常驻显存，增量 ≈ 张量数据字节数 × 2 / 1GB。
    strength 不影响驻留显存（仅影响激活峰值），用 ``max(0.1, |strength|)`` 做轻微修正。

    Args:
        adapter_path: LoRA 文件绝对路径
        strength: LoRA 强度

    Returns:
        增量显存（GB，保留 4 位小数）
    """
    tensor_bytes = _read_safetensors_tensor_bytes(adapter_path)
    if tensor_bytes is None:
        return _DEFAULT_LORA_INCREMENT_GB
    gb = (tensor_bytes * _BYTES_PER_PARAM) / (1024**3)
    return round(gb * max(0.1, abs(strength)), 4)


def estimate_lora_stack_vram(paths_with_strength: list[tuple[str | None, float]]) -> float:
    """估算整个 LoRA 栈的总增量显存（GB）。

    Args:
        paths_with_strength: ``[(abs_path, strength), ...]``，path 为空则跳过

    Returns:
        总增量显存（GB）
    """
    total = 0.0
    for path, strength in paths_with_strength:
        if not path:
            continue
        total += estimate_lora_vram_increment(path, strength)
    return round(total, 4)


def estimate_lora_stack_vram_from_stack(
    stack: list[dict],
    lora_paths: dict[str, str] | None = None,
) -> float:
    """从 ``effective_lora_stack()`` 结果与 name→path 映射估算总增量显存。

    Args:
        stack: ``[{"name", "strength"}, ...]``
        lora_paths: ``{name: abs_path}``（由 ``lora.resolve_lora_paths`` 生成）

    Returns:
        总增量显存（GB）
    """
    pairs: list[tuple[str | None, float]] = []
    for entry in stack or []:
        name = (entry or {}).get("name") or ""
        strength = float((entry or {}).get("strength", 1.0))
        path = (lora_paths or {}).get(name)
        pairs.append((path, strength))
    return estimate_lora_stack_vram(pairs)
