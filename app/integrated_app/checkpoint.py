"""
checkpoint.py — 断点续跑（PRD §2.7.2）

batch>500 时每 100 张落盘 checkpoint（已完成 prompt×seed 组合 + 剩余队列），
应用崩溃重启后可从 checkpoint 恢复未完成任务。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TaskCheckpoint:
    """
    断点续跑管理器。

    存储格式: data/checkpoints/{task_id}.json
    {
        "task_id": "...",
        "engine": "...",
        "total": 32,
        "completed": 16,
        "completed_items": [{"prompt": "...", "seed": 42}, ...],
        "remaining": [{"prompt": "...", "seed": 99}, ...],
        "config": {GenerationConfig dict},
        "updated_at": 1234567890
    }
    """

    def __init__(self, checkpoint_dir: str = "data/checkpoints") -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        return self.checkpoint_dir / f"{task_id}.json"

    def save(
        self,
        task_id: str,
        engine: str,
        total: int,
        completed_items: list[dict[str, Any]],
        remaining: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> None:
        """保存/更新 checkpoint"""
        data = {
            "task_id": task_id,
            "engine": engine,
            "total": total,
            "completed": len(completed_items),
            "completed_items": completed_items,
            "remaining": remaining,
            "config": config,
            "updated_at": time.time(),
        }
        path = self._path(task_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"Checkpoint saved: {task_id} ({len(completed_items)}/{total})")

    def load(self, task_id: str) -> dict[str, Any] | None:
        """加载 checkpoint"""
        path = self._path(task_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"Checkpoint loaded: {task_id} ({data.get('completed', 0)}/{data.get('total', 0)})")
            return data
        except Exception as e:
            logger.warning(f"Failed to load checkpoint {task_id}: {e}")
            return None

    def delete(self, task_id: str) -> bool:
        """删除 checkpoint（任务完成后）"""
        path = self._path(task_id)
        if path.exists():
            path.unlink()
            logger.debug(f"Checkpoint deleted: {task_id}")
            return True
        return False

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """列出所有未完成 checkpoint"""
        results = []
        for p in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("completed", 0) < data.get("total", 0):
                    results.append(data)
            except Exception:
                continue
        return results

    def should_checkpoint(self, completed_count: int, checkpoint_every: int = 100) -> bool:
        """判断是否需要写 checkpoint"""
        return completed_count > 0 and completed_count % checkpoint_every == 0
