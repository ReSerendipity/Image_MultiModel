"""
native/lora.py — 动态 LoRA 栈叠加

复用参考 Comfy 的 ``comfy.sd.load_lora_for_models``（comfy_kernel，经
``source.ensure_loaded()`` 后 ``import comfy.sd``）把任意数量的 LoRA 依次叠加到
model / clip 的 clone 上。单个 LoRA 不可用或加载失败时静默跳过该层（记录 warning），
不阻断主推理。

Phase 3 扩展：支持 ``GenerationConfig.effective_lora_stack()`` 返回的动态栈
（数量不固定），而不再受限于旧的 6 层字段。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..config_models import ModelsConfig, scan_resource_files
from . import source

logger = logging.getLogger(__name__)


def resolve_lora_paths(
    config: ModelsConfig,
    project_root: str | Path,
) -> dict[str, str]:
    """扫描 LoRA 资源目录，返回 ``{模块名: 绝对路径}`` 映射。

    Args:
        config: ModelsConfig 实例（决定 shared/portable 模式与目录映射）
        project_root: 项目根目录

    Returns:
        按文件名（不含扩展）作为 key 的绝对路径映射，如 ``{"lora_style":
        "/abs/loras/lora_style.safetensors"}``
    """
    relatives = scan_resource_files("lora", config, project_root)
    mapping: dict[str, str] = {}
    for rel in relatives:
        name = Path(rel).stem
        if name and name not in mapping:
            # scan_resource_files 返回相对路径，需拼回资源根
            from ..config import get_config  # 延迟导入避免循环

            cfg = get_config()
            mapping[name] = _absolute_lora_path(rel, config, cfg.project_root)
    if not mapping and relatives:
        # 兜底：直接用相对路径拼项目根（双模式均以 base 为根）
        for rel in relatives:
            name = Path(rel).stem
            if name and name not in mapping:
                mapping[name] = str(Path(project_root) / rel).replace("\\", "/")
    return mapping


def _absolute_lora_path(rel: str, config: ModelsConfig, project_root: str | Path) -> str:
    """把 scan_resource_files 返回的相对路径拼成绝对路径。"""
    project_root = Path(project_root).resolve()
    if config.model_source_mode == "portable":
        sub_dir_name = config.portable.sub_dirs.get("lora", "loras")
        base = project_root / config.portable.internal_models_dir / sub_dir_name
    else:
        sub_dir_name = config.shared.mount_map.get("lora", "loras")
        base = Path(config.shared.comfy_models_dir) / sub_dir_name
    return str(base / rel).replace("\\", "/")


def apply_lora_stack(
    model: Any,
    clip: Any,
    lora_paths: dict[str, str],
    stack: list[dict],
    comfy_root: str | None = None,
) -> tuple[Any, Any]:
    """把 LoRA 栈依次叠加到 model / clip 的 clone 上。

    Args:
        model: Comfy model patcher（``comfy.model_patcher.ModelPatcher``）
        clip: Comfy CLIP 对象
        lora_paths: ``{模块名: 绝对路径}`` 映射（由 resolve_lora_paths 生成）
        stack: ``effective_lora_stack()`` 返回的 ``[{name, strength}]`` 列表
        comfy_root: Comfy 源码根目录（传给 source.ensure_loaded）

    Returns:
        ``(model, clip)`` 叠加后的新 clone。任一 LoRA 缺失/失败都会静默跳过，
        返回仍可用模型，不抛异常。

    Note:
        每个 LoRA 通过 ``comfy.sd.load_lora_for_models(model, clip, lora_sd,
        strength, strength)`` 在 model/clip 的 clone 上打 patch，因此可安全链式
        叠加多个 LoRA，且不修改传入的原始 model/clip。
    """
    # 预筛：没有可应用的 LoRA（空栈 / 全部缺失路径）时，不加载 comfy 依赖
    pending: list[tuple[str, float]] = []
    for entry in stack:
        name = (entry or {}).get("name") or ""
        strength = float((entry or {}).get("strength", 1.0))
        if not name or not lora_paths.get(name):
            continue
        pending.append((name, strength))
    if not pending:
        if stack:
            logger.warning("No LoRA layers applied (stack size=%d)", len(stack))
        return model, clip

    source.ensure_loaded(comfy_root=comfy_root)
    import comfy.sd
    import comfy.utils

    applied = 0
    for name, strength in pending:
        path = lora_paths.get(name)
        try:
            lora_sd = comfy.utils.load_torch_file(path)
            model, clip = comfy.sd.load_lora_for_models(
                model, clip, lora_sd, strength, strength
            )
            applied += 1
            logger.info("Applied LoRA '%s' (strength=%.3f)", name, strength)
        except Exception as e:  # noqa: BLE001 - 静默跳过不阻断主推理
            logger.warning("Failed to apply LoRA '%s': %s", name, e)

    logger.info("Applied %d/%d LoRA layers", applied, len(pending))
    return model, clip
