@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================
::  Art Claw Bridge — One-Click Setup (Windows)
::  阶段 4.5: 极简一键部署方案
::
::  用法: 双击此脚本，或在命令行运行:
::    setup.bat [UE项目路径]
::
::  功能:
::    1. 检测 UE 安装和项目路径
::    2. 复制插件到 UE 项目的 Plugins 目录
::    3. 安装 Python 依赖 (websockets 等)
::    4. 关联 OpenClaw 配置 (如已安装)
::    5. 运行 Health Check 验证
:: ============================================================

echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║      Art Claw Bridge — One-Click Setup         ║
echo  ║      UE Claw Bridge Plugin Installer           ║
echo  ╚════════════════════════════════════════════════╝
echo.

:: ----- 步骤 0: 定位自身 -----
set "SCRIPT_DIR=%~dp0"
set "PLUGIN_SRC=%SCRIPT_DIR%Plugins\UEClawBridge"

if not exist "%PLUGIN_SRC%\UEClawBridge.uplugin" (
    echo [ERROR] Cannot find plugin source at: %PLUGIN_SRC%
    echo         Please run this script from the project root directory.
    pause
    exit /b 1
)
echo [OK] Plugin source found: %PLUGIN_SRC%

:: ----- 步骤 1: 确定 UE 项目路径 -----
if "%~1"=="" (
    :: 尝试自动检测: 当前目录或上级目录
    if exist "%SCRIPT_DIR%*.uproject" (
        for %%f in ("%SCRIPT_DIR%*.uproject") do set "UE_PROJECT_DIR=%SCRIPT_DIR%"
    ) else (
        echo.
        echo [INPUT] Please enter the path to your UE project directory:
        echo         (the folder containing your .uproject file)
        set /p UE_PROJECT_DIR="  > "
    )
) else (
    set "UE_PROJECT_DIR=%~1"
)

:: 去除尾部反斜杠
if "%UE_PROJECT_DIR:~-1%"=="\" set "UE_PROJECT_DIR=%UE_PROJECT_DIR:~0,-1%"

:: 验证 .uproject 存在
set "FOUND_UPROJECT="
for %%f in ("%UE_PROJECT_DIR%\*.uproject") do set "FOUND_UPROJECT=%%f"
if "%FOUND_UPROJECT%"=="" (
    echo [ERROR] No .uproject file found in: %UE_PROJECT_DIR%
    pause
    exit /b 1
)
echo [OK] UE Project: %FOUND_UPROJECT%

:: ----- 步骤 2: 复制插件 -----
set "PLUGIN_DST=%UE_PROJECT_DIR%\Plugins\UEClawBridge"

echo.
echo [2/5] Installing plugin...

if exist "%PLUGIN_DST%" (
    echo       Plugin directory already exists. Updating...
)

:: 使用 robocopy 镜像复制 (比 xcopy 更可靠)
robocopy "%PLUGIN_SRC%" "%PLUGIN_DST%" /MIR /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
if %ERRORLEVEL% LEQ 7 (
    echo [OK] Plugin installed to: %PLUGIN_DST%
) else (
    echo [ERROR] Failed to copy plugin. Error code: %ERRORLEVEL%
    pause
    exit /b 1
)

:: ----- 步骤 3: 安装 Python 依赖 -----
echo.
echo [3/5] Installing Python dependencies...

:: 查找 UE 的内置 Python
set "UE_PYTHON="
for %%v in (5.7 5.6 5.5 5.4 5.3) do (
    if exist "C:\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" (
        set "UE_PYTHON=C:\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
        echo       Found UE %%v Python: !UE_PYTHON!
        goto :found_python
    )
)

:: 也检查 Program Files
for %%v in (5.7 5.6 5.5 5.4 5.3) do (
    if exist "C:\Program Files\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" (
        set "UE_PYTHON=C:\Program Files\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
        echo       Found UE %%v Python: !UE_PYTHON!
        goto :found_python
    )
)

echo [WARN] UE Python not found automatically.
echo        Trying system Python...
set "UE_PYTHON=python"

:found_python

:: 先尝试离线安装 (Lib_bundle)
set "BUNDLE_DIR=%PLUGIN_DST%\Content\Python\Lib_bundle"
if exist "%BUNDLE_DIR%\websockets*.whl" (
    echo       Installing from offline bundle...
    "%UE_PYTHON%" -m pip install --no-index --find-links="%BUNDLE_DIR%" websockets pydantic 2>nul
) else (
    echo       Installing from PyPI (requires network)...
    "%UE_PYTHON%" -m pip install websockets pydantic 2>nul
)

:: 验证
"%UE_PYTHON%" -c "import websockets; print(f'       websockets {websockets.__version__}')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] websockets installation may have failed. Continue anyway.
) else (
    echo [OK] Python dependencies installed.
)

:: ----- 步骤 4: 关联 OpenClaw (可选) -----
echo.
echo [4/5] Configuring OpenClaw integration...

set "OPENCLAW_CONFIG=%USERPROFILE%\.openclaw\openclaw.json"
if not exist "%OPENCLAW_CONFIG%" (
    echo [SKIP] OpenClaw not installed (no ~/.openclaw/openclaw.json)
    echo        Install OpenClaw later: npm install -g openclaw
    goto :skip_openclaw
)

:: 检查 mcp-bridge 是否已配置
findstr /C:"mcp-bridge" "%OPENCLAW_CONFIG%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] OpenClaw mcp-bridge already configured.
) else (
    echo [INFO] OpenClaw found but mcp-bridge not configured.
    echo        Please add the following to %OPENCLAW_CONFIG%:
    echo.
    echo          "mcp-bridge": {
    echo            "enabled": true,
    echo            "config": {
    echo              "servers": {
    echo                "ue-editor": {
    echo                  "type": "websocket",
    echo                  "url": "ws://127.0.0.1:8080",
    echo                  "enabled": true
    echo                }
    echo              }
    echo            }
    echo          }
    echo.
)

:skip_openclaw

:: ----- 步骤 5: 验证 -----
echo.
echo [5/5] Running health check...

"%UE_PYTHON%" -c "import sys; sys.path.insert(0, r'%PLUGIN_DST%\Content\Python'); from health_check import run_health_check; print(run_health_check())" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Health check could not run. This is normal outside UE.
)

:: ----- 完成 -----
echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║            Setup Complete!                      ║
echo  ╚════════════════════════════════════════════════╝
echo.
echo  Next steps:
echo    1. Open your UE project in Unreal Editor
echo    2. Enable the plugin: Edit → Plugins → "UE Claw Bridge"
echo    3. Restart UE Editor
echo    4. Open the panel: Window menu → UE Claw Bridge
echo    5. Type /diagnose to verify the connection
echo.
pause
