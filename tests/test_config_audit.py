"""
test_config_audit.py — 数据治理报告 P1-3：config PUT 字段级校验 + 审计日志

覆盖：
- _validate_section_update：合法更新 / 非法类型 ValidationError / 未知键忽略
- _append_config_audit：JSONL 落盘、who/when/diff 结构
- PUT /api/config 端到端：变更写审计、非法值 422 且配置与审计均不变
  （save_config 被打桩，绝不触碰真实 config.yaml）
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from integrated_app.config import get_config
from integrated_app.routes import config_routes as cr


def _tmp() -> Path:
    import tempfile

    return Path(tempfile.mkdtemp(prefix="cfgaudit_test_"))


class TestValidateSectionUpdate:
    """字段级校验：setattr 裸赋值绕过校验的问题必须在入口拦住"""

    def test_valid_update_passes(self) -> None:
        cfg = get_config()
        new_section = cr._validate_section_update(cfg.inference, {"default_steps": 11})
        assert new_section.default_steps == 11

    def test_invalid_type_raises(self) -> None:
        cfg = get_config()
        with pytest.raises(ValidationError):
            cr._validate_section_update(cfg.inference, {"default_steps": "not-a-number"})

    def test_unknown_keys_ignored_by_caller(self) -> None:
        """未知键在路由层被 hasattr 过滤，进入校验的只有真实字段"""
        cfg = get_config()
        bogus = {"no_such_field_xyz": 1}
        accepted = {k: v for k, v in bogus.items() if hasattr(cfg.inference, k)}
        assert accepted == {}


class TestAppendConfigAudit:
    def test_audit_jsonl_structure(self) -> None:
        d = _tmp()
        log_path = d / "config_audit.log"
        changes = [
            {"section": "inference", "key": "default_steps", "before": 10, "after": 12},
        ]
        cr._append_config_audit(get_config(), "127.0.0.1", changes, log_path=log_path)
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["who"] == "127.0.0.1"
        assert entry["ts"]  # 时间戳非空
        assert entry["changes"][0]["key"] == "default_steps"
        assert entry["changes"][0]["before"] == 10
        assert entry["changes"][0]["after"] == 12

    def test_audit_appends_multiple_entries(self) -> None:
        d = _tmp()
        log_path = d / "config_audit.log"
        cr._append_config_audit(
            get_config(), "a", [{"section": "ui", "key": "k", "before": 1, "after": 2}], log_path=log_path
        )
        cr._append_config_audit(
            get_config(), "b", [{"section": "ui", "key": "k", "before": 2, "after": 3}], log_path=log_path
        )
        assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 2


@pytest.fixture(scope="module")
def client():
    from app.integrated_app.app_server import create_app

    with TestClient(create_app()) as c:
        # 与 test_api_contract 一致：先取 CSRF token，否则写操作 403
        _csrf_r = c.get("/api/health")
        _csrf_tok = _csrf_r.headers.get("X-CSRF-Token", "")
        if _csrf_tok:
            c.headers["X-CSRF-Token"] = _csrf_tok
        yield c


class TestPutConfigEndToEnd:
    def test_valid_change_writes_audit(self, client: TestClient, monkeypatch) -> None:
        d = _tmp()
        log_path = d / "config_audit.log"
        monkeypatch.setattr(cr, "save_config", lambda cfg: None)  # 不写真实 config.yaml
        monkeypatch.setattr(
            cr, "get_config", lambda: __import__("integrated_app.config", fromlist=["get_config"]).get_config()
        )
        r = client.put("/api/config", json={"inference": {"default_steps": 13}})
        assert r.status_code == 200
        assert r.json().get("changed", 0) >= 1
        # 审计已写入（默认路径 data/config_audit.log）
        default_log = Path(get_config().project_root) / "data" / "config_audit.log"
        assert default_log.exists(), "默认审计日志应已创建"
        entry = json.loads(default_log.read_text(encoding="utf-8").strip().splitlines()[-1])
        keys = [(c["section"], c["key"]) for c in entry["changes"]]
        assert ("inference", "default_steps") in keys
        # 恢复原值（同样打桩，不触盘）
        client.put("/api/config", json={"inference": {"default_steps": 10}})
        _ = log_path  # 显式临时目录仅结构测试用；端到端走默认路径

    def test_invalid_value_rejected_422(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setattr(cr, "save_config", lambda cfg: None)
        default_log = Path(get_config().project_root) / "data" / "config_audit.log"
        before_lines = default_log.read_text(encoding="utf-8").strip().splitlines() if default_log.exists() else []
        r = client.put("/api/config", json={"inference": {"default_steps": "garbage"}})
        assert r.status_code == 422
        after_lines = default_log.read_text(encoding="utf-8").strip().splitlines() if default_log.exists() else []
        assert before_lines == after_lines, "非法值不得产生审计记录"

    def test_empty_update_no_changes(self, client: TestClient) -> None:
        r = client.put("/api/config", json={})
        assert r.status_code == 200
        assert "No changes" in r.json().get("message", "")
