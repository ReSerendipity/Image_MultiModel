"""
cost_governance.py — 成本资源治理中心模块

对应 COST_GOVERNANCE_ASSESSMENT_v2.0.0.md 整改路线（按优先级）：
- MetricsStore      : GPU 指标持久化环形缓冲 + 泄漏判定落库（P1·成本可见性）
- VRAMScheduler     : VRAM 水位感知的动态 batch 上限（P1·GPU 利用率）
- IdleUnloadManager : 空闲自动卸载计时（P2·空闲浪费）
- WeightDedupScanner: 多版本权重孤儿回收扫描（P1·存储去重）
- FinOpsReporter    : 基于 processing_time_s 的成本分摊报表（P2·FinOps）
- BudgetChecker      : 预算阈值告警（P3·预算告警）

所有组件均为无 GPU 依赖的纯逻辑（torch 仅在采样器内被 try 保护），
便于单测，并由 app_server 生命周期内启停后台循环驱动。
"""

from __future__ import annotations

import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  MetricsStore — GPU 指标持久化（反模式 #5 修复）
# ──────────────────────────────────────────────────────────────
class MetricsStore:
    """GPU/资源指标环形缓冲，落地为可查询时序，供 /api/metrics 与成本看板使用。

    SSE 的 gpu_status 仅实时流、不持久化；本存储把采样写入内存环形缓冲，
    使「均值/峰值」利用率、泄漏状态可被事后分析。
    """

    def __init__(self, history_points: int = 360) -> None:
        self._history_points = max(1, int(history_points))
        self._gpu: deque[dict[str, Any]] = deque(maxlen=self._history_points)
        self._leak: dict[str, Any] = {"leak_detected": False, "growth_gb": 0.0, "reason": "ok"}
        self._leak_history: deque[dict[str, Any]] = deque(maxlen=60)

    def record_gpu(self, sample: dict[str, Any]) -> None:
        """记录一次 GPU 采样（含 total/used/free/allocated/reserved）。"""
        self._gpu.append({"ts": time.time(), **sample})

    def record_leak(self, report: dict[str, Any]) -> None:
        """记录一次显存泄漏判定结果。"""
        self._leak = report
        self._leak_history.append({"ts": time.time(), **report})

    @property
    def latest_gpu(self) -> dict[str, Any] | None:
        return self._gpu[-1] if self._gpu else None

    def get_gpu_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        items = list(self._gpu)
        if limit is not None and limit > 0:
            items = items[-limit:]
        return items

    def gpu_utilization_stats(self) -> dict[str, float]:
        """计算已采样窗口内的 VRAM 利用率统计（均值/峰值/空闲均值）。"""
        if not self._gpu:
            return {"mean_used_gb": 0.0, "peak_used_gb": 0.0, "mean_free_gb": 0.0, "samples": 0}
        used = [s.get("used_vram_gb", 0.0) or 0.0 for s in self._gpu]
        free = [s.get("free_vram_gb", 0.0) or 0.0 for s in self._gpu]
        return {
            "mean_used_gb": round(sum(used) / len(used), 2),
            "peak_used_gb": round(max(used), 2),
            "mean_free_gb": round(sum(free) / len(free), 2),
            "samples": len(used),
        }

    @property
    def leak_status(self) -> dict[str, Any]:
        return self._leak


# ──────────────────────────────────────────────────────────────
#  VRAMScheduler — VRAM 水位感知动态 batch 上限（P1）
# ──────────────────────────────────────────────────────────────
class VRAMScheduler:
    """根据空闲显存比例在 [min,max] 间计算当前允许的最大 batch_size。

    高水位之上 → 顶到 max_batch_size（充分摊薄单位图像成本）；
    低水位之下 → 降到 min_batch_size（避免 OOM 与频繁 chunk）；
    中间线性插值。
    """

    def __init__(
        self,
        enabled: bool = False,
        high_watermark_pct: int = 90,
        low_watermark_pct: int = 70,
        max_batch_size: int = 4,
        min_batch_size: int = 1,
    ) -> None:
        self.enabled = enabled
        self.high = max(1, min(100, int(high_watermark_pct)))
        self.low = max(0, min(self.high - 1, int(low_watermark_pct)))
        self.max = max(1, int(max_batch_size))
        self.min = max(1, min(self.max, int(min_batch_size)))
        self._current = self.max

    def configure(self, cfg: Any) -> None:
        """用 VRamSchedulerConfig 重新配置。"""
        self.enabled = bool(getattr(cfg, "enabled", self.enabled))
        self.high = max(1, min(100, int(getattr(cfg, "vram_high_watermark_pct", self.high))))
        self.low = max(0, min(self.high - 1, int(getattr(cfg, "vram_low_watermark_pct", self.low))))
        self.max = max(1, int(getattr(cfg, "max_batch_size", self.max)))
        self.min = max(1, min(self.max, int(getattr(cfg, "min_batch_size", self.min))))
        if not self.enabled:
            self._current = self.max

    def update(self, free_pct: float | None) -> int:
        """喂入空闲显存百分比，返回当前建议的最大 batch_size。"""
        if not self.enabled or free_pct is None:
            self._current = self.max
            return self._current
        free_pct = max(0.0, min(100.0, float(free_pct)))
        if free_pct >= self.high:
            self._current = self.max
        elif free_pct <= self.low:
            self._current = self.min
        else:
            frac = (free_pct - self.low) / max(1e-6, (self.high - self.low))
            self._current = max(self.min, min(self.max, round(self.min + frac * (self.max - self.min))))
        return self._current

    @property
    def current_max_batch_size(self) -> int:
        return self._current

    def clamp(self, requested: int) -> int:
        """把用户请求的 batch_size 钳制到当前允许上限内。"""
        if not self.enabled:
            return max(1, int(requested))
        return max(self.min, min(int(requested), self._current))


