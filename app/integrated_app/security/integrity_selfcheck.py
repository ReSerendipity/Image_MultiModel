"""
security/integrity_selfcheck.py — 启动时核心模块完整性自检

P1-1 改造（来源：Seedvr2）：在应用启动时计算核心安全模块的 SHA256 哈希值
并与预期值比对，检测文件是否被篡改或注入后门 (CWE-912 供应链投毒防御)。
P0 升级（任务书 2026-09-10）：清单签名 + enforce 拒绝启动——
- 验签步骤：先验 Ed25519 签名（.sig.ed25519 + 内置公钥），失败回退 HMAC（.sig）；
  签名把信任根外移到签发机，堵住"攻击者同时改代码和清单"的投毒路径。
- enforce=true（config.yaml security.integrity_selfcheck.enforce）时，验签失败
  或哈希失败或清单缺失 → RuntimeError 拒绝启动（fail-closed）。
- 行尾归一化（_compute_file_sha256）保留不动：跨平台哈希稳定的既有资产。

使用方式:
    from .security.integrity_selfcheck import run_startup_selfcheck

    results = run_startup_selfcheck()
    if results["failed"]:
        logger.error("WARNING: 核心模块完整性校验失败！")

哈希清单文件:
    哈希值存储在 ``app/integrated_app/security/integrity_manifest.json`` 中。
    首次运行或代码更新后，运行 ``python scripts/generate_integrity_manifest.py``
    重新生成清单，再运行 ``python scripts/sign_integrity_manifest.py`` 签名。
    若清单文件不存在，自检跳过并提示生成命令（enforce 模式下拒绝启动）。
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

# 核心安全模块清单 (相对于 app/integrated_app/)
_CORE_MODULES = [
    "app_server.py",
    "config.py",
    "config_models.py",
    "engine_interface.py",
    "model_manager.py",
    "model_registry.py",
    "task_queue.py",
    "history_db.py",
    "lineage.py",
    "i18n.py",
    "gpu_utils.py",
    "sse.py",
    "watermark.py",
    "checkpoint.py",
    "security/path_guard.py",
    "security/magic_check.py",
    "security/integrity_selfcheck.py",
    "security/weight_integrity.py",
    "security/content_filter.py",
    "security/kernel_baseline.py",
    "middleware/csrf.py",
    "middleware/rate_limit.py",
    "middleware/request_id.py",
    "middleware/auth.py",
    "middleware/security_headers.py",
    "routes/config_routes.py",
    "routes/system_routes.py",
    "routes/generate_routes.py",
    "routes/task_routes.py",
    "routes/output_routes.py",
    "routes/preset_routes.py",
    "routes/engine_routes.py",
    "mcp_server.py",
]

# 清单文件路径
_MANIFEST_FILENAME = "integrity_manifest.json"


class SelfCheckResult(NamedTuple):
    """自检结果。"""

    total: int
    passed: int
    failed: int
    skipped: int
    failed_files: list[str]


def _load_secret_key_module():
    """弹性加载 secret_key 模块（三级回退）。

    check_integrity_manifest.py 用 importlib 按文件路径裸加载本模块（绕开
    app 包 __init__ 副作用），此时包内相对导入无父包可依；CI 裸环境也不保证
    项目根在 sys.path（sys.path[0]=scripts/）。三级回退保证任何加载方式下
    验签逻辑都真实可跑，而不是静默降级为"未签名"。
    """
    try:
        from . import secret_key  # 1) 包内正常导入

        return secret_key
    except ImportError:
        pass
    try:
        from app.integrated_app.security import secret_key  # 2) 绝对导入（项目根在 path）

        return secret_key
    except ImportError:
        pass
    import importlib.util  # 3) importlib 按文件路径兜底

    path = Path(__file__).with_name("secret_key.py")
    spec = importlib.util.spec_from_file_location("_imm_secret_key", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_manifest_signature(manifest_path: Path | str) -> bool:
    """校验完整性清单签名（P0：Ed25519 优先，HMAC 兼容）。

    发布版：清单由签发机用私钥签名（.sig.ed25519），包内内置公钥验证 →
    用户端可验签、无需持有私钥，enforce 模式下正常启动且防篡改。
    开发机：无 Ed25519 私钥/公钥时回退 HMAC（data/.imm_secret，.sig）。

    Args:
        manifest_path: 清单文件路径。

    Returns:
        任一签名有效返回 True；否则 False。
    """
    # 1) Ed25519 公钥验证（发布版主路径；公钥内置、私钥不出构建机）
    try:
        secret_key = _load_secret_key_module()
        if secret_key.verify_manifest_signature_ed25519(manifest_path):
            return True
    except Exception as e:  # noqa: BLE001 - 模块不可用时按未签名处理
        logger.debug("[SELF-CHECK] Ed25519 验签不可用: %s", e)
    # 2) HMAC 兼容（开发机/历史清单）
    try:
        secret_key = _load_secret_key_module()
    except Exception as e:  # noqa: BLE001
        logger.debug("[SELF-CHECK] 签名校验模块不可用: %s", e)
        return False
    return secret_key.verify_file_signature(manifest_path)


def _get_manifest_path() -> Path:
    """获取清单文件路径。

    优先采用 ``security.integrity_selfcheck.manifest_file`` 配置（此前该配置
    只声明、无代码消费）；未配置或读取失败时回退到模块同目录默认清单。
    """
    try:
        from ..config import get_config

        configured = get_config().security.integrity_selfcheck.manifest_file
        if configured:
            p = Path(configured)
            if not p.is_absolute():
                # 相对路径相对项目根解析（security/ -> integrated_app/ -> app/ -> 项目根）
                p = Path(__file__).resolve().parents[3] / p
            return p
    except Exception:  # noqa: BLE001 - 配置不可用时回退默认
        pass
    return Path(__file__).parent / _MANIFEST_FILENAME


def _compute_file_sha256(filepath: Path) -> str:
    """计算文件 SHA256（行尾归一化，跨平台稳定）。

    WHY 必须归一化行尾：清单首次在 Windows 工作区生成，而 ``core.autocrlf=true``
    使工作区 .py 文件为 CRLF；Linux CI 上 checkout 得到 LF。若直接对原始字节求
    哈希，同一份源码在两地得到不同 SHA256 —— 结果是「本地自检全绿、CI 必红」，
    且失败模块随机取决于当初谁在哪个平台跑过生成脚本（本次事故命中
    model_registry.py / checkpoint.py / middleware/rate_limit.py 三个模块）。

    归一化规则：删除所有 ``\\r``，即 ``\\r\\n`` 与孤立 ``\\r`` 均折算为 ``\\n``。
    这不削弱篡改检测 —— 任何实质内容改动（含增删空行）仍会改变哈希，被消除的
    只有与代码语义无关的行尾差异。

    跨块边界安全：分块读取时若 ``\\r`` 落在块尾，删除操作逐块独立成立，
    不存在跨块拼接问题（``\\n`` 不会被误删）。
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            # 删除 \r：CRLF/CR → LF，使 Windows 与 Linux 得到同一哈希
            sha256.update(chunk.translate(None, b"\r"))
    return sha256.hexdigest()


