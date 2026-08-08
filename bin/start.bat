@echo off
chcp 65001 >nul
title Image MultiModel

echo ========================================
echo   Image MultiModel - Starting...
echo ========================================

cd /d "%~dp0\.."

python bin\clean_launch.py

pause
