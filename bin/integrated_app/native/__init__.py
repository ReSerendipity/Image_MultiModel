"""
native/__init__.py — 原生进程内引擎包

复用本地 Comfy 源码（comfy_kernel）在同一进程内直接推理，
不依赖外部 ComfyUI 进程。仅做推理，禁止出现 FastAPI / SQLite 代码。

Phase 1：骨架 + Z-Image Turbo 文生图 PoC（核心出图链路）。
"""

__version__ = "0.1.0"
