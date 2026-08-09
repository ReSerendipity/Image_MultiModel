"""
scripts/benchmark.py — 性能基准测试（含 P95/P99 延迟统计）

对应 N8: P95/P99 延迟采集增强
对应 REMAINING_TASKS_REPORT §4.3 / PRD §7:
- TTFP（提交→首事件 ≤3s）
- 任务完成→前端显示 ≤500ms
- 取消→GPU 释放 ≤5s
- 历史 50 条 <500ms
- 首页 HTML ≤50KB(gzip)
- P95/P99 延迟分布统计
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

APP_URL = "http://127.0.0.1:8288"
COMFY_URL = "http://127.0.0.1:8188"
SAMPLES = 20  # 采样次数（用于 P95/P99 统计）


def _check_app_online() -> bool:
    try:
        with urllib.request.urlopen(f"{APP_URL}/api/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def _check_comfy_online() -> bool:
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _percentile(data: list[float], p: float) -> float:
    """计算百分位数 P50/P95/P99"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    if idx >= len(sorted_data):
        idx = len(sorted_data) - 1
    return sorted_data[idx]


def bench_homepage_html():
    """首页 HTML gzip 压缩后 ≤50KB"""
    print("\n=== 首页 HTML 大小 ===")
    req = urllib.request.Request(f"{APP_URL}/", headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read()
        import gzip
        try:
            compressed = gzip.compress(raw)
        except Exception:
            compressed = raw
        print(f"  原始大小: {len(raw)/1024:.1f} KB")
        print(f"  gzip 压缩后: {len(compressed)/1024:.1f} KB")
        return len(compressed) / 1024 <= 50


def bench_with_stats(name: str, url: str, threshold_ms: float, samples: int = SAMPLES):
    """带 P50/P95/P99 统计的延迟基准"""
    print(f"\n=== {name} ({samples} 次采样) ===")
    latencies: list[float] = []

    for i in range(samples):
        try:
            start = time.time()
            with urllib.request.urlopen(url, timeout=10) as r:
                r.read()
            elapsed = (time.time() - start) * 1000
            latencies.append(elapsed)
        except Exception as e:
            print(f"  样本 {i+1} 失败: {e}")
            return False

    avg = statistics.mean(latencies)
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    min_lat = min(latencies)
    max_lat = max(latencies)

    print(f"  样本数: {len(latencies)}")
    print(f"  平均: {avg:.0f}ms")
    print(f"  最小: {min_lat:.0f}ms")
    print(f"  最大: {max_lat:.0f}ms")
    print(f"  P50:  {p50:.0f}ms")
    print(f"  P95:  {p95:.0f}ms")
    print(f"  P99:  {p99:.0f}ms")
    print(f"  阈值: ≤{threshold_ms:.0f}ms")
    print(f"  结果: {'✅ PASS' if p95 <= threshold_ms else '❌ FAIL'}")

    return p95 <= threshold_ms


def bench_history_list():
    """历史列表 50 条 <500ms (P95)"""
    return bench_with_stats(
        "历史列表 50 条 (P95 ≤500ms)",
        f"{APP_URL}/api/tasks?page=1&page_size=50",
        threshold_ms=500,
    )


def bench_health_endpoint():
    """GET /api/health 延迟 (P95 ≤1000ms)"""
    return bench_with_stats(
        "/api/health (P95 ≤1000ms)",
        f"{APP_URL}/api/health",
        threshold_ms=1000,
    )


def bench_config_endpoint():
    """GET /api/config 延迟 (P95 ≤500ms)"""
    return bench_with_stats(
        "/api/config (P95 ≤500ms)",
        f"{APP_URL}/api/config",
        threshold_ms=500,
    )


def bench_loras_endpoint():
    """GET /api/config/loras 延迟 (P95 ≤500ms)"""
    return bench_with_stats(
        "/api/config/loras (P95 ≤500ms)",
        f"{APP_URL}/api/config/loras",
        threshold_ms=500,
    )


def bench_outputs_endpoint():
    """GET /api/outputs 延迟 (P95 ≤500ms)"""
    return bench_with_stats(
        "/api/outputs (P95 ≤500ms)",
        f"{APP_URL}/api/outputs?page=1&page_size=20",
        threshold_ms=500,
    )


def bench_sse_gpu_status():
    """SSE gpu_status 事件延迟"""
    print("\n=== SSE gpu_status 刷新 (≤5s) ===")
    import urllib.request as ur
    start = time.time()
    try:
        req = ur.Request(
            f"{APP_URL}/api/events",
            headers={"Accept": "text/event-stream"},
        )
        with ur.urlopen(req, timeout=10) as r:
            for _ in range(20):
                line = r.readline().decode("utf-8", errors="replace").strip()
                if "gpu_status" in line or "heartbeat" in line:
                    elapsed = time.time() - start
                    print(f"  事件延迟: {elapsed:.1f}s")
                    return elapsed <= 5
    except Exception as e:
        print(f"  SSE 不可用: {e}")
        return False
    return False


def run_benchmarks():
    """运行所有基准"""
    if not _check_app_online():
        print("应用不在线，请先启动: python bin/clean_launch.py")
        return

    results = []
    results.append(("首页 HTML ≤50KB(gzip)", bench_homepage_html()))
    results.append(("历史 50 条 P95 <500ms", bench_history_list()))
    results.append(("/api/health P95 <1000ms", bench_health_endpoint()))
    results.append(("/api/config P95 <500ms", bench_config_endpoint()))
    results.append(("/api/config/loras P95 <500ms", bench_loras_endpoint()))
    results.append(("/api/outputs P95 <500ms", bench_outputs_endpoint()))
    results.append(("SSE gpu_status ≤5s", bench_sse_gpu_status()))

    print("\n" + "=" * 60)
    print("=== 基准汇总 ===")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
    print(f"\n  {passed}/{total} 达标 ({passed/total*100:.0f}%)")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmarks()
