#!/usr/bin/env python3
"""
03_sse_progress.py — SSE 实时进度监听示例

通过 SSE (Server-Sent Events) 实时监听生成进度条事件，比轮询更优雅。

用法:
    python examples/03_sse_progress.py

需要修改:
    - SERVER_URL: 服务器地址

前置条件:
    1. Image MultiModel 已启动
    2. 可以先启动此脚本监听，然后在 Web UI 或用 01_text_to_image.py 提交任务

注意:
    需要安装 sseclient-py: pip install sseclient-py
    或者使用标准库方式（本示例使用 requests + 手动解析，无需额外依赖）
"""

from __future__ import annotations

import json
import sys
import threading
import time
from typing import Any

import requests

# ── 配置 ──────────────────────────────────────────────────
SERVER_URL = "http://127.0.0.1:8288"
LISTEN_DURATION = 120  # 监听时长（秒），0 = 持续监听


def listen_sse(server_url: str, duration: int) -> None:
    """连接 SSE 端点并实时打印事件"""
    url = f"{server_url}/api/events"
    print(f"连接 SSE: {url}")
    print(f"监听时长: {duration}s" if duration else "持续监听 (Ctrl+C 退出)")
    print("-" * 60)

    start = time.time()
    try:
        resp = requests.get(url, stream=True, timeout=None)
        resp.raise_for_status()

        event_type = ""
        data_buffer = ""

        for line in resp.iter_lines(decode_unicode=True):
            if duration and (time.time() - start) > duration:
                print("\n" + "-" * 60)
                print("监听时长结束")
                break

            if line is None:
                continue

            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_buffer = line[5:].strip()
            elif line == "":
                # 空行 = 事件结束
                if event_type and data_buffer:
                    handle_event(event_type, data_buffer)
                event_type = ""
                data_buffer = ""

    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print("用户中断")
    except requests.ConnectionError:
        print(f"\n连接失败: 请确认服务器已启动 ({server_url})")
        sys.exit(1)


def handle_event(event_type: str, data_str: str) -> None:
    """处理单个 SSE 事件"""
    try:
        data: dict[str, Any] = json.loads(data_str)
    except json.JSONDecodeError:
        data = {"raw": data_str}

    timestamp = data.get("timestamp")
    ts_str = f"[{time.strftime('%H:%M:%S')}]" if not timestamp else f"[{time.strftime('%H:%M:%S', time.localtime(timestamp))}]"

    if event_type == "connected":
        print(f"{ts_str} ✅ SSE 连接已建立")

    elif event_type == "heartbeat":
        # 心跳包，静默
        pass

    elif event_type == "task_status":
        task_id = data.get("task_id", "?")
        status = data.get("status", "?")
        progress = data.get("progress", 0)
        stage = data.get("stage", "")
        bar_len = 30
        filled = int(progress * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"{ts_str} 📋 任务 {task_id[:12]}... [{bar}] {progress*100:.0f}% {status} {stage}")

    elif event_type == "gpu_status":
        gpu_name = data.get("name", "?")
        used = data.get("used_vram_gb", 0)
        total = data.get("total_vram_gb", 0)
        freed = data.get("freed", False)
        pct = (used / total * 100) if total > 0 else 0
        marker = "🔄" if freed else "📊"
        print(f"{ts_str} {marker} GPU: {gpu_name} | VRAM {used:.1f}/{total:.1f}GB ({pct:.0f}%)")

    elif event_type == "model_status":
        engine = data.get("engine", "?")
        state = data.get("state", "?")
        print(f"{ts_str} 🧠 模型 {engine}: {state}")

    elif event_type == "queue_status":
        pending = data.get("pending", 0)
        processing = data.get("processing", 0)
        completed = data.get("completed", 0)
        print(f"{ts_str} 📦 队列: 等待 {pending} | 处理中 {processing} | 完成 {completed}")

    elif event_type == "comfy_preview":
        # 预览图（base64 缩略图），只打印提示不显示图片
        print(f"{ts_str} 🖼️  收到预览图")

    else:
        print(f"{ts_str} ❓ 未知事件: {event_type} | {data_str[:80]}")


def submit_demo_task(server_url: str) -> None:
    """在后台线程提交一个演示任务"""
    time.sleep(2)  # 等 SSE 连接建立
    print("\n--- 提交演示任务 ---")
    payload = {
        "positive_prompt": "a cute cat sitting on a windowsill, warm sunlight, detailed fur",
        "cfg": 1.0,
        "steps": 6,
        "width": 1024,
        "height": 1024,
        "seed": -1,
        "batch_size": 1,
        "engine_name": "z_image_turbo",
        "seedvr2_enable": False,
        "eses_enable": False,
        "vram_enable": True,
        "vram_reserved_gb": 0.6,
        "output_format": "png",
    }
    try:
        resp = requests.post(f"{server_url}/api/generate", json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        print(f"任务已提交: {result['task_id']}")
        print(f"预计耗时: {result.get('estimated_time_s', '?')}s")
        print("-" * 60)
    except Exception as e:
        print(f"提交任务失败: {e}")
        print("-" * 60)


def main() -> None:
    # 如果监听时长 > 0，启动后台线程提交演示任务
    if LISTEN_DURATION > 0:
        thread = threading.Thread(target=submit_demo_task, args=(SERVER_URL,), daemon=True)
        thread.start()

    listen_sse(SERVER_URL, LISTEN_DURATION)


if __name__ == "__main__":
    main()
