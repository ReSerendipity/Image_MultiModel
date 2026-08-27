"""
test_native_vram.py — VRAM 预留 + BlockSwap（Task 3.5）单测

VRAM 查询/预留/释放用 mock 验证；BlockSwap 验证禁用与最小 offload 路径。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from integrated_app.native import vram


class _FakeMM:
    """comfy.model_management 替身。"""

    EXTRA_RESERVED_VRAM = 0
    calls: list[str] = []

    @classmethod
    def set_extra_reserved_vram(cls, gb: float) -> None:
        cls.EXTRA_RESERVED_VRAM = gb
        cls.calls.append("set_extra_reserved_vram")

    @classmethod
    def unload_all_models(cls) -> None:
        cls.calls.append("unload_all_models")

    @classmethod
    def soft_empty_cache(cls) -> None:
        cls.calls.append("soft_empty_cache")


def test_get_gpu_memory_info_uses_nvml(monkeypatch) -> None:
    """get_gpu_memory_info 优先 pynvml。"""
    class _Info:
        total = 8 * 1024**3
        used = 2 * 1024**3

    class _FakeNVML:
        def nvmlDeviceGetHandleByIndex(self, i):
            return "h"

        def nvmlDeviceGetMemoryInfo(self, h):
            return _Info()

    monkeypatch.setattr(vram, "_pynvml", _FakeNVML())
    total, used = vram.get_gpu_memory_info()
    assert total == pytest.approx(8.0)
    assert used == pytest.approx(2.0)


def test_get_gpu_memory_info_falls_back_torch(monkeypatch) -> None:
    """pynvml 不可用/失败时回退 torch.cuda.mem_get_info。"""
    monkeypatch.setattr(vram, "_pynvml", None)

    class _FakeCuda:
        @staticmethod
        def is_available() -> bool:
            return True

        @staticmethod
        def mem_get_info():
            return (6 * 1024**3, 16 * 1024**3)  # free, total

    monkeypatch.setattr("torch.cuda", _FakeCuda())
    total, used = vram.get_gpu_memory_info()
    assert total == pytest.approx(16.0)
    assert used == pytest.approx(10.0)


def test_reserve_vram_manual(monkeypatch) -> None:
    """manual 模式直接使用给定值。"""
    monkeypatch.setattr(vram, "set_reserved_vram", lambda gb: None)
    result = vram.reserve_vram(0.6, mode="manual")
    assert result == pytest.approx(0.6)


def test_reserve_vram_auto_uses_used_plus_reserved(monkeypatch) -> None:
    """auto 模式在已用显存基础上累加，并受上限约束。"""
    monkeypatch.setattr(vram, "get_gpu_memory_info", lambda: (16.0, 4.0))
    applied: list[float] = []
    monkeypatch.setattr(vram, "set_reserved_vram", lambda gb: applied.append(gb))

    result = vram.reserve_vram(0.6, mode="auto")
    assert result == pytest.approx(4.6)
    assert applied == [4.6]

    applied.clear()
    result = vram.reserve_vram(0.6, mode="auto", auto_max_reserved=4.0)
    assert result == pytest.approx(4.0)


def test_reserve_vram_auto_fallback_manual(monkeypatch) -> None:
    """auto 模式拿不到显存信息时使用手动值。"""
    monkeypatch.setattr(vram, "get_gpu_memory_info", lambda: (None, None))
    applied: list[float] = []
    monkeypatch.setattr(vram, "set_reserved_vram", lambda gb: applied.append(gb))
    result = vram.reserve_vram(0.6, mode="auto")
    assert result == pytest.approx(0.6)
    assert applied == [0.6]


def test_free_vram_calls_cleanup(monkeypatch) -> None:
    """free_vram 触发 gc + unload_all_models + soft_empty_cache。"""
    pytest.importorskip("torch")
    from integrated_app.native import source

    source.ensure_loaded(comfy_root=Path(__file__).resolve().parent.parent / "references" / "ComfyUI")
    _FakeMM.calls = []
    try:
        import comfy.model_management as mm
    except Exception as e:  # pragma: no cover - 环境相关
        pytest.skip(f"Comfy 依赖不可用（{e}），跳过 free_vram 真实清理测试")

    monkeypatch.setattr(mm, "unload_all_models", _FakeMM.unload_all_models)
    monkeypatch.setattr(mm, "soft_empty_cache", _FakeMM.soft_empty_cache)
    vram.free_vram()
    assert "unload_all_models" in _FakeMM.calls
    assert "soft_empty_cache" in _FakeMM.calls


def test_configure_blockswap_disabled() -> None:
    """blocks_to_swap<=0 时禁用，不触碰模型。"""
    model = object()
    res = vram.configure_blockswap(model, blocks_to_swap=0)
    assert res["applied"] is False
    assert res["mode"] == "disabled"


def test_configure_blockswap_no_blocks_attr() -> None:
    """模型无 blocks 属性时禁用。"""
    model = object()
    res = vram.configure_blockswap(model, blocks_to_swap=4)
    assert res["applied"] is False
    assert res["mode"] == "no_blocks"


def test_configure_blockswap_minimal_offload(monkeypatch) -> None:
    """最小 offload：前 N 块移到 offload device。"""
    blocks = [type("_B", (), {"to": lambda self, dev: None})() for _ in range(6)]
    model = type("_M", (), {"blocks": blocks, "main_device": "cuda"})()
    monkeypatch.setattr(vram, "_apply_reused_blockswap", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no seedvr")))
    res = vram.configure_blockswap(model, blocks_to_swap=2)
    assert res["applied"] is True
    assert res["mode"] == "minimal"
    assert res["blocks_swapped"] == 2
    assert model.blocks_to_swap == 1