"""
render_pages.py — 渲染 Jinja2 页面模板为静态 HTML，供前端 smoke 测试读取。

Image MultiModel 前端由 FastAPI + Jinja2 服务端渲染（app/integrated_app/templates/）。
jsdom smoke 测试无法执行 Jinja2，因此先由本脚本把页面模板渲染到
tests/frontend/_rendered/，smoke.js 再读取。

用法: python scripts/render_pages.py
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "app" / "integrated_app" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "frontend" / "_rendered"

PAGES = ["index"]


def _i18n_t(key: str, lang: str = "zh", default: str | None = None, **kw) -> str:
    """模板内 _() 翻译函数占位（对齐 app_server.py 的模板全局）。"""
    return key if default is None else default


def main() -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["_"] = _i18n_t
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx = {"lang": "zh-CN", "theme": "dark"}
    for name in PAGES:
        html = env.get_template(f"{name}.html").render(**ctx)
        (OUTPUT_DIR / f"{name}.html").write_text(html, encoding="utf-8")
        print(f"[OK] 渲染 {name}.html -> tests/frontend/_rendered/")


if __name__ == "__main__":
    main()