# ──────────────────────────────────────────────────────────────
#  IdleUnloadManager — 空闲自动卸载计时（P2）
# ──────────────────────────────────────────────────────────────
class IdleUnloadManager:
    """跟踪最近一次活跃时间，空闲超过阈值后建议卸载常驻引擎权重。

    实际卸载动作由 app_server 循环在触发 should_unload 时执行
    （需访问 model_registry / model_manager），本类只负责计时判定。
    """

    def __init__(self, idle_unload_minutes: int = 0) -> None:
        self.idle_unload_minutes = max(0, int(idle_unload_minutes))
        self._last_activity_ts = time.time()
        self._unloaded = False

    def mark_activity(self) -> None:
        """标记一次推理活动（任务完成/开始时调用）。"""
        self._last_activity_ts = time.time()
        self._unloaded = False

    def should_unload(self, now: float | None = None) -> bool:
        """空闲时长是否超过阈值（阈值 0 = 禁用）。"""
        if self.idle_unload_minutes <= 0:
            return False
        now = now if now is not None else time.time()
        if self._unloaded:
            return False
        idle_s = now - self._last_activity_ts
        return idle_s >= self.idle_unload_minutes * 60

    def note_unloaded(self) -> None:
        self._unloaded = True

    @property
    def idle_minutes(self) -> float:
        return round((time.time() - self._last_activity_ts) / 60.0, 1)


# ──────────────────────────────────────────────────────────────
#  WeightDedupScanner — 多版本权重孤儿回收扫描（P1）
# ──────────────────────────────────────────────────────────────
def scan_orphan_weights(config: Any, project_root: str | Path) -> dict[str, Any]:
    """扫描模型目录，找出未被任何引擎配置引用的权重文件（孤儿/旧版本）。

    去重策略：先收集所有引擎通过 resolve_engine_model_paths 引用的绝对路径，
    再遍历各模型子目录的全部权重文件，差集即为孤儿。

    Returns:
        {"orphans": [{"path","size_mb"}], "orphan_count", "wasted_mb", "referenced_count"}
    """
    from .config_models import resolve_engine_model_paths

    project_root = Path(project_root).resolve()
    referenced: set[str] = set()
    for engine_cfg in config.models.engines.values():
        try:
            paths = resolve_engine_model_paths(engine_cfg, config.models, project_root)
            for p in paths.values():
                if p:
                    referenced.add(str(Path(p).resolve()).replace("\\", "/"))
        except Exception as e:  # noqa: BLE001
            logger.debug("resolve engine paths failed for dedup scan: %s", e)

    # 收集所有子目录下的权重文件
    exts = (".safetensors", ".pt", ".bin", ".ckpt", ".gguf")
    all_files: list[Path] = []
    roots: list[Path] = []
    try:
        if config.models.model_source_mode == "portable":
            base = project_root / config.models.portable.internal_models_dir
            roots = [base / d for d in config.models.portable.sub_dirs.values()]
        else:
            base = Path(config.models.shared.comfy_models_dir)
            roots = [base / d for d in config.models.shared.mount_map.values()]
        if getattr(config.models, "shared_cache_dir", ""):
            sc = Path(config.models.shared_cache_dir)
            roots = [sc / d for d in config.models.portable.sub_dirs.values()] + roots
    except Exception as e:  # noqa: BLE001
        logger.debug("build weight scan roots failed: %s", e)

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for f in root.rglob("*"):
            if f.is_file() and f.name.lower().endswith(exts):
                all_files.append(f)

    orphans: list[dict[str, Any]] = []
    wasted = 0.0
    for f in all_files:
        key = str(f.resolve()).replace("\\", "/")
        if key not in referenced:
            size_mb = round(f.stat().st_size / (1024 * 1024), 2)
            wasted += size_mb
            orphans.append({"path": key, "size_mb": size_mb})

    return {
        "orphans": orphans,
        "orphan_count": len(orphans),
        "wasted_mb": round(wasted, 2),
        "referenced_count": len(referenced),
    }


