# -*- coding: utf-8 -*-
"""Phase E3 byte-preservation verification.

Uses the same build() as the migrator (single source of truth):
  expected AGENTS.md  == build(backup_text)
  expected docs       == build(backup_text) docs
  actual files must equal expected, byte-for-byte (LF-normalized).
"""
import os
import sys

sys.path.insert(0, r"C:\Users\Doro\Image_MultiModel\docs\_devarchive")
from migrate_agents_e3 import build, NOTE, LOCAL  # noqa: E402

ROOT = r"C:\Users\Doro\Image_MultiModel"
BACKUP = os.path.join(ROOT, "docs", "_devarchive", "AGENTS_v1.26_before_E3_backup.md")
NEW = os.path.join(ROOT, "AGENTS.md")
DOC = os.path.join(ROOT, "docs", "project")

backup = open(BACKUP, encoding="utf-8").read()
exp_agents, exp_docs = build(backup)

cur_agents = open(NEW, encoding="utf-8").read()
ok = True

if cur_agents != exp_agents:
    ok = False
    print("AGENTS.md MISMATCH")
    import difflib
    d = list(difflib.unified_diff(exp_agents.split("\n"), cur_agents.split("\n"),
                                  "expected", "actual", lineterm="", n=1))
    print("\n".join(d[:80]))
else:
    print("AGENTS.md recompose == actual: OK")

for name, expected in sorted(exp_docs.items()):
    actual = open(os.path.join(DOC, name), encoding="utf-8").read()
    if actual != expected:
        ok = False
        print(f"{name} MISMATCH (expected {len(expected)} got {len(actual)})")
    else:
        print(f"{name}: OK ({len(actual)} bytes)")

# --- verbatim matrix vs backup (moved slices = H2 header + new body) ---------
bl = backup.splitlines(keepends=True)


def bdx(prefix, after=0):
    for i in range(after, len(bl)):
        if bl[i].startswith(prefix):
            return i
    raise KeyError(prefix)


def jb(a, b):
    return "".join(bl[a:b]).rstrip("\n") + "\n"


I3 = bdx("## 3. \u6a21\u5757\u8fb9\u754c")
I4 = bdx("## 4. \u6d4b\u8bd5\u7ea6\u5b9a")
I6 = bdx("## 6. \u6784\u5efa")
I7 = bdx("## 7. \u4f9d\u8d56\u6ce8\u5165")
I8 = bdx("## 8. i18n")
I9 = bdx("## 9. Git")
I11 = bdx("## 11. \u5b89\u5168\u6ce8\u610f\u4e8b\u9879")
I12 = bdx("## 12. MASTER_PLAN")
I13 = bdx("## 13. \u5178\u578b AI")
IDASH13 = bdx("---", after=I13)
IC3 = bdx("### \U0001f534 5 \u6761\u786c\u7ea6\u675f")
I41 = bdx("### 4.1")
I45END = [i for i in range(I41, I6) if bl[i].startswith("---")][0]

orig_slices = {
    "MODULE_MAP.md": jb(I3 + 1, IC3),               # tree (no H2 inside)
    "TEST_LAYERS.md": jb(I41, I45END),              # 4.1..4.5 (no H2 inside)
    "BUILD_COMMANDS.md": jb(I6, I7),                # §6 (H2 first line)
    "I18N_STANDARD.md": jb(I8, I9),                 # §8 (H2 first line)
    "SECURITY_NOTES.md": jb(I11, I12),              # §11 (H2 first line)
    "AI_DEV_SOPS.md": jb(I13, IDASH13),             # §13 (H2 first line)
}
for name, seg in orig_slices.items():
    content = open(os.path.join(DOC, name), encoding="utf-8").read()
    lines_c = content.splitlines(keepends=True)
    t_idx = next(i for i, l in enumerate(lines_c) if l.startswith("# "))
    body = "".join(lines_c[t_idx + 1:])
    if body.startswith("\n"):            # the blank line of "\n\n" after title
        body = body[1:]
    first, _, rest = seg.partition("\n")
    if first.startswith("## "):
        expected_body = rest.lstrip("\n")
    else:
        expected_body = seg
    if body != expected_body:
        ok = False
        print(f"VERBATIM FAIL {name}: body != stripped original slice")
    else:
        print(f"verbatim {name}: OK (title line replaced only)")

# structural spot checks on anchors / notes
sec14 = "\u7b2c 14 \u8282"
sec13 = "\u7b2c 13 \u8282"
notes_ok = True
for name, content in exp_docs.items():
    sec_of = {"MODULE_MAP.md": "\u00a73", "TEST_LAYERS.md": "\u00a74", "BUILD_COMMANDS.md": "\u00a76",
              "I18N_STANDARD.md": "\u00a78", "SECURITY_NOTES.md": "\u00a711", "AI_DEV_SOPS.md": "\u00a713"}
    if NOTE.format(n=sec_of[name]) not in content:
        notes_ok = False
        print("note missing in", name)
checks = [
    ("derived-from notes in docs", notes_ok),
    ("locals marked", cur_agents.count(LOCAL) >= 6),
    ("old \u00a7 numbers replaced", sec14 not in cur_agents and sec13 not in cur_agents),
]
for name, okk in checks:
    print(name, "OK" if okk else "FAIL")
    if not okk:
        ok = False

print("\nVERDICT:", "PASS" if ok else "FAIL")