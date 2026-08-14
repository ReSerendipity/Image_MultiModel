#!/usr/bin/env python3
"""
04_list_history.py — 查询历史记录示例

调用 GET /api/tasks 查询历史记录，演示分页、搜索、筛选参数。

用法:
    python examples/04_list_history.py

需要修改:
    - SERVER_URL: 服务器地址
    - 查询参数: status / engine / q / favorite / page / page_size

前置条件:
    1. Image MultiModel 已启动
    2. 已有生成历史记录（先跑 01_text_to_image.py 生成几张图）
"""

from __future__ import annotations

import sys

import requests

# ── 配置 ──────────────────────────────────────────────────
SERVER_URL = "http://127.0.0.1:8288"


def list_all_tasks(server_url: str) -> None:
    """查询所有历史任务（分页遍历）"""
    print("=" * 70)
    print("查询全部历史记录")
    print("=" * 70)

    page = 1
    page_size = 20
    all_tasks: list[dict] = []

    while True:
        resp = requests.get(
            f"{server_url}/api/tasks",
            params={"page": page, "page_size": page_size},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        tasks = data["tasks"]
        all_tasks.extend(tasks)

        total = data["total"]
        total_pages = data["total_pages"]

        if page >= total_pages or not tasks:
            break
        page += 1

    print(f"总计: {len(all_tasks)} 条记录\n")
    _print_task_table(all_tasks)


def search_by_keyword(server_url: str, keyword: str) -> None:
    """按关键词搜索历史记录"""
    print("=" * 70)
    print(f"搜索关键词: '{keyword}'")
    print("=" * 70)

    resp = requests.get(
        f"{server_url}/api/tasks",
        params={"q": keyword, "page": 1, "page_size": 50},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    tasks = data["tasks"]

    print(f"匹配: {len(tasks)} 条 (共 {data['total']} 条)\n")
    _print_task_table(tasks)


def filter_by_engine(server_url: str, engine: str) -> None:
    """按引擎筛选历史记录"""
    print("=" * 70)
    print(f"按引擎筛选: {engine}")
    print("=" * 70)

    resp = requests.get(
        f"{server_url}/api/tasks",
        params={"engine": engine, "page": 1, "page_size": 50},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    tasks = data["tasks"]

    print(f"匹配: {len(tasks)} 条 (共 {data['total']} 条)\n")
    _print_task_table(tasks)


def filter_by_status(server_url: str, status: str) -> None:
    """按状态筛选历史记录"""
    print("=" * 70)
    print(f"按状态筛选: {status}")
    print("=" * 70)

    resp = requests.get(
        f"{server_url}/api/tasks",
        params={"status": status, "page": 1, "page_size": 50},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    tasks = data["tasks"]

    print(f"匹配: {len(tasks)} 条 (共 {data['total']} 条)\n")
    _print_task_table(tasks)


def get_task_detail(server_url: str, task_id: str) -> None:
    """查询单个任务详情"""
    print("=" * 70)
    print(f"任务详情: {task_id}")
    print("=" * 70)

    resp = requests.get(f"{server_url}/api/tasks/{task_id}", timeout=10)
    if resp.status_code == 404:
        print("任务不存在")
        return
    resp.raise_for_status()
    task = resp.json()

    print(f"  任务 ID:     {task.get('task_id', '?')}")
    print(f"  引擎:        {task.get('engine', '?')}")
    print(f"  状态:        {task.get('status', '?')}")
    print(f"  模式:        {task.get('mode', '?')}")
    print(f"  Prompt:      {task.get('prompt', '?')[:60]}...")
    print(f"  创建时间:    {task.get('created_at', '?')}")
    print(f"  处理耗时:    {task.get('processing_time_s', '?')}s")
    print(f"  输出数量:    {len(task.get('outputs', []))}")

    gen_config = task.get("generation_config", {})
    if gen_config:
        print("  ── 生成参数 ──")
        print(f"    分辨率:    {gen_config.get('width', '?')}x{gen_config.get('height', '?')}")
        print(f"    Steps:     {gen_config.get('steps', '?')}")
        print(f"    CFG:       {gen_config.get('cfg', '?')}")
        print(f"    Seed:      {gen_config.get('seed', '?')}")

    outputs = task.get("outputs", [])
    if outputs:
        print("  ── 输出文件 ──")
        for out in outputs:
            print(f"    {out.get('output_type', '?')}: {out.get('path', '?')} ({out.get('width', '?')}x{out.get('height', '?')})")


def _print_task_table(tasks: list[dict]) -> None:
    """打印任务列表表格"""
    if not tasks:
        print("  (无记录)")
        return

    # 表头
    print(f"  {'ID':<16} {'引擎':<28} {'状态':<12} {'Prompt':<30} {'时间'}")
    print(f"  {'-'*16} {'-'*28} {'-'*12} {'-'*30} {'-'*20}")

    for t in tasks:
        tid = t.get("task_id", "?")[:16]
        engine = t.get("engine", "?")[:28]
        status = t.get("status", "?")[:12]
        prompt = (t.get("prompt", "") or "")[:30]
        created = t.get("created_at", "?")
        if isinstance(created, (int, float)):
            import time
            created = time.strftime("%Y-%m-%d %H:%M", time.localtime(created))

        print(f"  {tid:<16} {engine:<28} {status:<12} {prompt:<30} {created}")

    print()


def main() -> None:
    # 健康检查
    try:
        resp = requests.get(f"{SERVER_URL}/api/health", timeout=5)
        resp.raise_for_status()
    except Exception:
        print(f"无法连接服务器: {SERVER_URL}")
        sys.exit(1)

    # 1. 查询全部
    list_all_tasks(SERVER_URL)

    # 2. 按引擎筛选
    filter_by_engine(SERVER_URL, "z_image_turbo_native")

    # 3. 按状态筛选
    filter_by_status(SERVER_URL, "completed")

    # 4. 按关键词搜索
    search_by_keyword(SERVER_URL, "cat")

    # 5. 查询第一条记录的详情
    resp = requests.get(f"{SERVER_URL}/api/tasks", params={"page": 1, "page_size": 1}, timeout=10)
    resp.raise_for_status()
    tasks = resp.json()["tasks"]
    if tasks:
        get_task_detail(SERVER_URL, tasks[0]["task_id"])


if __name__ == "__main__":
    main()
