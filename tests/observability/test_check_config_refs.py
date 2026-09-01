"""
tests/observability/test_check_config_refs.py — P0-1 配置字段检查器单测

验证 check_config_refs.scan_source_for_missing 能正确：
- 放过合法 config 字段访问；
- 捕获未定义字段访问；
- 忽略 getattr(..., default) / .get() 安全访问；
- 忽略非 config 根的属性访问。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = Path(__file__).resolve().parents[2] / "scripts" / "check_config_refs.py"


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("check_config_refs", _SPEC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def fields():
    # 包含链式访问的中间属性（runtime / task_queue / models / engines 等也是真实字段）
    return {
        "idle_unload_minutes", "runtime", "task_queue", "maxsize", "max_timeout_s",
        "project_root", "models", "engines", "display_name", "backend",
    }


def test_legal_access_passes(mod, fields):
    src = "x = config.runtime.idle_unload_minutes\ny = get_config().project_root\n"
    assert mod.scan_source_for_missing(src, fields) == []


def test_undefined_field_flagged(mod, fields):
    src = "x = config.runtime.does_not_exist\n"
    errs = mod.scan_source_for_missing(src, fields)
    assert any("does_not_exist" in e for e in errs)


def test_getattr_with_default_safe(mod, fields):
    src = 'val = getattr(cfg.runtime.task_queue, "maxsize", 0)\n'
    assert mod.scan_source_for_missing(src, fields) == []


def test_dict_get_safe(mod, fields):
    src = "val = config.models.engines.get(name)\n"
    assert mod.scan_source_for_missing(src, fields) == []


def test_non_config_root_ignored(mod, fields):
    src = "val = state.value\nother = mm.get_state(name).value\n"
    assert mod.scan_source_for_missing(src, fields) == []


def test_runtime_method_ignored(mod, fields):
    src = "d = config.runtime.model_dump()\n"
    assert mod.scan_source_for_missing(src, fields) == []