# ──────────────────────────────────────────────────────────────
#  FinOpsReporter — 成本分摊报表（P2）
# ──────────────────────────────────────────────────────────────
def finops_cost_report(history_db: Any, config: Any) -> dict[str, Any]:
    """基于 history_db 的任务记录聚合每引擎算力成本估算。

    算力成本以 ``processing_time_s`` 为唯一可量化来源，折算为 GPU·小时。
    假设单 GPU 串行（与本项目的 single_serial worker 一致）。

    Returns:
        {"by_engine":[...], "totals":{...}, "generated_at"}
    """
    rows = history_db.aggregate_cost_by_engine() if hasattr(history_db, "aggregate_cost_by_engine") else []
    by_engine: list[dict[str, Any]] = []
    tot_tasks = tot_out = 0
    tot_s = 0.0
    for r in rows:
        proc_s = float(r.get("total_processing_s") or 0.0)
        gpu_hours = round(proc_s / 3600.0, 4)
        by_engine.append({
            "engine": r.get("engine"),
            "tasks": r.get("tasks", 0),
            "completed": r.get("completed", 0),
            "failed": r.get("failed", 0),
            "output_count": r.get("output_count", 0),
            "total_processing_s": round(proc_s, 2),
            "avg_processing_s": round(proc_s / max(1, r.get("completed", 0)), 3),
            "est_gpu_hours": gpu_hours,
        })
        tot_tasks += r.get("tasks", 0)
        tot_s += proc_s
        tot_out += r.get("output_count", 0)

    return {
        "by_engine": by_engine,
        "totals": {
            "tasks": tot_tasks,
            "total_processing_s": round(tot_s, 2),
            "est_gpu_hours": round(tot_s / 3600.0, 4),
            "output_count": tot_out,
        },
        "note": "est_gpu_hours 假设单 GPU 串行（single_serial worker），为成本分摊下限估算。",
        "generated_at": time.time(),
    }


# ──────────────────────────────────────────────────────────────
#  BudgetChecker — 预算阈值告警（P3）
# ──────────────────────────────────────────────────────────────
def budget_check(config: Any, metrics: dict[str, Any]) -> dict[str, Any]:
    """根据 FinOps 预算阈值与当前指标产出告警列表。

    Args:
        config: AppConfig（含 finops 段）
        metrics: {"gpu":{...}, "storage":{...}, "cost":{...}}

    Returns:
        {"alerts":[...], "within_budget": bool}
    """
    fin = getattr(config, "finops", None)
    alerts: list[dict[str, Any]] = []
    if fin is None:
        return {"alerts": alerts, "within_budget": True}

    # GPU 时租预算（按日均 GPU·小时）
    gpu_budget = float(getattr(fin, "budget_gpu_hours_per_day", 0) or 0)
    if gpu_budget > 0:
        est = metrics.get("cost", {}).get("est_gpu_hours", 0.0)
        if est > gpu_budget:
            alerts.append({
                "level": "warning",
                "dimension": "gpu_hours",
                "budget": gpu_budget,
                "actual": round(est, 4),
                "message": f"GPU·小时 usage {est:.2f} 超过日预算 {gpu_budget:.2f}",
            })

    # 存储预算（GB）
    storage_budget = float(getattr(fin, "storage_gb_budget", 0) or 0)
    if storage_budget > 0:
        used = metrics.get("storage", {}).get("used_gb", 0.0)
        if used > storage_budget:
            alerts.append({
                "level": "warning",
                "dimension": "storage_gb",
                "budget": storage_budget,
                "actual": round(used, 2),
                "message": f"存储使用 {used:.1f}GB 超过预算 {storage_budget:.1f}GB",
            })

    return {"alerts": alerts, "within_budget": len(alerts) == 0}


# ──────────────────────────────────────────────────────────────
#  全局单例 + Depends 获取器
# ──────────────────────────────────────────────────────────────
_metrics_store: MetricsStore | None = None
_vram_scheduler: VRAMScheduler | None = None
_idle_unload_manager: IdleUnloadManager | None = None


def get_metrics_store() -> MetricsStore:
    global _metrics_store
    if _metrics_store is None:
        from .config import get_config

        _metrics_store = MetricsStore(history_points=get_config().gpu.monitor.history_points * 6)
    return _metrics_store


def get_vram_scheduler() -> VRAMScheduler:
    global _vram_scheduler
    if _vram_scheduler is None:
        from .config import get_config

        s = VRAMScheduler()
        s.configure(get_config().runtime.vram_scheduler)
        _vram_scheduler = s
    return _vram_scheduler


def get_idle_unload_manager() -> IdleUnloadManager:
    global _idle_unload_manager
    if _idle_unload_manager is None:
        from .config import get_config

        _idle_unload_manager = IdleUnloadManager(
            idle_unload_minutes=get_config().runtime.idle_unload_minutes
        )
    return _idle_unload_manager
