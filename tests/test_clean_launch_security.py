"""
tests/test_clean_launch_security.py — M-05 启动器安全

- find_winpython 不再硬编码其它项目/系统的绝对解释器路径；
- check_dependencies 缺失时从锁定的 requirements-lock.txt 安装（不装未锁定包）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.clean_launch import PROJECT_ROOT, find_winpython

pytestmark = pytest.mark.security

# 这些硬编码绝对路径在 M-05 前作为解释器探测存在，必须已被移除
_FORBIDDEN_HARDCODED = (
    "SeedVR2-lite",
    "ComfyUI-aki-v3",
    "C:\\Python312",
    r"C:\Users\Doro\APP",
)


def test_no_hardcoded_external_interpreter_paths() -> None:
    """源码中不得再出现硬编码的其它项目/系统解释器路径。"""
    src = Path(__file__).resolve().parents[1] / "app" / "clean_launch.py"
    text = src.read_text(encoding="utf-8")
    for bad in _FORBIDDEN_HARDCODED:
        assert bad not in text, f"仍存在硬编码外部解释器路径: {bad}"


def test_find_winpython_prefers_project_venv() -> None:
    """存在项目 .venv 时优先返回它（不落到外部/系统 Python）。"""
    venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv_py.exists():
        pytest.skip(".venv 不存在，跳过")
    chosen = find_winpython()
    assert "venv" in chosen.replace("\\", "/"), f"应优先项目 .venv，实际: {chosen}"


def test_check_dependencies_uses_lockfile(monkeypatch: pytest.MonkeyPatch) -> None:
    """依赖缺失时从 requirements-lock.txt 安装，而非未锁定包名。"""
    import builtins

    import app.clean_launch as cl

    captured: dict[str, list[str]] = {}
    orig_import = builtins.__import__

    def fake_import(name, *a, **k):  # 模拟 fastapi 缺失
        if name == "fastapi":
            raise ImportError("no fastapi")
        return orig_import(name, *a, **k)

    def fake_check_call(cmd, *a, **k):
        captured["cmd"] = list(cmd)
        return 0

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(cl.subprocess, "check_call", fake_check_call)

    cl.check_dependencies()
    assert captured.get("cmd"), "应触发 pip 安装"
    assert "-r" in captured["cmd"], "应使用 -r 安装锁定文件"
    assert any("requirements-lock.txt" in str(c) for c in captured["cmd"]), \
        "应从 requirements-lock.txt 安装（版本钉死）"
