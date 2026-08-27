# -*- coding: utf-8 -*-
"""Final check: revision-log region identical to backup."""
import hashlib
import io

new = io.open(r"C:\Users\Doro\Image_MultiModel\AGENTS.md", encoding="utf-8").read().splitlines(keepends=True)
bak = io.open(r"C:\Users\Doro\Image_MultiModel\docs\_devarchive\AGENTS_v1.26_before_E3_backup.md", encoding="utf-8").read().splitlines(keepends=True)


def h(x):
    return hashlib.sha256("".join(x).encode("utf-8")).hexdigest()


i = [j for j, l in enumerate(new) if l.startswith("## \U0001f4cb \u81ea\u8fdb\u5316")][0]
j = [k for k, l in enumerate(bak) if l.startswith("## \U0001f4cb \u81ea\u8fdb\u5316")][0]
same = h(new[i:]) == h(bak[j:])
print("revision region identical to backup:", same)
if not same:
    import difflib
    print("\n".join(list(difflib.unified_diff(bak[j:], new[i:], "backup", "new", lineterm="", n=0))[:40]))