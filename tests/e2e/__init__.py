"""tests/e2e 包标记。

⚠️ 坑（2026-09-01）：tests/e2e/test_generation_flow.py 使用
``from .pages.home_page import HomePage`` 相对导入，若本文件缺失会报
``ImportError: attempted relative import with no known parent package``，
导致 6 个 POM 用例在收集后全部失败。请勿删除本文件。
"""
