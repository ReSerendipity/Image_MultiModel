#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断 index.html 的 mojibake 编码问题"""
from pathlib import Path

f = Path(__file__).resolve().parent.parent / "bin" / "integrated_app" / "static" / "index.html"
raw = f.read_bytes()

# 当前文件按 UTF-8 解码（能成功但中文乱码）
text_utf8 = raw.decode("utf-8", errors="replace")

# 找代表性乱码行
line = None
for l in text_utf8.splitlines():
    if "setOpen" in l:
        line = l
        break
print("原始行 repr:", repr(line[:120]))
print()

# mojibake 修复路径测试集
paths = [
    ("gbk->utf8", lambda s: s.encode("gbk", errors="replace").decode("utf-8", errors="replace")),
    ("utf8->gbk", lambda s: s.encode("utf-8", errors="replace").decode("gbk", errors="replace")),
    ("latin1->utf8", lambda s: s.encode("latin1", errors="replace").decode("utf-8", errors="replace")),
    ("gbk->gb18030", lambda s: s.encode("gbk", errors="replace").decode("gb18030", errors="replace")),
]

for name, fn in paths:
    try:
        fixed = fn(line)
        print(f"[{name}] -> {repr(fixed[:120])}")
    except Exception as e:
        print(f"[{name}] 失败: {e}")