@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
title ArtClaw Tool Manager - Restart

set PORT=9876
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

echo.
echo ==========================================
echo    ArtClaw Tool Manager - Restart
echo ==========================================
echo.

:: ============================================================
:: Step 1: 停止已运行的实例
:: ============================================================
echo [1/2] Stopping existing instance on port %PORT%...

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    echo       Killing PID %%p
    taskkill /PID %%p /F >nul 2>&1
)

:: 等待端口释放
set WAIT=0
:wait_loop
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% == 0 (
    set /a WAIT+=1
    if !WAIT! GEQ 10 (
        echo [Warn] Port %PORT% still in use after 5s, proceeding anyway...
        goto :start
    )
    timeout /t 1 /nobreak >nul
    goto :wait_loop
)
echo       Stopped.

:: ============================================================
:: Step 2: 重新启动
:: ============================================================
:start
echo [2/2] Starting Tool Manager...
echo.

call "%ROOT_DIR%\start-tool-manager.bat"
