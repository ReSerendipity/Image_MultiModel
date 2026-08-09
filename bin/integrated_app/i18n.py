"""
i18n.py — 后端错误文案国际化

对应 MASTER_PLAN §4: i18n.py
对应 PRD §2.11: 5 语言后端错误文案清单
"""

from __future__ import annotations

from typing import Dict, Optional

# ── 5 语言后端错误文案字典 ───────────────────────────────────
ERROR_MESSAGES: Dict[str, Dict[str, str]] = {
    "zh": {
        # 引擎错误
        "engine_not_found": "引擎不存在: {name}",
        "engine_not_ready": "引擎未就绪，请先加载模型",
        "engine_load_failed": "引擎加载失败: {detail}",
        "engine_unload_failed": "引擎卸载失败: {detail}",
        # 任务错误
        "task_not_found": "任务不存在: {task_id}",
        "task_already_running": "任务已在运行中",
        "task_cancel_failed": "取消任务失败: {detail}",
        "task_timeout": "任务超时（{timeout}s）",
        "task_queue_full": "任务队列已满，请稍后重试",
        # 参数错误
        "invalid_param": "无效参数: {param}={value}",
        "batch_too_large": "批量大小超过限制（最大 9999）",
        "seed_must_be_int": "种子必须是整数或 -1（随机）",
        "resolution_too_large": "分辨率过大，建议不超过 2048×2048",
        # ComfyUI 错误
        "comfy_not_reachable": "ComfyUI 后端不可达: {url}",
        "comfy_ws_error": "ComfyUI WebSocket 错误: {detail}",
        "comfy_workflow_error": "工作流执行错误: {detail}",
        "comfy_node_not_found": "工作流节点不存在: {node_id}",
        # 显存错误
        "vram_insufficient": "显存不足（需要 {need}GB，可用 {avail}GB），请降低分辨率或 batch",
        "vram_preflight_failed": "显存预检失败: {detail}",
        # 路径错误
        "path_traversal": "路径不安全: {path}",
        "file_not_found": "文件不存在: {path}",
        # 认证错误
        "auth_required": "需要认证",
        "auth_failed": "认证失败",
        "rate_limit_exceeded": "请求过于频繁，请稍后再试",
        # 通用
        "config_save_failed": "配置保存失败: {detail}",
        "config_invalid": "配置无效: {detail}",
        "preset_not_found": "预设不存在",
        "preset_name_exists": "预设名称已存在",
        "unknown_error": "未知错误: {detail}",
    },
    "en": {
        "engine_not_found": "Engine not found: {name}",
        "engine_not_ready": "Engine not ready, please load model first",
        "engine_load_failed": "Engine load failed: {detail}",
        "engine_unload_failed": "Engine unload failed: {detail}",
        "task_not_found": "Task not found: {task_id}",
        "task_already_running": "Task is already running",
        "task_cancel_failed": "Cancel task failed: {detail}",
        "task_timeout": "Task timed out ({timeout}s)",
        "task_queue_full": "Task queue is full, please try later",
        "invalid_param": "Invalid parameter: {param}={value}",
        "batch_too_large": "Batch size exceeds limit (max 9999)",
        "seed_must_be_int": "Seed must be integer or -1 (random)",
        "resolution_too_large": "Resolution too large, suggest ≤ 2048×2048",
        "comfy_not_reachable": "ComfyUI backend not reachable: {url}",
        "comfy_ws_error": "ComfyUI WebSocket error: {detail}",
        "comfy_workflow_error": "Workflow execution error: {detail}",
        "comfy_node_not_found": "Workflow node not found: {node_id}",
        "vram_insufficient": "VRAM insufficient (need {need}GB, avail {avail}GB), reduce resolution or batch",
        "vram_preflight_failed": "VRAM preflight failed: {detail}",
        "path_traversal": "Unsafe path: {path}",
        "file_not_found": "File not found: {path}",
        "auth_required": "Authentication required",
        "auth_failed": "Authentication failed",
        "rate_limit_exceeded": "Rate limit exceeded, try later",
        "config_save_failed": "Config save failed: {detail}",
        "config_invalid": "Invalid config: {detail}",
        "preset_not_found": "Preset not found",
        "preset_name_exists": "Preset name already exists",
        "unknown_error": "Unknown error: {detail}",
    },
    "ja": {
        "engine_not_found": "エンジンが見つかりません: {name}",
        "engine_not_ready": "エンジンの準備ができていません。モデルを先にロードしてください",
        "engine_load_failed": "エンジンのロードに失敗: {detail}",
        "engine_unload_failed": "エンジンのアンロードに失敗: {detail}",
        "task_not_found": "タスクが見つかりません: {task_id}",
        "task_already_running": "タスクは既に実行中です",
        "task_cancel_failed": "タスクのキャンセルに失敗: {detail}",
        "task_timeout": "タスクがタイムアウトしました（{timeout}s）",
        "task_queue_full": "タスクキューが満杯です。後で再試行してください",
        "invalid_param": "無効なパラメータ: {param}={value}",
        "batch_too_large": "バッチサイズが制限を超えています（最大 9999）",
        "seed_must_be_int": "シードは整数または -1（ランダム）である必要があります",
        "resolution_too_large": "解像度が大きすぎます。2048×2048 以下を推奨",
        "comfy_not_reachable": "ComfyUIバックエンドに接続できません: {url}",
        "comfy_ws_error": "ComfyUI WebSocketエラー: {detail}",
        "comfy_workflow_error": "ワークフロー実行エラー: {detail}",
        "comfy_node_not_found": "ワークフローノードが見つかりません: {node_id}",
        "vram_insufficient": "VRAM不足（必要 {need}GB、利用可能 {avail}GB）",
        "vram_preflight_failed": "VRAM事前チェック失敗: {detail}",
        "path_traversal": "安全でないパス: {path}",
        "file_not_found": "ファイルが見つかりません: {path}",
        "auth_required": "認証が必要です",
        "auth_failed": "認証に失敗しました",
        "rate_limit_exceeded": "リクエストが多すぎます。後で再試行してください",
        "config_save_failed": "設定の保存に失敗: {detail}",
        "config_invalid": "無効な設定: {detail}",
        "preset_not_found": "プリセットが見つかりません",
        "preset_name_exists": "プリセット名が既に存在します",
        "unknown_error": "不明なエラー: {detail}",
    },
    "ko": {
        "engine_not_found": "엔진을 찾을 수 없습니다: {name}",
        "engine_not_ready": "엔진이 준비되지 않았습니다. 모델을 먼저 로드하세요",
        "engine_load_failed": "엔진 로드 실패: {detail}",
        "engine_unload_failed": "엔진 언로드 실패: {detail}",
        "task_not_found": "태스크를 찾을 수 없습니다: {task_id}",
        "task_already_running": "태스크가 이미 실행 중입니다",
        "task_cancel_failed": "태스크 취소 실패: {detail}",
        "task_timeout": "태스크 시간 초과 ({timeout}s)",
        "task_queue_full": "태스크 큐가 가득 찼습니다. 나중에 시도하세요",
        "invalid_param": "잘못된 매개변수: {param}={value}",
        "batch_too_large": "배치 크기 제한 초과 (최대 9999)",
        "seed_must_be_int": "시드는 정수 또는 -1(랜덤)이어야 합니다",
        "resolution_too_large": "해상도가 너무 큽니다. 2048×2048 이하 권장",
        "comfy_not_reachable": "ComfyUI 백엔드에 연결할 수 없습니다: {url}",
        "comfy_ws_error": "ComfyUI WebSocket 오류: {detail}",
        "comfy_workflow_error": "워크플로 실행 오류: {detail}",
        "comfy_node_not_found": "워크플로 노드를 찾을 수 없습니다: {node_id}",
        "vram_insufficient": "VRAM 부족 (필요 {need}GB, 사용 가능 {avail}GB)",
        "vram_preflight_failed": "VRAM 사전 확인 실패: {detail}",
        "path_traversal": "안전하지 않은 경로: {path}",
        "file_not_found": "파일을 찾을 수 없습니다: {path}",
        "auth_required": "인증이 필요합니다",
        "auth_failed": "인증 실패",
        "rate_limit_exceeded": "요청이 너무 많습니다. 나중에 시도하세요",
        "config_save_failed": "설정 저장 실패: {detail}",
        "config_invalid": "잘못된 설정: {detail}",
        "preset_not_found": "프리셋을 찾을 수 없습니다",
        "preset_name_exists": "프리셋 이름이 이미 존재합니다",
        "unknown_error": "알 수 없는 오류: {detail}",
    },
    "zh-tw": {
        "engine_not_found": "引擎不存在: {name}",
        "engine_not_ready": "引擎未就緒，請先載入模型",
        "engine_load_failed": "引擎載入失敗: {detail}",
        "engine_unload_failed": "引擎卸載失敗: {detail}",
        "task_not_found": "任務不存在: {task_id}",
        "task_already_running": "任務已在執行中",
        "task_cancel_failed": "取消任務失敗: {detail}",
        "task_timeout": "任務逾時（{timeout}s）",
        "task_queue_full": "任務佇列已滿，請稍後重試",
        "invalid_param": "無效參數: {param}={value}",
        "batch_too_large": "批次大小超過限制（最大 9999）",
        "seed_must_be_int": "種子必須是整數或 -1（隨機）",
        "resolution_too_large": "解析度過大，建議不超過 2048×2048",
        "comfy_not_reachable": "ComfyUI 後端不可達: {url}",
        "comfy_ws_error": "ComfyUI WebSocket 錯誤: {detail}",
        "comfy_workflow_error": "工作流程執行錯誤: {detail}",
        "comfy_node_not_found": "工作流程節點不存在: {node_id}",
        "vram_insufficient": "顯存不足（需要 {need}GB，可用 {avail}GB），請降低解析度或批次",
        "vram_preflight_failed": "顯存預檢失敗: {detail}",
        "path_traversal": "路徑不安全: {path}",
        "file_not_found": "檔案不存在: {path}",
        "auth_required": "需要認證",
        "auth_failed": "認證失敗",
        "rate_limit_exceeded": "請求過於頻繁，請稍後再試",
        "config_save_failed": "設定儲存失敗: {detail}",
        "config_invalid": "無效設定: {detail}",
        "preset_not_found": "預設不存在",
        "preset_name_exists": "預設名稱已存在",
        "unknown_error": "未知錯誤: {detail}",
    },
}


def get_error_message(key: str, locale: str = "zh", **kwargs) -> str:
    """
    获取本地化错误消息。

    Args:
        key: 错误消息 key
        locale: 语言代码 (zh / en / ja / ko)
        **kwargs: 模板变量

    Returns:
        格式化后的错误消息字符串
    """
    messages = ERROR_MESSAGES.get(locale, ERROR_MESSAGES.get("zh", {}))
    template = messages.get(key, ERROR_MESSAGES["zh"].get(key, key))
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
