@echo off
chcp 65001 >nul
title Image MultiModel - Install

echo ========================================
echo   Image MultiModel - Installing Dependencies
echo ========================================

cd /d "%~dp0\.."

echo [1/3] Installing Python packages...
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn pydantic pyyaml aiohttp websockets python-multipart aiofiles pytest pytest-asyncio

echo.
echo [2/3] Creating data directories...
if not exist "data" mkdir "data"
if not exist "data\presets" mkdir "data\presets"
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\cache" mkdir "data\cache"
if not exist "outputs" mkdir "outputs"
if not exist "logs" mkdir "logs"

echo.
echo [3/3] Done!
echo.
echo To start the application, run: bin\start.bat
pause
