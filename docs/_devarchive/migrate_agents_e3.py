# -*- coding: utf-8 -*-
"""Phase E3: slim AGENTS.md to <=50000 bytes by moving sections into docs/project/.

Move-only (no deletions, no fact rewrites).  build() is shared by the migrator
and the byte-preservation verifier, so both always agree on slicing semantics.
"""
import os

ROOT = r"C:\Users\Doro\Image_MultiModel"
SRC = os.path.join(ROOT, "AGENTS.md")
DOC = os.path.join(ROOT, "docs", "project")
NOTE = "\u201c\u672c\u6587\u7531 2026-08-27 \u5bb6\u65cf\u6cbb\u7406 E3 \u4ece AGENTS.md {n} \u79fb\u51fa\uff0c\u5185\u5bb9\u9010\u5b57\u4fdd\u7559\u201d"
LOCAL = "\uff08\u672c\u5730\u6587\u6863\uff0c\u672a\u968f\u4ed3\u5e93\u53d1\u5e03\uff09"


def _idx(lines, prefix, after=0):
    for i in range(after, len(lines)):
        if lines[i].startswith(prefix):
            return i
    raise KeyError(prefix)


def _joinblk(lines, a, b):
    return "".join(lines[a:b]).rstrip("\n") + "\n"


def _keep(lines, a, b):
    return "".join(lines[a:b])


