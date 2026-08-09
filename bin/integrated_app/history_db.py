"""
history_db.py — SQLite 历史记录数据库

对应 MASTER_PLAN §4 / 附录 B3: history_db.py
对应 PRD §6.3: tasks / outputs / presets + WAL/FTS5 + 崩溃恢复
对应 MASTER_PLAN §8: 数据模型
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class HistoryDB:
    """
    SQLite 数据库管理器：
    - tasks 表：任务记录
    - outputs 表：输出文件
    - presets 表：预设
    - tasks_fts：全文检索（FTS5）
    - WAL 模式：崩溃恢复
    """

    SCHEMA_SQL = """
    -- 任务表
    CREATE TABLE IF NOT EXISTS tasks (
        task_id          TEXT PRIMARY KEY,
        engine           TEXT NOT NULL,
        mode             TEXT NOT NULL DEFAULT 'txt2img',  -- txt2img | batch
        status           TEXT NOT NULL DEFAULT 'pending',  -- pending|processing|completed|failed|cancelled
        prompt           TEXT DEFAULT '',
        negative_prompt  TEXT DEFAULT '',
        generation_config TEXT DEFAULT '{}',  -- JSON 22 项
        thumbnail        TEXT DEFAULT '',
        output_count     INTEGER DEFAULT 0,
        processing_time_s REAL DEFAULT 0,
        error            TEXT DEFAULT '',
        favorite         INTEGER DEFAULT 0,
        tags             TEXT DEFAULT '[]',  -- JSON 数组
        created_at       TEXT DEFAULT (datetime('now')),
        updated_at       TEXT DEFAULT (datetime('now')),
        interrupted_at_reboot INTEGER DEFAULT 0
    );

    -- 输出表（一对多）
    CREATE TABLE IF NOT EXISTS outputs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id    TEXT NOT NULL,
        path       TEXT NOT NULL,
        format     TEXT DEFAULT 'png',
        file_size  INTEGER DEFAULT 0,
        width      INTEGER DEFAULT 0,
        height     INTEGER DEFAULT 0,
        seed       TEXT DEFAULT '',
        output_type TEXT DEFAULT 'original',  -- original|upscaled|compare
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
    );

    -- 预设表
    CREATE TABLE IF NOT EXISTS presets (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        engine_name TEXT NOT NULL,
        name        TEXT NOT NULL,
        thumbnail   TEXT DEFAULT '',
        config      TEXT DEFAULT '{}',  -- JSON，不含 seed
        created_at  TEXT DEFAULT (datetime('now')),
        UNIQUE(engine_name, name)
    );

    -- 全文检索索引
    CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
        task_id UNINDEXED,
        prompt,
        tags,
        content='tasks',
        content_rowid='rowid'
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
    CREATE INDEX IF NOT EXISTS idx_tasks_engine ON tasks(engine);
    CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
    CREATE INDEX IF NOT EXISTS idx_tasks_favorite ON tasks(favorite);
    CREATE INDEX IF NOT EXISTS idx_outputs_task_id ON outputs(task_id);
    CREATE INDEX IF NOT EXISTS idx_outputs_path ON outputs(path);
    """

    FTS_TRIGGER_SQL = """
    CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
        INSERT INTO tasks_fts(task_id, prompt, tags)
        VALUES (new.task_id, new.prompt, new.tags);
    END;
    CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
        INSERT INTO tasks_fts(tasks_fts, rowid, prompt, tags)
        VALUES ('delete', old.rowid, old.prompt, old.tags);
    END;
    CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE ON tasks BEGIN
        INSERT INTO tasks_fts(tasks_fts, rowid, prompt, tags)
        VALUES ('delete', old.rowid, old.prompt, old.tags);
        INSERT INTO tasks_fts(task_id, prompt, tags)
        VALUES (new.task_id, new.prompt, new.tags);
    END;
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        # WAL 模式（崩溃恢复）
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(self.SCHEMA_SQL)
        conn.executescript(self.FTS_TRIGGER_SQL)
        conn.commit()
        self._conn = conn
        logger.info(f"HistoryDB initialized at {self.db_path}")

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._init_db()
        assert self._conn is not None
        return self._conn

    # ── 崩溃恢复 ──────────────────────────────────────────────
    def recover_stuck_tasks(self, max_processing_hours: float = 1.0) -> int:
        """
        清理卡死的 processing 任务（超过 max_processing_hours 小时）。

        Returns:
            清理的任务数量
        """
        conn = self.conn
        # 标记卡死任务为 interrupted
        cutoff = time.time() - max_processing_hours * 3600
        cutoff_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(cutoff))
        cur = conn.execute(
            "UPDATE tasks SET status='interrupted', interrupted_at_reboot=1, "
            "updated_at=datetime('now') "
            "WHERE status='processing' AND created_at < ?",
            (cutoff_str,),
        )
        conn.commit()
        count = cur.rowcount
        if count > 0:
            logger.warning(f"Recovered {count} stuck tasks (marked as interrupted)")
        return count

    # ── 任务 CRUD ─────────────────────────────────────────────
    def create_task(
        self,
        task_id: str,
        engine: str,
        mode: str = "txt2img",
        prompt: str = "",
        negative_prompt: str = "",
        generation_config: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """创建新任务"""
        conn = self.conn
        conn.execute(
            "INSERT INTO tasks (task_id, engine, mode, prompt, negative_prompt, "
            "generation_config, tags, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
            (
                task_id, engine, mode, prompt, negative_prompt,
                json.dumps(generation_config or {}, ensure_ascii=False),
                json.dumps(tags or [], ensure_ascii=False),
            ),
        )
        conn.commit()

    def update_task_status(
        self,
        task_id: str,
        status: str,
        error: str = "",
        processing_time_s: float = 0,
        output_count: int = 0,
        thumbnail: str = "",
    ) -> None:
        """更新任务状态"""
        conn = self.conn
        conn.execute(
            "UPDATE tasks SET status=?, error=?, processing_time_s=?, "
            "output_count=?, thumbnail=?, updated_at=datetime('now') "
            "WHERE task_id=?",
            (status, error, processing_time_s, output_count, thumbnail, task_id),
        )
        conn.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """获取任务详情（含 generation_config + 三路输出）"""
        conn = self.conn
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if not row:
            return None
        task = dict(row)
        task["generation_config"] = json.loads(task.get("generation_config") or "{}")
        task["tags"] = json.loads(task.get("tags") or "[]")
        # 获取关联的输出
        outputs = conn.execute(
            "SELECT * FROM outputs WHERE task_id=? ORDER BY id", (task_id,)
        ).fetchall()
        task["outputs"] = [dict(o) for o in outputs]
        return task

    def list_tasks(
        self,
        status: str | None = None,
        engine: str | None = None,
        q: str | None = None,
        favorite: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        分页筛选任务列表。

        Returns:
            (tasks, total_count)
        """
        conn = self.conn
        where = []
        params: list = []

        if status:
            where.append("status=?")
            params.append(status)
        if engine:
            where.append("engine=?")
            params.append(engine)
        if favorite is not None:
            where.append("favorite=?")
            params.append(1 if favorite else 0)
        if q:
            where.append("tasks_fts MATCH ?")
            params.append(q)

        where_clause = " AND ".join(where) if where else "1=1"

        # 总数
        if q:
            count_sql = (
                f"SELECT COUNT(*) FROM tasks JOIN tasks_fts ON tasks.rowid=tasks_fts.rowid "
                f"WHERE {where_clause}"
            )
        else:
            count_sql = f"SELECT COUNT(*) FROM tasks WHERE {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # 分页
        offset = (page - 1) * page_size
        if q:
            sql = (
                f"SELECT t.* FROM tasks t JOIN tasks_fts ON t.rowid=tasks_fts.rowid "
                f"WHERE {where_clause} "
                f"ORDER BY t.created_at DESC LIMIT ? OFFSET ?"
            )
        else:
            sql = (
                f"SELECT * FROM tasks WHERE {where_clause} "
                f"ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
        rows = conn.execute(sql, params + [page_size, offset]).fetchall()
        tasks = []
        for r in rows:
            t = dict(r)
            t["generation_config"] = json.loads(t.get("generation_config") or "{}")
            t["tags"] = json.loads(t.get("tags") or "[]")
            tasks.append(t)
        return tasks, total

    def delete_tasks(self, task_ids: list[str]) -> int:
        """批量删除任务"""
        if not task_ids:
            return 0
        conn = self.conn
        placeholders = ",".join("?" * len(task_ids))
        cur = conn.execute(
            f"DELETE FROM tasks WHERE task_id IN ({placeholders})", task_ids
        )
        conn.commit()
        return cur.rowcount

    def set_favorite(self, task_id: str, favorite: bool) -> None:
        """设置/取消收藏"""
        conn = self.conn
        conn.execute(
            "UPDATE tasks SET favorite=?, updated_at=datetime('now') WHERE task_id=?",
            (1 if favorite else 0, task_id),
        )
        conn.commit()

    # ── 输出 CRUD ─────────────────────────────────────────────
    def add_output(
        self,
        task_id: str,
        path: str,
        format: str = "png",
        file_size: int = 0,
        width: int = 0,
        height: int = 0,
        seed: str = "",
        output_type: str = "original",
    ) -> None:
        """添加输出记录"""
        conn = self.conn
        conn.execute(
            "INSERT INTO outputs (task_id, path, format, file_size, width, height, seed, output_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, path, format, file_size, width, height, seed, output_type),
        )
        conn.commit()

    def list_outputs(
        self,
        output_type: str | None = None,
        favorite: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        分页查询输出文件（图库用）。
        JOIN tasks 获取 favorite 状态。
        """
        conn = self.conn
        where = []
        params: list = []
        if output_type:
            where.append("o.output_type=?")
            params.append(output_type)
        if favorite:
            where.append("t.favorite=1")

        where_clause = " AND ".join(where) if where else "1=1"
        total = conn.execute(
            f"SELECT COUNT(*) FROM outputs o JOIN tasks t ON o.task_id=t.task_id WHERE {where_clause}",
            params,
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT o.*, t.engine, t.prompt, t.favorite, t.created_at "
            f"FROM outputs o JOIN tasks t ON o.task_id=t.task_id "
            f"WHERE {where_clause} "
            f"ORDER BY o.created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
        return [dict(r) for r in rows], total

    def set_output_favorite(self, file_path: str, favorite: bool) -> None:
        """标记输出文件收藏"""
        conn = self.conn
        conn.execute(
            "UPDATE tasks SET favorite=? WHERE task_id IN "
            "(SELECT task_id FROM outputs WHERE path=?)",
            (1 if favorite else 0, file_path),
        )
        conn.commit()

    # ── 预设 CRUD ─────────────────────────────────────────────
    def create_preset(
        self,
        engine_name: str,
        name: str,
        config: dict[str, Any],
        thumbnail: str = "",
    ) -> int:
        """创建预设，返回 id"""
        conn = self.conn
        try:
            cur = conn.execute(
                "INSERT INTO presets (engine_name, name, config, thumbnail) "
                "VALUES (?, ?, ?, ?)",
                (engine_name, name, json.dumps(config, ensure_ascii=False), thumbnail),
            )
            conn.commit()
            return cur.lastrowid or 0
        except sqlite3.IntegrityError:
            raise ValueError(f"Preset '{name}' for engine '{engine_name}' already exists")

    def list_presets(self, engine_name: str | None = None) -> list[dict[str, Any]]:
        """列出预设"""
        conn = self.conn
        if engine_name:
            rows = conn.execute(
                "SELECT * FROM presets WHERE engine_name=? ORDER BY created_at DESC",
                (engine_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM presets ORDER BY created_at DESC"
            ).fetchall()
        result = []
        for r in rows:
            p = dict(r)
            p["config"] = json.loads(p.get("config") or "{}")
            result.append(p)
        return result

    def get_preset(self, preset_id: int) -> dict[str, Any] | None:
        """获取预设"""
        conn = self.conn
        row = conn.execute(
            "SELECT * FROM presets WHERE id=?", (preset_id,)
        ).fetchone()
        if not row:
            return None
        p = dict(row)
        p["config"] = json.loads(p.get("config") or "{}")
        return p

    def update_preset(
        self,
        preset_id: int,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        thumbnail: str | None = None,
    ) -> None:
        """更新预设"""
        conn = self.conn
        sets = []
        params: list = []
        if name is not None:
            sets.append("name=?")
            params.append(name)
        if config is not None:
            sets.append("config=?")
            params.append(json.dumps(config, ensure_ascii=False))
        if thumbnail is not None:
            sets.append("thumbnail=?")
            params.append(thumbnail)
        if not sets:
            return
        params.append(preset_id)
        conn.execute(
            f"UPDATE presets SET {', '.join(sets)} WHERE id=?", params
        )
        conn.commit()

    def delete_preset(self, preset_id: int) -> bool:
        """删除预设"""
        conn = self.conn
        cur = conn.execute("DELETE FROM presets WHERE id=?", (preset_id,))
        conn.commit()
        return cur.rowcount > 0

    def add_task_tags(self, task_ids: list[str], tags: list[str]) -> int:
        """批量给任务加标签"""
        if not task_ids or not tags:
            return 0
        conn = self.conn
        count = 0
        for tid in task_ids:
            row = conn.execute("SELECT tags FROM tasks WHERE task_id=?", (tid,)).fetchone()
            if not row:
                continue
            existing = json.loads(row["tags"] or "[]")
            merged = list(set(existing) | set(tags))
            conn.execute(
                "UPDATE tasks SET tags=?, updated_at=datetime('now') WHERE task_id=?",
                (json.dumps(merged, ensure_ascii=False), tid),
            )
            count += 1
        conn.commit()
        return count

    def cleanup_old_tasks(self, keep_days: int = 30, max_gb: float = 0) -> int:
        """
        清理超期任务（保留策略：天数/大小双阈值）。

        Args:
            keep_days: 保留天数（0 = 不按天数清理）
            max_gb: 输出目录最大 GB（0 = 不按大小清理）

        Returns:
            删除的任务数
        """
        conn = self.conn
        deleted = 0

        if keep_days > 0:
            cutoff = time.time() - keep_days * 86400
            cutoff_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(cutoff))
            cur = conn.execute(
                "DELETE FROM tasks WHERE created_at < ? AND favorite=0",
                (cutoff_str,),
            )
            deleted += cur.rowcount

        if max_gb > 0:
            # 按输出目录大小清理（删除最旧的非收藏任务）
            import shutil as _shutil
            outputs_dir = Path(self.db_path).parent.parent / "outputs"
            if outputs_dir.exists():
                try:
                    size_gb = _shutil.disk_usage(str(outputs_dir)).used / (1024**3)
                    if size_gb > max_gb:
                        # 删除最旧的非收藏任务
                        cur = conn.execute(
                            "DELETE FROM tasks WHERE favorite=0 ORDER BY created_at ASC LIMIT ?",
                            (max(1, int((size_gb - max_gb) * 10)),),
                        )
                        deleted += cur.rowcount
                except Exception:
                    pass

        conn.commit()
        if deleted > 0:
            logger.info(f"Cleanup: deleted {deleted} old tasks")
        return deleted

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
