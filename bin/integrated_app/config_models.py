"""
config_models.py — Pydantic 模型 + resolve_model_path() 双模式解析

对应 MASTER_PLAN §4 M0: config_models.py + resolve_model_path() 双模式解析
对应 PRD §10.2: shared/portable 双模式
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────────────────────
#  1. Server 配置
# ──────────────────────────────────────────────────────────────
class SSLConfig(BaseModel):
    enabled: bool = False
    certfile: str = "bin/cert.pem"
    keyfile: str = "bin/key.pem"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8288
    auto_open_browser: bool = True
    auto_load_default_engine: bool = False
    workers: int = 1
    ssl: SSLConfig = SSLConfig()

    @field_validator("host")
    @classmethod
    def host_must_be_loopback(cls, v: str) -> str:
        """安全强制：host 只读校验，不允许改成 0.0.0.0"""
        allowed = {"127.0.0.1", "localhost", "::1"}
        if v not in allowed:
            raise ValueError(
                f"host must be loopback (127.0.0.1 / localhost / ::1), got: {v}"
            )
        return v


# ──────────────────────────────────────────────────────────────
#  2. 模型源双模式
# ──────────────────────────────────────────────────────────────
class SharedConfig(BaseModel):
    comfy_models_dir: str = ""
    mount_map: Dict[str, str] = Field(
        default_factory=lambda: {
            "text": "text_encoders",
            "unet": "unet",
            "vae": "vae",
            "lora": "loras",
            "controlnet": "controlnet",
            "checkpoint": "checkpoints",
        }
    )
    symlink_strategy: str = "junction"


class PortableConfig(BaseModel):
    internal_models_dir: str = "pretrained_models"
    sub_dirs: Dict[str, str] = Field(
        default_factory=lambda: {
            "text": "text_encoders",
            "unet": "unet",
            "vae": "vae",
            "lora": "loras",
            "controlnet": "controlnet",
            "checkpoint": "checkpoints",
        }
    )


class ModelPaths(BaseModel):
    """单个模型文件的路径声明（如 text_encoder / unet / vae）"""
    sub_dir: str = ""
    sub_path: str = ""


class EngineConfig(BaseModel):
    """引擎声明——对齐 TTS_MultiModel declarative engines"""
    name: str
    display_name: str = ""
    display_name_en: str = ""
    backend: str = "comfyui"
    comfy_backend_preference: str = "local"
    workflow_file: str = ""
    parameter_schema: str = ""
    text_encoder: Optional[ModelPaths] = None
    unet: Optional[ModelPaths] = None
    vae: Optional[ModelPaths] = None
    vram_gb: float = 16.0
    ram_gb: float = 24.0
    default_precision: str = "fp8"
    fallback_precision: str = "fp8"
    supported_features: List[str] = Field(default_factory=list)
    default_width: int = 1024
    default_height: int = 1024
    image_formats: List[str] = Field(default_factory=lambda: ["png"])
    license: str = ""
    tags: List[str] = Field(default_factory=list)


class ModelsConfig(BaseModel):
    """模型源双模式配置"""
    model_source_mode: str = "shared"  # "shared" | "portable"
    default_engine: str = "flux2_klein_9b_distilled"
    shared: SharedConfig = SharedConfig()
    portable: PortableConfig = PortableConfig()
    engines: Dict[str, EngineConfig] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
#  3. ComfyUI 后端
# ──────────────────────────────────────────────────────────────
class ComfySpawnConfig(BaseModel):
    comfy_root: str = ""
    launch_exe: str = "python"
    extra_args: List[str] = Field(default_factory=list)


class ComfyBackend(BaseModel):
    name: str
    display_name: str = ""
    base_url: str = "http://127.0.0.1:8188"
    ws_url: str = "ws://127.0.0.1:8188/ws"
    auth_token: str = ""
    client_id_prefix: str = "img_multimodel_"
    health_check_interval_s: int = 30
    auto_spawn_if_dead: bool = False
    spawn: Optional[ComfySpawnConfig] = None


class ComfyConfig(BaseModel):
    backends: Dict[str, ComfyBackend] = Field(default_factory=dict)
    load_balance: str = "prefer_local"


# ──────────────────────────────────────────────────────────────
#  4. 推理参数
# ──────────────────────────────────────────────────────────────
class TorchCompileConfig(BaseModel):
    enabled: bool = False
    backend: str = "inductor"
    dynamic: bool = True
    mode: str = "default"


class InferenceConfig(BaseModel):
    default_steps: int = 8
    default_cfg: float = 1.0
    default_sampler: str = "dpmpp_3m_sde_gpu"
    default_scheduler: str = "sgm_uniform"
    default_seed: int = -1
    default_batch_size: int = 1
    default_format: str = "png"
    default_quality: int = 95
    enable_fp8_fallback: bool = True
    vram_headroom_gb: float = 2.0
    vram_multisample_rule: float = 1.5
    # 显存估算不足时是否放行（依赖 ComfyUI 低显存分块换入换出 --lowvram，如 12GB 笔记本跑 SeedVR2）
    vram_tight_continue: bool = True
    torch_compile: TorchCompileConfig = TorchCompileConfig()
    lora_max_units: int = 6


# ──────────────────────────────────────────────────────────────
#  5. 输出 & 命名
# ──────────────────────────────────────────────────────────────
class HistoryOutputConfig(BaseModel):
    db_path: str = "data/history.db"
    max_records: int = 50000
    keep_days: int = 0
    cleanup_cron: str = "0 3 * * *"


class UploadsConfig(BaseModel):
    cache_dir: str = "data/uploads"
    max_size_mb: int = 2000
    ttl_s: int = 86400


class OutputConfig(BaseModel):
    base_dir: str = "outputs"
    naming_template: str = "{engine}_{date}_{taskid}_{seed}_{idx}"
    organize_by: str = "engine_date"
    save_thumbnail: bool = True
    thumbnail_max_side: int = 512
    history: HistoryOutputConfig = HistoryOutputConfig()
    uploads: UploadsConfig = UploadsConfig()


# ──────────────────────────────────────────────────────────────
#  6. 预设 / 水印
# ──────────────────────────────────────────────────────────────
class PresetsConfig(BaseModel):
    dir: str = "data/presets"
    allow_engine_mix_presets: bool = True


class WatermarkConfig(BaseModel):
    enabled_in_code: bool = True
    method: str = "dct_frequency"
    product_id: str = "IMGMULTI-1"
    embed_timestamp: bool = True
    embed_task_id: bool = True
    strength: float = 0.008


# ──────────────────────────────────────────────────────────────
#  7. 运行时队列
# ──────────────────────────────────────────────────────────────
class TaskQueueConfig(BaseModel):
    maxsize: int = 100
    worker_mode: str = "single_serial"
    cancel_timeout_s: int = 5
    auto_recover: bool = False
    max_timeout_s: int = 86400
    id_format: str = "ulid"


class BatchConfig(BaseModel):
    max_retries: int = 2
    retry_base_delay_s: float = 1.0
    retry_max_delay_s: float = 30.0
    stop_on_error: bool = False


class SSEConfig(BaseModel):
    poll_interval_s: float = 0.5
    heartbeat_interval_s: int = 30
    max_duration_s: int = 3600
    send_comfy_preview: bool = True
    preview_b64_max_width: int = 256


class RuntimeConfig(BaseModel):
    task_queue: TaskQueueConfig = TaskQueueConfig()
    batch: BatchConfig = BatchConfig()
    sse: SSEConfig = SSEConfig()


# ──────────────────────────────────────────────────────────────
#  8. 安全
# ──────────────────────────────────────────────────────────────
class RateLimitConfig(BaseModel):
    infer_per_minute: int = 30
    upload_per_minute: int = 10
    global_per_minute: int = 600


class BasicAuthConfig(BaseModel):
    enabled: bool = False
    username: str = "admin"
    password_bcrypt_hash: str = ""


class APITokenConfig(BaseModel):
    enabled: bool = False
    tokens: List[str] = Field(default_factory=list)


class CORSConfig(BaseModel):
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:8288",
            "http://localhost:8288",
            "ws://127.0.0.1:*",
        ]
    )
    allow_credentials: bool = True


class ModelFormatConfig(BaseModel):
    only_safetensors: bool = True
    warn_if_pickle_found: bool = True


class IntegritySelfcheckConfig(BaseModel):
    enabled: bool = True
    manifest_file: str = "bin/integrated_app/security/integrity_manifest.json"


class SecurityConfig(BaseModel):
    allowed_base_dirs: List[str] = Field(
        default_factory=lambda: ["outputs/", "data/", "workflows/", "pretrained_models/"]
    )
    rate_limit: RateLimitConfig = RateLimitConfig()
    basic_auth: BasicAuthConfig = BasicAuthConfig()
    api_token: APITokenConfig = APITokenConfig()
    cors: CORSConfig = CORSConfig()
    model_format: ModelFormatConfig = ModelFormatConfig()
    integrity_selfcheck: IntegritySelfcheckConfig = IntegritySelfcheckConfig()


# ──────────────────────────────────────────────────────────────
#  9. GPU & 硬件
# ──────────────────────────────────────────────────────────────
class GPUMonitorConfig(BaseModel):
    sample_interval_s: int = 2
    history_points: int = 60


class GPUConfig(BaseModel):
    backend: str = "auto"
    device_ids: List[int] = Field(default_factory=lambda: [0])
    allow_fallback_to_cpu: bool = True
    low_vram_mode: str = "auto"
    monitor: GPUMonitorConfig = GPUMonitorConfig()


# ──────────────────────────────────────────────────────────────
#  10. UI & i18n
# ──────────────────────────────────────────────────────────────
class A11yConfig(BaseModel):
    focus_ring: bool = True
    reduce_motion: bool = False


class UIConfig(BaseModel):
    theme_default: str = "dark"
    accent_color: str = "#5e7d5a"
    font_pair: str = "instrument_serif_dm_sans"
    sidebar_collapsed_by_default: bool = False
    accordion_default_groups: List[str] = Field(default_factory=lambda: ["basic", "prompt"])
    history_page_size: int = 50
    preview_max_size_mb: int = 20
    a11y: A11yConfig = A11yConfig()


class I18nConfig(BaseModel):
    default_locale: str = "zh"
    available_locales: List[str] = Field(
        default_factory=lambda: ["zh", "en", "ja", "ko"]
    )
    locale_dir: str = "bin/integrated_app/locales"
    fallback_to_en: bool = True


# ──────────────────────────────────────────────────────────────
#  11. 日志 & 缓存
# ──────────────────────────────────────────────────────────────
class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/app.log"
    max_size_mb: int = 50
    backup_count: int = 5
    include_traceback: bool = True
    mask_sensitive_headers: bool = True


class CacheConfig(BaseModel):
    dir: str = "data/cache"
    max_size_mb: int = 500
    ttl_s: int = 86400
    comfy_object_info_ttl_s: int = 3600


# ──────────────────────────────────────────────────────────────
#  12. 加速
# ──────────────────────────────────────────────────────────────
class VLLMConfig(BaseModel):
    enabled: bool = False
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.85


class TensorRTConfig(BaseModel):
    enabled: bool = False
    engine_cache_dir: str = "data/trt_engines"


class AccelerationConfig(BaseModel):
    vllm: VLLMConfig = VLLMConfig()
    tensorrt: TensorRTConfig = TensorRTConfig()


# ──────────────────────────────────────────────────────────────
#  13. 环境变量
# ──────────────────────────────────────────────────────────────
class EnvironmentConfig(BaseModel):
    HF_HUB_OFFLINE: str = "1"
    TRANSFORMERS_OFFLINE: str = "1"
    MODELSCOPE_OFFLINE: str = "1"
    COMFYUI_DISABLE_UPDATE_CHECK: str = "1"


# ──────────────────────────────────────────────────────────────
#  顶层配置模型
# ──────────────────────────────────────────────────────────────
class AppConfig(BaseModel):
    """整个 config.yaml 的 Pydantic 映射"""
    version: str = "1.0.0"
    server: ServerConfig = ServerConfig()
    models: ModelsConfig = ModelsConfig()
    comfy: ComfyConfig = ComfyConfig()
    inference: InferenceConfig = InferenceConfig()
    output: OutputConfig = OutputConfig()
    presets: PresetsConfig = PresetsConfig()
    watermark: WatermarkConfig = WatermarkConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    security: SecurityConfig = SecurityConfig()
    gpu: GPUConfig = GPUConfig()
    ui: UIConfig = UIConfig()
    i18n: I18nConfig = I18nConfig()
    logging: LoggingConfig = LoggingConfig()
    cache: CacheConfig = CacheConfig()
    acceleration: AccelerationConfig = AccelerationConfig()
    environment: EnvironmentConfig = EnvironmentConfig()

    # 运行时注入（非 YAML 来源）
    project_root: str = ""

    @classmethod
    def from_yaml(cls, yaml_dict: Dict[str, Any], project_root: str = "") -> "AppConfig":
        """从 YAML 字典构建 AppConfig"""
        cfg = cls(**yaml_dict)
        cfg.project_root = str(Path(project_root).resolve())
        return cfg

    def to_yaml_dict(self) -> Dict[str, Any]:
        """序列化回 YAML 可写的字典（脱敏）"""
        d = self.model_dump(exclude={"project_root"})
        # 脱敏：隐藏 auth_token / password
        for bk, bv in d.get("comfy", {}).get("backends", {}).items():
            if bv.get("auth_token"):
                bv["auth_token"] = "***REDACTED***"
        if d.get("security", {}).get("basic_auth", {}).get("password_bcrypt_hash"):
            d["security"]["basic_auth"]["password_bcrypt_hash"] = "***REDACTED***"
        for t in d.get("security", {}).get("api_token", {}).get("tokens", []):
            pass  # tokens 脱敏在 route 层处理
        return d

    def get_safe_config_dict(self) -> Dict[str, Any]:
        """返回脱敏后的配置字典，供前端读取"""
        d = self.to_yaml_dict()
        # api_token tokens 完全隐藏
        d["security"]["api_token"]["tokens"] = []
        return d


# ──────────────────────────────────────────────────────────────
#  resolve_model_path() —— 双模式解析核心
# ──────────────────────────────────────────────────────────────
def resolve_model_path(
    model_paths: ModelPaths,
    config: ModelsConfig,
    project_root: Union[str, Path],
) -> str:
    """
    根据 model_source_mode (shared / portable) 解析模型的完整路径。

    shared 模式:
        {comfy_models_dir}/{mount_map[sub_dir]}/{sub_path}
        例如: C:/Users/Doro/APP/ComfyUI/models/text_encoders/FLUX.2-klein-9b/qwen_3_8b_fp8mixed.safetensors

    portable 模式:
        {project_root}/{internal_models_dir}/{sub_dirs[sub_dir]}/{sub_path}
        例如: ./pretrained_models/text_encoders/FLUX.2-klein-9b/qwen_3_8b_fp8mixed.safetensors

    Args:
        model_paths: 引擎配置中的 text_encoder / unet / vae 等 ModelPaths
        config: ModelsConfig 实例
        project_root: 项目根目录

    Returns:
        解析后的绝对路径字符串（使用正斜杠，跨平台兼容）
    """
    project_root = Path(project_root).resolve()

    if config.model_source_mode == "portable":
        # ── portable 模式 ──
        sub_dir_key = model_paths.sub_dir
        sub_dir_name = config.portable.sub_dirs.get(sub_dir_key, sub_dir_key)
        base = project_root / config.portable.internal_models_dir / sub_dir_name
    else:
        # ── shared 模式 ──
        sub_dir_key = model_paths.sub_dir
        sub_dir_name = config.shared.mount_map.get(sub_dir_key, sub_dir_key)
        base = Path(config.shared.comfy_models_dir) / sub_dir_name

    full_path = base / model_paths.sub_path
    # 统一用正斜杠返回
    return str(full_path).replace("\\", "/")


def resolve_engine_model_paths(
    engine: EngineConfig,
    config: ModelsConfig,
    project_root: Union[str, Path],
) -> Dict[str, str]:
    """
    解析一个引擎的所有模型路径（text_encoder / unet / vae）。

    Returns:
        {"text_encoder": "/abs/path/to/model.safetensors",
         "unet": "/abs/path/to/model.safetensors",
         "vae": "/abs/path/to/model.safetensors"}
    """
    result: Dict[str, str] = {}
    for attr in ("text_encoder", "unet", "vae"):
        mp: Optional[ModelPaths] = getattr(engine, attr, None)
        if mp and mp.sub_path:
            result[attr] = resolve_model_path(mp, config, project_root)
    return result


def scan_resource_files(
    sub_dir_key: str,
    config: ModelsConfig,
    project_root: Union[str, Path],
    extensions: tuple = (".safetensors", ".pt", ".bin", ".ckpt"),
) -> List[str]:
    """
    扫描某个子目录下的所有模型文件，返回相对路径列表。
    用于前端 LoRA 下拉等资源扫描。

    Args:
        sub_dir_key: "text" / "unet" / "vae" / "lora" / "checkpoint" / "controlnet"
        config: ModelsConfig 实例
        project_root: 项目根目录
        extensions: 允许的文件扩展名

    Returns:
        相对路径列表（相对于该子目录根）
    """
    project_root = Path(project_root).resolve()

    if config.model_source_mode == "portable":
        sub_dir_name = config.portable.sub_dirs.get(sub_dir_key, sub_dir_key)
        base = project_root / config.portable.internal_models_dir / sub_dir_name
    else:
        sub_dir_name = config.shared.mount_map.get(sub_dir_key, sub_dir_key)
        base = Path(config.shared.comfy_models_dir) / sub_dir_name

    if not base.exists() or not base.is_dir():
        return []

    results: List[str] = []
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.lower().endswith(extensions):
                rel = Path(root, f).relative_to(base)
                results.append(str(rel).replace("\\", "/"))
    return sorted(results)
