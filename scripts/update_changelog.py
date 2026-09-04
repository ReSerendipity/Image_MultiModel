#!/usr/bin/env python
"""更新 CHANGELOG.md 添加新版本条目"""

from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def main():
    content = CHANGELOG.read_text(encoding="utf-8")
    new_entry = """## [1.2.1] - 2026-08-14

### Changed

- **前端 UI 优化**：顶部栏图标按钮添加文字标签（主题、颜色、字体、关于、设置、模型、语言），移除冗余的「全部 / Native」引擎过滤选项，引擎选择简化为直接显示引擎列表

---

"""
    # 在 "## [1.2.0]" 之前插入新条目
    content = content.replace("## [1.2.0]", new_entry + "## [1.2.0]")
    CHANGELOG.write_text(content, encoding="utf-8")
    print("✓ 已更新 CHANGELOG.md")


if __name__ == "__main__":
    main()
