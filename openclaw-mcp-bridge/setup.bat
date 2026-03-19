@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================
::  ArtClaw Bridge — UE 插件快速安装 (Windows)
::
::  用法: setup.bat [UE项目路径]
::
::  注意: 这是 UE 专用的简化安装脚本。
::        完整安装 (UE + Maya + Max) 请使用根目录的:
::          install.bat  (交互菜单)
::          install.py   (命令行)
:: ============================================================

echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║      ArtClaw Bridge — UE Quick Setup           ║
echo  ║      UE Claw Bridge Plugin Installer           ║
echo  ╚════════════════════════════════════════════════╝
echo.

:: ----- 步骤 0: 定位自身和插件源 -----
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: setup.bat 位于 openclaw-mcp-bridge/ 目录
:: UE 插件位于 ../subprojects/UEDAgentProj/Plugins/UEClawBridge
set "PROJECT_ROOT=%SCRIPT_DIR%\.."
set "PROJECT_ROOT=!PROJECT_ROOT:\openclaw-mcp-bridge\..=!"

:: 规范化路径
pushd "%SCRIPT_DIR%\.."
set "PROJECT_ROOT=%CD%"
popd

set "PLUGIN_SRC=%PROJECT_ROOT%\subprojects\UEDAgentProj\Plugins\UEClawBridge"
set "BRIDGE_MODULES=%SCRIPT_DIR%"

if not exist "%PLUGIN_SRC%\UEClawBridge.uplugin" (
    echo [ERROR] 未找到 UE 插件源码: %PLUGIN_SRC%
    echo         请确认项目结构完整。
    echo.
    echo         期望路径: subprojects\UEDAgentProj\Plugins\UEClawBridge\
    pause
    exit /b 1
)
echo [OK] 插件源码: %PLUGIN_SRC%

:: ----- 步骤 1: 确定 UE 项目路径 -----
if "%~1"=="" (
    echo.
    echo [输入] 请输入 UE 项目路径 (包含 .uproject 文件的目录):
    set /p UE_PROJECT_DIR="  > "
) else (
    set "UE_PROJECT_DIR=%~1"
)

if "%UE_PROJECT_DIR%"=="" (
    echo [错误] 未输入项目路径
    pause
    exit /b 1
)

:: 去除尾部反斜杠
set "UE_PROJECT_DIR=%UE_PROJECT_DIR:"=%"
if "%UE_PROJECT_DIR:~-1%"=="\" set "UE_PROJECT_DIR=%UE_PROJECT_DIR:~0,-1%"

:: 验证 .uproject 存在
set "FOUND_UPROJECT="
for %%f in ("%UE_PROJECT_DIR%\*.uproject") do set "FOUND_UPROJECT=%%f"
if "%FOUND_UPROJECT%"=="" (
    echo [ERROR] 未找到 .uproject 文件: %UE_PROJECT_DIR%
    pause
    exit /b 1
)
echo [OK] UE 项目: %FOUND_UPROJECT%

:: ----- 步骤 2: 复制插件 -----
set "PLUGIN_DST=%UE_PROJECT_DIR%\Plugins\UEClawBridge"

echo.
echo [2/5] 安装插件...

if exist "%PLUGIN_DST%" (
    echo       插件目录已存在，更新中...
)

robocopy "%PLUGIN_SRC%" "%PLUGIN_DST%" /MIR /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
if %ERRORLEVEL% GTR 7 (
    echo [ERROR] 复制插件失败 (robocopy: %ERRORLEVEL%)
    pause
    exit /b 1
)
echo [OK] 插件已安装: %PLUGIN_DST%

:: ----- 步骤 2.5: 复制共享模块 -----
echo.
echo [2.5/5] 打包 bridge_core 共享模块...
set "PYTHON_DST=%PLUGIN_DST%\Content\Python"
if not exist "%PYTHON_DST%" mkdir "%PYTHON_DST%"
copy /Y "%BRIDGE_MODULES%\bridge_core.py" "%PYTHON_DST%\" >nul
copy /Y "%BRIDGE_MODULES%\bridge_config.py" "%PYTHON_DST%\" >nul
copy /Y "%BRIDGE_MODULES%\bridge_diagnostics.py" "%PYTHON_DST%\" >nul
copy /Y "%BRIDGE_MODULES%\memory_core.py" "%PYTHON_DST%\" >nul
copy /Y "%BRIDGE_MODULES%\integrity_check.py" "%PYTHON_DST%\" >nul
echo [OK] 共享模块已打包: %PYTHON_DST%

