"""test_auth_bootstrap.py — 最小 api_token 鉴权 bootstrap 单测（2026-09-04 安全评估 M3）"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from integrated_app.config_models import APITokenConfig
from integrated_app.security.auth_bootstrap import TOKEN_FILE_NAME, ensure_api_token


def _cfg(tmp_path: Path, *, bootstrap: bool, enabled: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        project_root=str(tmp_path),
        security=SimpleNamespace(
            api_token=APITokenConfig(bootstrap=bootstrap, enabled=enabled)
        ),
    )


def test_bootstrap_disabled_is_noop(tmp_path: Path) -> None:
    """off-by-default：bootstrap=false 时零行为改变"""
    cfg = _cfg(tmp_path, bootstrap=False)
    assert ensure_api_token(cfg) is None
    assert cfg.security.api_token.enabled is False
    assert not (tmp_path / TOKEN_FILE_NAME).exists()


def test_bootstrap_enabled_already_is_noop(tmp_path: Path) -> None:
    """已显式启用鉴权时尊重现有配置，不覆盖"""
    cfg = _cfg(tmp_path, bootstrap=True, enabled=True)
    cfg.security.api_token.tokens = ["existing"]
    assert ensure_api_token(cfg) is None
    assert cfg.security.api_token.tokens == ["existing"]


def test_bootstrap_generates_and_enables(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, bootstrap=True)
    token = ensure_api_token(cfg)
    assert token
    assert cfg.security.api_token.enabled is True
    assert cfg.security.api_token.tokens == [token]
    tf = tmp_path / TOKEN_FILE_NAME
    assert tf.exists()
    assert tf.read_text(encoding="utf-8").strip() == token


def test_bootstrap_reuses_token_across_calls(tmp_path: Path) -> None:
    """token 跨重启稳定：已有 .api_token 时复用，不重新生成"""
    first = ensure_api_token(_cfg(tmp_path, bootstrap=True))
    second = ensure_api_token(_cfg(tmp_path, bootstrap=True))
    assert first == second


def test_bootstrap_no_security_section(tmp_path: Path) -> None:
    """异常形态（无 security 段）下安全返回 None，不抛异常"""
    assert ensure_api_token(SimpleNamespace(project_root=str(tmp_path))) is None
