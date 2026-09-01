"""
单元测试：cache.py（P0-2 缓存层）

验证 TTL 过期、LRU 淘汰、get_or_set、统计、命名空间注册表与
build_caches_from_config 容量折算。
"""

import asyncio
import time

import pytest

from app.integrated_app.cache import (
    TTLCache,
    build_caches_from_config,
    cache_stats_snapshot,
    clear_all_caches,
    get_cache,
)


@pytest.fixture(autouse=True)
def _clean_caches():
    clear_all_caches()
    yield
    clear_all_caches()


def test_put_get_basic():
    c = TTLCache(name="t", max_entries=10, ttl_s=100)
    c.put("a", 1)
    assert c.get("a") == 1
    assert c.size() == 1


def test_ttl_expiry():
    c = TTLCache(name="t", max_entries=10, ttl_s=0.05)
    c.put("a", 1)
    assert c.get("a") == 1
    time.sleep(0.08)
    assert c.get("a") is None
    assert c.stats.expirations >= 1
    assert c.stats.misses >= 1


def test_lru_eviction():
    c = TTLCache(name="t", max_entries=3, ttl_s=100)
    for i in range(5):
        c.put(f"k{i}", i)
    # 超出容量，保留最近写入的 3 条
    assert c.size() == 3
    assert c.get("k0") is None
    assert c.get("k4") == 4
    assert c.stats.evictions >= 2


def test_get_or_set_computes_once():
    c = TTLCache(name="t", max_entries=10, ttl_s=100)
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return 42

    assert c.get_or_set("x", factory) == 42
    assert c.get_or_set("x", factory) == 42
    assert calls["n"] == 1  # 仅计算一次


def test_purge_expired():
    c = TTLCache(name="t", max_entries=10, ttl_s=0.05)
    c.put("a", 1)
    c.put("b", 2)
    time.sleep(0.08)
    removed = c.purge_expired()
    assert removed == 2
    assert c.size() == 0


def test_stats_hit_rate():
    c = TTLCache(name="t", max_entries=10, ttl_s=100)
    c.put("a", 1)
    c.get("a")
    c.get("missing")
    assert c.stats.hits == 1
    assert c.stats.misses == 1
    assert c.stats.hit_rate == 0.5


def test_registry_and_snapshot():
    c = get_cache("safety")
    c.put("k", "v")
    snap = cache_stats_snapshot()
    assert "safety" in snap
    assert snap["safety"]["size"] == 1


def test_build_caches_from_config():
    class FakeCache:
        ttl_s = 60
        max_size_mb = 200

    class FakeCfg:
        cache = FakeCache()

    caches = build_caches_from_config(FakeCfg())
    assert set(caches.keys()) >= {"safety", "model", "prompt"}
    # safety 命名空间应已按配置容量建立
    assert caches["safety"].size() == 0


def test_async_no_deadlock():
    """缓存同步操作不应阻塞事件循环（基本烟雾测试）。"""
    c = get_cache("prompt")

    async def go():
        c.put("k", 1)
        return c.get("k")

    assert asyncio.run(go()) == 1