:: ----- 步骤 3: 安装 Python 依赖 -----
echo.
echo [3/5] 安装 Python 依赖...

set "UE_PYTHON="
for %%v in (5.7 5.6 5.5 5.4 5.3) do (
    if exist "C:\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" (
        set "UE_PYTHON=C:\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
        echo       找到 UE %%v Python: !UE_PYTHON!
        goto :found_python
    )
    if exist "C:\Program Files\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" (
        set "UE_PYTHON=C:\Program Files\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
        echo       找到 UE %%v Python: !UE_PYTHON!
        goto :found_python
    )
)

echo [警告] 未自动找到 UE Python，使用系统 Python...
set "UE_PYTHON=python"

:found_python

:: 尝试离线安装
set "BUNDLE_DIR=%PLUGIN_DST%\Content\Python\Lib_bundle"
if exist "%BUNDLE_DIR%\websockets*.whl" (
    echo       从离线包安装...
    "%UE_PYTHON%" -m pip install --no-index --find-links="%BUNDLE_DIR%" websockets pydantic 2>nul
) else (
    echo       从 PyPI 安装 (需要网络)...
    "%UE_PYTHON%" -m pip install websockets pydantic 2>nul
)

"%UE_PYTHON%" -c "import websockets; print(f'       websockets {websockets.__version__}')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [警告] websockets 安装可能失败，继续...
) else (
    echo [OK] Python 依赖已安装
)

:: ----- 步骤 4: 配置 OpenClaw -----
echo.
echo [4/5] 配置 OpenClaw...

set "OPENCLAW_EXT=%USERPROFILE%\.openclaw\extensions\mcp-bridge"
if not exist "%USERPROFILE%\.openclaw\extensions" mkdir "%USERPROFILE%\.openclaw\extensions" 2>nul
if not exist "%OPENCLAW_EXT%" mkdir "%OPENCLAW_EXT%" 2>nul

:: 复制 mcp-bridge 插件
set "MCP_SRC=%SCRIPT_DIR%\mcp-bridge"
if exist "%MCP_SRC%\index.ts" (
    copy /Y "%MCP_SRC%\index.ts" "%OPENCLAW_EXT%\" >nul
    copy /Y "%MCP_SRC%\openclaw.plugin.json" "%OPENCLAW_EXT%\" >nul
    echo [OK] mcp-bridge 插件已复制: %OPENCLAW_EXT%
)

:: 运行配置脚本
set "CONFIG_SCRIPT=%SCRIPT_DIR%\setup_openclaw_config.py"
if exist "%CONFIG_SCRIPT%" (
    where python >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        python "%CONFIG_SCRIPT%" --ue
        if !ERRORLEVEL! EQU 0 (
            echo [OK] OpenClaw 配置已更新
        ) else (
            echo [警告] 配置脚本失败，请手动配置
        )
    ) else (
        echo [提示] 未找到 Python，请手动运行: python "%CONFIG_SCRIPT%"
    )
) else (
    echo [跳过] 配置脚本不存在
)

:: ----- 步骤 5: 验证 -----
echo.
echo [5/5] 健康检查...

"%UE_PYTHON%" -c "import sys; sys.path.insert(0, r'%PLUGIN_DST%\Content\Python'); from health_check import run_health_check; print(run_health_check())" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [提示] 健康检查无法在 UE 外运行，属正常现象
)

:: ----- 完成 -----
echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║            安装完成!                            ║
echo  ╚════════════════════════════════════════════════╝
echo.
echo  后续步骤:
echo    1. 打开 UE 项目
echo    2. 启用插件: Edit → Plugins → "UE Claw Bridge"
echo    3. 重启编辑器
echo    4. 打开面板: Window → UE Claw Bridge
echo    5. 输入 /diagnose 验证连接
echo.
echo  提示: 安装 Maya / Max 插件请使用根目录的 install.bat 或 install.py
echo.
pause
