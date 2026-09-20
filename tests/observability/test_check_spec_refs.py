"""
tests/observability/test_check_spec_refs.py — 文档路径引用「仓内自检」门禁单测

覆盖 better-harness 修复：check_spec_refs 不再依赖仓外 .spec_audit、干净 checkout 也能
产出真实 clean/gap 结论。用 tmp_path 构造隔离仓库，直接调用纯函数 run_self_check，
断言：

- 合法嵌套路径 / 相对链接存在 → clean（gaps==0）；
- 人为植入失效路径 → 报 gap（gap_count>0，非零）；
- 条件/计划表述（若本仓存在…）与构建产物（*/target/）不作失效判定；
- 端口号 / 引擎 key / 裸文件名 / 模块路径 / 非根相对单段目录不被误判为路径引用。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = Path(__file__).resolve().parents[2] / "scripts" / "check_spec_refs.py"


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("check_spec_refs", _SPEC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _mkfile(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("stub\n", encoding="utf-8")


def _agents(root: Path, body: str) -> Path:
    doc = root / "AGENTS.md"
    doc.write_text("# fixture\n\n" + body, encoding="utf-8")
    return doc


def test_clean_when_refs_exist(mod, tmp_path):
    _mkfile(tmp_path, "app/clean_launch.py")
    _mkfile(tmp_path, "docs/agents/SOPS.md")
    doc = _agents(tmp_path, "- entry `app/clean_launch.py`\n- doc [SOP](docs/agents/SOPS.md)\n")
    checked, skipped, gaps, lines = mod.run_self_check(tmp_path, [doc], strict=True)
    assert gaps == 0, lines
    assert checked >= 2


def test_planted_phantom_is_gap_and_nonzero(mod, tmp_path):
    _mkfile(tmp_path, "app/clean_launch.py")
    tmp_path.joinpath("docs/agents").mkdir(parents=True, exist_ok=True)
    doc = _agents(tmp_path, "- ok `app/clean_launch.py`\n- broken `docs/agents/DOES_NOT_EXIST_XYZ.md`\n")
    checked, skipped, gaps, lines = mod.run_self_check(tmp_path, [doc], strict=True)
    assert gaps >= 1
    assert any("DOES_NOT_EXIST_XYZ.md" in ln for ln in lines)


def test_conditional_reference_is_skipped_not_gap(mod, tmp_path):
    tmp_path.joinpath("docs").mkdir(parents=True, exist_ok=True)
    # 指向不存在的 docs/official_spec.md，但行内带「若本仓存在/当前本仓无」限定语 → 不判失效
    doc = _agents(tmp_path, "2. `docs/official_spec.md`（若本仓存在；当前本仓无 official_spec）\n")
    checked, skipped, gaps, lines = mod.run_self_check(tmp_path, [doc], strict=True)
    assert gaps == 0, lines
    assert skipped >= 1


def test_build_artifact_reference_is_skipped(mod, tmp_path):
    tmp_path.joinpath("desktop/src-tauri").mkdir(parents=True, exist_ok=True)
    # 滚动清理铁律下 target/ 本就不该存在：应 skip 而非 gap
    doc = _agents(tmp_path, "- clean `desktop/src-tauri/target/` 后重建\n")
    checked, skipped, gaps, lines = mod.run_self_check(tmp_path, [doc], strict=True)
    assert gaps == 0, lines


def test_non_path_tokens_are_not_flagged(mod, tmp_path):
    tmp_path.joinpath("docs/agents").mkdir(parents=True, exist_ok=True)
    body = (
        "- port `8288`\n"
        "- engine key `z_image_turbo_native`\n"
        "- bare name `integrity_manifest.json`\n"
        "- module `sys.path` and `comfy.sd`\n"
        "- subdir `comfy/` `comfy_extras/`\n"
        "- nested runtime `runtime/model/data/logs`\n"
    )
    doc = _agents(tmp_path, body)
    checked, skipped, gaps, lines = mod.run_self_check(tmp_path, [doc], strict=True)
    # 以上均非「仓内相对路径引用」，不应产生任何 gap
    assert gaps == 0, lines


def test_glob_dir_reference_resolves(mod, tmp_path):
    tmp_path.joinpath("comfy_kernel").mkdir(parents=True, exist_ok=True)
    tmp_path.joinpath("app").mkdir(parents=True, exist_ok=True)
    doc = _agents(tmp_path, "- kernel `comfy_kernel/**`\n- code `app/**`\n")
    checked, skipped, gaps, lines = mod.run_self_check(tmp_path, [doc], strict=True)
    assert gaps == 0, lines
    assert checked >= 2


def test_looks_pathlike_rules(mod):
    children = {"app", "docs", "scripts", "LICENSE"}
    ok = mod._looks_pathlike
    assert ok("app/clean_launch.py", is_link=False, children=children)
    assert ok("docs/agents/SOPS.md", is_link=False, children=children)
    assert ok("LICENSE", is_link=False, children=children)
    assert ok("docs/GPL_COMPLIANCE.md", is_link=True, children=set())  # 链接更宽松
    # 反例：端口 / 引擎 key / 裸文件名 / 模块路径 / 非根相对单段或首段目录
    assert not ok("8288", is_link=False, children=children)
    assert not ok("z_image_turbo_native", is_link=False, children=children)
    assert not ok("integrity_manifest.json", is_link=False, children=children)
    assert not ok("sys.path", is_link=False, children=children)
    assert not ok("comfy/", is_link=False, children=children)
    assert not ok("runtime/model/data/logs", is_link=False, children=children)


def test_enhancement_absent_when_no_auditor(mod, tmp_path):
    # tmp_path 无 .spec_audit，其父目录亦无 → 增强层不可用（available=False）
    available, rc = mod._family_enhancement(tmp_path)
    assert available is False
    assert rc == 0
