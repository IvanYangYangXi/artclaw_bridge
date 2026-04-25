@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
title ArtClaw Tool Manager

set PORT=9876
set URL=http://localhost:%PORT%
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "TM_DIR=%ROOT_DIR%\subprojects\ArtClawToolManager"

:: ============================================================
:: 检查是否已在运行
:: ============================================================
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% == 0 (
    echo [Info] ArtClaw Tool Manager is already running.
    start "" "%URL%"
    exit /b 0
)

:: ============================================================
:: 检查环境
:: ============================================================
if not exist "%TM_DIR%\venv\Scripts\python.exe" (
    echo [Error] Virtual environment not found.
    echo         Please run install.bat first to set up the environment.
    pause
    exit /b 1
)

"%TM_DIR%\venv\Scripts\python.exe" -c "import fastapi" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [Error] Dependencies not installed.
    echo         Please run install.bat first to set up the environment.
    pause
    exit /b 1
)

if not exist "%TM_DIR%\src\web\dist\index.html" (
    echo [Error] Frontend not built.
    echo         Please run install.bat first to set up the environment.
    pause
    exit /b 1
)

:: ============================================================
:: 启动服务
:: ============================================================
cd /d "%TM_DIR%"
call "%TM_DIR%\venv\Scripts\activate.bat"

echo.
echo ==========================================
echo    ArtClaw Tool Manager
echo ==========================================
echo.
echo    %URL%       (App)
echo    %URL%/docs  (API Docs)
echo.
echo    Press Ctrl+C to stop
echo ==========================================
echo.

:: Open browser after 2s delay
start /b cmd /c "timeout /t 2 /nobreak >nul && start %URL%"

:: Run (blocking)
python -m src.server.main
