@echo off
setlocal

set PORT=9876
set URL=http://localhost:%PORT%

:: Check if server is already running on port 9876
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% == 0 (
    echo ArtClaw Tool Manager already running, opening browser...
    start "" "%URL%"
    exit /b 0
)

:: Not running - start the server
echo Starting ArtClaw Tool Manager...
cd /d "%~dp0"

:: Activate venv if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: Launch server in background, then open browser after a short delay
start "" /b python -m src.server.main

:: Wait for server to start (up to 10 seconds)
echo Waiting for server to start...
set /a attempts=0
:wait_loop
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% == 0 goto server_ready
set /a attempts+=1
if %attempts% lss 10 goto wait_loop
echo Warning: Server may not have started yet, opening browser anyway...

:server_ready
echo Opening browser...
start "" "%URL%"
endlocal
