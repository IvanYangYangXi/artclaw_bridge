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
:: 自动环境检查与安装
:: ============================================================

:: ---- 1. 检查 Python 环境 ----
where python >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo ============================================================
    echo    [错误] 未检测到 Python 环境
    echo ============================================================
    echo.
    echo  本工具需要 Python 3.10+ 环境。
    echo  请先安装 Python: https://www.python.org/downloads/
    echo  安装时请勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

:: ---- 2. 自动创建虚拟环境 ----
if not exist "%TM_DIR%\venv\Scripts\python.exe" (
    echo.
    echo [安装] 虚拟环境不存在，正在创建...
    echo.
    python -m venv "%TM_DIR%\venv"
    if !ERRORLEVEL! NEQ 0 (
        echo [错误] 虚拟环境创建失败，请检查 Python 安装。
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建。
)

:: ---- 3. 自动安装 Python 依赖 ----
"%TM_DIR%\venv\Scripts\python.exe" -c "import fastapi" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [安装] Python 依赖未安装，正在安装...
    echo.

    :: 安装顶层 requirements.txt
    if exist "%TM_DIR%\requirements.txt" (
        echo   [pip] 安装 %TM_DIR%\requirements.txt ...
        "%TM_DIR%\venv\Scripts\python.exe" -m pip install -r "%TM_DIR%\requirements.txt" --quiet
        if !ERRORLEVEL! NEQ 0 (
            echo [警告] pip install (顶层) 部分失败，继续尝试 server 依赖...
        ) else (
            echo [OK] 顶层依赖安装完成。
        )
    )

    :: 安装 server 子目录 requirements.txt
    if exist "%TM_DIR%\src\server\requirements.txt" (
        echo   [pip] 安装 %TM_DIR%\src\server\requirements.txt ...
        "%TM_DIR%\venv\Scripts\python.exe" -m pip install -r "%TM_DIR%\src\server\requirements.txt" --quiet
        if !ERRORLEVEL! NEQ 0 (
            echo [警告] pip install (server) 部分失败，继续检查...
        ) else (
            echo [OK] server 依赖安装完成。
        )
    )

    :: 最终验证
    "%TM_DIR%\venv\Scripts\python.exe" -c "import fastapi" >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo [错误] Python 依赖安装失败，请手动运行 install.bat 并选择选项 T。
        pause
        exit /b 1
    )
    echo [OK] Python 依赖检查通过。
)

:: ---- 4. 自动构建前端 ----
if not exist "%TM_DIR%\src\web\dist\index.html" (
    echo.
    echo [构建] 前端文件未构建，正在构建...

    where node >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo [错误] 未检测到 Node.js，无法构建前端。
        echo        请安装 Node.js 18+: https://nodejs.org/
        pause
        exit /b 1
    )

    set "TM_WEB_DIR=%TM_DIR%\src\web"
    if exist "%TM_WEB_DIR%\package.json" (
        pushd "%TM_WEB_DIR%"

        echo   [npm] 安装前端依赖...
        call npm install --silent
        if !ERRORLEVEL! EQU 0 (
            echo   [npm] 构建前端静态文件...
            call npm run build
            if !ERRORLEVEL! EQU 0 (
                echo [OK] 前端构建完成。
            ) else (
                echo [警告] 前端构建失败，可稍后手动执行:
                echo         cd %TM_WEB_DIR% ^&^& npm run build
            )
        ) else (
            echo [警告] npm install 失败，跳过前端构建。
        )

        popd
    ) else (
        echo [警告] 未找到 %TM_WEB_DIR%\package.json，跳过前端构建。
    )
)

:: 最终验证前端
if not exist "%TM_DIR%\src\web\dist\index.html" (
    echo.
    echo [错误] 前端构建文件不存在，Tool Manager 可能无法正常显示。
    echo        请手动运行 install.bat 并选择选项 T。
    echo.
    echo [提示] 后端仍会启动，但页面可能无法访问。
    echo        你可以稍后在 %TM_WEB_DIR% 目录下手动执行:
    echo         npm install ^&^& npm run build
    echo.
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
