"""
model_card.py — 权重级 Model Card / 元数据注册表（MLOps P2·治理）

对应审计反模式 #3（每个 checkpoint 缺 model card 文档）：
- ``ModelCard`` 聚合引擎的权重治理元数据（SHA256 / 版本 / 训练溯源 / 兼容矩阵）
- ``build_model_card`` / ``build_registry`` 由 ``EngineConfig`` 生成 model card
- ``is_complete`` 用于校验治理元数据是否齐备（CI / 启动自检可据此告警）

字段来源：``config_models.EngineConfig`` 的 MLOps P2 扩展字段。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config_models import EngineConfig

logger = logging.getLogger(__name__)


@dataclass
class ModelCard:
    """权重级 Model Card（治理元数据聚合）。"""

    name: str
    display_name: str = ""
    backend: str = ""
    weight_sha256: str = ""
    weight_version: str = ""
    training_data_source: str = ""
    license: str = ""
    compatibility_matrix: dict[str, list[str]] = field(default_factory=dict)
    vram_gb: float = 0.0

    # 治理所需的最小字段集合
    _REQUIRED = ("weight_sha256", "weight_version", "training_data_source")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "backend": self.backend,
            "weight_sha256": self.weight_sha256,
            "weight_version": self.weight_version,
            "training_data_source": self.training_data_source,
            "license": self.license,
            "compatibility_matrix": self.compatibility_matrix,
            "vram_gb": self.vram_gb,
        }

    def is_complete(self) -> bool:
        """治理元数据是否齐备（SHA256 / 版本 / 训练溯源均非空）。"""
        return all(getattr(self, f) for f in self._REQUIRED)

    def missing_fields(self) -> list[str]:
        return [f for f in self._REQUIRED if not getattr(self, f)]


def build_model_card(engine_cfg: EngineConfig) -> ModelCard:
    """由 ``EngineConfig`` 生成权重级 Model Card。"""
    return ModelCard(
        name=engine_cfg.name,
        display_name=engine_cfg.display_name or engine_cfg.name,
        backend=engine_cfg.backend,
        weight_sha256=engine_cfg.weight_sha256,
        weight_version=engine_cfg.weight_version,
        training_data_source=engine_cfg.training_data_source,
        license=engine_cfg.license,
        compatibility_matrix=engine_cfg.compatibility_matrix,
        vram_gb=engine_cfg.vram_gb,
    )


def build_registry(models_cfg: Any) -> dict[str, ModelCard]:
    """由 ``ModelsConfig`` 生成全部引擎的 Model Card 注册表。

    Args:
        models_cfg: 含 ``engines: dict[str, EngineConfig]`` 的配置对象

    Returns:
        ``{engine_name: ModelCard}``
    """
    registry: dict[str, ModelCard] = {}
    engines = getattr(models_cfg, "engines", {}) or {}
    for name, ecfg in engines.items():
        try:
            registry[name] = build_model_card(ecfg)
        except Exception as e:  # noqa: BLE001
            logger.warning("生成 Model Card 失败 (%s): %s", name, e)
    return registry


def audit_registry(registry: dict[str, ModelCard]) -> dict[str, Any]:
    """审计注册表治理完备度，返回不完整项。

    Returns:
        ``{"total", "complete", "incomplete", "details": {name: [missing_fields]}}``
    """
    total = len(registry)
    complete = sum(1 for c in registry.values() if c.is_complete())
    details = {name: c.missing_fields() for name, c in registry.items() if not c.is_complete()}
    return {
        "total": total,
        "complete": complete,
        "incomplete": total - complete,
        "details": details,
    }


__all__ = [
    "ModelCard",
    "build_model_card",
    "build_registry",
    "audit_registry",
    "compute_engine_weight_fingerprint",
    "register_weight_fingerprint",
]


# ── 权重指纹登记（数据治理报告 P2-2）─────────────────────────────
# 主权重子目录（与 portable.sub_dirs 对齐；lora 逐层指纹由 lineage.compute_lora_checksums
# 单独覆盖，不在此重复统计）。
_WEIGHT_SUB_DIRS = ("text_encoders", "unet", "vae")
# 启动期登记的成本护栏：fingerprint 在引擎注册时同步计算，不能把启动拖成
# 全量权重哈希作业（那归 scripts/generate_weight_manifest.py 离线完成）。
_MAX_FILES = 200  # 最多统计的权重文件数
_MAX_FILE_BYTES = 1 << 30  # 单文件 > 1GiB 跳过（启动期哈希不现实）


def compute_engine_weight_fingerprint(
    models_cfg: Any,
    project_root: str | Path,
) -> str:
    """对引擎主权重文件计算聚合指纹（有界的启动期快速指纹）。

    算法：对 ``<internal_models_dir>/{text_encoders,unet,vae}`` 下全部
    ``*.safetensors`` 逐文件 sha256，按 ``相对路径:hash`` 行排序拼接后
    再做一次 sha256 —— 任一权重字节变动都会改变指纹。

    成本护栏（实测教训：portable.internal_models_dir 指向 symlink/junction
    到外部 ComfyUI 权重树时，全量哈希达数十 GB，会把每次启动/测试挂死）：
    - **symlink/junction 子目录整树跳过**——外部权重树的治理归权重清单
      脚本与上游，不属于本进程启动期职责；
    - 单文件 > 1 GiB 跳过、累计最多 200 个文件。

    Returns:
        64 位十六进制指纹；无可纳管权重文件时返回空串（不视为错误）。
    """
    import hashlib

    from .security.weight_integrity import compute_file_sha256

    base = Path(project_root) / models_cfg.portable.internal_models_dir
    lines: list[str] = []
    for sub in _WEIGHT_SUB_DIRS:
        d = base / sub
        if not d.is_dir() or d.is_symlink():
            continue
        for f in sorted(d.rglob("*.safetensors")):
            if len(lines) >= _MAX_FILES:
                logger.warning(
                    "weight fingerprint: file cap (%d) reached, fingerprint partial",
                    _MAX_FILES,
                )
                break
            try:
                if f.is_symlink() or f.stat().st_size > _MAX_FILE_BYTES:
                    continue
                lines.append(f"{f.relative_to(base).as_posix()}:{compute_file_sha256(f)}")
            except OSError as e:  # noqa: BLE001 - 单文件失败不阻断
                logger.warning("weight fingerprint: hash failed for %s: %s", f, e)
    if not lines:
        return ""
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def register_weight_fingerprint(
    engine_cfg: Any,
    models_cfg: Any,
    project_root: str | Path,
) -> str:
    """把权重指纹登记进 ``engine_cfg``（数据治理报告 P2-2）。

    - ``weight_sha256`` 为空时填充聚合指纹；已有值（运维手工登记）不覆盖。
    - ``weight_version`` 为空时填充内容派生版本 ``auto-sha256:<前 12 位>``——
      基于权重内容的确定性版本标签，不伪造上游发布号。
    - 仅内存态；磁盘留档由 ``scripts/generate_weight_manifest.py`` 的
      权重清单承担。

    Returns:
        指纹（空串 = 无权重可登记）。
    """
    fingerprint = compute_engine_weight_fingerprint(models_cfg, project_root)
    if not fingerprint:
        return fingerprint
    if not getattr(engine_cfg, "weight_sha256", ""):
        engine_cfg.weight_sha256 = fingerprint
    if not getattr(engine_cfg, "weight_version", ""):
        engine_cfg.weight_version = f"auto-sha256:{fingerprint[:12]}"
    return fingerprint
