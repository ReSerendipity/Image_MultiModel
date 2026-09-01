"""
cache.py — 进程内 TTL/LRU 缓存（架构评估 P0-2）

落地原先"声明但无任何消费者"的 ``CacheConfig``（config.yaml → cache 段），
为高频、昂贵且幂等的计算提供缓存：

- **prompt/image 缓存**：CLIP 安全检测结果（按文件路径 + size + mtime 版本化）
- **model 缓存**：模型资源目录扫描结果（``scan_resource_files``，按 TTL 失效）

设计取舍：
- 进程内缓存即可覆盖单进程单 GPU 部署模型的绝大多数重复计算；
  跨进程场景应外置 Redis，此处刻意保持轻量、无新依赖。
- 采用「TTL 过期 + 条目数上限 LRU」双约束，避免无界增长；
  条目估算体积按 ``_estimate_size`` 近似计算（不追求精确字节）。
- 所有失败（磁盘不可写、序列化失败）均降级为「未命中」，绝不阻断业务。
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)


class CacheStats:
    """缓存命中统计（便于可观测与测试断言）。"""

    def __init__(self) -> None:
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0
        self.expirations: int = 0
        self.sets: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "sets": self.sets,
        }

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total else 0.0


class TTLCache:
    """线程安全的 TTL + LRU 缓存。

    Args:
        name: 命名空间（便于日志与统计隔离）。
        max_entries: 最大条目数；超过时按 LRU 淘汰。
        ttl_s: 条目生存期（秒）；<=0 表示不过期。
    """

    def __init__(self, name: str = "default", max_entries: int = 512, ttl_s: float = 300.0) -> None:
        self._name = name
        self._max_entries = max(1, int(max_entries))
        self._ttl_s = float(ttl_s)
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()

    # ── 基本操作 ──────────────────────────────────────────────
    def get(self, key: str) -> Any:
        """读取缓存；未命中或已过期返回 ``None``。"""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._stats.misses += 1
                return None
            ts, value = entry
            if self._ttl_s > 0 and (time.time() - ts) > self._ttl_s:
                self._data.pop(key, None)
                self._stats.expirations += 1
                self._stats.misses += 1
                return None
            # LRU：命中后移到末尾
            self._data.move_to_end(key)
            self._stats.hits += 1
            return value

    def put(self, key: str, value: Any) -> None:
        """写入缓存（超限时按 LRU 淘汰最久未用条目）。"""
        with self._lock:
            self._data[key] = (time.time(), value)
            self._data.move_to_end(key)
            self._stats.sets += 1
            while len(self._data) > self._max_entries:
                self._data.popitem(last=False)
                self._stats.evictions += 1

    def invalidate(self, key: str) -> bool:
        """删除指定键；返回是否确实存在。"""
        with self._lock:
            return self._data.pop(key, None) is not None

    def clear(self) -> None:
        """清空本命名空间所有条目。"""
        with self._lock:
            self._data.clear()

    # ── 便捷：get-or-compute ──────────────────────────────────
    def get_or_set(self, key: str, factory) -> Any:
        """命中则返回值，否则调用 ``factory()`` 计算并写入。

        ``factory`` 抛异常时向上传播（不缓存失败结果）。
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.put(key, value)
        return value

    # ── 观测 ──────────────────────────────────────────────────
    @property
    def stats(self) -> CacheStats:
        return self._stats

    def size(self) -> int:
        with self._lock:
            return len(self._data)

    @property
    def name(self) -> str:
        return self._name

    def purge_expired(self) -> int:
        """清理所有已过期条目，返回清理数量。"""
        if self._ttl_s <= 0:
            return 0
        now = time.time()
        removed = 0
        with self._lock:
            for key in [k for k, (ts, _v) in self._data.items() if now - ts > self._ttl_s]:
                self._data.pop(key, None)
                removed += 1
        return removed


# ── 命名空间注册表 ────────────────────────────────────────────
_NAMESPACES: dict[str, TTLCache] = {}
_REGISTRY_LOCK = threading.RLock()

# 各命名空间的默认容量（条目数）。体积受 CacheConfig.max_size_mb 统一约束，
# 此处按「每条目平均占用」折算，见 build_caches_from_config。
_NAMESPACE_MAX_ENTRIES = {
    "safety": 1024,  # CLIP 检测结果（按图片路径）
    "model": 256,  # 模型资源扫描结果
    "prompt": 2048,  # 提示词相关派生结果
}


def get_cache(namespace: str = "default") -> TTLCache:
    """获取（或惰性创建）指定命名空间的缓存实例。"""
    with _REGISTRY_LOCK:
        cache = _NAMESPACES.get(namespace)
        if cache is None:
            cache = TTLCache(
                name=namespace,
                max_entries=_NAMESPACE_MAX_ENTRIES.get(namespace, 512),
                ttl_s=_DEFAULT_TTL_S,
            )
            _NAMESPACES[namespace] = cache
        return cache


_DEFAULT_TTL_S: float = 300.0


def clear_all_caches() -> None:
    """清空所有命名空间（供测试隔离与配置热更新使用）。"""
    with _REGISTRY_LOCK:
        for cache in _NAMESPACES.values():
            cache.clear()


def build_caches_from_config(cfg: Any) -> dict[str, TTLCache]:
    """按 ``CacheConfig`` 重建缓存参数（消费 config.yaml → cache 段的唯一入口）。

    把 ``max_size_mb`` 折算为「每命名空间条目上限」：以每条目约 64KB 估算，
    再按命名空间权重分配，保证总体积不越过配置上限。

    Args:
        cfg: AppConfig（需含 ``cache: CacheConfig``）。

    Returns:
        ``{namespace: TTLCache}`` 已按新参数重建的缓存集合。
    """
    global _DEFAULT_TTL_S

    cache_cfg = getattr(cfg, "cache", None)
    ttl_s = float(getattr(cache_cfg, "ttl_s", 300.0) or 300.0)
    max_size_mb = float(getattr(cache_cfg, "max_size_mb", 500) or 500.0)

    _DEFAULT_TTL_S = ttl_s

    # 每条目按 64KB 估算 → 总条目预算
    total_entries = max(64, int(max_size_mb * 1024 / 64))
    weights = {"safety": 4, "model": 2, "prompt": 6, "default": 2}
    weight_sum = sum(weights.values())

    with _REGISTRY_LOCK:
        _NAMESPACES.clear()
        for ns, weight in weights.items():
            max_entries = max(16, int(total_entries * weight / weight_sum))
            ttl = ttl_s
            # 模型目录扫描变化不频繁，给更长 TTL（4 倍，上限 1 小时）
            if ns == "model":
                ttl = min(ttl_s * 4, 3600.0)
            _NAMESPACES[ns] = TTLCache(name=ns, max_entries=max_entries, ttl_s=ttl)
        logger.info(
            "Cache initialized from config: ttl=%.0fs, max_size=%dMB, namespaces=%s",
            ttl_s,
            int(max_size_mb),
            sorted(_NAMESPACES),
        )
        return dict(_NAMESPACES)


def cache_stats_snapshot() -> dict[str, dict[str, Any]]:
    """返回所有命名空间的统计快照（供 /api/system/health 等观测面消费）。"""
    with _REGISTRY_LOCK:
        return {
            name: {**cache.stats.as_dict(), "size": cache.size(), "hit_rate": round(cache.stats.hit_rate, 4)}
            for name, cache in _NAMESPACES.items()
        }


__all__ = [
    "CacheStats",
    "TTLCache",
    "build_caches_from_config",
    "cache_stats_snapshot",
    "clear_all_caches",
    "get_cache",
]