def build(text):
    """Return (new_agents_text, {doc_name: content}) for the E3 refactor."""
    lines = text.splitlines(keepends=True)

    I3 = _idx(lines, "## 3. \u6a21\u5757\u8fb9\u754c")
    I4 = _idx(lines, "## 4. \u6d4b\u8bd5\u7ea6\u5b9a")
    I6 = _idx(lines, "## 6. \u6784\u5efa")
    I7 = _idx(lines, "## 7. \u4f9d\u8d56\u6ce8\u5165")
    I8 = _idx(lines, "## 8. i18n")
    I9 = _idx(lines, "## 9. Git")
    I10 = _idx(lines, "## 10. Pre-commit")
    I11 = _idx(lines, "## 11. \u5b89\u5168\u6ce8\u610f\u4e8b\u9879")
    I12 = _idx(lines, "## 12. MASTER_PLAN")
    I13 = _idx(lines, "## 13. \u5178\u578b AI")
    IREV = _idx(lines, "## \U0001f4cb \u81ea\u8fdb\u5316\u4fee\u8ba2\u8bb0\u5f55\u8868")
    IDASH13 = _idx(lines, "---", after=I13)
    IROAD = _idx(lines, "## \u8def\u7ebf\u56fe\u843d\u5730")
    IARCH = _idx(lines, "## \U0001f4c2 \u6587\u4ef6\u5f52\u6863")
    IFREE = _idx(lines, "## \U0001f6ab \u7981\u533a\u76ee\u5f55")
    IC3 = _idx(lines, "### \U0001f534 5 \u6761\u786c\u7ea6\u675f")
    PREV3 = [i for i in range(IC3, I4) if lines[i].startswith("---")][0]
    I41 = _idx(lines, "### 4.1")
    I45END = [i for i in range(I41, I6) if lines[i].startswith("---")][0]

    # --- moved content (verbatim) ------------------------------------
    m13 = _joinblk(lines, I13, IDASH13)
    m3 = _joinblk(lines, I3 + 1, IC3)
    m4 = _joinblk(lines, I41, I45END)
    m6 = _joinblk(lines, I6, I7)
    m8 = _joinblk(lines, I8, I9)
    m11 = _joinblk(lines, I11, I12)

    # the original "## N. 标题" header line is replaced by the new "# 标题"
    # (规则：'## N. 标题' 改为新文档 '# 标题'), so drop it from the body.
    def without_h2(s):
        first, _, rest = s.partition("\n")
        if first.startswith("## "):
            return rest.lstrip("\n")
        return s

    m13 = without_h2(m13)
    m6 = without_h2(m6)
    m8 = without_h2(m8)
    m11 = without_h2(m11)

    # --- kept content -------------------------------------------------
    kA = _keep(lines, 0, I3)
    kC = _keep(lines, IFREE, I4)
    kE = _keep(lines, I45END, I6)
    k7 = _joinblk(lines, I7, I8)
    k9 = _joinblk(lines, I9, I10)
    k10 = _joinblk(lines, I10, I11)
    k12 = _joinblk(lines, I12, I13)
    kI = _keep(lines, IDASH13, IROAD)
    kJ = _keep(lines, IROAD, IARCH)
    kK = _keep(lines, IARCH, len(lines))
    k3_head = _keep(lines, I3, I3 + 1)
    k3_hard = _joinblk(lines, IC3, PREV3)
    k4_head = _keep(lines, I4, I41)

    h6 = "## 6. \u6784\u5efa / \u542f\u52a8\u547d\u4ee4\n"
    h8 = "## 8. i18n \u591a\u8bed\u8a00\u89c4\u8303\uff085 \u79cd\u8bed\u8a00\uff1a\u7b80\u4e2d / \u7e41\u4e2d / \u82f1 / \u65e5 / \u97e9\uff09\n"
    h11 = "## 11. \u5b89\u5168\u6ce8\u610f\u4e8b\u9879\n"
    h13 = "## 13. \u5178\u578b AI \u5f00\u53d1\u573a\u666f SOP\uff08\u7167\u7740\u505a\uff0c\u5c11\u8e29\u5751\uff09\n"

    a3 = ("> \U0001f4c2 \u5b8c\u6574\u76ee\u5f55\u6811\uff08\u5404\u6a21\u5757\u6587\u4ef6\u804c\u8d23 / \u4fee\u6539\u6ce8\u610f\u4e8b\u9879\uff09"
          "\u5df2\u79fb\u5165 [MODULE_MAP.md](docs/project/MODULE_MAP.md)" + LOCAL + "\u3002\n"
          "> \u672c\u8282\u4fdd\u7559 5 \u6761\u786c\u7ea6\u675f\u539f\u6587\u3002\n")
    a4 = ("> \U0001f4c2 6 \u5c42\u6d4b\u8bd5\u5206\u5c42\u8868 / \u547d\u540d\u89c4\u8303 / \u8986\u76d6\u7387\u8def\u7ebf\u56fe / \u6d4b\u8bd5\u547d\u4ee4 / "
          "\u5b89\u5168\u6d4b\u8bd5\u8981\u6c42\u5df2\u79fb\u5165 [TEST_LAYERS.md](docs/project/TEST_LAYERS.md)" + LOCAL + "\u3002\n"
          "> \u95e8\u69db\uff1a`pyproject.toml \u2192 [tool.coverage.report] fail_under = 75`\uff08CI \u5f3a\u5236\uff0c\u4f4e\u4e8e "
          "75% \u76f4\u63a5\u963b\u65ad PR\uff09\u3002\n")
    a6 = ("> \U0001f4c2 \u4e00\u952e\u542f\u52a8 / \u624b\u52a8\u542f\u52a8 / \u542f\u52a8\u540e\u9a8c\u8bc1\u8be6\u8868\u5df2\u79fb\u5165 "
          "[BUILD_COMMANDS.md](docs/project/BUILD_COMMANDS.md)" + LOCAL + "\u3002\n"
          "> \u5e38\u7528\uff1a`python app/clean_launch.py`\uff08\u63a8\u8350\u5165\u53e3\uff0c\u76d1\u542c http://127.0.0.1:8288\uff09\u3002\n")
    a8 = ("> \U0001f4c2 \u7ffb\u8bd1\u673a\u5236 / \u4e09\u5c42 fallback \u94fe / \u65b0\u589e key 6 \u6b65\u6d41\u7a0b\u5df2\u79fb\u5165 "
          "[I18N_STANDARD.md](docs/project/I18N_STANDARD.md)" + LOCAL + "\u3002\n")
    a11 = ("> \U0001f4c2 \u5b89\u5168\u6ce8\u610f\u4e8b\u9879\u5168\u6587\uff086 \u6761\uff09\u5df2\u79fb\u5165 "
           "[SECURITY_NOTES.md](docs/project/SECURITY_NOTES.md)" + LOCAL + "\u3002\n")
    a13 = ("> \U0001f4c2 \u5b8c\u6574\u5185\u5bb9\uff08SOP-1~SOP-5 + Known Gotchas \u8868\uff09\u5df2\u79fb\u5165 "
           "[AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)" + LOCAL + "\u3002\n"
           "> \u65b0 SOP / \u65b0\u5751\u4e00\u5f8b\u8ffd\u52a0\u5230\u8be5\u6587\u4ef6\uff08\u94c1\u5f8b #2/#3\uff09\u3002\n")

    blocks = [kA, k3_head, "\n", a3, k3_hard, kC, k4_head, "\n", a4, kE,
              h6, a6, k7,
              h8, a8, k9, k10,
              h11, a11, k12,
              h13, a13,
              kI, kJ, kK]
    new_agents = "".join(blocks)

    refs = [
        ("\u8ffd\u52a0\u4e00\u6761\u5230\u7b2c 14 \u8282\u300c\u5e38\u89c1\u9677\u9631\uff08Known Gotchas\uff09\u300d",
         "\u8ffd\u52a0\u4e00\u6761\u5230 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)" + LOCAL + " \u7684 Known Gotchas \u8868"),
        ("\u8ffd\u52a0\u5230\u7b2c 13 \u8282\u300c\u5178\u578b AI \u5f00\u53d1\u573a\u666f SOP\u300d",
         "\u8ffd\u52a0\u5230 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)" + LOCAL),
        ("\u662f\u5426\u5df2\u8ffd\u52a0\u5230\u7b2c 14 \u8282 Known Gotchas\uff1f",
         "\u662f\u5426\u5df2\u8ffd\u52a0\u5230 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)" + LOCAL + " \u7684 Known Gotchas \u8868\uff1f"),
        ("\uff08\u89c1\u7b2c 8 \u8282 i18n \u89c4\u8303\uff09",
         "\uff08\u89c1 [I18N_STANDARD.md](docs/project/I18N_STANDARD.md)" + LOCAL + "\uff09"),
        ("\u89c1\u7b2c 14 \u8282\u9677\u9631\uff09",
         "\u89c1 [AI_DEV_SOPS.md](docs/project/AI_DEV_SOPS.md)" + LOCAL + " Known Gotchas\uff09"),
    ]
    for old, new in refs:
        c = new_agents.count(old)
        assert c <= 1, f"non-unique ref: {old[:30]} x{c}"
        if c:
            new_agents = new_agents.replace(old, new)

    titles = {
        "MODULE_MAP.md": ("\u6a21\u5757\u8fb9\u754c\uff08\u5b8c\u6574\u76ee\u5f55\u6811\uff09", m3, "\u00a73"),
        "TEST_LAYERS.md": ("\u6d4b\u8bd5\u7ea6\u5b9a\u8be6\u8868\uff086 \u5c42\u6d4b\u8bd5\u5206\u5c42\u7b49\uff09", m4, "\u00a74"),
        "BUILD_COMMANDS.md": ("\u6784\u5efa / \u542f\u52a8\u547d\u4ee4", m6, "\u00a76"),
        "I18N_STANDARD.md": ("i18n \u591a\u8bed\u8a00\u89c4\u8303\uff085 \u79cd\u8bed\u8a00\uff1a\u7b80\u4e2d / \u7e41\u4e2d / \u82f1 / \u65e5 / \u97e9\uff09", m8, "\u00a78"),
        "SECURITY_NOTES.md": ("\u5b89\u5168\u6ce8\u610f\u4e8b\u9879", m11, "\u00a711"),
        "AI_DEV_SOPS.md": ("\u5178\u578b AI \u5f00\u53d1\u573a\u666f SOP\uff08\u7167\u7740\u505a\uff0c\u5c11\u8e29\u5751\uff09", m13, "\u00a713"),
    }
    docs = {n: NOTE.format(n=sec) + "\n\n# " + title + "\n\n" + body
            for n, (title, body, sec) in titles.items()}
    return new_agents, docs


if __name__ == "__main__":
    """Re-run from the pre-E3 backup; write SRC and docs/project files."""
    BACKUP = os.path.join(ROOT, "docs", "_devarchive", "AGENTS_v1.26_before_E3_backup.md")
    text = open(BACKUP, encoding="utf-8").read()
    new_agents, docs = build(text)
    os.makedirs(DOC, exist_ok=True)
    with open(SRC, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(new_agents)
    for name, content in docs.items():
        with open(os.path.join(DOC, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    print("AGENTS.md -> %d bytes" % os.path.getsize(SRC))
    for name in sorted(docs):
        print(f"{name:24} {os.path.getsize(os.path.join(DOC, name)):>8} bytes")
    print("OK" if os.path.getsize(SRC) <= 50000 else "OVER BUDGET")