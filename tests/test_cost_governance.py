"""
tests/test_cost_governance.py — 成本资源治理整改验收测试

覆盖 COST_GOVERNANCE_ASSESSMENT_v2.0.0.md 整改路线 P0~P3：
- MetricsStore / VRAMScheduler / IdleUnloadManager
- 多版本权重孤儿扫描 / 共享缓存解析
- 输出 WebP 压缩
- 留存清理真正删除磁盘文件
- FinOps 成本报表 / 预算告警
- governance 路由端点
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrated_app.config_models import (
    AppConfig,
    EngineConfig,
    ModelPaths,
)
from integrated_app.cost_governance import (
    IdleUnloadManager,
    MetricsStore,
    VRAMScheduler,
    budget_check,
    finops_cost_report,
    scan_orphan_weights,
)
from integrated_app.history_db import HistoryDB
from integrated_app.native.output_pipeline import save_image
from integrated_app.routes.governance_routes import router


# ──────────────────────────────────────────────────────────────
#  P1 · MetricsStore
# ──────────────────────────────────────────────────────────────
def test_metrics_store_ring_buffer_and_stats():
    store = MetricsStore(history_points=5)
    for i in range(8):  # 超出 maxlen 验证环形
        store.record_gpu({"total_vram_gb": 10, "used_vram_gb": float(i), "free_vram_gb": 10 - i})
    assert len(store.get_gpu_history()) == 5
    stats = store.gpu_utilization_stats()
    assert stats["samples"] == 5
    assert stats["peak_used_gb"] >= 0
    assert store.latest_gpu is not None


def test_metrics_store_leak_status():
    store = MetricsStore()
    store.record_leak({"leak_detected": True, "growth_gb": 3.0, "reason": "monotonic_growth"})
    assert store.leak_status["leak_detected"] is True


# ──────────────────────────────────────────────────────────────
#  P1 · VRAMScheduler
# ──────────────────────────────────────────────────────────────
def test_vram_scheduler_bounds():
    s = VRAMScheduler(enabled=True, high_watermark_pct=90, low_watermark_pct=70, max_batch_size=4, min_batch_size=1)
    assert s.update(95.0) == 4      # 高水位之上 → max
    assert s.update(60.0) == 1      # 低水位之下 → min
    mid = s.update(80.0)            # 中间线性
    assert 1 <= mid <= 4
    # 禁用时不钳制，原样返回请求值
    s.enabled = False
    assert s.update(None) == 4
    assert s.clamp(100) == 100


def test_vram_scheduler_clamp():
    s = VRAMScheduler(enabled=True, high_watermark_pct=90, low_watermark_pct=70, max_batch_size=4, min_batch_size=1)
    s.update(100.0)  # current = 4
    assert s.clamp(8) == 4
    assert s.clamp(2) == 2


# ──────────────────────────────────────────────────────────────
#  P2 · IdleUnloadManager
# ──────────────────────────────────────────────────────────────
def test_idle_unload_disabled_by_default():
    m = IdleUnloadManager(idle_unload_minutes=0)
    assert m.should_unload() is False


def test_idle_unload_triggers_after_threshold():
    m = IdleUnloadManager(idle_unload_minutes=1)  # 1 分钟
    m.mark_activity()
    assert m.should_unload(now=time.time()) is False
    # 模拟 2 分钟后
    assert m.should_unload(now=time.time() + 120) is True
    m.note_unloaded()
    assert m.should_unload(now=time.time() + 200) is False


# ──────────────────────────────────────────────────────────────
#  P1 · 多版本权重孤儿扫描 / 共享缓存
# ──────────────────────────────────────────────────────────────
def _make_portable_config(tmp: Path, shared_cache: str = "") -> AppConfig:
    cfg = AppConfig()
    cfg.project_root = str(tmp)
    cfg.models.model_source_mode = "portable"
    cfg.models.portable.internal_models_dir = "model"
    cfg.models.shared_cache_dir = shared_cache
    cfg.models.engines = {
        "e1": EngineConfig(
            name="e1",
            unet=ModelPaths(sub_dir="unet", sub_path="real.safetensors"),
        )
    }
    return cfg


def test_scan_orphan_weights(tmp_path: Path):
    cfg = _make_portable_config(tmp_path)
    (tmp_path / "model" / "unet").mkdir(parents=True)
    (tmp_path / "model" / "unet" / "real.safetensors").write_bytes(b"x")      # 被引用
    (tmp_path / "model" / "unet" / "old_v1.safetensors").write_bytes(b"y")    # 孤儿
    res = scan_orphan_weights(cfg, cfg.project_root)
    assert res["orphan_count"] == 1
    assert res["orphans"][0]["path"].endswith("old_v1.safetensors")
    assert res["referenced_count"] == 1


def test_resolve_shared_cache_preference(tmp_path: Path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "unet").mkdir()
    (shared / "unet" / "real.safetensors").write_bytes(b"x")
    cfg = _make_portable_config(tmp_path, shared_cache=str(shared))
    from integrated_app.config_models import resolve_model_path

    p = resolve_model_path(cfg.models.engines["e1"].unet, cfg.models, cfg.project_root)
    p_norm = p.replace("\\", "/")
    shared_norm = str(shared.resolve()).replace("\\", "/")
    assert p_norm.startswith(shared_norm)


# ──────────────────────────────────────────────────────────────
#  P0 · 输出 WebP 压缩
# ──────────────────────────────────────────────────────────────
def test_save_image_webp_real(tmp_path: Path):
    from PIL import Image

    img = Image.new("RGB", (32, 32), color=(123, 200, 50))
    out = tmp_path / "t.webp"
    save_image(out, img, is_tensor=False, image_format="webp", quality=80)
    assert out.exists()
    reopened = Image.open(out)
    assert reopened.format == "WEBP"
    # webp 应明显小于同尺寸 PNG
    png = tmp_path / "t.png"
    save_image(png, img, is_tensor=False, image_format="png")
    assert out.stat().st_size < png.stat().st_size


# ──────────────────────────────────────────────────────────────
#  P0 · 留存清理真正删除磁盘文件
# ──────────────────────────────────────────────────────────────
def test_cleanup_deletes_files(tmp_path: Path):
    db = HistoryDB(tmp_path / "data" / "history.db")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir(parents=True)
    f = outputs_dir / "e1" / "20200101" / "old.png"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"data")
    # 手动插入一条超期任务（created_at 远早于 keep_days）
    db.conn.execute(
        "INSERT INTO tasks (task_id, engine, mode, status, created_at) "
        "VALUES ('old1', 'e1', 'txt2img', 'completed', '2000-01-01 00:00:00')"
    )
    db.conn.execute(
        "INSERT INTO outputs (task_id, path, format) VALUES ('old1', 'e1/20200101/old.png', 'png')"
    )
    db.conn.commit()
    deleted = db.cleanup_old_tasks(keep_days=1, max_gb=0)
    assert deleted == 1
    assert not f.exists()  # 磁盘文件被真正删除
    assert db.get_task("old1") is None


# ──────────────────────────────────────────────────────────────
#  P2 · FinOps 成本报表
# ──────────────────────────────────────────────────────────────
def test_finops_cost_report(tmp_path: Path):
    db = HistoryDB(tmp_path / "data" / "history.db")
    db.conn.execute(
        "INSERT INTO tasks (task_id, engine, mode, status, processing_time_s, output_count) "
        "VALUES ('a', 'e1', 'txt2img', 'completed', 3600.0, 10)"
    )
    db.conn.execute(
        "INSERT INTO tasks (task_id, engine, mode, status, processing_time_s, output_count) "
        "VALUES ('b', 'e1', 'txt2img', 'failed', 0.0, 0)"
    )
    db.conn.commit()
    report = finops_cost_report(db, AppConfig())
    assert report["totals"]["tasks"] == 2
    assert report["totals"]["est_gpu_hours"] == 1.0  # 3600s / 3600
    assert report["by_engine"][0]["engine"] == "e1"


# ──────────────────────────────────────────────────────────────
#  P3 · 预算告警
# ──────────────────────────────────────────────────────────────
def test_budget_check_alert():
    cfg = AppConfig()
    cfg.finops.budget_gpu_hours_per_day = 0.5
    metrics = {"gpu": {}, "storage": {"used_gb": 1.0}, "cost": {"est_gpu_hours": 2.0}}
    res = budget_check(cfg, metrics)
    assert res["within_budget"] is False
    assert len(res["alerts"]) == 1
    assert res["alerts"][0]["dimension"] == "gpu_hours"


def test_budget_check_ok_when_zero_budget():
    cfg = AppConfig()  # budget 全 0
    res = budget_check(cfg, {"gpu": {}, "storage": {"used_gb": 9999}, "cost": {"est_gpu_hours": 9999}})
    assert res["within_budget"] is True


# ──────────────────────────────────────────────────────────────
#  路由端点（轻量 FastAPI，避免拉起完整 lifespan）
# ──────────────────────────────────────────────────────────────
def test_governance_routes():
    app = FastAPI()
    app.state.history_db = HistoryDB(":memory:")
    app.include_router(router)
    client = TestClient(app)
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert "gpu_stats" in r.json()
    r = client.get("/api/vram-scheduler")
    assert r.status_code == 200
    assert "current_max_batch_size" in r.json()
    r = client.get("/api/models/orphans")
    assert r.status_code == 200
    assert "orphan_count" in r.json()
    r = client.get("/api/finops/cost-report")
    assert r.status_code == 200
    assert "totals" in r.json()
    r = client.get("/api/finops/budget")
    assert r.status_code == 200
    assert "within_budget" in r.json()


def test_orphans_prune_requires_confirm(tmp_path: Path):
    app = FastAPI()
    app.state.history_db = HistoryDB(":memory:")
    app.include_router(router)
    client = TestClient(app)
    # 没有 confirm 应 400
    assert client.post("/api/models/orphans/prune").status_code == 400
