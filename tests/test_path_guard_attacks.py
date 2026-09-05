"""
test_path_guard_attacks.py — 14 类路径攻击全拒绝

对应 AUDIT_REPORT_2.0 Y2: test_path_guard_attacks.py
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from integrated_app.security.path_guard import PathGuard, PathGuardError


@pytest.fixture
def guard():
    return PathGuard(
        allowed_base_dirs=["outputs/", "data/", "workflows/", "model/"],
        project_root=str(PROJECT_ROOT),
    )


class TestPathGuardAttacks:
    """14 类路径攻击全拒绝"""

    # 1. 简单路径穿越
    @pytest.mark.smoke
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

    # 15. 跨平台归一化：反斜杠在任意平台都被视为分隔符
    def test_normalize_backslash(self):
        from integrated_app.security.path_guard import _normalize_platform_path

        assert _normalize_platform_path(r"..\..\..\etc\passwd", "nt") == "../../../etc/passwd"
        assert _normalize_platform_path(r"..\..\..\etc\passwd", "posix") == "../../../etc/passwd"

    # 16. 跨平台归一化：盘符路径在非 Windows 平台挂根（超出白名单后被拒绝）
    def test_normalize_drive_prefix(self):
        from integrated_app.security.path_guard import _normalize_platform_path

        assert _normalize_platform_path("C:/Windows/System32/config/SAM", "posix") == "/C:/Windows/System32/config/SAM"
        assert _normalize_platform_path("C:/Windows/System32/config/SAM", "nt") == "C:/Windows/System32/config/SAM"

    # 17. 盘符路径（含反斜杠变体）在非 Windows 语义下经 resolve 被拒绝
    def test_drive_letter_path_rejected_via_resolve(self, guard):
        from integrated_app.security.path_guard import _normalize_platform_path

        normalized = _normalize_platform_path(r"C:\Windows\System32\config\SAM", "posix")
        with pytest.raises(PathGuardError):
            guard.resolve(normalized)
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


class TestWindowsPathVariants:
    """Windows 特有变形（2026-09-04 测试体系评估 P2 补齐）

    语义以 2026-09-04 在 Windows（os.name == 'nt'）实测为准：
    - UNC / 8.3 短名：一律 PathGuardError（fail-closed）；
    - 尾部点/空格、NTFS ADS（::$DATA）、".. ." 类伪父目录段：
      允许解析，但结果必须仍被钳制在白名单目录内（无逃逸）。

    断言设计为跨平台稳定（nt 实测 + posix 语义推演），
    若后续改动 _normalize_platform_path / resolve 导致行为变化，
    本组用例会先红，作为安全回归哨兵。
    """

    # ---- 必须拒绝（fail-closed）----

    def test_unc_share_rejected(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve(r"\\server\share\secret.png")

    def test_unc_admin_share_rejected(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve(r"\\localhost\c$\Windows\win.ini")

    def test_unc_escaped_backslash_rejected(self, guard):
        # 正斜杠归一化后的 UNC（\\ → /），语义等价，仍须拒绝
        with pytest.raises(PathGuardError):
            guard.resolve("//server/share/secret.png")

    def test_shortname_83_relative_rejected(self, guard):
        # outputs 目录的 8.3 短名别名：宁可误拒（fail-closed），不得放行
        with pytest.raises(PathGuardError):
            guard.resolve("OUTPUTS~1/test.png")

    def test_shortname_83_absolute_rejected(self, guard):
        with pytest.raises(PathGuardError):
            guard.resolve("C:/PROGRA~1/secret.txt")

    def test_trailing_dot_space_traversal_rejected(self, guard):
        # Windows 会剥掉尾部 " . ."，但父目录逃逸部分必须先被拦截
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/../../../Windows/win.ini. . ")

    # ---- 允许解析，但必须钳制在白名单内（无逃逸）----

    def test_trailing_dot_stays_inside_whitelist(self, guard):
        resolved = guard.resolve("outputs/test.png.")
        assert resolved.is_relative_to(guard.project_root / "outputs")

    def test_trailing_space_stays_inside_whitelist(self, guard):
        resolved = guard.resolve("outputs/test.png ")
        assert resolved.is_relative_to(guard.project_root / "outputs")

    def test_ads_stream_stays_inside_whitelist(self, guard):
        # NTFS 备用数据流：不是穿越，但需确认不会解析到白名单之外
        resolved = guard.resolve("outputs/test.png::$DATA")
        assert resolved.is_relative_to(guard.project_root / "outputs")

    def test_dot_space_segments_stay_inside_whitelist(self, guard):
        # ".. ." 不是父目录（尾随空格使其成为普通目录名），不得借此逃逸
        resolved = guard.resolve("outputs/.. ./. ./. ./Windows/win.ini")
        assert resolved.is_relative_to(guard.project_root / "outputs")


class TestSymlinkLoopFailClosed:
    """符号链接环：resolve 失败 fail-closed，或解析结果落在白名单外即拒绝
    （2026-09-04 安全评估 L6：旧实现 resolve 失败回退未解析 absolute()，
    丢失符号链接解析依据）"""

    def _make_loop(self, tmp_path: Path) -> None:
        import os

        a = tmp_path / "loop_a"
        b = tmp_path / "loop_b"
        a.mkdir()
        b.mkdir()
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(b), str(a / "self"))  # a/self -> b
            _winapi.CreateJunction(str(a), str(b / "back"))  # b/back -> a
        else:
            (a / "self").symlink_to(b, target_is_directory=True)
            (b / "back").symlink_to(a, target_is_directory=True)

    def test_symlink_loop_rejected(self, tmp_path):

        self._make_loop(tmp_path)
        guard = PathGuard(["outputs/"], project_root=str(tmp_path))
        # POSIX：resolve() 抛 RuntimeError → fail-closed PathGuardError；
        # Windows：junction 环解析到环外真实路径 → 白名单拒绝。
        with pytest.raises(PathGuardError):
            guard.resolve("loop_a/self/back/self/x.png")

    def test_resolve_failure_fails_closed_not_fallback(self, tmp_path, monkeypatch):
        """resolve() 抛 OSError 时必须拒绝（不得回退未解析的 absolute()）"""
        from pathlib import Path as _P

        guard = PathGuard(["outputs/"], project_root=str(tmp_path))

        def _boom(_self, **_kw):
            raise OSError("simulated resolve failure")

        monkeypatch.setattr(_P, "resolve", _boom)
        with pytest.raises(PathGuardError):
            guard.resolve("outputs/ok.png")
