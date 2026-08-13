"""
test_native_security.py — NativeEngine 输出落盘安全攻击测试

对应 AGENTS.md §4.5 铁律：新增文件操作 / 输出落盘逻辑必须补安全攻击向量。
验证 NativeEngine._save_outputs 的输出路径经过 PathGuard 校验（防 ``../`` 穿越），
覆盖：``../`` 穿越、深度穿越、Windows/Unix 绝对路径、反斜杠穿越、恶意引擎名注入等
向量，全部必须抛 PathGuardError 拒绝；合法引擎名正向通过。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import integrated_app.native.engine as engine_mod
from integrated_app.engine_interface import GenerationConfig
from integrated_app.native.engine import NativeEngine
from integrated_app.security.path_guard import PathGuardError


class _FakeOutput:
    base_dir = "outputs"
    save_thumbnail = False
    thumbnail_max_side = 512


class _FakeWatermark:
    enabled_in_code = False
    product_id = "TEST"


class _FakeSecurity:
    allowed_base_dirs = ["outputs/"]


class _FakeConfig:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.output = _FakeOutput()
        self.watermark = _FakeWatermark()
        self.security = _FakeSecurity()


@pytest.fixture
def fake_config(monkeypatch, tmp_path):
    """把 engine 模块的 get_config 指向临时配置，避免污染真实 outputs/ 目录。"""
    monkeypatch.setattr(engine_mod, "get_config", lambda: _FakeConfig(tmp_path))
    return tmp_path


def _save(engine: NativeEngine, config: GenerationConfig | None = None) -> list[str]:
    """调用 _save_outputs（sync），images 为空列表即可触发路径解析。"""
    return engine._save_outputs([], config or GenerationConfig())


class TestNativeSavePathTraversal:
    """NativeEngine._save_outputs 输出路径穿越攻击向量"""

    def test_double_dot_engine_name(self, fake_config) -> None:
        """引擎名含 ``../`` 穿越 → 拒绝。"""
        eng = NativeEngine(name="../../etc")
        with pytest.raises(PathGuardError):
            _save(eng)

    def test_deep_traversal_engine_name(self, fake_config) -> None:
        """引擎名深度穿越到系统目录 → 拒绝。"""
        eng = NativeEngine(name="../../../Windows/System32/config/SAM")
        with pytest.raises(PathGuardError):
            _save(eng)

    def test_absolute_path_engine_name(self, fake_config) -> None:
        """引擎名为 Windows 绝对盘符路径 → 拒绝。"""
        eng = NativeEngine(name="C:/Windows/System32/config/SAM")
        with pytest.raises(PathGuardError):
            _save(eng)

    def test_unix_absolute_engine_name(self, fake_config) -> None:
        """引擎名为 Unix 绝对路径 → 拒绝。"""
        eng = NativeEngine(name="/etc/passwd")
        with pytest.raises(PathGuardError):
            _save(eng)

    def test_backslash_traversal_engine_name(self, fake_config) -> None:
        """引擎名反斜杠穿越 → 拒绝。"""
        eng = NativeEngine(name="..\\..\\..\\etc")
        with pytest.raises(PathGuardError):
            _save(eng)

    def test_valid_engine_name_passes(self, fake_config) -> None:
        """正向：合法引擎名通过并落在临时 outputs/{name}/{date} 下。"""
        eng = NativeEngine(name="z_image_turbo")
        saved = _save(eng)
        assert saved == []
        out_root = Path(fake_config) / "outputs"
        assert out_root.is_dir()