def run_startup_selfcheck(enforce: bool = False) -> dict:
    """执行启动时核心模块完整性自检。

    流程:
        1. 读取 integrity_manifest.json 清单文件
        2. 验签（Ed25519 优先，HMAC 回退）——签名把信任根外移到签发机
        3. 若清单不存在，跳过自检并提示生成命令（enforce 模式下拒绝启动）
        4. 对每个核心模块计算当前 SHA256
        5. 与清单中的预期哈希比对
        6. 不一致的文件记录为失败

    Args:
        enforce: True 时验签失败/哈希失败/清单缺失均抛出 RuntimeError 阻断
            启动（fail-closed，拒绝裸奔）。默认 False 保持 fail-open 兼容
            开发与 CI 环境（验签失败仅告警，不阻断）。

    Returns:
        dict: 包含 total/passed/failed/skipped/failed_files/manifest_signed 字段。

    Raises:
        RuntimeError: enforce=True 且验签失败 / 哈希失败 / 清单缺失。
    """
    manifest_path = _get_manifest_path()
    app_dir = Path(__file__).parent.parent  # app/integrated_app/

    # 读取清单
    if not manifest_path.exists():
        message = (
            "[SELF-CHECK] 完整性清单不存在，跳过自检。"
            " 运行 `python scripts/generate_integrity_manifest.py` 生成清单以启用启动自检。"
        )
        logger.info(message)
        if enforce:
            raise RuntimeError(message + "；已开启 enforce，拒绝启动")
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": len(_CORE_MODULES),
            "failed_files": [],
            "manifest_signed": False,
        }

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        message = f"[SELF-CHECK] 清单文件读取失败: {e}"
        logger.warning(message)
        if enforce:
            raise RuntimeError(message + "；已开启 enforce，拒绝启动")
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": len(_CORE_MODULES),
            "failed_files": [],
            "manifest_signed": False,
        }

    # P0：验签——清单与被校验代码同目录，"能改代码就能同步改清单"是原方案的
    # 结构性弱点；签名把信任根外移到签发机私钥（Ed25519）/本机 HMAC 密钥。
    # 验签失败不直接计入 failed（避免开发/CI 无签名环境误红），enforce 时阻断。
    signature_ok = verify_manifest_signature(manifest_path)
    if not signature_ok:
        message = (
            "[SELF-CHECK] 完整性清单缺少有效签名（运行 `python scripts/sign_integrity_manifest.py` 生成）。"
            "未签名清单无法防御'同步篡改代码与清单'的投毒路径"
        )
        logger.warning(message)
        if enforce:
            raise RuntimeError(message + "；已开启 enforce，拒绝启动")

    expected_hashes = manifest.get("files", {})
    if isinstance(expected_hashes.get("__dummy__"), str):
        # 旧版 manifest 格式（值为 "core" 等标签而非哈希），跳过自检
        message = "[SELF-CHECK] 检测到旧版 manifest 格式，跳过自检。请运行 generate_integrity_manifest.py 更新。"
        logger.info(message)
        if enforce:
            raise RuntimeError(message + "；已开启 enforce，拒绝启动")
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": len(_CORE_MODULES),
            "failed_files": [],
            "manifest_signed": signature_ok,
        }

    total = 0
    passed = 0
    failed = 0
    skipped = 0
    failed_files: list[str] = []

    for module_rel in _CORE_MODULES:
        module_path = app_dir / module_rel
        if not module_path.exists():
            logger.warning(f"[SELF-CHECK] 核心模块不存在: {module_path}")
            skipped += 1
            continue

        expected = expected_hashes.get(module_rel, "")

        if not expected:
            skipped += 1
            continue

        total += 1

        try:
            actual = _compute_file_sha256(module_path)
        except OSError as e:
            logger.error(f"[SELF-CHECK] 无法读取 {module_path}: {e}")
            failed += 1
            failed_files.append(module_rel)
            continue

        if actual == expected:
            passed += 1
            logger.debug(f"[SELF-CHECK] ✓ {module_rel}")
        else:
            failed += 1
            failed_files.append(module_rel)
            logger.error(
                f"[SECURITY WARNING] 核心模块完整性校验失败: {module_rel}\n"
                f"    期望 SHA256: {expected}\n"
                f"    实际 SHA256: {actual}\n"
                f"    该文件可能已被篡改！请检查代码完整性。"
            )

    # 输出汇总
    if failed > 0:
        logger.error(
            "=" * 60 + "\n"
            "[SECURITY] ⚠️  核心模块完整性自检失败！\n"
            f"    通过: {passed}/{total}, 失败: {failed}, 跳过: {skipped}\n"
            f"    失败文件: {', '.join(failed_files)}\n"
            "    请检查上述文件是否被篡改，或运行 "
            "`python scripts/generate_integrity_manifest.py` 更新清单。\n" + "=" * 60
        )
    if skipped > 0:
        # L-01 修复：历史上 magic_check.py / weight_integrity.py 在 _CORE_MODULES 中
        # 却不在清单里，被静默 skipped 后启动日志仍打印「通过 25/25」，形成假安全感
        # （对应安全评估 H-04）。即使 manifest 已补齐，此处仍保留显式告警，确保任何
        # 清单漂移都能立即可见，而非淹没在「通过」日志中。
        logger.warning(
            "=" * 60 + "\n"
            "[SELF-CHECK] ⚠️ 核心模块完整性自检存在 %d 个模块被跳过（无哈希记录）！\n"
            f"    通过: {passed}/{total}, 失败: {failed}, 跳过: {skipped}\n"
            "    被跳过的模块不会参与篡改检测，等于裸奔。请运行 "
            "`python scripts/generate_integrity_manifest.py` 重新生成清单并重启。\n" + "=" * 60
        )
    if passed > 0:
        logger.info(f"[SELF-CHECK] 核心模块完整性自检通过: {passed}/{total} ✓（跳过 {skipped}）")

    # P0 enforce：哈希失败 / 清单覆盖缺口（skipped 裸奔）均拒绝启动（fail-closed）
    if enforce and failed > 0:
        raise RuntimeError(f"核心模块完整性校验失败（enforce 模式，拒绝启动）: {', '.join(failed_files)}")
    if enforce and skipped > 0:
        raise RuntimeError(f"核心模块完整性自检存在 {skipped} 个模块被跳过（enforce 模式不允许裸奔，拒绝启动）")

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failed_files": failed_files,
        "manifest_signed": signature_ok,
    }
