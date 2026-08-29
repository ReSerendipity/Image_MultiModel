"""
i18n.py — 后端错误文案国际化

P1-2 改造（来源：TTS_MultiModel）：从硬编码 Python 字典迁移到 JSON 文件。
翻译内容存储在 ``locales/*.json`` 的 ``backend_errors`` namespace 中。

三层 fallback 链保障翻译永不显示空值：
1. 用户指定语言 → 英文（en）回退 → key 本身兜底
2. 翻译键查找支持扁平优先 + 命名空间嵌套下钻

向后兼容：``ERROR_MESSAGES`` 和 ``get_error_message()`` 仍保留可用，
内部改为从 JSON 文件加载。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("integrated_app")

# ── 路径与语言映射 ────────────────────────────────────────────

_LOCALES_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

_LANG_FILE_MAP: dict[str, str] = {
    "en": "en.json",
    "zh-CN": "zh.json",
    "zh-Hans": "zh.json",
    "zh": "zh.json",
    "zh-TW": "zh-tw.json",
    "zh-Hant": "zh-tw.json",
    "zh-tw": "zh-tw.json",
    "ja": "ja.json",
    "ko": "ko.json",
}

# ── 翻译缓存 ──────────────────────────────────────────────────

_I18N_TRANSLATIONS: dict[str, dict[str, Any]] = {}
_BACKEND_ERRORS_CACHE: dict[str, dict[str, str]] | None = None


def _load_translations(lang: str) -> dict[str, Any] | None:
    """加载指定语言的翻译字典（带缓存）。

    Args:
        lang: 语言代码（如 "zh"、"en"）。

    Returns:
        翻译字典；语言不支持、文件不存在时返回 None。
    """
    if lang in _I18N_TRANSLATIONS:
        return _I18N_TRANSLATIONS[lang]
    filename = _LANG_FILE_MAP.get(lang)
    if filename is None:
        return None
    filepath = os.path.join(_LOCALES_DIR, filename)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"国际化文件加载失败: {filepath}: {e}")
        return None
    _I18N_TRANSLATIONS[lang] = data
    return data


def _load_backend_errors() -> dict[str, dict[str, str]]:
    """从 JSON locale 文件加载 backend_errors namespace（带缓存）。

    Returns:
        dict: {locale: {key: message}} 格式的后端错误文案字典。
              只包含 5 个主语言：zh / en / ja / ko / zh-tw
    """
    global _BACKEND_ERRORS_CACHE
    if _BACKEND_ERRORS_CACHE is not None:
        return _BACKEND_ERRORS_CACHE

    result: dict[str, dict[str, str]] = {}
    # 只加载 5 个主语言（不含别名）
    _PRIMARY_LOCALES = ["zh", "en", "ja", "ko", "zh-tw"]
    for lang in _PRIMARY_LOCALES:
        filename = _LANG_FILE_MAP.get(lang)
        if not filename:
            continue
        filepath = os.path.join(_LOCALES_DIR, filename)
        if not os.path.exists(filepath):
            continue
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        backend = data.get("backend_errors", {})
        if isinstance(backend, dict):
            result[lang] = dict(backend)

    _BACKEND_ERRORS_CACHE = result
    return result


# ── 向后兼容：ERROR_MESSAGES ──────────────────────────────────

def _get_error_messages() -> dict[str, dict[str, str]]:
    """获取 ERROR_MESSAGES（从 JSON 加载，带缓存）。

    向后兼容：旧代码使用 ``from .i18n import ERROR_MESSAGES`` 时，
    通过本函数从 JSON locale 文件的 ``backend_errors`` namespace 加载。
    """
    return _load_backend_errors()


class _ErrorMessagesProxy:
    """ERROR_MESSAGES 的延迟加载代理。

    首次访问时从 JSON 文件加载 backend_errors，
    之后缓存供后续访问使用。
    """

    def _get_data(self) -> dict[str, dict[str, str]]:
        return _load_backend_errors()

    def __contains__(self, key: str) -> bool:
        return key in self._get_data()

    def __getitem__(self, key: str) -> dict[str, str]:
        return self._get_data()[key]

    def __iter__(self):
        return iter(self._get_data())

    def keys(self):
        return self._get_data().keys()

    def values(self):
        return self._get_data().values()

    def items(self):
        return self._get_data().items()

    def get(self, key: str, default: Any = None) -> Any:
        return self._get_data().get(key, default)


# 向后兼容别名
ERROR_MESSAGES = _ErrorMessagesProxy()


# ── 向后兼容：get_error_message ───────────────────────────────


def get_error_message(key: str, locale: str = "zh", **kwargs) -> str:
    """获取本地化错误消息（向后兼容接口）。

    P1-2 改造后内部从 JSON locale 文件加载。

    Args:
        key: 错误消息 key
        locale: 语言代码 (zh / en / ja / ko / zh-tw)
        **kwargs: 模板变量

    Returns:
        格式化后的错误消息字符串
    """
    messages = _load_backend_errors()
    lang_messages = messages.get(locale, messages.get("zh", {}))
    template = lang_messages.get(key, messages.get("zh", {}).get(key, key))
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


# ── 新接口：t() 三层 fallback ─────────────────────────────────


def _resolve_key(translations: dict[str, Any], key: str) -> str | None:
    """在翻译字典中解析翻译键。

    先尝试扁平查找：以完整 key 作为字典键直接命中；
    失败后再使用 "." 分割并逐段下钻嵌套 dict。
    只有最终叶子节点是 str 类型才返回。

    Args:
        translations: 翻译字典。
        key: 翻译键。

    Returns:
        翻译文本字符串；未找到时返回 None。
    """
    try:
        if key in translations:
            result = translations[key]
            return result if isinstance(result, str) else None
    except (TypeError, AttributeError):
        pass

    if "." in key:
        try:
            parts = key.split(".")
            result = translations
            for part in parts:
                if isinstance(result, dict) and part in result:
                    result = result[part]
                else:
                    return None
            return result if isinstance(result, str) else None
        except Exception:
            return None
    return None


def t(key: str, lang: str = "zh", default: str | None = None, **kwargs) -> str:
    """翻译函数，三层 fallback 链保障不显示空值。

    fallback 顺序：
    1. 指定 lang 的翻译字典 → _resolve_key
    2. 英文（en）翻译字典 → _resolve_key
    3. default 参数（若不为 None）或 key 本身作为最终兜底

    Args:
        key: 翻译键。
        lang: 目标语言代码，默认 "zh"。
        default: 可选的自定义兜底文本。
        **kwargs: str.format 参数替换。

    Returns:
        翻译结果或兜底字符串，永不返回 None。
    """
    try:
        lang_dict = _load_translations(lang)
        if lang_dict is not None:
            result = _resolve_key(lang_dict, key)
            if result is not None:
                return result.format(**kwargs) if kwargs else result
        en_dict = _load_translations("en")
        if en_dict is not None:
            result = _resolve_key(en_dict, key)
            if result is not None:
                return result.format(**kwargs) if kwargs else result
    except Exception:
        pass
    return default if default is not None else key


# ── 前端 i18n JSON 合并 ────────────────────────────────────────


def get_i18n_json(lang: str) -> dict[str, Any]:
    """返回前端 JS 侧使用的合并翻译字典。

    合并策略：以英文（en）字典为基础，再用目标语言字典 update 覆盖。

    Args:
        lang: 目标语言代码。

    Returns:
        合并后的翻译字典。
    """
    translations = _load_translations(lang)
    if translations is None:
        translations = _load_translations("zh") or {}
    en_dict = _load_translations("en") or {}
    merged: dict[str, Any] = dict(en_dict)
    merged.update(translations)
    return merged
