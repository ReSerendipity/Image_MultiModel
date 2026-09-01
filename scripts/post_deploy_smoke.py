#!/usr/bin/env python3
"""scripts/post_deploy_smoke.py — P2-11 staging + post-deploy smoke

评估 §9-P2-11 要求：部署后自动检查 health、config、engine list、假生成任务、
队列满保护和 SSE；smoke 失败自动停止晋级，不允许仅打印日志。

设计要点：
- 每个检查独立成函数，签名 `check_X(client, cfg) -> CheckResult`，便于单测；
- 总结果汇总成 `SmokeReport`（含每项耗时与详情），失败时返回非零退出码；
- 同时支持「真服务」和「In-process fake engine」两种目标，CI 与 staging 复用同一份代码；
- SSE 探测使用 stdlib `urllib` 流式读取，避免引入 httpx / requests。

用法：
    python scripts/post_deploy_smoke.py \
        --base-url http://127.0.0.1:8288 \
        --timeout 30 \
        --output smoke_report.json
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any


# ────────────────────────── 结果数据类 ──────────────────────────
@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    duration_s: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class SmokeReport:
    base_url: str
    started_at: float
    finished_at: float = 0.0
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def failed_checks(self) -> list[str]:
        return [r.name for r in self.results if not r.ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "passed": self.passed,
            "failed": self.failed_checks,
            "results": [asdict(r) for r in self.results],
        }


# ────────────────────────── HTTP 客户端 ──────────────────────────
@dataclass
class SmokeClient:
    base_url: str
    timeout: float
    csrf_token: str = ""
    csrf_cookie: str = ""

    def _request(
        self, method: str, path: str, *, body: dict | None = None, headers: dict | None = None, stream: bool = False
    ):
        url = self.base_url.rstrip("/") + path
        data = None
        req_headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        if self.csrf_token:
            req_headers["X-CSRF-Token"] = self.csrf_token
        # CSRF 双重提交：服务端比对 X-CSRF-Token 头与 csrf_token cookie，须同时携带
        if self.csrf_cookie:
            req_headers["Cookie"] = f"csrf_token={self.csrf_cookie}"
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
        return urllib.request.urlopen(req, timeout=self.timeout)  # noqa: S310 - URL 由调用方提供


def get_json(client: SmokeClient, path: str) -> tuple[int, dict | list | None]:
    """GET 路径；返回 (status, parsed_json_or_None)。"""
    return _do_get(client, path, parse_json=True)


def get_text(client: SmokeClient, path: str) -> tuple[int, str]:
    """GET 路径；返回 (status, raw_text)。用于 Prometheus / SSE 等非 JSON 端点。"""
    status, payload = _do_get(client, path, parse_json=False)
    if isinstance(payload, str):
        return status, payload
    return status, ""


def _do_get(client: SmokeClient, path: str, *, parse_json: bool) -> tuple[int, dict | list | str | None]:
    try:
        with client._request("GET", path) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not parse_json:
                return resp.status, raw
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def post_json(client: SmokeClient, path: str, body: dict) -> tuple[int, dict | None]:
    try:
        with client._request("POST", path, body=body) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"raw": raw[:200]}
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


# ────────────────────────── 各检查项 ──────────────────────────
def check_health(client: SmokeClient, _cfg: dict) -> CheckResult:
    t0 = time.perf_counter()
    status, body = get_json(client, "/api/health")
    ok = status == 200 and isinstance(body, dict) and body.get("status") in ("ok", "healthy", "degraded")
    detail = f"HTTP {status}; status={body.get('status') if isinstance(body, dict) else 'n/a'}"
    return CheckResult(
        "health",
        ok,
        detail,
        time.perf_counter() - t0,
        extras={"status": body.get("status") if isinstance(body, dict) else None},
    )


def check_config(client: SmokeClient, _cfg: dict) -> CheckResult:
    """校验 config 端点可服务，且队列 maxsize > 0（与 P1-8 分级过载保护配套）。"""
    t0 = time.perf_counter()
    status, body = get_json(client, "/api/config")
    runtime = body.get("runtime") if isinstance(body, dict) else None
    maxsize = (runtime or {}).get("task_queue", {}).get("maxsize") if isinstance(runtime, dict) else None
    ok = status == 200 and isinstance(body, dict) and bool(body) and isinstance(maxsize, int) and maxsize > 0
    return CheckResult(
        "config",
        ok,
        f"HTTP {status}; runtime.task_queue.maxsize={maxsize}",
        time.perf_counter() - t0,
        extras={"queue_maxsize": maxsize},
    )


def check_engines(client: SmokeClient, _cfg: dict) -> CheckResult:
    t0 = time.perf_counter()
    status, body = get_json(client, "/api/engine/engines")
    ok = status == 200 and isinstance(body, dict)
    engines = body.get("engines") if isinstance(body, dict) else None
    has_zimage = bool(engines and any(e.get("name") == "z_image_turbo_native" for e in engines))
    return CheckResult(
        "engines",
        ok and has_zimage,
        f"HTTP {status}; contains z_image_turbo_native={has_zimage}",
        time.perf_counter() - t0,
        extras={"engine_names": [e.get("name") for e in (engines or [])]} if engines else {},
    )


def check_generation(client: SmokeClient, cfg: dict) -> CheckResult:
    t0 = time.perf_counter()
    payload = {
        "positive_prompt": cfg.get("prompt", "post-deploy smoke"),
        "cfg": 1.0,
        "steps": 4,
        "seed": 1,
        "width": cfg.get("width", 256),
        "height": cfg.get("height", 256),
        "batch_size": 1,
        "engine_name": "z_image_turbo_native",
    }
    status, body = post_json(client, "/api/generate", payload)
    if status != 200 or not isinstance(body, dict) or "task_id" not in body:
        return CheckResult(
            "generation_submit",
            False,
            f"submit HTTP {status}; body={body}",
            time.perf_counter() - t0,
        )
    task_id = body["task_id"]
    deadline = t0 + cfg.get("generation_timeout_s", 30.0)
    last_status = None
    while time.perf_counter() < deadline:
        st, detail = get_json(client, f"/api/tasks/{task_id}")
        if st == 200 and isinstance(detail, dict):
            last_status = detail.get("status")
            if last_status == "completed":
                return CheckResult(
                    "generation_completed",
                    True,
                    f"task {task_id[:12]}… completed",
                    time.perf_counter() - t0,
                    extras={"task_id": task_id, "elapsed_s": round(time.perf_counter() - t0, 3)},
                )
            if last_status == "failed":
                return CheckResult(
                    "generation_completed",
                    False,
                    f"task {task_id[:12]}… failed: {detail.get('error', '')[:120]}",
                    time.perf_counter() - t0,
                    extras={"task_id": task_id},
                )
        time.sleep(0.1)
    return CheckResult(
        "generation_completed",
        False,
        f"task {task_id[:12]}… timed out (last status={last_status})",
        time.perf_counter() - t0,
        extras={"task_id": task_id, "last_status": last_status},
    )


def check_queue_protection(client: SmokeClient, _cfg: dict) -> CheckResult:
    """验证队列过载保护已装载：Prometheus 端点必须暴露 queue_depth / queue_rejected_total，
    且 config.runtime.task_queue.maxsize > 0（与 P1-8 分级过载策略配套）。"""
    t0 = time.perf_counter()
    status, text = get_text(client, "/api/metrics/prometheus")
    has_depth = "queue_depth" in text
    has_reject = "queue_rejected_total" in text
    # 二次确认 maxsize
    _, cfg_body = get_json(client, "/api/config")
    maxsize = 0
    if isinstance(cfg_body, dict):
        maxsize = (cfg_body.get("runtime") or {}).get("task_queue", {}).get("maxsize", 0) or 0
    ok = (status == 200) and has_depth and has_reject and maxsize > 0
    detail = f"prometheus HTTP {status} depth={has_depth} reject={has_reject} maxsize={maxsize}"
    return CheckResult(
        "queue_protection",
        ok,
        detail,
        time.perf_counter() - t0,
        extras={"maxsize": maxsize, "has_depth": has_depth, "has_reject": has_reject},
    )


def check_sse(client: SmokeClient, _cfg: dict) -> CheckResult:
    """验证 SSE 端点可连，且在 timeout 内至少收到 1 个 chunk（含注释行 / 事件 / 心跳）。"""
    t0 = time.perf_counter()
    url = client.base_url.rstrip("/") + "/api/events"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    try:
        resp = urllib.request.urlopen(req, timeout=client.timeout)  # noqa: S310
    except Exception as e:
        return CheckResult("sse", False, f"connect failed: {e}", time.perf_counter() - t0)
    try:
        deadline = t0 + client.timeout
        first_byte = False
        while time.perf_counter() < deadline:
            chunk = resp.read(512)
            if not chunk:
                break
            if not first_byte:
                first_byte = True
            # SSE 服务一般立即输出冒号注释行或事件；只要拿到 1 字节即视为已建流
            return CheckResult(
                "sse",
                True,
                f"connected; first chunk {len(chunk)} bytes",
                time.perf_counter() - t0,
            )
        return CheckResult(
            "sse",
            first_byte,
            "connected but no bytes within timeout",
            time.perf_counter() - t0,
        )
    except Exception as e:
        return CheckResult("sse", False, f"stream error: {e}", time.perf_counter() - t0)
    finally:
        try:
            resp.close()
        except Exception:  # pragma: no cover
            pass


# ────────────────────────── 入口 ──────────────────────────
DEFAULT_CHECKS: list[str] = [
    "health",
    "config",
    "engines",
    "generation",
    "queue_protection",
    "sse",
]


def _resolve_check(name: str) -> Callable[[SmokeClient, dict], CheckResult] | None:
    return {
        "health": check_health,
        "config": check_config,
        "engines": check_engines,
        "generation": check_generation,
        "queue_protection": check_queue_protection,
        "sse": check_sse,
    }.get(name)


def run(base_url: str, timeout: float, checks: list[str], cfg: dict | None = None) -> SmokeReport:
    cfg = cfg or {}
    client = SmokeClient(base_url=base_url, timeout=timeout)
    report = SmokeReport(base_url=base_url, started_at=time.time())
    # 预热：先取 csrf（如有）—— 服务端用「头 == cookie」双重提交校验，
    # 二者值相同，必须同时回传，否则 POST 会 403。
    try:
        with urllib.request.urlopen(  # noqa: S310
            urllib.request.Request(base_url.rstrip("/") + "/api/health", method="GET"),
            timeout=5,
        ) as r:
            csrf = r.headers.get("X-CSRF-Token")
            if csrf:
                client.csrf_token = csrf
                client.csrf_cookie = csrf
    except Exception:  # pragma: no cover - 无 csrf 也可继续
        pass

    for name in checks:
        fn = _resolve_check(name)
        if fn is None:
            report.results.append(CheckResult(name, False, "unknown check"))
            continue
        try:
            report.results.append(fn(client, cfg))
        except Exception as e:  # noqa: BLE001 - 任一检查崩溃即视为失败
            report.results.append(CheckResult(name, False, f"crashed: {e}"))

    report.finished_at = time.time()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="P2-11 staging + post-deploy smoke")
    ap.add_argument("--base-url", default="http://127.0.0.1:8288", help="被测服务 base URL")
    ap.add_argument("--timeout", type=float, default=10.0, help="HTTP / 总体 timeout（秒）")
    ap.add_argument("--checks", default=",".join(DEFAULT_CHECKS), help="逗号分隔的检查项列表")
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--height", type=int, default=256)
    ap.add_argument("--prompt", default="post-deploy smoke")
    ap.add_argument("--generation-timeout", type=float, default=30.0)
    ap.add_argument("--output", default="", help="JSON 报告输出路径（默认仅 stdout）")
    args = ap.parse_args()

    cfg = {
        "width": args.width,
        "height": args.height,
        "prompt": args.prompt,
        "generation_timeout_s": args.generation_timeout,
    }
    checks = [c.strip() for c in args.checks.split(",") if c.strip()]
    report = run(args.base_url, args.timeout, checks, cfg)

    if report.passed:
        print(f"[PASS] smoke 通过（{len(report.results)} 项 / 用时 {report.finished_at - report.started_at:.1f}s）")
    else:
        print(f"[FAIL] smoke 失败：{report.failed_checks}")
        for r in report.results:
            mark = "OK " if r.ok else "FAIL"
            print(f"  [{mark}] {r.name}: {r.detail} ({r.duration_s:.2f}s)")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"[INFO] 已写出 {args.output}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
