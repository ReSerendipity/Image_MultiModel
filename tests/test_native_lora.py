"""
test_native_lora.py — 动态 LoRA 栈叠加（Task 3.2）单测

覆盖：栈解析、name→路径解析、缺失/失败时静默跳过、clone 链式叠加。
真实 Comfy 贴片（load_lora_for_models）用 mock 验证参数流转。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from integrated_app.native import lora, source

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMFY_ROOT = PROJECT_ROOT / "references" / "ComfyUI"


@pytest.fixture(scope="module")
def comfy_sd():
    """确保 Comfy 源码已装载可 import，返回 comfy.sd 模块。"""
    pytest.importorskip("torch")
    source.ensure_loaded(comfy_root=COMFY_ROOT)
    try:
        import comfy.sd
        import comfy.utils
    except Exception as e:  # pragma: no cover - 环境相关
        pytest.skip(f"Comfy 依赖不可用（{e}），跳过真实贴片测试")

    return comfy.sd, comfy.utils


class _FakeModel:
    def __init__(self) -> None:
        self.patches: list[str] = []

    def clone(self) -> _FakeModel:
        c = _FakeModel()
        c.patches = list(self.patches)
        return c


def test_apply_lora_stack_empty_stack_returns_inputs() -> None:
    """空栈直接返回原模型，不触发任何加载。"""
    model, clip = object(), object()
    out_model, out_clip = lora.apply_lora_stack(model, clip, {"a": "/x/a.safetensors"}, [])
    assert out_model is model
    assert out_clip is clip


def test_apply_lora_stack_skips_missing_name() -> None:
    """栈中 name 不在 lora_paths 时静默跳过该层。"""
    model, clip = _FakeModel(), _FakeModel()
    stack = [{"name": "ghost", "strength": 1.0}]
    out_model, out_clip = lora.apply_lora_stack(model, clip, {}, stack)
    assert out_model is model
    assert out_clip is clip


def test_apply_lora_stack_chains_clones(comfy_sd, monkeypatch) -> None:
    """多个 LoRA 依次叠加到 clone 上，返回新实例。"""
    sd, utils = comfy_sd
    recorded: list[tuple] = []

    def fake_load_torch_file(path: str):
        return {"sd": path}

    def fake_load_lora_for_models(model, clip, lora_sd, sm, sc):
        recorded.append((model, lora_sd, sm, sc))
        return model.clone(), clip.clone()

    monkeypatch.setattr(utils, "load_torch_file", fake_load_torch_file)
    monkeypatch.setattr(sd, "load_lora_for_models", fake_load_lora_for_models)

    model, clip = _FakeModel(), _FakeModel()
    stack = [
        {"name": "a", "strength": 1.0},
        {"name": "b", "strength": 0.5},
    ]
    out_model, out_clip = lora.apply_lora_stack(model, clip, {"a": "/x/a", "b": "/x/b"}, stack)
    assert recorded != []
    assert [r[1] for r in recorded] == [{"sd": "/x/a"}, {"sd": "/x/b"}]
    assert [r[2] for r in recorded] == [1.0, 0.5]
    # 链式：第二次输入的 model 是第一次 clone 的结果
    assert recorded[1][0] is not model
    assert out_model is not model
    assert out_clip is not clip


def test_apply_lora_stack_skips_layer_on_loading_error(comfy_sd, monkeypatch) -> None:
    """某层加载失败时静默跳过，不抛异常，其余层继续。"""
    sd, utils = comfy_sd

    def fake_load_lora_for_models(model, clip, lora_sd, sm, sc):
        raise RuntimeError("boom")

    monkeypatch.setattr(utils, "load_torch_file", lambda p: {"sd": p})
    monkeypatch.setattr(sd, "load_lora_for_models", fake_load_lora_for_models)

    model, clip = _FakeModel(), _FakeModel()
    out_model, out_clip = lora.apply_lora_stack(
        model, clip, {"a": "/x/a"}, [{"name": "a", "strength": 1.0}]
    )
    # 失败层被跳过，返回原模型（未被修改）
    assert out_model is model
    assert out_clip is clip


def test_resolve_lora_paths_maps_stem_to_abs(monkeypatch) -> None:
    """name→绝对路径映射用文件名 stem 作为 key。"""
    monkeypatch.setattr(
        lora, "scan_resource_files",
        lambda *a, **k: ["sub/lora_style.safetensors", "another.safetensors"],
    )
    monkeypatch.setattr(lora, "_absolute_lora_path", lambda rel, cfg, root: f"/abs/{rel}")

    class _Cfg:
        model_source_mode = "shared"
        shared = type("_S", (), {"mount_map": {"lora": "loras"}})()
        portable = None

    mapping = lora.resolve_lora_paths(_Cfg(), "C:/proj")
    assert mapping == {
        "lora_style": "/abs/sub/lora_style.safetensors",
        "another": "/abs/another.safetensors",
    }
