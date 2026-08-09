"""
test_config.py — 配置加载 + resolve_model_path() 双模式单测

对应 MASTER_PLAN M0 验收: 路径解析器双模式单测
"""

import sys
from pathlib import Path

import pytest
import yaml

# 添加 bin 到 path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

from integrated_app.config_models import (
    AppConfig,
    ModelPaths,
    ModelsConfig,
    PortableConfig,
    SharedConfig,
    resolve_engine_model_paths,
    resolve_model_path,
    scan_resource_files,
)


@pytest.fixture
def project_root():
    return PROJECT_ROOT


@pytest.fixture
def config_yaml(project_root):
    """加载 config.yaml"""
    with open(project_root / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def app_config(config_yaml, project_root):
    """构建 AppConfig"""
    return AppConfig.from_yaml(config_yaml, project_root=str(project_root))


class TestConfigLoading:
    """测试配置加载"""

    @pytest.mark.smoke
    def test_config_loads_successfully(self, config_yaml):
        """配置文件可正常加载"""
        assert config_yaml is not None
        assert "version" in config_yaml
        assert "server" in config_yaml
        assert "models" in config_yaml

    def test_app_config_builds(self, app_config):
        """AppConfig 构建成功"""
        assert app_config.version == "1.0.0"
        assert app_config.server.host == "127.0.0.1"
        assert app_config.server.port == 8288
        assert app_config.models.model_source_mode in ("shared", "portable")

    def test_host_must_be_loopback(self, config_yaml, project_root):
        """host 只读校验：不允许 0.0.0.0"""
        config_yaml["server"]["host"] = "0.0.0.0"
        with pytest.raises(Exception):
            AppConfig.from_yaml(config_yaml, project_root=str(project_root))

    def test_engines_loaded(self, app_config):
        """引擎声明正确加载"""
        engines = app_config.models.engines
        assert "flux2_klein_9b_distilled" in engines
        assert "z_image_turbo" in engines

        flux = engines["flux2_klein_9b_distilled"]
        assert flux.backend == "comfyui"
        assert flux.workflow_file == "workflows/Flux.2_Klein-9B-Distilled.json"

        zturbo = engines["z_image_turbo"]
        assert zturbo.backend == "comfyui"
        assert zturbo.workflow_file == "workflows/Z_image_turbo.json"

    def test_config_safe_dict_redacts_secrets(self, app_config):
        """脱敏：auth_token / password 不暴露"""
        safe = app_config.get_safe_config_dict()
        # api_token tokens 应为空
        assert safe["security"]["api_token"]["tokens"] == []


class TestResolveModelPath:
    """测试 resolve_model_path() 双模式解析"""

    def test_shared_mode_resolution(self, project_root):
        """shared 模式：路径基于 comfy_models_dir"""
        models_config = ModelsConfig(
            model_source_mode="shared",
            shared=SharedConfig(
                comfy_models_dir="C:/Users/Doro/APP/ComfyUI-aki-v3/ComfyUI/models",
                mount_map={"text": "text_encoders", "unet": "unet", "vae": "vae"},
            ),
        )
        mp = ModelPaths(sub_dir="text", sub_path="FLUX.2-klein-9b/qwen_3_8b_fp8mixed.safetensors")
        result = resolve_model_path(mp, models_config, project_root)

        assert "text_encoders" in result
        assert "FLUX.2-klein-9b/qwen_3_8b_fp8mixed.safetensors" in result
        assert "C:/Users/Doro/APP/ComfyUI-aki-v3/ComfyUI/models" in result or "C:" in result

    def test_portable_mode_resolution(self, project_root):
        """portable 模式：路径基于 pretrained_models/"""
        models_config = ModelsConfig(
            model_source_mode="portable",
            portable=PortableConfig(
                internal_models_dir="pretrained_models",
                sub_dirs={"text": "text_encoders", "unet": "unet", "vae": "vae"},
            ),
        )
        mp = ModelPaths(sub_dir="text", sub_path="FLUX.2-klein-9b/qwen_3_8b_fp8mixed.safetensors")
        result = resolve_model_path(mp, models_config, project_root)

        assert "pretrained_models" in result
        assert "text_encoders" in result
        assert "FLUX.2-klein-9b/qwen_3_8b_fp8mixed.safetensors" in result

    def test_engine_model_paths_resolution(self, app_config, project_root):
        """引擎的所有模型路径都能解析"""
        flux = app_config.models.engines["flux2_klein_9b_distilled"]
        paths = resolve_engine_model_paths(flux, app_config.models, project_root)

        assert "text_encoder" in paths
        assert "unet" in paths
        assert "vae" in paths
        # 所有路径应以 .safetensors 结尾
        for key, path in paths.items():
            assert path.endswith(".safetensors"), f"{key} path doesn't end with .safetensors: {path}"

    def test_z_image_paths_resolution(self, app_config, project_root):
        """Z-Image 引擎路径解析"""
        z = app_config.models.engines["z_image_turbo"]
        paths = resolve_engine_model_paths(z, app_config.models, project_root)

        assert "text_encoder" in paths
        assert "unet" in paths
        assert "vae" in paths


class TestScanResourceFiles:
    """测试资源扫描"""

    def test_scan_loras(self, app_config, project_root):
        """扫描 LoRA 目录"""
        # shared 模式扫描
        if app_config.models.model_source_mode == "shared":
            loras = scan_resource_files("lora", app_config.models, project_root)
            # 可能返回空（如果 ComfyUI 的 loras 目录没有文件）
            assert isinstance(loras, list)

    def test_scan_local_text_encoders(self, project_root):
        """扫描本地 text/ 目录（项目根下）"""
        models_config = ModelsConfig(
            model_source_mode="portable",
            portable=PortableConfig(
                internal_models_dir="pretrained_models",
                sub_dirs={"text": "text_encoders"},
            ),
        )
        # 项目根下的 text/ 目录（Junction 挂载点）
        # 在 shared 模式下可能扫描的是 ComfyUI 目录
        # 这里测试 portable 模式下的扫描
        result = scan_resource_files("text", models_config, project_root)
        assert isinstance(result, list)

    def test_scan_nonexistent_dir(self, project_root):
        """扫描不存在的目录返回空列表"""
        models_config = ModelsConfig(
            model_source_mode="shared",
            shared=SharedConfig(comfy_models_dir="/nonexistent/path"),
        )
        result = scan_resource_files("text", models_config, project_root)
        assert result == []


class TestPathGuard:
    """测试路径穿越守卫"""

    def test_safe_path_allowed(self, project_root):
        """安全路径通过"""
        from integrated_app.security.path_guard import PathGuard
        guard = PathGuard(["outputs/", "data/"], project_root)
        path = guard.resolve("outputs/test.png")
        assert str(path).endswith("test.png")

    def test_path_traversal_blocked(self, project_root):
        """路径穿越被拒绝"""
        from integrated_app.security.path_guard import PathGuard
        guard = PathGuard(["outputs/"], project_root)
        with pytest.raises(Exception):
            guard.resolve("../../../etc/passwd")

    def test_absolute_path_outside_blocked(self, project_root):
        """绝对路径在白名单外被拒绝"""
        from integrated_app.security.path_guard import PathGuard
        guard = PathGuard(["outputs/"], project_root)
        with pytest.raises(Exception):
            guard.resolve("C:/Windows/System32/config/SAM")

    def test_is_safe(self, project_root):
        """is_safe 不抛异常"""
        from integrated_app.security.path_guard import PathGuard
        guard = PathGuard(["outputs/", "data/"], project_root)
        assert guard.is_safe("outputs/test.png") is True
        assert guard.is_safe("../../etc/passwd") is False


class TestHistoryDB:
    """测试历史数据库"""

    @pytest.fixture
    def db(self, tmp_path):
        from integrated_app.history_db import HistoryDB
        d = HistoryDB(tmp_path / "test_history.db")
        yield d
        d.close()

    def test_create_and_get_task(self, db):
        """创建并获取任务"""
        db.create_task(
            task_id="test-001",
            engine="flux2_klein_9b_distilled",
            mode="txt2img",
            prompt="test prompt",
            negative_prompt="",
            generation_config={"cfg": 1.0, "steps": 8},
        )
        task = db.get_task("test-001")
        assert task is not None
        assert task["engine"] == "flux2_klein_9b_distilled"
        assert task["prompt"] == "test prompt"
        assert task["generation_config"]["cfg"] == 1.0

    def test_list_tasks_pagination(self, db):
        """分页查询"""
        for i in range(10):
            db.create_task(
                task_id=f"test-{i:03d}",
                engine="flux2_klein_9b_distilled",
                prompt=f"prompt {i}",
            )
        tasks, total = db.list_tasks(page=1, page_size=5)
        assert total == 10
        assert len(tasks) == 5

    def test_delete_tasks(self, db):
        """批量删除"""
        for i in range(5):
            db.create_task(task_id=f"del-{i:03d}", engine="test")
        count = db.delete_tasks(["del-000", "del-001", "del-002"])
        assert count == 3

    def test_preset_crud(self, db):
        """预设 CRUD"""
        pid = db.create_preset("flux2_klein_9b_distilled", "test-preset", {"cfg": 1.0})
        assert pid > 0

        preset = db.get_preset(pid)
        assert preset["name"] == "test-preset"

        db.update_preset(pid, name="updated-preset")
        preset = db.get_preset(pid)
        assert preset["name"] == "updated-preset"

        assert db.delete_preset(pid) is True

    def test_recover_stuck_tasks(self, db):
        """崩溃恢复"""
        db.create_task(task_id="stuck-001", engine="test")
        db.update_task_status("stuck-001", "processing")
        # 手动修改 created_at 为 2 小时前
        db.conn.execute(
            "UPDATE tasks SET created_at=datetime('now', '-2 hours') WHERE task_id=?",
            ("stuck-001",),
        )
        db.conn.commit()
        recovered = db.recover_stuck_tasks(max_processing_hours=1.0)
        assert recovered == 1
        task = db.get_task("stuck-001")
        assert task["status"] == "interrupted"
