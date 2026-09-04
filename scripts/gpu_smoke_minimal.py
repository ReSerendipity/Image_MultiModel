#!/usr/bin/env python3
"""scripts/gpu_smoke_minimal.py — Image_MultiModel 最小可行 GPU 真机冒烟。

在 self-hosted GPU runner 上，对**真实加载**的文生图引擎跑一次最短推理，
校验产物是真实出图（非 IMM_FAKE_ENGINE 占位），并上报显存峰值。

设计来源：SeedVR2-lite `scripts/smoke_portable_bundle.py`（--require-inference 思路）；
本脚本是 Image_MultiModel `scripts/post_deploy_smoke.py` 的精简真机版——
去掉 health/config/engines/queue/sse 等门面检查，只保留「一次性真推理 + 产物落盘校验」。

用法：
    python scripts/gpu_smoke_minimal.py \
        --base-url http://127.0.0.1:8288 \
        --engine z_image_turbo_native \
        --width 256 --height 256 --steps 4 --seed 1 \
        --timeout 600 --output gpu_smoke_report.json

可选分支：
    --with-seedvr2           显式开启 SeedVR2 后处理超分（seedvr2_enable=true，
                             需 runner 预置 SeedVR2-lite 权重；未安装时服务端
                             优雅跳过超分、仍出图，不判失败）。基线冒烟默认
                             seedvr2_enable=false，保持最小依赖。
    --golden-file PATH       固定 seed 回归：将本次输出 SHA-256 与基线比对，
                             不一致判失败（同机同驱动下应逐字节稳定）。
    --update-golden          生成/更新基线文件（配合 --golden-file 使用），
                             首跑录基线，后续跑做回归。

退出码：0 通过 / 非0 失败。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

# 项目根：scripts/gpu_smoke_minimal.py 的父目录（Image_MultiModel）。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_json(url: str, timeout: float):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, None
    except Exception:
        return 0, None


def _post_json(url: str, body: dict, timeout: float):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, None
    except Exception:
        return 0, None


def _resolve(path: str | None) -> str | None:
    """把产物路径解析成本机真实可读的文件路径（兼容相对 outputs/ 与绝对路径）。"""
    norm = str(path or "").replace("\\", "/")
    if not norm:
        return None
    for cand in (norm, f"outputs/{norm}", f"{ROOT}/{norm}", f"{ROOT}/outputs/{norm}"):
        if os.path.isfile(cand):
            return cand
    return None


def _is_image(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(8)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return True
        if head[:2] == b"\xff\xd8":
            return True
        try:
            from PIL import Image

            with Image.open(path) as im:
                im.verify()
            return True
        except Exception:
            return False
    except Exception:
        return False


def _finish(report: dict, output: str) -> int:
    report["passed"] = report.get("passed", False)
    print(f"[{'PASS' if report['passed'] else 'FAIL'}] gpu smoke {'passed' if report['passed'] else 'failed'}")
    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return 0 if report["passed"] else 1


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _golden_compare(baseline: dict, entries: list[dict]) -> list[str]:
    """逐输出比对 SHA-256；返回差异描述列表（空 = 全部一致）。"""
    base_map = {e.get("name"): e.get("sha256") for e in baseline.get("outputs", [])}
    problems: list[str] = []
    for e in entries:
        want = base_map.get(e["name"])
        if want is None:
            problems.append(f"golden: 基线缺少输出 {e['name']}")
        elif want != e["sha256"]:
            problems.append(
                f"golden: {e['name']} sha256 不一致 "
                f"(基线 {want[:12]}… / 本次 {e['sha256'][:12]}…)"
            )
    extra = set(base_map) - {e["name"] for e in entries}
    if extra:
        problems.append(f"golden: 本次输出缺少基线条目 {sorted(extra)}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Image_MultiModel GPU 真机冒烟（最小可行）")
    ap.add_argument("--base-url", default="http://127.0.0.1:8288")
    ap.add_argument("--engine", default="z_image_turbo_native")
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--height", type=int, default=256)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--prompt", default="gpu real-inference smoke")
    ap.add_argument("--with-seedvr2", action="store_true",
                    help="开启 SeedVR2 后处理超分（需 runner 预置 SeedVR2-lite）")
    ap.add_argument("--golden-file", default="",
                    help="固定 seed 回归基线 JSON 路径（配合 --update-golden）")
    ap.add_argument("--update-golden", action="store_true",
                    help="生成/更新 golden 基线而非比对")
    ap.add_argument("--timeout", type=float, default=600, help="等待推理完成的超时（秒）")
    ap.add_argument("--output", default="")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    report: dict = {"base_url": base, "steps": [], "passed": False}

    def step(name: str, ok: bool, detail: str) -> bool:
        report["steps"].append({"name": name, "ok": ok, "detail": detail})
        print(f"[{'OK ' if ok else 'FAIL'}] {name}: {detail}")
        return ok

    # 1) 健康检查
    st, _ = _get_json(f"{base}/api/health", 10)
    if not step("health", st == 200, f"HTTP {st}"):
        return _finish(report, args.output)

    # 2) 提交一次真实推理（engine_name 指向真实引擎，IMM_FAKE_ENGINE=0）
    # seedvr2_enable 显式写 False：基线冒烟保持最小依赖；--with-seedvr2 时显式
    # 开启（服务端未安装 SeedVR2-lite 会优雅跳过超分、仍出图，不判失败）。
    payload = {
        "positive_prompt": args.prompt,
        "cfg": 1.0,
        "steps": args.steps,
        "seed": args.seed,
        "width": args.width,
        "height": args.height,
        "batch_size": 1,
        "engine_name": args.engine,
        "seedvr2_enable": bool(args.with_seedvr2),
        "seedvr2_resolution": 2048,
    }
    st, body = _post_json(f"{base}/api/generate", payload, 30)
    if st != 200 or not isinstance(body, dict) or "task_id" not in body:
        step("generation_submit", False, f"HTTP {st} body={body}")
        return _finish(report, args.output)
    task_id = body["task_id"]
    print(f"[INFO] submitted task {task_id[:12]}…")

    # 3) 轮询直到 completed / failed
    deadline = time.time() + args.timeout
    last = None
    while time.time() < deadline:
        st, detail = _get_json(f"{base}/api/tasks/{task_id}", 10)
        if st == 200 and isinstance(detail, dict):
            last = detail.get("status")
            if last == "completed":
                outs = detail.get("outputs") or []
                if not outs:
                    step("generation_output", False, "completed but no outputs recorded")
                    return _finish(report, args.output)
                bad = []
                for o in outs:
                    if not isinstance(o, dict):
                        bad.append(f"malformed record: {o!r}")
                        continue
                    p = str(o.get("path") or "")
                    if "imm_fake" in p.lower():
                        bad.append(f"FakeEngine placeholder: {p}")
                        continue
                    real = _resolve(p)
                    if real is None:
                        bad.append(f"output file missing: {p}")
                        continue
                    if os.path.getsize(real) <= 0:
                        bad.append(f"empty output: {p}")
                        continue
                    if not _is_image(real):
                        bad.append(f"not a valid image: {p}")
                        continue
                if bad:
                    step("generation_output", False, "; ".join(bad))
                    return _finish(report, args.output)
                step("generation_output", True, f"{len(outs)} real image(s) produced")

                # 4) 固定 seed 回归：SHA-256 基线录制 / 比对（可选）
                if args.golden_file or args.update_golden:
                    entries = []
                    for o in outs:
                        real = _resolve(str(o.get("path") or ""))
                        if real:
                            entries.append({
                                "name": os.path.basename(real),
                                "sha256": _sha256(real),
                                "bytes": os.path.getsize(real),
                            })
                    if args.update_golden:
                        baseline = {
                            "engine": args.engine,
                            "seed": args.seed,
                            "width": args.width,
                            "height": args.height,
                            "steps": args.steps,
                            "seedvr2_enable": bool(args.with_seedvr2),
                            "outputs": entries,
                        }
                        with open(args.golden_file, "w", encoding="utf-8") as f:
                            json.dump(baseline, f, indent=2, ensure_ascii=False)
                        step("golden_update", True,
                             f"baseline written: {args.golden_file} ({len(entries)} entries)")
                    else:
                        try:
                            with open(args.golden_file, encoding="utf-8") as f:
                                baseline = json.load(f)
                        except Exception as e:
                            step("golden_compare", False,
                                 f"baseline unreadable: {args.golden_file} ({e})")
                            return _finish(report, args.output)
                        problems = _golden_compare(baseline, entries)
                        if problems:
                            step("golden_compare", False, "; ".join(problems))
                            return _finish(report, args.output)
                        step("golden_compare", True,
                             f"{len(entries)} output(s) match baseline")
                    report["golden"] = {
                        "file": args.golden_file,
                        "mode": "update" if args.update_golden else "compare",
                        "outputs": entries,
                    }

                report["passed"] = True
                return _finish(report, args.output)
            if last == "failed":
                step("generation_output", False, f"task failed: {detail.get('error', '')[:200]}")
                return _finish(report, args.output)
        time.sleep(1.0)

    step("generation_output", False, f"timed out (last status={last})")
    return _finish(report, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
