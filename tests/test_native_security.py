"""
tests/test_native_security.py — 默认引擎 NativeEngine 权重完整性校验（H-02）

验收：
- verify_weights=True 时 load() 会对 resolve_engine_model_paths 解析出的权重做校验；
- 损坏权重（pickle 载荷）在 fail_closed_on_corrupt_weight=True 时抛 WeightIntegrityError；
- 文件缺失（懒加载未就位）时不阻断启动，跳过校验；
- 合法 safetensors 文件通过校验并继续加载。
"""

from __future__ import annotations

import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.integrated_app.native.engine import NativeEngine
from app.integrated_app.security.weight_integrity import WeightIntegrityError


def _make_safetensors(path: Path) -> None:
    """写一个最小合法 safetensors 文件（空 header，0 张量）。"""
    header = b"{}"
    path.write_bytes(struct.pack("<Q", len(header)) + header)


def _make_pickle(path: Path) -> None:
    """写一个 pickle 魔数文件（触发 CWE-502 危险载荷检测）。"""
    path.write_bytes(b"\x80\x02cbuiltins\nexec\n(S'x'\ntR.")


def _fake_config(
    *,
    verify_weights: bool = True,
    fail_closed: bool = False,
    only_safetensors: bool = True,
    engine_name: str = "z_image_turbo_native",
) -> SimpleNamespace:
    model_format = SimpleNamespace(
        verify_weights=verify_weights,
        fail_closed_on_corrupt_weight=fail_closed,
        only_safetensors=only_safetensors,
        # 2026-09-04 安全评估 M4 新增字段：未登记权重策略（engine 校验路径消费）
        allow_unregistered_weights=True,
    )
    security = SimpleNamespace(model_format=model_format)
    engines = {engine_name: SimpleNamespace(name=engine_name)}
    models = SimpleNamespace(engines=engines)
    return SimpleNamespace(
        models=models,
        security=security,
        project_root=Path(__file__).resolve().parents[1],
    )


@pytest.fixture
def patch_source_load():
    """屏蔽 comfy 源码装载（避免重型 import comfy），保持测试轻量。"""
    with patch("app.integrated_app.native.source.ensure_loaded", return_value=None) as m:
        yield m


@pytest.mark.asyncio
async def test_corrupt_weight_fail_closed_raises(patch_source_load, tmp_path):
    """损坏权重 + fail_closed=True → load() 抛 WeightIntegrityError。"""
    corrupt = tmp_path / "unet.safetensors"
    _make_pickle(corrupt)

    cfg = _fake_config(fail_closed=True)
    with patch(
        "app.integrated_app.native.engine.get_config", return_value=cfg
    ), patch(
        "app.integrated_app.native.engine.resolve_engine_model_paths",
        return_value={"unet": str(corrupt)},
    ):
        eng = NativeEngine(name="z_image_turbo_native")
        with pytest.raises(WeightIntegrityError):
            await eng.load()
    assert not eng.is_ready()


@pytest.mark.asyncio
async def test_corrupt_weight_fail_open_skips(patch_source_load, tmp_path):
    """损坏权重 + fail_closed=False → 跳过该权重，load() 正常完成。"""
    corrupt = tmp_path / "unet.safetensors"
    _make_pickle(corrupt)

    cfg = _fake_config(fail_closed=False)
    with patch(
        "app.integrated_app.native.engine.get_config", return_value=cfg
    ), patch(
        "app.integrated_app.native.engine.resolve_engine_model_paths",
        return_value={"unet": str(corrupt)},
    ):
        eng = NativeEngine(name="z_image_turbo_native")
        await eng.load()  # 不应抛异常
    assert eng.is_ready()


@pytest.mark.asyncio
async def test_missing_weight_skipped_lazy(patch_source_load, tmp_path):
    """权重文件尚未就位（file_not_found）→ 跳过校验，不阻断启动。"""
    cfg = _fake_config()
    with patch(
        "app.integrated_app.native.engine.get_config", return_value=cfg
    ), patch(
        "app.integrated_app.native.engine.resolve_engine_model_paths",
        return_value={"unet": str(tmp_path / "not_yet.safetensors")},
    ):
        eng = NativeEngine(name="z_image_turbo_native")
        await eng.load()
    assert eng.is_ready()


@pytest.mark.asyncio
async def test_valid_safetensors_passes(patch_source_load, tmp_path):
    """合法 safetensors → 通过校验，load() 继续。"""
    good = tmp_path / "unet.safetensors"
    _make_safetensors(good)

    cfg = _fake_config(fail_closed=True)
    with patch(
        "app.integrated_app.native.engine.get_config", return_value=cfg
    ), patch(
        "app.integrated_app.native.engine.resolve_engine_model_paths",
        return_value={"unet": str(good)},
    ):
        eng = NativeEngine(name="z_image_turbo_native")
        await eng.load()
    assert eng.is_ready()


@pytest.mark.asyncio
async def test_verify_disabled_skips_check(patch_source_load, tmp_path):
    """verify_weights=False → 即便权重损坏也不校验，load() 正常完成。"""
    corrupt = tmp_path / "unet.safetensors"
    _make_pickle(corrupt)

    cfg = _fake_config(verify_weights=False, fail_closed=True)
    with patch(
        "app.integrated_app.native.engine.get_config", return_value=cfg
    ), patch(
        "app.integrated_app.native.engine.resolve_engine_model_paths",
        return_value={"unet": str(corrupt)},
    ):
        eng = NativeEngine(name="z_image_turbo_native")
        await eng.load()
    assert eng.is_ready()
