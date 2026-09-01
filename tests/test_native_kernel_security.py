"""
tests/test_native_kernel_security.py — M-04 内核装载安全

- custom_nodes_dir 必须位于项目内（PathGuard 白名单），越权即拒绝；
- vendored 内核完整性基线校验：基线缺失时跳过（零开销），存在时
  能检测篡改（fail-open，仅告警）。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.integrated_app.native.source import resolve_custom_nodes_dir
from app.integrated_app.security.kernel_baseline import (
    generate_kernel_baseline,
    verify_kernel_baseline,
)

pytestmark = pytest.mark.security

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_custom_nodes_outside_project_rejected() -> None:
    """项目外目录（路径穿越）→ RuntimeError。"""
    with pytest.raises(RuntimeError):
        resolve_custom_nodes_dir("/etc/evil_nodes")


def test_custom_nodes_traversal_rejected() -> None:
    """相对路径穿越出项目 → RuntimeError。"""
    with pytest.raises(RuntimeError):
        resolve_custom_nodes_dir("../../etc/evil_nodes")


def test_custom_nodes_nonexistent_rejected() -> None:
    """不存在的目录 → RuntimeError。"""
    with pytest.raises(RuntimeError):
        resolve_custom_nodes_dir("this_dir_does_not_exist_xyz")


def test_custom_nodes_inside_project_accepted() -> None:
    """项目内目录 → 返回解析后的绝对路径（白名单允许）。"""
    # 用项目内真实存在的目录验证白名单放行
    node_dir = _PROJECT_ROOT / "app"
    assert node_dir.is_dir(), "app/ 应存在"
    resolved = resolve_custom_nodes_dir(str(node_dir))
    assert resolved.is_absolute()
    assert str(_PROJECT_ROOT) in str(resolved)


def test_kernel_baseline_skipped_when_missing() -> None:
    """基线文件缺失 → skipped=True，不抛异常、零开销。"""
    with tempfile.TemporaryDirectory() as d:
        fake_root = Path(d) / "comfy_kernel"
        fake_root.mkdir()
        (fake_root / "nodes.py").write_text("x = 1\n", encoding="utf-8")
        # 指向一个确定不存在的基线文件
        res = verify_kernel_baseline(fake_root, baseline_path=str(Path(d) / "no_such_baseline.json"))
        assert res["skipped"] is True
        assert res["ok"] is True


def test_kernel_baseline_detects_tamper() -> None:
    """基线存在且被篡改 → mismatched>0，ok=False（fail-open 不抛）。"""
    with tempfile.TemporaryDirectory() as d:
        fake_root = Path(d) / "comfy_kernel"
        fake_root.mkdir()
        f = fake_root / "nodes.py"
        f.write_text("x = 1\n", encoding="utf-8")
        baseline_path = Path(d) / "baseline.json"
        generate_kernel_baseline(fake_root, baseline_path)
        # 篡改文件内容
        f.write_text("x = 999  # tampered\n", encoding="utf-8")
        res = verify_kernel_baseline(fake_root, baseline_path=baseline_path)
        assert res["skipped"] is False
        assert res["mismatched"] >= 1
        assert res["ok"] is False


def test_kernel_baseline_passes_when_unchanged() -> None:
    """基线存在且未改 → ok=True。"""
    with tempfile.TemporaryDirectory() as d:
        fake_root = Path(d) / "comfy_kernel"
        fake_root.mkdir()
        f = fake_root / "nodes.py"
        f.write_text("x = 1\n", encoding="utf-8")
        baseline_path = Path(d) / "baseline.json"
        generate_kernel_baseline(fake_root, baseline_path)
        res = verify_kernel_baseline(fake_root, baseline_path=baseline_path)
        assert res["skipped"] is False
        assert res["ok"] is True
        assert res["mismatched"] == 0
