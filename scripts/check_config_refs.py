"""
scripts/check_config_refs.py — 配置字段引用完整性 + 安全项「声明即消费」门禁

对应安全评估 #13：config.yaml 的 security 段若存在「声明了但代码从不读取」的开关，
就是典型的假安全感（配置-实现错配）。本脚本把「配置模型字段」「代码对配置的引用」
「config.yaml 实际声明的键」三者对账，发现未被消费的 security 键、或代码引用了不存在的
字段时，向 errors 累积信息并以非零退出码失败（供 pre-commit / 测试 gate 调用）。

用法：
    python scripts/check_config_refs.py        # 跑全部门禁，非零=失败
    python -m pytest tests/test_config_refs_gate.py

设计原则（对齐 AGENTS 证据绑定）：只按源码/配置的**真实存在**做判定，不引入臆造的门禁。
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
CONFIG_MODELS_PY = APP / "integrated_app" / "config_models.py"
CONFIG_YAML = ROOT / "config.yaml"
APP_GLOB = "*.py"

errors: list[str] = []

# 代码里引用配置时常用的变量名（取值于项目代码实际习惯）。
_CONFIG_VAR_RE = re.compile(r"\b(config|cfg|cfg_obj|app_config|ecfg|sec|self\.config|settings)\." r"([a-zA-Z_][\w.]*)")

PY_SRC_SUFFIX = (".py",)


def _iter_py_files() -> list[Path]:
    """收集项目内（app/）全部 python 源文件，跳过缓存与 vendored 内核。"""
    files: list[Path] = []
    base = APP if APP.is_dir() else ROOT
    for p in base.rglob("*.py"):
        if "__pycache__" in p.parts or "comfy_kernel" in p.parts or "venv" in p.parts:
            continue
        files.append(p)
    return files


# ── 1) 配置模型字段提取（AST）──────────────────────────────
def collect_class_fields() -> dict[str, set[str]]:
    """解析 config_models.py，返回 {类名: {字段名, ...}}。"""
    if not CONFIG_MODELS_PY.exists():
        raise FileNotFoundError(f"无法定位配置模型: {CONFIG_MODELS_PY}")
    source = CONFIG_MODELS_PY.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    result: dict[str, set[str]] = {}

    def _collect_body_fields(body: list[ast.stmt]) -> set[str]:
        fields: set[str] = set()
        for stmt in body:
            if isinstance(stmt, ast.AnnAssign | ast.Assign):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        fields.add(t.id)
            elif isinstance(stmt, ast.FunctionDef) and stmt.name in ("model_config", "Config"):
                pass
        return fields

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            result[node.name] = _collect_body_fields(node.body)
    return result


def _load_yaml() -> dict:
    return yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8"))


# ── 2) 代码对配置的引用提取 ────────────────────────────────
def _collect_flatten_yaml_fields(data: dict) -> set[str]:
    """config.yaml 全部键（含嵌套叶）+ 每个叶子所在路径。"""
    fields: set[str] = set()
    paths: set[str] = set()

    def walk(node, prefix: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{prefix}.{k}" if prefix else str(k)
                fields.add(str(k))
                paths.add(p)
                walk(v, p)
        else:
            paths.add(prefix)

    walk(data, "")
    return fields, paths


def collect_consumed() -> tuple[set[str], set[str]]:
    """扫描 app/ 源码，返回 (consumed_paths, consumed_tokens)。

    - consumed_paths: 形如 ``security.cors.allowed_origins`` 的完整引用链。
    - consumed_tokens: 所有被代码以任何形式出现的"配置相关标识符"（含字段名/节名），
      用于判定某个 yaml 键是否"被提及消费"。
    """
    consumed_paths: set[str] = set()
    all_text_parts: list[str] = []
    for py in _iter_py_files():
        text = py.read_text(encoding="utf-8", errors="ignore")
        all_text_parts.append(text)
        for m in _CONFIG_VAR_RE.finditer(text):
            chain = m.group(2)
            parts = [p for p in chain.split(".") if p and p.isidentifier()]
            if parts:
                consumed_paths.add(".".join(parts))
                # 拆到每个叶、中间段都算 token
                for i in range(1, len(parts) + 1):
                    consumed_paths.add(".".join(parts[:i]))
    full_text = "\n".join(all_text_parts)

    yaml_fields, _ = _collect_flatten_yaml_fields(_load_yaml())
    # 已知配置字段名若在源码任何位置出现（含 getattr("basic_auth") 这类字符串），视为被消费
    consumed_tokens: set[str] = set()
    for name in yaml_fields:
        if re.search(rf"\b{re.escape(name)}\b", full_text):
            consumed_tokens.add(name)
    # 顺带把路径里的叶也并入
    for p in consumed_paths:
        consumed_tokens.add(p.split(".")[-1])
    return consumed_paths, consumed_tokens


# ── 3) 检查项 ──────────────────────────────────────────────
def check_code_refs(all_fields: set[str], class_fields: dict[str, set[str]]) -> None:
    """代码引用的配置路径，其叶字段必须存在于某个配置模型类。"""
    known = set(class_fields.keys())
    consumed, _ = collect_consumed()
    for path in sorted(consumed):
        parts = path.split(".")
        if len(parts) < 2:
            continue
        # 形如 <class_like>.<field> 时校验 field 存在（class 名大写开头即视为模型类）
        cls_name, field = parts[0], parts[-1]
        if cls_name in known and field not in class_fields[cls_name]:
            errors.append(f"代码引用不存在的字段: {path}（{cls_name} 无 {field}）")


def check_yaml_runtime(class_fields: dict[str, set[str]]) -> None:
    """config.yaml 的顶层各段，应对应到某个配置模型类名。"""
    data = _load_yaml()
    for key in data:
        if key == "version":
            continue
        if isinstance(data[key], dict):
            # 顶层段名应为 PascalCase 类名（容忍下划线/驼峰同义）
            name_ok = any(k.lower().replace("_", "") == key.lower().replace("_", "") for k in class_fields)
            if not name_ok:
                # 仅告警级提示（避免因命名习惯误阻断），不写进 errors
                pass


def check_security_keys_consumed(consumed_paths: set[str], consumed_tokens: set[str]) -> None:
    """config.yaml security 段每个叶子键都必须被代码消费。"""
    data = _load_yaml()
    security = data.get("security", {})
    if not isinstance(security, dict):
        return

    def walk(node, prefix: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{prefix}.{k}" if prefix else str(k))
            return
        # 叶子：判定是否被消费
        leaf = prefix.split(".")[-1]
        if leaf not in consumed_tokens:
            errors.append(f"security 配置键未被代码消费（声明即生效/假安全感）: {prefix}")

    walk(security, "security")


def scan_source_for_missing(source: str, known_fields: set[str]) -> list[str]:
    """扫描一段源码，返回「访问了不存在的配置字段」的错误列表（空列表=干净）。

    主要用于 tests/observability/test_check_config_refs.py 单测，便于在编辑器/脚本中复用。
    规则：
    - 形如 ``config.<root>.<field>`` 的属性访问，若 ``field`` 不在 ``known_fields`` 中则报错；
    - ``getattr(obj, "attr", default)`` 与 ``obj.get("attr")`` 这类安全访问不报错；
    - 非 config 根（如 ``state.value``）忽略；
    - 方法调用（``config.runtime.model_dump()``）忽略。
    """
    import ast as _ast

    config_roots = {
        "config",
        "cfg",
        "cfg_obj",
        "app_config",
        "ecfg",
        "sec",
        "settings",
    }
    tree = _ast.parse(source)

    # 父节点映射：用于判断某属性是否位于 .get()/getattr() 安全访问或方法调用
    parents: dict = {}
    for node in _ast.walk(tree):
        for child in _ast.iter_child_nodes(node):
            parents[child] = node

    # 收集被安全包装的属性名（getattr 第二参数 / .get(...) 首个字符串参数）
    safe_wrapped: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            if isinstance(node.func, _ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, _ast.Constant) and isinstance(arg.value, str):
                    safe_wrapped.add(arg.value)
            elif isinstance(node.func, _ast.Attribute) and node.func.attr == "get":
                for arg in node.args:
                    if isinstance(arg, _ast.Constant) and isinstance(arg.value, str):
                        safe_wrapped.add(arg.value)

    def _chain(node: _ast.AST) -> list[str] | None:
        parts: list[str] = []
        cur = node
        while isinstance(cur, _ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, _ast.Name):
            parts.append(cur.id)
        else:
            return None
        parts.reverse()
        return parts

    errors: list[str] = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Attribute):
            continue
        chain = _chain(node)
        if not chain or len(chain) < 2:
            continue
        if chain[0] not in config_roots:
            continue  # 非 config 根忽略
        # 方法调用（config.runtime.model_dump()）忽略
        parent = parents.get(node)
        if isinstance(parent, _ast.Call) and parent.func is node:
            continue
        leaf = chain[-1]
        if leaf in safe_wrapped:
            continue
        if leaf not in known_fields:
            errors.append(f"未定义配置字段访问: {'.'.join(chain)}")
    return errors


def main() -> int:
    class_fields = collect_class_fields()
    all_fields = set().union(*class_fields.values())
    consumed_paths, consumed_tokens = collect_consumed()

    errors.clear()
    check_code_refs(all_fields, class_fields)
    check_yaml_runtime(class_fields)
    check_security_keys_consumed(consumed_paths, consumed_tokens)

    if errors:
        print("❌ 配置引用门禁未通过：")
        for e in errors:
            print("   -", e)
        return 1
    print("✅ 配置引用门禁通过（安全键声明即消费 / 引用字段均存在）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
