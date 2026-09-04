"""uploads_ttl.py — ``data/uploads`` TTL 清理执行者（数据治理报告 P1-2）

此前 ``uploads.ttl_s: 86400`` 只在配置里声明、全仓无任何消费方——上传图片的
隐私暴露窗口实际为**永久**。本模块兑现该承诺：按文件 mtime 扫描超龄上传
文件并删除，随历史清理 cron 联跑（``app_server.history_cleanup_cron``）。

设计要点：
- 只清理 ``uploads_dir`` 下的**普通文件**（不上溯、不递归子目录）；
  目录本身与其余内容一律不碰。
- ``ttl_s <= 0`` 或目录不存在时为 no-op（语义：0 = 不清理，与
  ``history.keep_days=0`` 语义对齐）。
- 单文件 unlink 失败仅 debug 记录，不阻断其余文件（与 history_db 清理一致）。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_expired_uploads(
    uploads_dir: str | Path,
    ttl_s: int,
    now: float | None = None,
) -> tuple[int, int]:
    """删除 uploads 目录中超过 TTL 的文件。

    Args:
        uploads_dir: 上传缓存目录（``cfg.output.uploads.cache_dir``）
        ttl_s: 保留秒数（``cfg.output.uploads.ttl_s``；<=0 时不清理）
        now: 当前时间戳（可注入以便测试）；None 则取 ``time.time()``

    Returns:
        ``(deleted_count, freed_bytes)``
    """
    if ttl_s <= 0:
        return (0, 0)
    d = Path(uploads_dir)
    if not d.is_dir():
        return (0, 0)
    ts = time.time() if now is None else now
    deleted = 0
    freed = 0
    for f in sorted(d.iterdir()):
        try:
            if not f.is_file():
                continue
            st = f.stat()
            if ts - st.st_mtime > ttl_s:
                f.unlink()
                deleted += 1
                freed += st.st_size
        except OSError as e:  # noqa: BLE001 - 单文件失败不阻断
            logger.debug("Uploads TTL cleanup skipped %s: %s", f, e)
    if deleted:
        logger.info(
            "Uploads TTL cleanup: removed %d file(s), freed %.1f KB (ttl_s=%d)",
            deleted, freed / 1024, ttl_s,
        )
    return (deleted, freed)


__all__ = ["cleanup_expired_uploads"]
