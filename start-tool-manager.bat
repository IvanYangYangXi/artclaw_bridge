@echo off
chcp 65001 >nul
title ArtClaw Tool Manager

echo ==========================================
echo    ArtClaw Tool Manager
echo ==========================================
echo.

cd /d "%~dp0subprojects\ArtClawToolManager"

:: Check if server is already running on port 9876
netstat -ano | findstr ":9876 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [Info] ArtClaw Tool Manager is already running.
    echo [Info] Opening browser...
    start http://localhost:9876
    exit /b 0
)

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [Error] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

:: Setup venv + deps
if not exist "venv" (
    echo [1/3] Creating virtual environment ...
    python -m venv venv
)
call venv\Scripts\activate.bat

echo [1/3] Installing dependencies ...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [Error] Failed to install dependencies
    pause
    exit /b 1
)

:: Start backend (serves frontend static files too)
echo [2/3] Starting server ...
echo.
echo    http://localhost:9876       (App)
echo    http://localhost:9876/docs  (API Docs)
echo.
echo ==========================================
echo    Press Ctrl+C to stop
echo ==========================================
echo.

:: Open browser after 2s delay
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:9876"

:: Run (blocking)
python -m src.server.main
