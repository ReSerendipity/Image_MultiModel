#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""最终 UI 更新 - 仅添加 CSS 和简化引擎菜单"""
from pathlib import Path

HTML_FILE = Path(__file__).resolve().parent.parent / "app" / "integrated_app" / "static" / "index.html"

def main():
    # 读取原始字节
    raw = HTML_FILE.read_bytes()
    
    # 尝试 UTF-8，失败则用 GBK
    try:
        html = raw.decode('utf-8')
        encoding = 'utf-8'
    except UnicodeDecodeError:
        html = raw.decode('gbk')
        encoding = 'gbk'
    
    original = html
    
    # 1. 添加 CSS（英文注释，安全）
    css = '\n/* Button labels */\n.btn-label{margin-left:4px;font-size:11px;font-weight:500;color:var(--ink-soft);vertical-align:middle}'
    target = '.icon-btn:hover{background:var(--surface-2);color:var(--ink)}'
    if target in html and '.btn-label{' not in html:
        html = html.replace(target, target + css)
        print("✓ 已添加 CSS")
    
    # 2. 简化引擎菜单（删除 buildEngModeRow 调用）
    old = "if(menu){menu.innerHTML='';buildEngModeRow(menu);}"
    new = "if(menu){menu.innerHTML='';}"
    if old in html:
        html = html.replace(old, new)
        print("✓ 已简化引擎菜单（移除全部/Native 过滤）")
    
    # 保存
    if html != original:
        HTML_FILE.write_text(html, encoding=encoding)
        print(f"\n✓ 完成！使用 {encoding} 编码保存")
        
        # 更新完整性清单
        import subprocess
        subprocess.run(["python", "scripts/generate_integrity_manifest.py"], check=True)
    else:
        print("\n⚠ 未检测到变化")

if __name__ == "__main__":
    main()
