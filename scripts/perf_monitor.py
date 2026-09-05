#!/usr/bin/env python3
"""
Image_MultiModel 性能监控脚本
测量：图像生成 API 响应时间
运行方式：python perf_monitor.py
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


def benchmark():
    """Image 生成性能测试"""
    print("\n🔧 Image_MultiModel 性能基准测试")
    print("=" * 50)

    health_url = "http://127.0.0.1:8288/api/system/health"

    try:
        response = requests.get(health_url, timeout=3)
        if response.status_code == 200:
            print("[Image_MultiModel] ✅ 服务已在运行")

            # 测量 API 响应时间
            times = []
            for i in range(5):
                start = time.time()
                resp = requests.get(health_url, timeout=5)
                duration = (time.time() - start) * 1000
                times.append(duration)
                print(f"  请求 {i + 1}: {duration:.1f}ms")

            avg_time = sum(times) / len(times)
            print(f"\n✅ 平均响应时间：{avg_time:.1f}ms")

            return {
                "avg_response_ms": round(avg_time, 2),
                "min_ms": round(min(times), 2),
                "max_ms": round(max(times), 2),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            print("[Image_MultiModel] ⚠️ 服务返回非 200 状态码")
            return {"error": f"Status code: {response.status_code}"}

    except requests.exceptions.ConnectionError:
        print("[Image_MultiModel] ⚠️ 服务未运行")
        print("请先启动：python -m uvicorn app.integrated_app.app_server:app --host 127.0.0.1 --port 8288")
        return {"error": "Service not running"}
    except Exception as e:
        print(f"[Image_MultiModel] ❌ 异常：{e}")
        return {"error": str(e)}


def monitor_vram_leak(iterations: int = 30, interval: float = 5.0, growth_threshold_gb: float = 2.0) -> dict:
    """长运行显存泄漏监控（MLOps P1·可观测）。

    周期性采样 torch 峰值显存分配（``max_memory_allocated``），检测窗口内
    单调增长泄漏并打印告警。无 GPU / 无 torch 环境下分配量恒为 0，不会误报。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    try:
        from integrated_app.gpu_utils import VRAMLeakMonitor
    except Exception as e:  # noqa: BLE001
        print(f"❌ 无法导入 VRAMLeakMonitor: {e}")
        return {"error": str(e)}

    monitor = VRAMLeakMonitor(growth_threshold_gb=growth_threshold_gb)
    print(f"\n🔧 显存泄漏监控（{iterations} 次，间隔 {interval}s，阈值 {growth_threshold_gb}GB）")
    print("=" * 50)
    for i in range(iterations):
        s = monitor.sample()
        rep = monitor.check_leak()
        if rep["leak_detected"]:
            print(f"  [{i + 1}] ⚠️ 检测到显存泄漏: 累计增长 {rep['growth_gb']}GB（单调={rep['monotonic']}）")
        else:
            print(f"  [{i + 1}] 峰值分配 {s.allocated_bytes / 1024**3:.3f}GB / free {s.free_vram_gb:.2f}GB")
        if i + 1 < iterations:
            time.sleep(interval)
    return monitor.check_leak()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Image_MultiModel 性能 / 显存监控")
    parser.add_argument("--mode", choices=["benchmark", "vram-leak"], default="benchmark")
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--growth-threshold-gb", type=float, default=2.0)
    args = parser.parse_args()

    if args.mode == "vram-leak":
        monitor_vram_leak(
            iterations=args.iterations,
            interval=args.interval,
            growth_threshold_gb=args.growth_threshold_gb,
        )
    else:
        results_dir = Path("./perf/results")
        results_dir.mkdir(exist_ok=True)

        metrics = benchmark()

        output_file = results_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 结果已保存：{output_file}")
