"""
routes/config_routes.py — GET/PUT /api/config

对应 MASTER_PLAN §5.1: GET/PUT /api/config（脱敏 + host 只读校验）
数据治理报告 P1-3: PUT 热改增加字段级校验（model_validate，替代 setattr 裸赋值）
+ 审计日志（data/config_audit.log，记录 who/when/diff）。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError

from ..config import get_config, save_config
from ..config_models import scan_resource_files

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

# PUT 允许热改的 section（与 ConfigUpdateRequest 字段一一对应）
_AUDIT_SECTIONS = ("inference", "output", "ui", "i18n", "presets")


@router.get("/loras")
async def list_loras() -> dict[str, Any]:
    """GET /api/config/loras — 扫描 LoRA 目录，返回相对路径列表（前端下拉用）"""
    cfg = get_config()
    try:
        files = scan_resource_files("lora", cfg.models, cfg.project_root, (".safetensors",))
    except Exception as e:
        logger.error(f"LoRA scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"LoRA scan failed: {e}")
    return {"loras": files, "count": len(files), "mode": cfg.models.model_source_mode}


class ConfigUpdateRequest(BaseModel):
    """配置更新请求（部分更新）"""

    # 只允许更新非安全字段
    inference: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    ui: dict[str, Any] | None = None
    i18n: dict[str, Any] | None = None
    presets: dict[str, Any] | None = None


@router.get("")
async def get_config_api() -> dict[str, Any]:
    """GET /api/config — 读取配置（脱敏后返回前端）"""
    cfg = get_config()
    return cfg.get_safe_config_dict()


def _validate_section_update(current: Any, updates: dict[str, Any]) -> Any:
    """字段级校验后返回新 section 实例（数据治理 P1-3）。

    ``setattr`` 裸赋值绕过 Pydantic 字段校验，非法类型/越界值会静默写入 config.yaml。
    改为 whole-model ``model_validate``：合并现有值与更新值后全量校验，
    任何字段非法即抛 ``ValidationError``（调用方转 422）。
    """
    merged = {**current.model_dump(), **updates}
    return type(current).model_validate(merged)


def _append_config_audit(
    cfg: Any,
    who: str,
    changes: list[dict[str, Any]],
    log_path: Path | None = None,
) -> None:
    """把配置热改审计写入 data/config_audit.log（JSON Lines）。

    记录 who（客户端地址）/ when（本地时间）/ diff（逐字段 before→after）。
    写审计失败仅告警，不阻断配置保存本身。
    """
    if not changes:
        return
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "who": who,
        "changes": changes,
    }
    if log_path is None:
        log_path = Path(cfg.project_root) / "data" / "config_audit.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        logger.warning("Config audit log write failed: %s", e)


@router.put("")
async def update_config_api(req: ConfigUpdateRequest, request: Request) -> dict[str, Any]:
    """
    PUT /api/config — 更新配置（写回 config.yaml）
    host 字段只读，不允许通过 API 修改
    数据治理报告 P1-3：字段级校验 + 审计日志（who/when/diff）
    """
    cfg = get_config()
    who = request.client.host if request.client else "unknown"

    # 第一遍：全量校验（任一 section 非法即 422，保证不出现「半更新」内存态）
    validated: dict[str, tuple[Any, dict[str, Any]]] = {}
    for section_name in _AUDIT_SECTIONS:
        updates = getattr(req, section_name)
        if updates is None:
            continue
        current = getattr(cfg, section_name)
        accepted = {k: v for k, v in updates.items() if hasattr(current, k)}
        if not accepted:
            continue
        try:
            validated[section_name] = (_validate_section_update(current, accepted), accepted)
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {section_name} config: {e.errors()[:3]}",
            )

    # 第二遍：统一应用 + 收集 diff
    changes: list[dict[str, Any]] = []
    for section_name, (new_section, accepted) in validated.items():
        current = getattr(cfg, section_name)
        for k in accepted:
            before = getattr(current, k)
            after = getattr(new_section, k)
            if before != after:
                changes.append({"section": section_name, "key": k, "before": before, "after": after})
        setattr(cfg, section_name, new_section)

    if not changes:
        return {"status": "ok", "message": "No changes"}

    try:
        save_config(cfg)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail=f"Config save failed: {e}")

    _append_config_audit(cfg, who, changes)
    logger.info("Config updated and saved (%d field(s) changed by %s)", len(changes), who)
    return {"status": "ok", "message": "Config saved successfully", "changed": len(changes)}
