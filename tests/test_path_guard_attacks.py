"""
test_path_guard_attacks.py — 14 类路径攻击全拒绝

对应 AUDIT_REPORT_2.0 Y2: test_path_guard_attacks.py
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

from integrated_app.security.path_guard import PathGuard, PathGuardError


@pytest.fixture
def guard():
    return PathGuard(
        allowed_base_dirs=["outputs/", "data/", "workflows/", "pretrained_models/"],
        project_root=str(PROJECT_ROOT),
    )


class TestPathGuardAttacks:
    """14 类路径攻击全拒绝"""

    # 1. 简单路径穿越
    def test_double_dot(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("../../../etc/passwd")

    # 2. 双重路径穿越
    def test_double_double_dot(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/../../../etc/passwd")

    # 3. 绝对路径到系统目录
    def test_absolute_system_path(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("C:/Windows/System32/config/SAM")

    # 4. 绝对路径到用户目录
    def test_absolute_user_path(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("C:/Users/admin/.ssh/id_rsa")

    # 5. Unix 绝对路径
    def test_unix_absolute_path(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("/etc/shadow")

    # 6. 空字节注入
    def test_null_byte_injection(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/test\0../../../etc/passwd")

    # 7. URL 编码路径穿越
    def test_url_encoded_traversal(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/%2e%2e/%2e%2e/etc/passwd")

    # 8. 混合斜杠
    def test_mixed_slashes(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("outputs\\..\\..\\..\\etc\\passwd")

    # 9. 超长路径
    def test_long_path(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/" + "A" * 500 + "/../../../etc/passwd")

    # 10. 当前目录 + 穿越
    def test_dot_dot_slash(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("./../../../etc/passwd")

    # 11. outputs 下穿越
    def test_outputs_traversal(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/../../etc/passwd")

    # 12. data 下穿越到敏感文件
    def test_data_traversal(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("data/../../.ssh/id_rsa")

    # 13. 符号链接路径（模拟）
    def test_symlink_like_path(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/../data/../../etc/passwd")

    # 14. Windows 保留设备名
    def test_windows_reserved_name(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("CON")

    # 正向验证：合法路径通过
    def test_valid_outputs_path(self, guard):
        path = guard.resolve("outputs/test.png")
        assert str(path).endswith("test.png")

    def test_valid_data_path(self, guard):
        path = guard.resolve("data/history.db")
        assert str(path).endswith("history.db")

    def test_valid_workflows_path(self, guard):
        path = guard.resolve("workflows/test.json")
        assert str(path).endswith("test.json")

    def test_is_safe_true_for_valid(self, guard):
        assert guard.is_safe("outputs/test.png") is True

    def test_is_safe_false_for_attack(self, guard):
        assert guard.is_safe("../../../etc/passwd") is False

    def test_safe_join_valid(self, guard):
        path = guard.safe_join("outputs/", "subdir", "test.png")
        assert str(path).endswith("test.png")
