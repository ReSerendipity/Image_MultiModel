#!/usr/bin/env python3
"""
scripts/capacity_baseline.py — P1-9 单机容量基线 runner

评估 §9-P1-9：对引擎 × 分辨率 × batch × LoRA/SeedVR2 profile 运行多轮生成，
记录吞吐、P50/P95/P99、峰值显存、OOM、首预览与落盘时间，并用容量公式推导
「最大安全队列深度」与「扩容触发点」。

无 GPU：默认 IMM_FAKE_ENGINE=1 驱动 FakeEngine，使基线在 CI / CPU 环境可复现；
真实 GPU 基线只需去掉该环境变量并增大 --runs。

容量公式：
    safe_queue_depth = ceil( (latency_budget_s / p95_latency_s) * concurrency )
其中 concurrency = 单 Worker 串行 → 1；latency_budget_s 默认取配置中
队列 85% 档的容忍等待（默认 30s，可由 --latency-budget 覆盖）。
扩容触发点 = safe_queue_depth * 0.85（与分级过载 85% 档对齐）。

用法：
    python scripts/capacity_baseline.py                 # 默认 100 runs/profile
    python scripts/capacity_baseline.py --runs 6 --quick   # CI 快速
    python scripts/capacity_baseline.py --out baseline.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("IMM_FAKE_ENGINE", "1")

# 确保仓库根在 sys.path，支持以 `python scripts/capacity_baseline.py` 直接运行
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class ProfileResult:
    profile: str
    runs: int
    completed: int
    failed: int
    oom: int
    p50_s: float
    p95_s: float
    p99_s: float
    throughput_tps: float
    first_preview_avg_s: float
    persist_avg_s: float
    peak_vram_gb: float = 0.0


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def _reset_peak_vram() -> None:
    """重置 torch 峰值显存统计（无 GPU / 无 torch 时静默跳过）。"""
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:  # pragma: no cover - 无 GPU 环境
        pass


def _sample_peak_vram_gb() -> float:
    """采样当前进程 GPU 峰值显存占用（GB）。无 GPU / 无 torch 时返回 0.0。

    基线要求记录「峰值显存」，故以 torch 的 max_memory_allocated 为准；
    CPU / FakeEngine 环境下恒为 0.0，报告中标记为不可用。
    """
    try:
        import torch

        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / (1024**3), 3)
    except Exception:  # pragma: no cover - 无 GPU 环境
        pass
    return 0.0


def _run_profile(client, profile: str, base: dict, runs: int) -> ProfileResult:
    """对一个 profile 运行 runs 次，收集每轮端到端延迟。"""
    completed = failed = oom = 0
    durations: list[float] = []
    first_preview: list[float] = []
    persist: list[float] = []
    peak_vram_gb = 0.0

    for _ in range(runs):
        payload = dict(base)
        _reset_peak_vram()
        t0 = time.perf_counter()
        r = client.post("/api/generate", json=payload)
        if r.status_code != 200:
            # 队列过载（429/503）：等待并重试一次，避免污染基线计数
            if r.status_code in (429, 503):
                time.sleep(0.5)
                r = client.post("/api/generate", json=payload)
            if r.status_code != 200:
                failed += 1
                continue
        tid = r.json()["task_id"]
        # 串行等待该任务终态（单 Worker，基线测量须避免队列自拥挤）
        deadline = t0 + 60.0
        fp_seen = False
        done = False
        while time.perf_counter() < deadline:
            try:
                d = client.get(f"/api/tasks/{tid}").json()
            except Exception:
                break
            st = d.get("status")
            if not fp_seen and d.get("progress", 0) >= 1:
                first_preview.append(time.perf_counter() - t0)
                fp_seen = True
            peak_vram_gb = max(peak_vram_gb, _sample_peak_vram_gb())
            if st in ("completed", "failed", "cancelled"):
                if st == "completed":
                    completed += 1
                    durations.append(time.perf_counter() - t0)
                    persist.append(d.get("completed_at", 0) - d.get("started_at", 0) or 0.0)
                elif st == "failed":
                    failed += 1
                    err = str(d.get("error", "")).lower()
                    if "oom" in err:
                        oom += 1
                done = True
                break
            time.sleep(0.02)
        if not done:
            failed += 1
        peak_vram_gb = max(peak_vram_gb, _sample_peak_vram_gb())

    total = max(1, completed + failed)
    tput = completed / max(1e-9, sum(durations)) if durations else 0.0
    return ProfileResult(
        profile=profile,
        runs=runs,
        completed=completed,
        failed=failed,
        oom=oom,
        p50_s=_pct(durations, 50),
        p95_s=_pct(durations, 95),
        p99_s=_pct(durations, 99),
        throughput_tps=tput,
        first_preview_avg_s=statistics.fmean(first_preview) if first_preview else 0.0,
        persist_avg_s=statistics.fmean(persist) if persist else 0.0,
        peak_vram_gb=peak_vram_gb,
    )


def discover_lora_names(root: Path | None = None) -> list[str]:
    """发现 model/loras 下可用的 LoRA 文件名（无则返回空列表）。"""
    base = (root or ROOT) / "model" / "loras"
    if not base.is_dir():
        return []
    names = [
        p.stem
        for p in base.iterdir()
        if p.is_file() and p.suffix.lower() in (".safetensors", ".ckpt", ".pt", ".bin")
    ]
    return sorted(names)


def build_postprocess_matrix(root: Path | None = None) -> list[tuple[str, dict]]:
    """构造后处理开关 profile：SeedVR2 on/off + LoRA（若仓内存在 LoRA 权重）。

    与 build_matrix() 的「分辨率 × batch」矩阵互补，共同覆盖报告要求的
    「引擎 × 分辨率 × batch × LoRA × SeedVR2」五维组合。
    """
    base = {
        "positive_prompt": "capacity baseline",
        "cfg": 1.0,
        "steps": 4,
        "seed": 1,
        "width": 1024,
        "height": 1024,
        "batch_size": 1,
        "engine_name": "z_image_turbo_native",
    }
    profiles: list[tuple[str, dict]] = [
        ("1024px_b1_seedvr2_on", dict(base, seedvr2_enable=True)),
        ("1024px_b1_seedvr2_off", dict(base, seedvr2_enable=False)),
    ]
    loras = discover_lora_names(root)
    if loras:
        profiles.append(("1024px_b1_lora1", dict(base, lora_1_name=loras[0], lora_1_strength=1.0)))
    return profiles


def build_matrix() -> list[tuple[str, dict]]:
    """构造待测 profile 矩阵（分辨率 × batch）。"""
    profiles: list[tuple[str, dict]] = []
    base = {
        "positive_prompt": "capacity baseline",
        "cfg": 1.0, "steps": 4, "seed": 1,
        "engine_name": "z_image_turbo_native",
    }
    for res in (256, 512, 1024):
        for batch in (1, 2):
            p = dict(base, width=res, height=res, batch_size=batch)
            profiles.append((f"{res}px_b{batch}", p))
    return profiles


def derive_capacity(results: Iterable[ProfileResult], latency_budget_s: float) -> dict:
    """用容量公式推导最大安全队列深度与扩容触发点。"""
    # 以最慢 profile 的 P95 为准（最保守）
    slowest = max((r.p95_s for r in results), default=0.0)
    if slowest <= 0:
        safe_depth = 1
    else:
        safe_depth = max(1, int((latency_budget_s / slowest) * 1))  # 单 Worker 串行
    expansion_trigger = max(1, int(safe_depth * 0.85))
    return {
        "latency_budget_s": latency_budget_s,
        "slowest_p95_s": round(slowest, 4),
        "safe_queue_depth": safe_depth,
        "expansion_trigger_depth": expansion_trigger,
        "note": "单 Worker 串行（concurrency=1）；多实例水平扩展时按实例数线性放大",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="P1-9 单机容量基线 runner")
    ap.add_argument("--runs", type=int, default=100, help="每个 profile 运行次数（报告建议 >=100）")
    ap.add_argument("--quick", action="store_true", help="快速模式：降低 runs（覆盖 --runs 为 6）")
    ap.add_argument("--latency-budget", type=float, default=30.0, help="P95 等待容忍预算（秒）")
    ap.add_argument("--out", type=str, default="perf/results/capacity_baseline.json", help="结果 JSON 输出路径")
    args = ap.parse_args()

    runs = 6 if args.quick else args.runs

    from fastapi.testclient import TestClient

    from app.integrated_app.app_server import create_app

    print(f"[INFO] 启动容量基线 runner（fake engine，runs={runs}）...")
    with TestClient(create_app(enable_rate_limit=False)) as client:
        token = client.get("/api/health").headers.get("X-CSRF-Token", "")
        if token:
            client.headers["X-CSRF-Token"] = token

        matrix = build_matrix() + build_postprocess_matrix()
        results: list[ProfileResult] = []
        for name, payload in matrix:
            res = _run_profile(client, name, payload, runs)
            results.append(res)
            print(
                f"  {name:22s} completed={res.completed}/{res.runs} "
                f"p50={res.p50_s*1000:.0f}ms p95={res.p95_s*1000:.0f}ms "
                f"p99={res.p99_s*1000:.0f}ms tput={res.throughput_tps:.2f}/s "
                f"oom={res.oom} peak_vram={res.peak_vram_gb:.2f}GB"
            )

    capacity = derive_capacity(results, args.latency_budget)
    peak = max((r.peak_vram_gb for r in results), default=0.0)
    capacity["peak_vram_gb"] = peak
    capacity["vram_measured"] = bool(peak > 0.0)
    report = {
        "runs_per_profile": runs,
        "profiles": [asdict(r) for r in results],
        "capacity": capacity,
    }
    print("\n[CAPACITY] 推导结论：")
    print(f"  最慢 profile P95 = {capacity['slowest_p95_s']*1000:.0f} ms")
    print(f"  最大安全队列深度 = {capacity['safe_queue_depth']}")
    print(f"  扩容触发深度(85%) = {capacity['expansion_trigger_depth']}")
    if peak > 0.0:
        print(f"  峰值显存 = {peak:.2f} GB")
    else:
        print("  峰值显存 = 不可用（无 CUDA / 运行于 FakeEngine，需在有 GPU 的环境复跑）")

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[INFO] 已写出 {args.out}")

    # 推荐把安全队列深度回写到 config.yaml runtime.task_queue.maxsize 的参考值
    print(f"[RECOMMEND] 建议 runtime.task_queue.maxsize 参考值 <= {capacity['safe_queue_depth']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
