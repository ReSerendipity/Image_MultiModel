"""test_native_coverage.py — native/ 依赖包纯逻辑函数覆盖率补强

P0-2 修复：`import torch` 改为 `pytest.importorskip("torch")`，
避免无 CUDA torch 环境（如 CI ubuntu-latest）下 collection error。
所有依赖 torch 的用例自动 skip，不依赖 torch 的纯逻辑用例正常运行。
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")  # noqa: F811 — 无 torch 环境跳过本文件全部用例
from integrated_app.config_models import AppConfig
from integrated_app.engine_interface import GenerationConfig
from integrated_app.native import executor, lora, output_pipeline, seedvr, source, vram
from integrated_app.native.engine import NativeEngine, _map_phase

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMFY_ROOT = PROJECT_ROOT / "comfy_kernel"

def _fake_comfy_submodule(name):
    """构造 fake comfy 包 + 子模块，避免命中真实已导入的 comfy 包。"""
    pkg, _, sub = name.rpartition(".")
    comfy = types.ModuleType(pkg)
    sub_mod = types.ModuleType(name)
    setattr(comfy, sub, sub_mod)
    return comfy, sub_mod


# executor.py
def test_resolve_device_priority(monkeypatch):
    monkeypatch.setattr("torch.cuda.is_available", lambda: True)
    assert str(executor._resolve_device()) == "cuda"
    monkeypatch.setattr("torch.cuda.is_available", lambda: False)
    assert str(executor._resolve_device()) == "cpu"


def test_encode_conditioning():
    class _Clip:
        def tokenize(self, text):
            return {"t": text}
        def encode_from_tokens_scheduled(self, tokens):
            return [tokens]
    out = executor._encode_conditioning(_Clip(), "hello")
    assert out[0]["t"] == "hello"


def test_vae_decode():
    class _Vae:
        # executor._vae_decode 直接把 latent 张量传给 vae.decode（对齐 Z-Image VAE 接口）
        def decode(self, payload):
            return payload
    latent = torch.zeros(1, 2, 2, 3)
    assert executor._vae_decode(_Vae(), latent) is latent


def test_sampling_callback_reports_progress():
    calls = []
    cb = executor._make_sampling_callback(8, lambda p, ph, ex: calls.append((p, ph, ex)), [False])
    cb(4, None, None, 8)
    assert calls == [(55, "Sampling 4/8", {})]


def test_sampling_callback_no_total_steps():
    calls = []
    cb = executor._make_sampling_callback(8, lambda p, ph, ex: calls.append(p), [False])
    cb(1, None, None, 0)
    assert calls == []


def test_fixed_seed():
    assert executor._fixed_seed(-1) == 120429878797176
    assert executor._fixed_seed(42) == 42


def test_round_pixels():
    assert executor.round_pixels(1) == 8
    assert executor.round_pixels(8) == 8
    assert executor.round_pixels(10) == 16


def test_tentative_vram_gb():
    assert executor.tentative_vram_gb(1024, 1024, 1) == 1.0
    assert isinstance(executor.tentative_vram_gb(512, 512, 2), float)


# engine.py
def test_map_phase():
    assert _map_phase("Loading native models...") == "phase_loading_workflow"
    assert _map_phase("Encoding prompts...") == "phase_patching"
    assert _map_phase("Sampling...") == "phase_sampling"
    assert _map_phase("Sampling 3/8") == "phase_sampling"
    assert _map_phase("Completed") == "phase_completed"
    assert _map_phase("custom phase") == "custom phase"


def test_tensor_to_png(tmp_path):
    img = torch.zeros(8, 16, 3)
    path = tmp_path / "a.png"
    output_pipeline.save_image(path, img, is_tensor=True)
    assert path.exists() and path.stat().st_size > 0


def test_embed_watermark_identity(monkeypatch, tmp_path):
    # output_pipeline 通过 from-import 持有 embed_watermark 的引用，
    # 必须打在 output_pipeline 上才生效（打在 watermark 模块上对该调用点无效）。
    monkeypatch.setattr(output_pipeline, "embed_watermark", lambda arr, pid, tid, ts: arr)
    src = tmp_path / "src.png"
    output_pipeline.save_image(src, torch.zeros(8, 8, 3), is_tensor=True)
    output_pipeline.embed_provenance(src, "PROD", "task123")
    assert src.exists() and src.stat().st_size > 0


def test_embed_watermark_error_on_error(monkeypatch, tmp_path):
    import integrated_app.watermark as wm
    def boom(*a, **k):
        raise RuntimeError("wm fail")
    monkeypatch.setattr(wm, "embed_watermark", boom)
    src = tmp_path / "src.png"
    output_pipeline.save_image(src, torch.zeros(8, 8, 3), is_tensor=True)
    output_pipeline.embed_provenance(src, "PROD", "task123")
    assert src.exists()


def test_make_thumbnail_scale_and_no_scale(tmp_path):
    src = tmp_path / "src.png"
    output_pipeline.save_image(src, torch.zeros(8, 16, 3), is_tensor=True)
    thumb_dir = tmp_path / "thumbs"
    thumb_dir.mkdir()
    output_pipeline.make_thumbnail(src, thumb_dir, "t_down.png", 8)
    assert (thumb_dir / "t_down.png").exists()
    output_pipeline.make_thumbnail(src, thumb_dir, "t_same.png", 128)
    assert (thumb_dir / "t_same.png").exists()


def test_make_thumbnail_error_handled(tmp_path):
    output_pipeline.make_thumbnail(tmp_path / "missing.png", tmp_path, "x.png", 32)


def test_engine_unload(monkeypatch):
    comfy_pkg, mm = _fake_comfy_submodule("comfy.model_management")
    mm.soft_empty_cache = lambda: None
    monkeypatch.setitem(sys.modules, "comfy", comfy_pkg)
    monkeypatch.setitem(sys.modules, "comfy.model_management", mm)
    eng = NativeEngine(name="z_image_turbo")
    eng._ready = True
    eng._model_paths = {"unet": "x"}
    asyncio.run(eng.unload())
    assert eng.is_ready() is False
    assert eng._model_paths == {}


def test_save_outputs_full_flow(monkeypatch, tmp_path):
    import integrated_app.watermark as wm
    monkeypatch.setattr(wm, "embed_watermark", lambda arr, pid, tid, ts: arr)
    cfg = AppConfig(project_root=str(tmp_path))
    cfg.output.base_dir = "outputs"
    cfg.output.save_thumbnail = True
    cfg.output.thumbnail_max_side = 32
    cfg.watermark.enabled_in_code = True
    cfg.watermark.product_id = "PROD-1"
    cfg.security.allowed_base_dirs = ["outputs", "data"]
    monkeypatch.setattr("integrated_app.native.engine.get_config", lambda: cfg)
    eng = NativeEngine(name="z_image_turbo")
    images = [torch.zeros(8, 16, 3)]
    gcfg = GenerationConfig(workflow_sha256="a" * 64)
    saved = eng._save_outputs(images, gcfg)
    assert len(saved) == 1
    # 返回值应为相对 outputs/ 目录的路径（供前端 /api/outputs/<rel> 直接访问）
    assert ".." not in saved[0]
    assert not Path(saved[0]).is_absolute()
    assert (tmp_path / "outputs" / saved[0]).exists()
    thumbs = list((tmp_path / "data" / "cache" / "thumbs").glob("*_thumb.png"))
    assert len(thumbs) == 1


# source.py
def test_default_comfy_root():
    assert source._default_comfy_root() == COMFY_ROOT


def test_ensure_loaded_invalid_root_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(source, "_loaded", False)
    monkeypatch.setattr(source, "_comfy_root", None)
    with pytest.raises(RuntimeError):
        source.ensure_loaded(comfy_root=tmp_path)


def test_ensure_loaded_custom_nodes_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(source, "_loaded", False)
    monkeypatch.setattr(source, "_comfy_root", None)
    cnd = tmp_path / "custom_nodes"
    cnd.mkdir()
    root = source.ensure_loaded(comfy_root=COMFY_ROOT, custom_nodes_dir=cnd)
    assert root == COMFY_ROOT.resolve()
    assert str(cnd.resolve()) in sys.path
    assert source.is_loaded() is True
    assert source.ensure_loaded(comfy_root=COMFY_ROOT) == COMFY_ROOT.resolve()
    assert source.get_comfy_root() == COMFY_ROOT.resolve()


# lora.py
def test_absolute_lora_path_shared():
    config = types.SimpleNamespace(
        model_source_mode="shared",
        shared=types.SimpleNamespace(comfy_models_dir="C:/models", mount_map={"lora": "loras"}),
        portable=None,
    )
    assert lora._absolute_lora_path("sub/x.safetensors", config, "C:/proj") == (
        "C:/models/loras/sub/x.safetensors"
    )


def test_absolute_lora_path_portable(tmp_path):
    config = types.SimpleNamespace(
        model_source_mode="portable",
        portable=types.SimpleNamespace(internal_models_dir="model", sub_dirs={"lora": "loras"}),
        shared=None,
    )
    result = lora._absolute_lora_path("sub/x.safetensors", config, tmp_path)
    assert result == str(tmp_path / "model" / "loras" / "sub" / "x.safetensors").replace("\\", "/")


def test_apply_lora_stack_apply_loop_mocked(monkeypatch):
    fake_sd = types.ModuleType("comfy.sd")
    fake_utils = types.ModuleType("comfy.utils")
    fake_utils.load_torch_file = lambda p: {"sd": p}
    fake_sd.load_lora_for_models = lambda m, c, s, sm, sc: (m, c)
    monkeypatch.setitem(sys.modules, "comfy.sd", fake_sd)
    monkeypatch.setitem(sys.modules, "comfy.utils", fake_utils)
    monkeypatch.setattr(lora.source, "ensure_loaded", lambda *a, **k: None)
    model, clip = object(), object()
    out_m, out_c = lora.apply_lora_stack(
        model, clip, {"a": "/x/a", "b": "/x/b"},
        [{"name": "a", "strength": 1.0}, {"name": "b", "strength": 0.5}],
    )
    assert out_m is model and out_c is clip


def test_apply_lora_stack_nonempty_stack_all_missing(monkeypatch):
    monkeypatch.setattr(lora.source, "ensure_loaded", lambda *a, **k: None)
    model, clip = object(), object()
    out_m, out_c = lora.apply_lora_stack(
        model, clip, {"a": "/x/a"}, [{"name": "ghost", "strength": 1.0}]
    )
    assert out_m is model and out_c is clip


# seedvr.py
def test_seedvr_source_dir_default():
    d = seedvr._seedvr_source_dir()
    assert isinstance(d, Path) and str(d)


def test_inject_inserts_into_syspath(tmp_path):
    root = seedvr._inject(tmp_path)
    assert root == tmp_path.resolve()
    assert str(tmp_path.resolve()) in sys.path


def test_is_available_true_and_false(monkeypatch):
    src_module = types.ModuleType("src")
    src_core = types.ModuleType("src.core")
    src_core_infer = types.ModuleType("src.core.infer")
    src_core_infer.VideoDiffusionInfer = object
    monkeypatch.setitem(sys.modules, "src", src_module)
    monkeypatch.setitem(sys.modules, "src.core", src_core)
    monkeypatch.setitem(sys.modules, "src.core.infer", src_core_infer)
    monkeypatch.setattr(seedvr, "_inject", lambda *a: None)
    assert seedvr.is_available() is True

    def boom(*a, **k):
        raise RuntimeError("no seedvr")
    monkeypatch.setattr(seedvr, "_inject", boom)
    assert seedvr.is_available() is False


def test_build_sr_config_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        seedvr.build_sr_config(tmp_path)


def test_image_bytes_to_tensor_non_rgb():
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("L", (6, 4), 128).save(buf, format="PNG")
    tensor = seedvr._image_bytes_to_tensor(buf.getvalue())
    assert tensor.shape == (1, 4, 6, 3)


def test_get_runner_class_and_load_embeddings(monkeypatch, tmp_path):
    src_module = types.ModuleType("src")
    src_core = types.ModuleType("src.core")
    src_core_infer = types.ModuleType("src.core.infer")
    src_core_infer.VideoDiffusionInfer = type("VideoDiffusionInfer", (), {})
    monkeypatch.setitem(sys.modules, "src", src_module)
    monkeypatch.setitem(sys.modules, "src.core", src_core)
    monkeypatch.setitem(sys.modules, "src.core.infer", src_core_infer)
    assert seedvr._get_runner_class() is src_core_infer.VideoDiffusionInfer

    src_utils = types.ModuleType("src.utils")
    src_constants = types.ModuleType("src.utils.constants")
    src_constants.get_script_directory = lambda: str(tmp_path)
    monkeypatch.setitem(sys.modules, "src.utils", src_utils)
    monkeypatch.setitem(sys.modules, "src.utils.constants", src_constants)
    torch.save(torch.zeros(2, 3), tmp_path / "pos_emb.pt")
    emb = seedvr._load_embeddings("pos")
    assert emb.shape == (2, 3)
    with pytest.raises(FileNotFoundError):
        seedvr._load_embeddings("neg")


# vram.py
def test_get_gpu_memory_info_nvml_failed_to_none(monkeypatch):
    class _Bad:
        def nvmlDeviceGetHandleByIndex(self, i):
            raise RuntimeError("nv fail")
    monkeypatch.setattr(vram, "_pynvml", _Bad())
    monkeypatch.setattr("torch.cuda.is_available", lambda: False)
    total, used = vram.get_gpu_memory_info()
    assert total is None and used is None


def test_set_reserved_vram_has_method(monkeypatch):
    comfy_pkg, mm = _fake_comfy_submodule("comfy.model_management")
    recorded = []
    mm.set_extra_reserved_vram = lambda gb: recorded.append(gb)
    monkeypatch.setitem(sys.modules, "comfy", comfy_pkg)
    monkeypatch.setitem(sys.modules, "comfy.model_management", mm)
    vram.set_reserved_vram(2.5)
    vram.set_reserved_vram(-1)
    assert recorded == [2.5, 0.0]


def test_set_reserved_vram_attr_fallback(monkeypatch):
    comfy_pkg, mm = _fake_comfy_submodule("comfy.model_management")
    mm.EXTRA_RESERVED_VRAM = 0
    monkeypatch.setitem(sys.modules, "comfy", comfy_pkg)
    monkeypatch.setitem(sys.modules, "comfy.model_management", mm)
    vram.set_reserved_vram(2.5)
    assert int(2.5 * 1024**3) == mm.EXTRA_RESERVED_VRAM


def test_free_vram_mocked(monkeypatch):
    comfy_pkg, mm = _fake_comfy_submodule("comfy.model_management")
    calls = []
    mm.unload_all_models = lambda: calls.append("unload")
    mm.soft_empty_cache = lambda: calls.append("soft")
    monkeypatch.setitem(sys.modules, "comfy", comfy_pkg)
    monkeypatch.setitem(sys.modules, "comfy.model_management", mm)
    vram.free_vram()
    assert "unload" in calls and "soft" in calls


def test_configure_blockswap_seedvr2_mode(monkeypatch):
    blocks = [object() for _ in range(3)]
    model = types.SimpleNamespace(blocks=blocks, offload_device="cpu")
    monkeypatch.setattr(vram, "_apply_reused_blockswap", lambda m, e, o: None)
    res = vram.configure_blockswap(model, blocks_to_swap=2)
    assert res["applied"] is True and res["mode"] == "seedvr2"
    assert res["blocks_swapped"] == 2


def test_apply_reused_blockswap_success_and_no_debug(monkeypatch):
    opt = types.ModuleType("optimization.blockswap")
    opt.apply_block_swap_to_dit = lambda runner, config, debug: None
    monkeypatch.setitem(sys.modules, "optimization", types.ModuleType("optimization"))
    monkeypatch.setitem(sys.modules, "optimization.blockswap", opt)
    model = types.SimpleNamespace(blocks=[object()], _seedvr_debug="D")
    vram._apply_reused_blockswap(model, 1, "cpu")
    model2 = types.SimpleNamespace(blocks=[object()])
    with pytest.raises(RuntimeError):
        vram._apply_reused_blockswap(model2, 1, "cpu")




# engine.py — load / infer 分支
def test_engine_load_mocked(monkeypatch):
    import integrated_app.native.engine as _engine
    cfg = types.SimpleNamespace(
        models=types.SimpleNamespace(engines={"z_image_turbo": object()}),
        project_root="C:/proj",
        security=types.SimpleNamespace(
            model_format=types.SimpleNamespace(
                verify_weights=False, only_safetensors=True, fail_closed_on_corrupt_weight=False
            )
        ),
    )
    monkeypatch.setattr(_engine, "get_config", lambda: cfg)
    monkeypatch.setattr(
        _engine, "resolve_engine_model_paths",
        lambda ec, m, pr: {"unet": "/u", "vae": "/v", "text_encoder": "/t"},
    )
    eng = NativeEngine(name="z_image_turbo")
    progress = []
    asyncio.run(eng.load(lambda p, ph, ex: progress.append((p, ph))))
    assert eng.is_ready() is True
    assert eng._model_paths["unet"] == "/u"
    assert [p for p, _ in progress] == [10, 100]


def test_engine_load_engine_not_found(monkeypatch):
    import integrated_app.native.engine as _engine
    cfg = types.SimpleNamespace(models=types.SimpleNamespace(engines={}), project_root="C:/proj")
    monkeypatch.setattr(_engine, "get_config", lambda: cfg)
    eng = NativeEngine(name="ghost")
    with pytest.raises(RuntimeError):
        asyncio.run(eng.load())


def test_engine_infer_not_ready():
    eng = NativeEngine(name="z_image_turbo")
    with pytest.raises(RuntimeError):
        asyncio.run(eng.infer_txt2img(GenerationConfig()))


