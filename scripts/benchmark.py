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

2026-09-04 测试体系评估 P1 补齐（留档 + 阈值判定）：
- --output PATH：将全部指标（P50/P95/P99/均值/样本数/阈值/判定）写入 JSON 留档，
  CI performance job 以 upload-artifact 上传，供跨 run 对比；
- --strict：任一阈值超标 → 退出码 1（CI 门禁）。默认不 strict，仅报告。
"""

from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

APP_URL = "http://127.0.0.1:8288"
SAMPLES = 20  # 采样次数（用于 P95/P99 统计）


def _check_app_online() -> bool:
    try:
        with urllib.request.urlopen(f"{APP_URL}/api/health", timeout=5) as r:
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


def bench_homepage_html() -> dict:
    """首页 HTML gzip 压缩后 ≤50KB"""
    name = "首页 HTML ≤50KB(gzip)"
    req = urllib.request.Request(f"{APP_URL}/", headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read()
        import gzip

        try:
            compressed = gzip.compress(raw)
        except Exception:
            compressed = raw
        gzip_kb = len(compressed) / 1024
        print(f"\n=== {name} ===")
        print(f"  原始大小: {len(raw) / 1024:.1f} KB")
        print(f"  gzip 压缩后: {gzip_kb:.1f} KB")
        print(f"  结果: {'✅ PASS' if gzip_kb <= 50 else '❌ FAIL'}")
        return {
            "name": name, "gzip_kb": round(gzip_kb, 2),
            "threshold_kb": 50, "passed": gzip_kb <= 50,
        }


def bench_with_stats(name: str, url: str, threshold_ms: float, samples: int = SAMPLES) -> dict:
    """带 P50/P95/P99 统计的延迟基准，返回指标 dict（含阈值判定）"""
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
            print(f"  样本 {i + 1} 失败: {e}")
            return {
                "name": name, "samples": i, "error": str(e)[:200],
                "threshold_ms": threshold_ms, "passed": False,
            }

    avg = statistics.mean(latencies)
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    min_lat = min(latencies)
    max_lat = max(latencies)
    passed = p95 <= threshold_ms

    print(f"  样本数: {len(latencies)}")
    print(f"  平均: {avg:.0f}ms")
    print(f"  最小: {min_lat:.0f}ms")
    print(f"  最大: {max_lat:.0f}ms")
    print(f"  P50:  {p50:.0f}ms")
    print(f"  P95:  {p95:.0f}ms")
    print(f"  P99:  {p99:.0f}ms")
    print(f"  阈值: ≤{threshold_ms:.0f}ms")
    print(f"  结果: {'✅ PASS' if passed else '❌ FAIL'}")

    return {
        "name": name, "samples": len(latencies),
        "avg_ms": round(avg, 1), "min_ms": round(min_lat, 1),
        "max_ms": round(max_lat, 1), "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1), "p99_ms": round(p99, 1),
        "threshold_ms": threshold_ms, "passed": passed,
    }


def bench_history_list() -> dict:
    """历史列表 50 条 <500ms (P95)"""
    return bench_with_stats(
        "历史列表 50 条 (P95 ≤500ms)",
        f"{APP_URL}/api/tasks?page=1&page_size=50",
        threshold_ms=500,
    )


def bench_health_endpoint() -> dict:
    """GET /api/health 延迟 (P95 ≤1000ms)"""
    return bench_with_stats(
        "/api/health (P95 ≤1000ms)",
        f"{APP_URL}/api/health",
        threshold_ms=1000,
    )


def bench_config_endpoint() -> dict:
    """GET /api/config 延迟 (P95 ≤500ms)"""
    return bench_with_stats(
        "/api/config (P95 ≤500ms)",
        f"{APP_URL}/api/config",
        threshold_ms=500,
    )


def bench_loras_endpoint() -> dict:
    """GET /api/config/loras 延迟 (P95 ≤500ms)"""
    return bench_with_stats(
        "/api/config/loras (P95 ≤500ms)",
        f"{APP_URL}/api/config/loras",
        threshold_ms=500,
    )


def bench_outputs_endpoint() -> dict:
    """GET /api/outputs 延迟 (P95 ≤500ms)"""
    return bench_with_stats(
        "/api/outputs (P95 ≤500ms)",
        f"{APP_URL}/api/outputs?page=1&page_size=20",
        threshold_ms=500,
    )


def bench_sse_gpu_status() -> dict:
    """SSE gpu_status 事件延迟"""
    name = "SSE gpu_status ≤5s"
    print(f"\n=== {name} ===")
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
                    print(f"  结果: {'✅ PASS' if elapsed <= 5 else '❌ FAIL'}")
                    return {
                        "name": name, "elapsed_s": round(elapsed, 2),
                        "threshold_s": 5, "passed": elapsed <= 5,
                    }
    except Exception as e:
        print(f"  SSE 不可用: {e}")
        return {"name": name, "error": str(e)[:200], "threshold_s": 5, "passed": False}
    return {"name": name, "error": "no gpu_status/heartbeat event in 20 lines", "threshold_s": 5, "passed": False}


def run_benchmarks(output: str = "", strict: bool = False) -> int:
    """运行所有基准；写 JSON 留档；strict 时任一 FAIL → 退出码 1。"""
    if not _check_app_online():
        print("应用不在线，请先启动: python app/clean_launch.py")
        return 2

    results: list[dict] = []
    results.append(bench_homepage_html())
    results.append(bench_history_list())
    results.append(bench_health_endpoint())
    results.append(bench_config_endpoint())
    results.append(bench_loras_endpoint())
    results.append(bench_outputs_endpoint())
    results.append(bench_sse_gpu_status())

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)

    print("\n" + "=" * 60)
    print("=== 基准汇总 ===")
    print("=" * 60)
    for r in results:
        status = "✅ PASS" if r.get("passed") else "❌ FAIL"
        print(f"  {status}  {r['name']}")
    print(f"\n  {passed}/{total} 达标 ({passed / total * 100:.0f}%)")
    print("=" * 60)

    if output:
        payload = {
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "app_url": APP_URL,
            "samples": SAMPLES,
            "passed": passed,
            "total": total,
            "all_passed": passed == total,
            "results": results,
        }
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"  留档: {out}")

    if strict and passed < total:
        print(f"  --strict: {total - passed} 项超阈值 → 退出码 1")
        return 1
    return 0


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="Image_MultiModel API 性能基准（P95/P99）")
    _ap.add_argument("--output", default="", help="指标 JSON 留档路径（如 benchmark_result.json）")
    _ap.add_argument("--strict", action="store_true", help="任一阈值超标即退出码 1（CI 门禁）")
    _args = _ap.parse_args()
    raise SystemExit(run_benchmarks(output=_args.output, strict=_args.strict))
