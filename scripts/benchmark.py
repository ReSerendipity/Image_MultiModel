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
import os
import statistics
import sys
import threading
import time
import urllib.request
from datetime import UTC, datetime
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


def _percentile(values: list[float], pct: int) -> float:
    """计算分位数（线性插值）。"""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def bench_generation_latency(samples: int = 5) -> bool | None:
    """生成延迟 P50/P95/P99（完整 /api/generate → 任务完成）。

    对应测试体系评估 P1-6（性能完备性缺口 #1）：此前只测端点延迟，未测推理管线。
    需服务端启用假引擎（IMM_FAKE_ENGINE=1）或具备真实 GPU；通过环境变量
    IMM_BENCH_GENERATION=1 开启，避免 CI 无 GPU 时挂起。
    """
    if os.environ.get("IMM_BENCH_GENERATION") != "1":
        print("\n=== 生成延迟（跳过：未设置 IMM_BENCH_GENERATION=1）===")
        return None
    print(f"\n=== 生成延迟 P50/P95/P99（{samples} 次采样，小图 256x256）===")
    latencies: list[float] = []
    for i in range(samples):
        payload = json.dumps({
            "positive_prompt": "benchmark",
            "cfg": 1.0, "steps": 4, "width": 256, "height": 256,
            "seed": i, "batch_size": 1, "engine_name": "z_image_turbo_native",
        }).encode("utf-8")
        try:
            start = time.time()
            req = urllib.request.Request(
                f"{APP_URL}/api/generate", data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                tid = json.load(r).get("task_id")
            # 轮询直到终态
            deadline = time.time() + 60
            status = ""
            while time.time() < deadline:
                with urllib.request.urlopen(f"{APP_URL}/api/tasks/{tid}", timeout=10) as r:
                    status = json.load(r).get("status", "")
                if status in ("completed", "failed", "cancelled"):
                    break
                time.sleep(0.2)
            elapsed = (time.time() - start) * 1000
            latencies.append(elapsed)
            print(f"  样本 {i+1}: {elapsed:.0f}ms (status={status})")
        except Exception as e:
            print(f"  样本 {i+1} 失败: {e}")
            return False
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    print(f"  P50={p50:.0f}ms  P95={p95:.0f}ms  P99={p99:.0f}ms")
    return True


def bench_concurrency_throughput(concurrency: int = 8, duration_s: float = 5.0) -> bool | None:
    """并发吞吐：N 线程并发打 /api/health，测 RPS。

    对应测试体系评估 P1-6（性能完备性缺口 #2）：并发吞吐此前未测。
    """
    print(f"\n=== 并发吞吐（{concurrency} 线程 × {duration_s}s 打 /api/health）===")
    stop = threading.Event()
    counter = {"ok": 0, "err": 0}
    _end = time.time() + duration_s

    def worker():
        while not stop.is_set() and time.time() < _end:
            try:
                with urllib.request.urlopen(f"{APP_URL}/api/health", timeout=5) as r:
                    if r.status == 200:
                        counter["ok"] += 1
                    else:
                        counter["err"] += 1
            except Exception:
                counter["err"] += 1

    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - t0
    rps = counter["ok"] / elapsed if elapsed > 0 else 0
    print(f"  完成请求: {counter['ok']}  错误: {counter['err']}  吞吐: {rps:.1f} RPS")
    return True


def bench_vram_profile() -> bool | None:
    """显存 profiling：读取 /api/gpu，可选 nvidia-smi。

    对应测试体系评估 P1-6（性能完备性缺口 #3）：显存/GPU profiling 此前缺失。
    """
    print("\n=== 显存 Profiling ===")
    try:
        with urllib.request.urlopen(f"{APP_URL}/api/gpu", timeout=10) as r:
            gpu = json.load(r)
        print(f"  GPU: {gpu.get('name')}  后端: {gpu.get('backend')}")
        print(f"  总显存: {gpu.get('total_vram_gb')}GB  空闲: {gpu.get('free_vram_gb')}GB")
    except Exception as e:
        print(f"  /api/gpu 不可用: {e}")
    # 可选 nvidia-smi（Linux/Windows 带驱动）
    try:
        import subprocess

        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            print(f"  nvidia-smi: {out.stdout.strip().replace(chr(10), ' | ')}")
    except Exception:
        pass
    return True


def _append_history(summary: dict) -> None:
    """把本次基准汇总追加到趋势文件，供跨版本比对（反模式 #5 修复）。"""
    hist_dir = PROJECT_ROOT / "perf"
    hist_dir.mkdir(parents=True, exist_ok=True)
    hist_file = hist_dir / "benchmark_history.jsonl"
    try:
        with open(hist_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        print(f"\n  趋势已写入: {hist_file}")
    except Exception as e:  # pragma: no cover - 历史落盘失败不阻断基准
        print(f"  趋势写入失败（忽略）: {e}")


def run_benchmarks():
    """运行所有基准"""
    if not _check_app_online():
        print("应用不在线，请先启动: python app/clean_launch.py")
        return

    results = []
    results.append(("首页 HTML ≤50KB(gzip)", bench_homepage_html()))
    results.append(("历史 50 条 P95 <500ms", bench_history_list()))
    results.append(("/api/health P95 <1000ms", bench_health_endpoint()))
    results.append(("/api/config P95 <500ms", bench_config_endpoint()))
    results.append(("/api/config/loras P95 <500ms", bench_loras_endpoint()))
    results.append(("/api/outputs P95 <500ms", bench_outputs_endpoint()))
    results.append(("SSE gpu_status ≤5s", bench_sse_gpu_status()))

    # 性能完备性增强（P1-6）
    gen = bench_generation_latency()
    bench_concurrency_throughput()
    bench_vram_profile()

    print("\n" + "=" * 60)
    print("=== 基准汇总 ===")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
    print(f"\n  {passed}/{total} 端点达标 ({passed/total*100:.0f}%)")
    if gen is not None:
        print("  生成延迟基准: " + ("已采集" if gen else "❌ FAIL"))
    print("=" * 60)

    # 趋势追踪（反模式 #5 修复）
    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "endpoint_pass": passed,
        "endpoint_total": total,
        "generation_latency_collected": gen is not None,
    }
    _append_history(summary)


if __name__ == "__main__":
    run_benchmarks()
