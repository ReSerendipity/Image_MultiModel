"""
scripts/benchmark.py — 性能基准测试

对应 REMAINING_TASKS_REPORT §4.3 / PRD §7:
- TTFP（提交→首事件 ≤3s）
- 任务完成→前端显示 ≤500ms
- 取消→GPU 释放 ≤5s
- 历史 50 条 <500ms
- 首页 HTML ≤50KB(gzip)
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

APP_URL = "http://127.0.0.1:8288"
COMFY_URL = "http://127.0.0.1:8188"


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


def bench_history_list():
    """历史列表 50 条 <500ms"""
    print("\n=== 历史列表延迟 ===")
    start = time.time()
    with urllib.request.urlopen(f"{APP_URL}/api/tasks?page=1&page_size=50", timeout=10) as r:
        data = json.loads(r.read())
    elapsed = (time.time() - start) * 1000
    print(f"  查询 {len(data.get('tasks', []))} 条: {elapsed:.0f}ms")
    return elapsed < 500


def bench_health_endpoint():
    """GET /api/health 延迟"""
    print("\n=== /api/health 延迟 ===")
    start = time.time()
    with urllib.request.urlopen(f"{APP_URL}/api/health", timeout=10) as r:
        data = json.loads(r.read())
    elapsed = (time.time() - start) * 1000
    print(f"  延迟: {elapsed:.0f}ms")
    print(f"  GPU: {data.get('gpu', {}).get('name', 'N/A')}")
    print(f"  VRAM: {data.get('gpu', {}).get('free_vram_gb', 0):.1f}GB free")
    return elapsed < 1000


def bench_sse_gpu_status():
    """SSE gpu_status 事件延迟"""
    print("\n=== SSE gpu_status 刷新 ===")
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
                if "gpu_status" in line:
                    elapsed = time.time() - start
                    print(f"  gpu_status 事件延迟: {elapsed:.1f}s")
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
    results.append(("历史 50 条 <500ms", bench_history_list()))
    results.append(("/api/health <1s", bench_health_endpoint()))
    results.append(("SSE gpu_status ≤5s", bench_sse_gpu_status()))

    print("\n=== 基准汇总 ===")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status} {name}")
    print(f"\n  {passed}/{total} 达标 ({passed/total*100:.0f}%)")


if __name__ == "__main__":
    run_benchmarks()
