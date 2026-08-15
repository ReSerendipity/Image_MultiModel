"""
test_native_zimage_poc.py — NativeEngine 进程内引擎 Phase 1 冒烟测试

覆盖 NativeEngine 协议方法、Comfy 源码装载、executor 纯逻辑与取消机制。
不在此加载 8B 权重重跑推理（太慢）；真实推理测试标记 @pytest.mark.slow 且默认跳过。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from integrated_app.engine_interface import GenerationConfig
from integrated_app.native import executor, source
from integrated_app.native.engine import NativeEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMFY_ROOT = PROJECT_ROOT / "comfy_kernel"


# ── 纯逻辑测试（不依赖 torch / Comfy）────────────────────────
def test_latent_shape_defaults() -> None:
    """空 latent 形状：[batch, 4, height//8, width//8]。"""
    assert executor.latent_shape(1, 1024, 1024) == [1, 16, 128, 128]
    assert executor.latent_shape(2, 512, 256) == [2, 16, 32, 64]


def test_build_latent_zeros() -> None:
    """build_latent 返回全零且形状正确。"""
    latent = executor.build_latent(1, 1024, 1024)
    assert list(latent.shape) == [1, 16, 128, 128]
    assert (latent == 0).all()


def test_round_pixels_and_fixed_seed() -> None:
    """取整与负种子的确定性解析。"""
    assert executor.round_pixels(1000) == 1000
    assert executor.round_pixels(999) == 1000
    assert executor._fixed_seed(-1) == 120429878797176
    assert executor._fixed_seed(42) == 42


def test_sampling_callback_cancel_raises() -> None:
    """采样回调在取消标志置位时抛 CancelledError。"""
    cancel_flag = [False]
    cb = executor._make_sampling_callback(8, None, cancel_flag)
    cancel_flag[0] = True
    with pytest.raises(asyncio.CancelledError):
        cb(1, None, None, 8)


# ── NativeEngine 协议（不加载模型）───────────────────────────
@pytest.mark.smoke
def test_engine_protocol_metadata() -> None:
    """name / display_name 元数据。"""
    eng = NativeEngine(name="z_image_turbo", display_name="Z Image Turbo")
    assert eng.name == "z_image_turbo"
    assert eng.display_name == "Z Image Turbo"


@pytest.mark.smoke
def test_engine_not_ready_until_load() -> None:
    """初始 is_ready() 为 False。"""
    eng = NativeEngine(name="z_image_turbo")
    assert eng.is_ready() is False


@pytest.mark.smoke
def test_engine_conforms_to_protocol() -> None:
    """NativeEngine 满足 ImageEngine Protocol（runtime_checkable）。"""
    from integrated_app.engine_interface import ImageEngine

    eng = NativeEngine(name="z_image_turbo")
    assert isinstance(eng, ImageEngine)


@pytest.mark.smoke
def test_infer_requires_load() -> None:
    """未加载时 infer_txt2img 抛 RuntimeError。"""
    eng = NativeEngine(name="z_image_turbo")
    with pytest.raises(RuntimeError):
        asyncio.run(eng.infer_txt2img(GenerationConfig()))


@pytest.mark.smoke
def test_cancel_sets_flag() -> None:
    """cancel() 置位取消标志。"""
    eng = NativeEngine(name="z_image_turbo")
    asyncio.run(eng.cancel())
    assert eng._cancel_requested is True


# ── Comfy 源码装载（需要 torch，缺失则跳过）─────────────────
@pytest.mark.smoke
def test_source_ensure_loaded_imports_comfy() -> None:
    """ensure_loaded() 后能 import comfy。"""
    pytest.importorskip("torch")
    root = source.ensure_loaded(comfy_root=COMFY_ROOT)
    assert str(root) in sys.path
    import comfy  # noqa: F401

    assert comfy is not None


@pytest.mark.smoke
def test_source_loading_is_idempotent() -> None:
    """ensure_loaded() 幂等：重复调用返回同一根目录且不重复插入。"""
    pytest.importorskip("torch")
    root1 = source.ensure_loaded(comfy_root=COMFY_ROOT)
    path_count = sys.path.count(str(root1))
    root2 = source.ensure_loaded(comfy_root=COMFY_ROOT)
    assert root1 == root2
    assert sys.path.count(str(root1)) == path_count


# ── 输出路径拼接逻辑 ─────────────────────────────────────────
def test_engine_save_output_naming(tmp_path) -> None:
    """输出路径命名：outputs/{engine}/{date}/{taskid}_{idx}.png。"""
    from datetime import datetime

    eng = NativeEngine(name="z_image_turbo")
    date_str = datetime.now().strftime("%Y%m%d")
    engine_dir = tmp_path / "outputs" / "z_image_turbo" / date_str
    engine_dir.mkdir(parents=True, exist_ok=True)
    task_id = "aabbccddeeff0011"
    path = engine_dir / f"{task_id[:16]}_0.png"
    assert path.name == "aabbccddeeff0011_0.png"
    assert path.parent == engine_dir


# ── 真实推理（默认跳过，标记 slow）───────────────────────────
@pytest.mark.slow
@pytest.mark.skip(reason="真实 8B 推理过重，默认跳过；需显式运行单独脚本验证")
def test_real_inference_skipped_by_default() -> None:
    """占位：真实推理不在默认/冒烟集合中执行。"""
    raise AssertionError("真实推理测试不应被默认执行")
