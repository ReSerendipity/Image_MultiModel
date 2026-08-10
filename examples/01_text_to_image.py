#!/usr/bin/env python3
"""
01_text_to_image.py — 最简文生图示例

调用 POST /api/generate 提交生成任务，轮询任务状态，保存结果图片到本地。

用法:
    python examples/01_text_to_image.py

需要修改:
    - SERVER_URL: 如果 Image MultiModel 运行在其他地址
    - prompt: 你想生成的图片描述
    - engine_name: 使用哪个引擎 (flux2_klein_9b_distilled / z_image_turbo)

前置条件:
    1. Image MultiModel 已启动 (python bin/clean_launch.py)
    2. ComfyUI 后端已启动且引擎已加载
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

# ── 配置 ──────────────────────────────────────────────────
SERVER_URL = "http://127.0.0.1:8288"
SAVE_DIR = Path("examples/output")

# ── 生成参数 ──────────────────────────────────────────────
payload = {
    "positive_prompt": "a serene mountain landscape at golden hour, ultra detailed, 8k",
    "negative_prompt": "blurry, low quality, distorted",
    "cfg": 1.0,
    "steps": 8,
    "width": 1024,
    "height": 1024,
    "seed": -1,            # -1 = 随机
    "batch_size": 1,
    "engine_name": "flux2_klein_9b_distilled",
    # 以下为可选高级参数，使用默认值即可
    "seedvr2_enable": True,
    "seedvr2_resolution": 2048,
    "eses_enable": True,
    "vram_enable": True,
    "vram_reserved_gb": 0.6,
    "output_format": "png",
}


def main() -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 健康检查
    print(f"[1/4] 检查服务器健康状态: {SERVER_URL}/api/health")
    resp = requests.get(f"{SERVER_URL}/api/health", timeout=10)
    resp.raise_for_status()
    health = resp.json()
    print(f"      状态: {health['status']}, GPU: {health['gpu']['name']}")
    print()

    # 2. 提交生成任务
    print("[2/4] 提交生成任务...")
    print(f"      Prompt: {payload['positive_prompt'][:60]}...")
    print(f"      引擎: {payload['engine_name']}")
    print(f"      分辨率: {payload['width']}x{payload['height']}, Steps: {payload['steps']}")

    resp = requests.post(f"{SERVER_URL}/api/generate", json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    task_id = result["task_id"]
    print(f"      任务 ID: {task_id}")
    if result.get("estimated_time_s"):
        print(f"      预计耗时: {result['estimated_time_s']:.1f}s")
    if result.get("warning"):
        print(f"      ⚠ 警告: {result['warning']}")
    print()

    # 3. 轮询任务状态
    print("[3/4] 等待生成完成...")
    max_wait = 300  # 最长等待 5 分钟
    start = time.time()
    while time.time() - start < max_wait:
        resp = requests.get(f"{SERVER_URL}/api/tasks/{task_id}", timeout=10)
        if resp.status_code == 404:
            print("      任务不存在")
            sys.exit(1)
        resp.raise_for_status()
        task = resp.json()
        status = task.get("status", "unknown")
        elapsed = time.time() - start
        print(f"      [{elapsed:.0f}s] 状态: {status}")

        if status == "completed":
            break
        elif status in ("failed", "cancelled"):
            print(f"      任务结束: {status}")
            if task.get("error"):
                print(f"      错误: {task['error']}")
            sys.exit(1)
        time.sleep(2)
    else:
        print("      超时！任务未在预期时间内完成")
        sys.exit(1)
    print()

    # 4. 下载结果图片
    print("[4/4] 下载结果图片...")
    outputs = task.get("outputs", [])
    if not outputs:
        print("      没有输出文件")
        sys.exit(1)

    for i, out in enumerate(outputs):
        path = out.get("path", "")
        if not path:
            continue
        # 通过 API 下载图片
        download_url = f"{SERVER_URL}/api/outputs/{path}/download"
        try:
            resp = requests.get(download_url, timeout=60)
            resp.raise_for_status()
            filename = f"{task_id}_{i}_{Path(path).name}"
            save_path = SAVE_DIR / filename
            save_path.write_bytes(resp.content)
            print(f"      已保存: {save_path} ({len(resp.content) / 1024:.0f} KB)")
        except Exception as e:
            print(f"      下载失败 ({path}): {e}")

    print()
    print("完成！图片已保存到:", SAVE_DIR.resolve())


if __name__ == "__main__":
    main()
