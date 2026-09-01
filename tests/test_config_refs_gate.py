"""
tests/test_config_refs_gate.py — 配置字段引用完整性 + 安全项「声明即消费」门禁

对应安全评估 #13：config.yaml 的 security 段若存在「声明了但代码从不读取」
的开关，就是典型的假安全感（配置-实现错配）。本测试把
scripts/check_config_refs.py 作为门禁跑通，防止此类错配回归。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_config_refs.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_config_refs", _SCRIPT)
    assert spec and spec.loader, f"无法加载 {_SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_config_models_parseable() -> None:
    """能解析出配置模型与字段（门禁前提）。"""
    mod = _load_module()
    class_fields = mod.collect_class_fields()
    assert class_fields, "未解析到任何配置模型"
    all_fields = set().union(*class_fields.values())
    assert "allowed_base_dirs" in all_fields
    assert "image_read_base_dirs" in all_fields


def test_security_keys_all_consumed() -> None:
    """security 段每个键都被代码消费（无「声明即生效」的假安全感）。"""
    mod = _load_module()
    consumed_paths, consumed_tokens = mod.collect_consumed()
    assert consumed_paths, "未收集到任何配置访问路径"
    mod.errors.clear()
    mod.check_security_keys_consumed(consumed_paths, consumed_tokens)
    assert not mod.errors, "存在未被代码消费的 security 配置键:\n  " + "\n  ".join(mod.errors)


def test_gate_exits_zero() -> None:
    """整体门禁退出码为 0。"""
    mod = _load_module()
    mod.errors.clear()
    class_fields = mod.collect_class_fields()
    all_fields = set().union(*class_fields.values())
    mod.check_code_refs(all_fields, class_fields)
    mod.check_yaml_runtime(class_fields)
    consumed_paths, consumed_tokens = mod.collect_consumed()
    mod.check_security_keys_consumed(consumed_paths, consumed_tokens)
    assert not mod.errors, "配置引用门禁未通过:\n  " + "\n  ".join(mod.errors)
