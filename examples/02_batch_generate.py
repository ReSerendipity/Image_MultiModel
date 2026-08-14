#!/usr/bin/env python3
"""
02_batch_generate.py — 批量生成示例

读取 prompts.txt 中的 Prompt 列表，批量提交生成任务，演示任务队列 + 批量进度查询 + 批量取消。

用法:
    python examples/02_batch_generate.py

需要修改:
    - SERVER_URL: 服务器地址
    - prompts.txt: 编辑此文件添加你的 Prompt（每行一个）
    - base_config 中的参数（引擎 / 分辨率 / steps 等）

前置条件:
    1. Image MultiModel 已启动
    2. 原生引擎已就绪（z_image_turbo_native）
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

# ── 配置 ──────────────────────────────────────────────────
SERVER_URL = "http://127.0.0.1:8288"
PROMPTS_FILE = Path(__file__).parent / "prompts.txt"

# 基础生成参数（所有 Prompt 共享）
base_config = {
    "cfg": 1.0,
    "steps": 8,
    "width": 1024,
    "height": 1024,
    "seed": -1,
    "batch_size": 1,
    "engine_name": "z_image_turbo_native",  # Turbo 引擎更快，适合批量
    "seedvr2_enable": False,         # 批量时关闭超分以加速
    "eses_enable": False,
    "vram_enable": True,
    "vram_reserved_gb": 0.6,
    "output_format": "png",
}


def main() -> None:
    # 1. 读取 Prompt 列表
    if not PROMPTS_FILE.exists():
        print(f"错误: 找不到 Prompt 文件: {PROMPTS_FILE}")
        print("请创建该文件，每行一个 Prompt。")
        sys.exit(1)

    prompts = [line.strip() for line in PROMPTS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not prompts:
        print("错误: prompts.txt 为空")
        sys.exit(1)

    print(f"[1/3] 读取到 {len(prompts)} 条 Prompt:")
    for i, p in enumerate(prompts, 1):
        print(f"      {i}. {p[:60]}...")
    print()

    # 2. 提交批量生成
    print("[2/3] 提交批量生成任务...")
    payload = {
        "prompts": prompts,
        "base_config": base_config,
    }
    resp = requests.post(f"{SERVER_URL}/api/generate/batch", json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    batch_id = result["batch_id"]
    total = result["total_tasks"]
    task_ids = result["task_ids"]
    print(f"      批次 ID: {batch_id}")
    print(f"      总任务数: {total}")
    print(f"      任务 ID 列表: {task_ids[:3]}{'...' if len(task_ids) > 3 else ''}")
    print()

    # 3. 查询批次进度
    print("[3/3] 监控批次进度...")
    try:
        while True:
            resp = requests.get(f"{SERVER_URL}/api/tasks/batch/{batch_id}", timeout=10)
            resp.raise_for_status()
            progress = resp.json()
            pct = progress["progress_pct"]
            print(
                f"      进度: {pct}% "
                f"(完成 {progress['completed']}/{progress['total']}, "
                f"处理中 {progress['processing']}, "
                f"等待 {progress['pending']}, "
                f"失败 {progress['failed']}, "
                f"取消 {progress['cancelled']})"
            )

            if pct >= 100:
                print()
                print("批量生成完成！")
                break

            if progress["failed"] > 0 and progress["processing"] == 0 and progress["pending"] == 0:
                print()
                print(f"批量生成结束（{progress['failed']} 个失败）")
                break

            time.sleep(3)

    except KeyboardInterrupt:
        print()
        print("用户中断，正在取消批次中的剩余任务...")
        # 取消所有未完成的任务
        for tid in task_ids:
            try:
                requests.post(f"{SERVER_URL}/api/tasks/{tid}/cancel", timeout=5)
            except Exception:
                pass
        print("已取消所有任务。")


if __name__ == "__main__":
    main()
