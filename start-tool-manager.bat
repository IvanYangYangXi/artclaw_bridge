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
:: 检查 Python
:: ============================================================
where python >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [Error] Python not found. Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

:: ============================================================
:: 自动初始化
:: ============================================================
call :ensure_setup
if !ERRORLEVEL! NEQ 0 (
    echo [Error] Setup failed. See errors above.
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
goto :eof

:: ============================================================
:: ensure_setup — 检查并自动完成首次安装
:: ============================================================
:ensure_setup

:: ----- 1. venv -----
if not exist "%TM_DIR%\venv\Scripts\python.exe" (
    echo.
    echo [Setup] Creating Python virtual environment...
    python -m venv "%TM_DIR%\venv"
    if !ERRORLEVEL! NEQ 0 (
        echo [Error] Failed to create venv.
        exit /b 1
    )
    echo [OK] venv created.
)

:: ----- 2. pip install (check by sentinel package: fastapi) -----
"%TM_DIR%\venv\Scripts\python.exe" -c "import fastapi" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [Setup] Installing dependencies...
    "%TM_DIR%\venv\Scripts\pip.exe" install -r "%TM_DIR%\requirements.txt" -q
    if !ERRORLEVEL! NEQ 0 (
        echo [Error] pip install failed.
        exit /b 1
    )
    echo [OK] Dependencies installed.
)

:: ----- 3. npm build (check if dist/ exists) -----
if not exist "%TM_DIR%\src\web\dist\index.html" (
    where npm >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo.
        echo [Setup] Building frontend...
        pushd "%TM_DIR%\src\web"
        if not exist "node_modules" (
            call npm install -q
        )
        call npm run build
        popd
        if exist "%TM_DIR%\src\web\dist\index.html" (
            echo [OK] Frontend built.
        ) else (
            echo [Warning] Frontend build may have failed. Web UI might not work.
        )
    ) else (
        echo [Warning] npm not found, skipping frontend build. Web UI might not work.
    )
)

:: ----- 4. ~/.artclaw/config.json (project_root) -----
"%TM_DIR%\venv\Scripts\python.exe" -c "import json,os,sys;p=os.path.expanduser('~/.artclaw/config.json');d=json.load(open(p,'r',encoding='utf-8')) if os.path.exists(p) else {};r=d.get('project_root','');sys.exit(0 if r and os.path.isdir(r) else 1)" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [Setup] Initializing ArtClaw config...

    :: ROOT_DIR is artclaw_bridge root (where this bat lives)
    if exist "%ROOT_DIR%\core\bridge_config.py" (
        "%TM_DIR%\venv\Scripts\python.exe" -c "import json,os,sys;r=sys.argv[1];p=os.path.expanduser('~/.artclaw/config.json');os.makedirs(os.path.dirname(p),exist_ok=True);d=json.load(open(p,'r',encoding='utf-8')) if os.path.exists(p) else {};d['project_root']=r;open(p,'w',encoding='utf-8').write(json.dumps(d,indent=2,ensure_ascii=False))" "%ROOT_DIR%"
        if !ERRORLEVEL! EQU 0 (
            echo [OK] config.json updated: project_root = %ROOT_DIR%
        ) else (
            echo [Error] Failed to write config.json
            exit /b 1
        )
    ) else (
        echo [Error] Cannot verify artclaw_bridge root directory.
        echo         Expected core\bridge_config.py at: %ROOT_DIR%
        echo         Please run install.bat or manually set project_root in ~/.artclaw/config.json
        exit /b 1
    )
)

echo.
echo [OK] All prerequisites verified.
exit /b 0
