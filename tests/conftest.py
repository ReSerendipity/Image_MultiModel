"""
conftest.py — pytest 共享 fixture 与路径注入

对应 TEST_AUDIT_REPORT P0-3: 消除 9 个测试文件的 sys.path.insert 重复
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# ── 统一路径注入 ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"
TESTS_DIR = Path(__file__).resolve().parent

# 避免重复插入
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# 使 `from factories import ...`（tests/factories.py）可直接导入
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

# ── 无 GPU 测试环境默认启用假引擎 ──────────────────────────
# 测试/CI 环境无可用 GPU（亦无 comfy/torch 推理栈），所有「提交生成 → worker 处理」
# 的集成测试必须走 FakeEngine 才能可复现。生产环境不设置该变量，绝不生效。
# 统一在此置默认，避免各测试文件各自 setdefault 的竞态导致 batch_size 被 VRAM
# 调度器随机钳制（生成结果不确定 / flaky）。
os.environ.setdefault("IMM_FAKE_ENGINE", "1")


# ── 共享 fixture ────────────────────────────────────────────
@pytest.fixture
def project_root():
    """项目根目录"""
    return PROJECT_ROOT


@pytest.fixture
def tmp_db(tmp_path):
    """临时 HistoryDB 实例（自动关闭）"""
    from integrated_app.history_db import HistoryDB

    db = HistoryDB(tmp_path / "test_history.db")
    yield db
    db.close()


@pytest.fixture
def path_guard(project_root):
    """PathGuard 实例（4 个白名单目录）"""
    from integrated_app.security.path_guard import PathGuard

    return PathGuard(
        allowed_base_dirs=["outputs/", "data/", "workflows/", "model/"],
        project_root=str(project_root),
    )


# ── 环境感知：原生引擎栈不可用时跳过相关测试 ──────────────────
def _torch_is_functional() -> bool:
    """检测当前环境是否具备可用的 PyTorch（部分环境仅有占位/损坏的 torch）。"""
    try:
        import torch

        return bool(hasattr(torch, "tensor") and hasattr(torch, "__version__"))
    except Exception:  # pragma: no cover - 导入异常即视为不可用
        return False


def _comfy_available() -> bool:
    """检测原生引擎运行所需的 comfy 扩展是否可用。"""
    try:
        import comfy_aimdo  # noqa: F401

        return True
    except Exception:  # pragma: no cover - 依赖缺失
        return False


_TORCH_OK = _torch_is_functional()
_COMFY_OK = _comfy_available()
_ENGINE_OK = _TORCH_OK and _COMFY_OK

# 依赖原生引擎栈（torch + comfy）的测试文件：环境不可用时整体跳过
_NATIVE_TEST_FILES = {
    "test_preprocessors.py",
    "test_generate_routes.py",
    "test_forward_batch_and_cancel.py",
    "test_forward_path_api.py",
}


def pytest_collection_modifyitems(config, items):
    """原生引擎栈（torch / comfy_aimdo）不可用时，跳过依赖它的测试。

    仅作用于缺失可用 PyTorch 或 comfy 扩展的环境；在完整环境上
    ``_ENGINE_OK`` 为 True，本钩子不生效，全部测试照常执行。
    """
    if _ENGINE_OK:
        return
    skip_marker = pytest.mark.skip(reason="原生引擎栈不可用（缺 PyTorch 或 comfy_aimdo），跳过引擎相关测试")
    for item in items:
        name = Path(item.path).name
        if name.startswith("test_native_") or name in _NATIVE_TEST_FILES:
            item.add_marker(skip_marker)


# ── 反模式 #3 防护：消除测试间共享全局状态（对应测试体系评估 P2-8）────
@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    """每个测试结束后重置 app.dependency_overrides，避免跨测试状态污染。

    说明：路由测试沿用模块级 TestClient（函数级 `with TestClient` 会触发
    lifespan 关闭竞争导致偶发 hang，故不强行改为函数级）。此处通过自动清理
    FastAPI 的依赖覆盖注册表，消除"共享全局状态"这一主要污染面。
    """
    from integrated_app.app_server import app

    yield
    app.dependency_overrides.clear()


# ── 反模式 #3 防护（续）：重置限流器命中桶 ───────────────────────
@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """每个用例前后清空限流器命中计数，避免模块级共享 client 累积请求

    耗尽 per-IP 限流预算（infer 30/min）使后续用例误判 429。生产运行时
    本夹具同样运行，但测试间隔内无请求累积，对行为无影响。

    注意：测试环境 sys.path 同时包含 ``PROJECT_ROOT`` 与 ``PROJECT_ROOT/app``，
    同一份 ``rate_limit.py`` 可能被加载为 ``integrated_app.middleware.rate_limit``
    与 ``app.integrated_app.middleware.rate_limit`` 两个模块对象（取决于首个
    导入方的写法）。运行中的中间件用哪一个，重置就必须瞄准同一个。这里两个
    名字都尝试重置，确保无论 app 以哪种形式加载都能清空对应桶。
    """
    import sys

    def _reset_all():
        for modname in (
            "integrated_app.middleware.rate_limit",
            "app.integrated_app.middleware.rate_limit",
        ):
            mod = sys.modules.get(modname)
            if mod is not None and hasattr(mod, "reset_rate_limiters"):
                mod.reset_rate_limiters()

    _reset_all()
    yield
    _reset_all()


# ── 反模式 #4 防护：隔离 HistoryDB，消除 xdist 跨 worker 共享 DB 的锁竞争 ──
@pytest.fixture(autouse=True, scope="session")
def _isolate_history_db_for_tests():
    """测试/CI 环境：将应用 HistoryDB 重定向到每进程（每 xdist worker）临时目录。

    根因：``create_app()`` 复用全局配置单例，其 ``output.history.db_path`` 默认
    为 ``data/history.db``（项目根下的固定相对路径）。pytest-xdist 多 worker 并
    行时，每个 worker 进程都打开同一个物理文件，并发写入触发 SQLite
    ``database is locked``；生成 worker 捕获该异常后将任务标记为 ``failed``，
    于是 ``generation_completed_total`` 不增（``test_generation_lifecycle_counters_
    increment`` 偶发失败），``test_run_profile_completes_serial`` 也偶发 sqlite 锁
    失败。这都是共享 DB 竞争的表象，而非被测逻辑缺陷。

    修复：按 worker 进程（pid）分配独立临时目录，使各 worker 的 HistoryDB 互不
    干扰；worker 内测试串行执行，无锁竞争。生产不加载本 conftest，且 db_path 仅
    在测试期被覆盖，生产行为不受影响。

    注意：刻意不使用 pytest 的 tmp_path/tmp_path_factory —— Windows 上其
    ``pytest-current`` 符号链接清理会抛 PermissionError [WinError 5]（与被测代码
    无关，见 test_capacity_baseline._make_root 的同类规避）。
    """
    from integrated_app.config import get_config

    cfg = get_config()
    original_db_path = cfg.output.history.db_path
    original_uploads_dir = cfg.output.uploads.cache_dir
    original_cleanup_cron = cfg.output.history.cleanup_cron
    # 维护 cron 用环境开关禁用（见 app_server.history_cleanup_cron）：
    # load_config(path) 会整体替换配置单例，仅改 cleanup_cron 字段可能被冲掉。
    original_disable_env = os.environ.get("IMM_DISABLE_MAINTENANCE_CRON")
    os.environ["IMM_DISABLE_MAINTENANCE_CRON"] = "1"
    worker_tmp = Path(tempfile.mkdtemp(prefix=f"imm-hist-{os.getpid()}-"))
    cfg.output.history.db_path = str(worker_tmp / "history.db")
    # uploads 目录重定向为第二道防线（cron 已关，正常不会扫到真实上传文件）
    cfg.output.uploads.cache_dir = str(worker_tmp / "uploads")
    cfg.output.history.cleanup_cron = ""

    def _cleanup():
        shutil.rmtree(worker_tmp, ignore_errors=True)

    atexit.register(_cleanup)
    try:
        yield
    finally:
        cfg.output.history.db_path = original_db_path
        cfg.output.uploads.cache_dir = original_uploads_dir
        cfg.output.history.cleanup_cron = original_cleanup_cron
        if original_disable_env is None:
            os.environ.pop("IMM_DISABLE_MAINTENANCE_CRON", None)
        else:
            os.environ["IMM_DISABLE_MAINTENANCE_CRON"] = original_disable_env
        _cleanup()
