@echo off
chcp 65001 >nul
title Image MultiModel

echo ========================================
echo   Image MultiModel - Starting...
echo ========================================

cd /d "%~dp0\.."

REM ── 检测 Python ─────────────────────────────
set WPY_EXE=
if not "%IMM_PYTHON%"=="" (
    set WPY_EXE=%IMM_PYTHON%
) else if exist "%~dp0..\WPy64-312101\python\python.exe" (
    set WPY_EXE=%~dp0..\WPy64-312101\python\python.exe
) else (
    echo [WARN] WinPython not found, using system Python
    set WPY_EXE=python
)

echo [INFO] Using Python: %WPY_EXE%
"%WPY_EXE%" app\clean_launch.py

pause
