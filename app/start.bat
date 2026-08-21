@echo off
chcp 65001 >nul
title Image MultiModel

echo ========================================
echo   Image MultiModel - Starting...
echo ========================================

cd /d "%~dp0\.."

REM ── 检测 WinPython ──────────────────────────────
set WPY_EXE=
if exist "%~dp0..\WPy64-312101\python\python.exe" (
    set WPY_EXE=%~dp0..\WPy64-312101\python\python.exe
) else if exist "C:\Users\Doro\SeedVR2-lite\WPy64-312101\python\python.exe" (
    set WPY_EXE=C:\Users\Doro\SeedVR2-lite\WPy64-312101\python\python.exe
) else (
    echo [WARN] WinPython not found, using system Python
    set WPY_EXE=python
)

echo [INFO] Using Python: %WPY_EXE%
"%WPY_EXE%" app\clean_launch.py

pause
