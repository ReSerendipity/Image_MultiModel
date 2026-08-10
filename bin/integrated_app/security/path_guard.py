"""
security/path_guard.py — 路径穿越守卫

对应 MASTER_PLAN §4 / 附录 D1: PathGuard
对应 PRD §8: 路径穿越守卫，所有文件 I/O 必须在 allowed_base_dirs 中
"""

from __future__ import annotations

import urllib.parse
from pathlib import Path


class PathGuardError(PermissionError):
    """路径穿越安全异常"""
    pass


class PathGuard:
    """
    路径穿越守卫：所有文件 I/O 必须在白名单目录中。

    用法:
        guard = PathGuard(["outputs/", "data/", "workflows/"], project_root="/path/to/project")
        safe_path = guard.resolve("outputs/2026-01-01/test.png")  # OK
        guard.resolve("../../../etc/passwd")  # raises PathGuardError
    """

    def __init__(
        self,
        allowed_base_dirs: list[str],
        project_root: str | Path,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.allowed_bases: list[Path] = []
        for d in allowed_base_dirs:
            p = Path(d)
            if not p.is_absolute():
                p = self.project_root / p
            self.allowed_bases.append(p.resolve())

    def resolve(self, user_path: str | Path, base_dir: str | None = None) -> Path:
        """
        解析用户提供的路径，确保在白名单目录内。

        Args:
            user_path: 用户输入的路径（可能是相对路径）
            base_dir: 指定的基础目录 key（如 "outputs/"），None 时检查所有白名单

        Returns:
            解析后的绝对路径

        Raises:
            PathGuardError: 如果路径不在白名单内
        """
        # 解码 URL 编码（防止 %2e%2e 绕过）
        if isinstance(user_path, str):
            decoded = urllib.parse.unquote(user_path)
        else:
            decoded = str(user_path)
        # 空字节注入：任何平台都直接拒绝（Windows 下 Path.resolve 会抛
        # OSError 变体，Linux 下抛 ValueError: embedded null character
        # —— 统一在入口拦截，避免平台行为差异）
        if "\x00" in decoded:
            raise PathGuardError(f"Path '{user_path}' contains null byte")
        p = Path(decoded)

        # 如果是相对路径，相对于 base_dir 或 project_root 解析
        if not p.is_absolute():
            if base_dir:
                bp = Path(base_dir)
                if not bp.is_absolute():
                    bp = self.project_root / bp
                p = bp / p
            else:
                p = self.project_root / p

        # 规范化路径（消除 .., ., symlinks）
        try:
            resolved = p.resolve()
        except (OSError, RuntimeError):
            resolved = p.absolute()

        # 检查是否在白名单目录内
        if base_dir:
            bp = Path(base_dir)
            if not bp.is_absolute():
                bp = self.project_root / bp
            bp = bp.resolve()
            if not self._is_within(resolved, bp):
                raise PathGuardError(
                    f"Path '{user_path}' is outside allowed base dir '{base_dir}'"
                )
        else:
            # 检查所有白名单目录
            allowed = any(self._is_within(resolved, base) for base in self.allowed_bases)
            if not allowed:
                raise PathGuardError(
                    f"Path '{user_path}' is outside all allowed base dirs"
                )

        return resolved

    def ensure_dir(self, user_path: str | Path) -> Path:
        """
        解析路径并确保目录存在。

        Returns:
            解析后的安全目录路径
        """
        p = self.resolve(user_path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def safe_join(self, base_dir: str, *parts: str) -> Path:
        """
        安全拼接路径（相对于 base_dir 解析）。

        Args:
            base_dir: 白名单基础目录 key
            *parts: 路径组成部分

        Returns:
            解析后的绝对路径
        """
        bp = Path(base_dir)
        if not bp.is_absolute():
            bp = self.project_root / bp
        joined = bp.joinpath(*parts)
        return self.resolve(str(joined), base_dir=base_dir)

    def _is_within(self, path: Path, base: Path) -> bool:
        """检查 path 是否在 base 目录内"""
        try:
            path.relative_to(base)
            return True
        except ValueError:
            return False

    def is_safe(self, user_path: str | Path) -> bool:
        """检查路径是否安全（不抛异常）"""
        try:
            self.resolve(user_path)
            return True
        except PathGuardError:
            return False
