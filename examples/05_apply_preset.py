#!/usr/bin/env python3
"""
05_apply_preset.py — 加载并应用预设示例

演示预设管理：列出预设 → 创建预设 → 应用预设 → 使用预设参数生成图片。

用法:
    python examples/05_apply_preset.py

需要修改:
    - SERVER_URL: 服务器地址
    - preset_config: 预设参数内容

前置条件:
    1. Image MultiModel 已启动
    2. ComfyUI 后端已启动且引擎已加载
"""

from __future__ import annotations

import json
import sys
import time

import requests

# ── 配置 ──────────────────────────────────────────────────
SERVER_URL = "http://127.0.0.1:8288"

# 要创建的预设参数（不含 seed，预设不应固定 seed）
PRESET_CONFIG = {
    "positive_prompt": "cinematic portrait of a woman, soft lighting, bokeh background",
    "negative_prompt": "blurry, deformed, extra fingers",
    "cfg": 1.0,
    "steps": 10,
    "width": 1024,
    "height": 1024,
    "batch_size": 1,
    "seedvr2_enable": True,
    "seedvr2_resolution": 2048,
    "eses_enable": True,
    "eses_compare_axis": "horizontal",
    "vram_enable": True,
    "vram_reserved_gb": 0.6,
    "output_format": "png",
}


def list_presets(server_url: str) -> list[dict]:
    """列出所有预设"""
    print("=" * 60)
    print("1. 查询现有预设")
    print("=" * 60)

    resp = requests.get(f"{server_url}/api/presets", timeout=10)
    resp.raise_for_status()
    presets = resp.json()

    if not presets:
        print("  (暂无预设)")
    else:
        for p in presets:
            print(f"  [{p['id']}] {p['name']} (引擎: {p.get('engine_name', '?')})")

    print()
    return presets


def create_preset(server_url: str, name: str, engine: str, config: dict) -> int:
    """创建一个新预设"""
    print("=" * 60)
    print(f"2. 创建预设: '{name}'")
    print("=" * 60)

    payload = {
        "engine_name": engine,
        "name": name,
        "config": config,
        "thumbnail": "",
    }
    resp = requests.post(f"{server_url}/api/presets", json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    preset_id = result["id"]
    print(f"  预设 ID: {preset_id}")
    print(f"  引擎: {engine}")
    print(f"  参数: {json.dumps(config, ensure_ascii=False, indent=2)[:200]}...")
    print()
    return preset_id


def apply_preset(server_url: str, preset_id: int) -> dict:
    """应用预设，返回参数"""
    print("=" * 60)
    print(f"3. 应用预设 (ID: {preset_id})")
    print("=" * 60)

    resp = requests.post(f"{server_url}/api/presets/{preset_id}/apply", timeout=10)
    resp.raise_for_status()
    result = resp.json()
    print(f"  状态: {result['status']}")
    print(f"  引擎: {result['engine_name']}")
    print("  参数已获取，可用于生成")
    print()
    return result


def generate_with_preset(server_url: str, engine: str, config: dict) -> None:
    """使用预设参数生成图片"""
    print("=" * 60)
    print("4. 使用预设参数生成图片")
    print("=" * 60)

    # 从预设参数构建生成请求
    # seed 设为 -1（随机），因为预设不包含固定 seed
    generate_payload = {
        **config,
        "seed": config.get("seed", -1),
        "engine_name": engine,
    }

    print(f"  Prompt: {generate_payload.get('positive_prompt', '')[:50]}...")
    print(f"  引擎: {engine}")
    print(f"  分辨率: {generate_payload.get('width')}x{generate_payload.get('height')}")

    resp = requests.post(f"{server_url}/api/generate", json=generate_payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    task_id = result["task_id"]
    print(f"  任务 ID: {task_id}")
    print(f"  预计耗时: {result.get('estimated_time_s', '?')}s")
    print()

    # 等待完成
    print("  等待生成完成...")
    while True:
        resp = requests.get(f"{server_url}/api/tasks/{task_id}", timeout=10)
        resp.raise_for_status()
        task = resp.json()
        status = task.get("status", "unknown")
        print(f"    状态: {status}")

        if status in ("completed", "failed", "cancelled"):
            break
        time.sleep(2)

    if status == "completed":
        outputs = task.get("outputs", [])
        print(f"  生成完成，输出 {len(outputs)} 张图片")
    else:
        print(f"  任务结束: {status}")
        if task.get("error"):
            print(f"  错误: {task['error']}")


def cleanup_preset(server_url: str, preset_id: int) -> None:
    """删除演示预设"""
    print("=" * 60)
    print(f"5. 清理: 删除演示预设 (ID: {preset_id})")
    print("=" * 60)

    resp = requests.delete(f"{server_url}/api/presets/{preset_id}", timeout=10)
    resp.raise_for_status()
    print(f"  {resp.json()}")


def main() -> None:
    # 健康检查
    try:
        resp = requests.get(f"{SERVER_URL}/api/health", timeout=5)
        resp.raise_for_status()
    except Exception:
        print(f"无法连接服务器: {SERVER_URL}")
        sys.exit(1)

    engine = "flux2_klein_9b_distilled"

    # 1. 查询现有预设
    list_presets(SERVER_URL)

    # 2. 创建新预设
    preset_id = create_preset(SERVER_URL, "示例-人像", engine, PRESET_CONFIG)

    # 3. 应用预设
    applied = apply_preset(SERVER_URL, preset_id)

    # 4. 使用预设参数生成
    generate_with_preset(SERVER_URL, applied["engine_name"], applied["config"])

    # 5. 清理演示预设
    cleanup_preset(SERVER_URL, preset_id)

    print()
    print("完成！")


if __name__ == "__main__":
    main()
