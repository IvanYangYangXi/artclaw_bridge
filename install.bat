@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================
::  ArtClaw Bridge — 统一一键安装器 (Windows)
::
::  用法:
::    双击运行，按菜单选择安装目标
::
::  功能:
::    - 安装 UE 插件到 UE 项目
::    - 安装 Maya 插件到 Maya scripts 目录 (幂等追加 userSetup.py)
::    - 安装 3ds Max 插件到 Max scripts 目录 (幂等注入 startup)
::    - 配置 OpenClaw mcp-bridge 插件
::    - 自动打包 bridge_core 共享模块（自包含部署）
::    - 卸载已安装的插件
::
::  注意:
::    userSetup.py / startup.py 使用追加模式，不会覆盖用户已有内容。
::    重复运行安装是安全的（幂等）。
::    更完整的功能请使用 install.py (支持跨平台、卸载、CLI 参数等)。
:: ============================================================

:: ----- 定位项目根目录 -----
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "DCC_BRIDGE_SRC=%ROOT_DIR%\subprojects\DCCClawBridge"
set "UE_PLUGIN_SRC=%ROOT_DIR%\subprojects\UEDAgentProj\Plugins\UEClawBridge"
set "BRIDGE_MODULES_SRC=%ROOT_DIR%\openclaw-mcp-bridge"
set "MCP_BRIDGE_SRC=%ROOT_DIR%\openclaw-mcp-bridge\mcp-bridge"

:: 标记常量
set "INJECT_START=# ===== ArtClaw Bridge START ====="
set "INJECT_END=# ===== ArtClaw Bridge END ====="

:: 验证项目结构
if not exist "%DCC_BRIDGE_SRC%\core\bridge_dcc.py" (
    echo [错误] 未找到 DCCClawBridge 源码: %DCC_BRIDGE_SRC%
    echo        请确认从 artclaw_bridge 项目根目录运行此脚本。
    pause
    exit /b 1
)
if not exist "%UE_PLUGIN_SRC%\UEClawBridge.uplugin" (
    echo [错误] 未找到 UEClawBridge 插件: %UE_PLUGIN_SRC%
    echo        请确认从 artclaw_bridge 项目根目录运行此脚本。
    pause
    exit /b 1
)

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║       ArtClaw Bridge — 统一安装器 v1.0               ║
echo  ║       UE / Maya / 3ds Max 一键部署                   ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  项目目录: %ROOT_DIR%
echo.

:: ============================================================
:: 交互菜单
:: ============================================================
echo  请选择操作:
echo.
echo    [1] 安装 Unreal Engine 插件
echo    [2] 安装 Maya 插件
echo    [3] 安装 3ds Max 插件
echo    [4] 配置 OpenClaw mcp-bridge
echo    [5] 全部安装 (UE + Maya + Max + OpenClaw)
echo    [6] 卸载 Maya 插件
echo    [7] 卸载 3ds Max 插件
echo    [8] 卸载 UE 插件
echo    [0] 退出
echo.
set /p CHOICE="  请输入选项 (0-8): "

if "%CHOICE%"=="0" goto :exit_ok
if "%CHOICE%"=="1" goto :install_ue
if "%CHOICE%"=="2" goto :install_maya
if "%CHOICE%"=="3" goto :install_max
if "%CHOICE%"=="4" goto :install_openclaw
if "%CHOICE%"=="5" goto :install_all
if "%CHOICE%"=="6" goto :uninstall_maya
if "%CHOICE%"=="7" goto :uninstall_max
if "%CHOICE%"=="8" goto :uninstall_ue
echo [错误] 无效选项: %CHOICE%
pause
exit /b 1

:: ============================================================
:: 安装全部
:: ============================================================
:install_all
call :do_install_ue
if %ERRORLEVEL% NEQ 0 echo [警告] UE 安装未完成，继续...
call :do_install_maya
if %ERRORLEVEL% NEQ 0 echo [警告] Maya 安装未完成，继续...
call :do_install_max
if %ERRORLEVEL% NEQ 0 echo [警告] Max 安装未完成，继续...
call :do_install_openclaw
goto :summary

:: ============================================================
:: 安装 UE 插件
:: ============================================================
:install_ue
call :do_install_ue
goto :summary

:do_install_ue
echo.
echo  ── Unreal Engine 插件安装 ──────────────────────────
echo.

:: 获取 UE 项目路径
set "UE_PROJECT_DIR="
echo  请输入 UE 项目路径 (包含 .uproject 文件的目录):
set /p UE_PROJECT_DIR="  > "

if "%UE_PROJECT_DIR%"=="" (
    echo [跳过] 未输入 UE 项目路径
    exit /b 1
)

:: 去除尾部反斜杠和引号
set "UE_PROJECT_DIR=%UE_PROJECT_DIR:"=%"
if "%UE_PROJECT_DIR:~-1%"=="\" set "UE_PROJECT_DIR=%UE_PROJECT_DIR:~0,-1%"

:: 验证 .uproject
set "FOUND_UPROJECT="
for %%f in ("%UE_PROJECT_DIR%\*.uproject") do set "FOUND_UPROJECT=%%f"
if "%FOUND_UPROJECT%"=="" (
    echo [错误] 未找到 .uproject 文件: %UE_PROJECT_DIR%
    exit /b 1
)
echo [OK] UE 项目: %FOUND_UPROJECT%

set "PLUGIN_DST=%UE_PROJECT_DIR%\Plugins\UEClawBridge"

:: 检查目标已存在
if exist "%PLUGIN_DST%" (
    echo [提示] 目标目录已存在: %PLUGIN_DST%
    set /p OVERWRITE="       是否覆盖？(Y/N, 默认 Y): "
    if /I "!OVERWRITE!"=="N" (
        echo [跳过] UE 插件安装
        exit /b 0
    )
)

:: 复制插件 (robocopy /MIR 保证幂等)
echo [复制] UEClawBridge 插件...
robocopy "%UE_PLUGIN_SRC%" "%PLUGIN_DST%" /MIR /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
if %ERRORLEVEL% GTR 7 (
    echo [错误] 复制插件失败 (robocopy 错误: %ERRORLEVEL%)
    exit /b 1
)
echo [OK] 插件已安装到: %PLUGIN_DST%

:: 复制 bridge_core 共享模块到插件 Content/Python/
echo [复制] bridge_core 共享模块...
set "PYTHON_DST=%PLUGIN_DST%\Content\Python"
if not exist "%PYTHON_DST%" mkdir "%PYTHON_DST%"
copy /Y "%BRIDGE_MODULES_SRC%\bridge_core.py" "%PYTHON_DST%\" >nul
copy /Y "%BRIDGE_MODULES_SRC%\bridge_config.py" "%PYTHON_DST%\" >nul
copy /Y "%BRIDGE_MODULES_SRC%\bridge_diagnostics.py" "%PYTHON_DST%\" >nul
echo [OK] 共享模块已打包到: %PYTHON_DST%

:: 安装 Python 依赖
echo [安装] Python 依赖...
call :find_ue_python
if defined UE_PYTHON (
    "!UE_PYTHON!" -m pip install websockets pydantic >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Python 依赖已安装
    ) else (
        echo [警告] Python 依赖安装失败，请稍后手动安装
    )
) else (
    echo [警告] 未找到 UE Python，请手动安装 websockets 和 pydantic
)

echo [完成] UE 插件安装成功!
exit /b 0

:: ============================================================
:: 卸载 UE 插件
:: ============================================================
:uninstall_ue
echo.
echo  ── Unreal Engine 插件卸载 ──────────────────────────
echo.
set "UE_PROJECT_DIR="
echo  请输入 UE 项目路径:
set /p UE_PROJECT_DIR="  > "
if "%UE_PROJECT_DIR%"=="" (
    echo [跳过] 未输入路径
    goto :summary
)
set "UE_PROJECT_DIR=%UE_PROJECT_DIR:"=%"
if "%UE_PROJECT_DIR:~-1%"=="\" set "UE_PROJECT_DIR=%UE_PROJECT_DIR:~0,-1%"

set "PLUGIN_DST=%UE_PROJECT_DIR%\Plugins\UEClawBridge"
if exist "%PLUGIN_DST%" (
    rmdir /S /Q "%PLUGIN_DST%"
    echo [删除] 已删除: %PLUGIN_DST%
) else (
    echo [跳过] UE 插件不存在: %PLUGIN_DST%
)
goto :summary

:: ============================================================
:: 安装 Maya 插件
:: ============================================================
:install_maya
call :do_install_maya
goto :summary

:do_install_maya
echo.
echo  ── Maya 插件安装 ───────────────────────────────────
echo.

:: 获取 Maya 版本
set "MAYA_VER=2023"
echo  请输入 Maya 版本 (默认 2023):
set /p MAYA_VER_INPUT="  > "
if not "%MAYA_VER_INPUT%"=="" set "MAYA_VER=%MAYA_VER_INPUT%"

set "MAYA_SCRIPTS=%USERPROFILE%\Documents\maya\%MAYA_VER%\scripts"
set "DCC_DST=%MAYA_SCRIPTS%\DCCClawBridge"

echo  目标目录: %DCC_DST%
echo.

:: 检查目标已存在
if exist "%DCC_DST%" (
    echo [提示] 目标目录已存在: %DCC_DST%
    set /p OVERWRITE="       是否覆盖？(Y/N, 默认 Y): "
    if /I "!OVERWRITE!"=="N" (
        echo [跳过] Maya 插件安装
        exit /b 0
    )
)

:: 创建 scripts 目录
if not exist "%MAYA_SCRIPTS%" (
    mkdir "%MAYA_SCRIPTS%"
    echo [创建] %MAYA_SCRIPTS%
)

:: 复制 DCCClawBridge (robocopy /MIR 保证幂等)
echo [复制] DCCClawBridge...
robocopy "%DCC_BRIDGE_SRC%" "%DCC_DST%" /MIR /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
if %ERRORLEVEL% GTR 7 (
    echo [错误] 复制 DCCClawBridge 失败
    exit /b 1
)
echo [OK] DCCClawBridge 已安装到: %DCC_DST%

:: 复制 bridge_core 共享模块到 DCCClawBridge/core/
echo [复制] bridge_core 共享模块到 core/...
copy /Y "%BRIDGE_MODULES_SRC%\bridge_core.py" "%DCC_DST%\core\" >nul
copy /Y "%BRIDGE_MODULES_SRC%\bridge_config.py" "%DCC_DST%\core\" >nul
copy /Y "%BRIDGE_MODULES_SRC%\bridge_diagnostics.py" "%DCC_DST%\core\" >nul
echo [OK] 共享模块已打包 (自包含部署)

:: 处理 userSetup.py (幂等注入)
call :inject_maya_startup "%MAYA_SCRIPTS%"

echo [完成] Maya 插件安装成功!
exit /b 0

:: ============================================================
:: Maya userSetup.py 幂等注入
:: ============================================================
:inject_maya_startup
set "TARGET_DIR=%~1"
set "SETUP_DST=%TARGET_DIR%\userSetup.py"
set "SETUP_SRC=%DCC_BRIDGE_SRC%\maya_setup\userSetup.py"

:: 目标不存在 → 创建新文件 (带标记块)
if not exist "%SETUP_DST%" (
    echo %INJECT_START%> "%SETUP_DST%"
    type "%SETUP_SRC%" >> "%SETUP_DST%"
    echo.>> "%SETUP_DST%"
    echo %INJECT_END%>> "%SETUP_DST%"
    echo [创建] userSetup.py (新建)
    goto :eof
)

:: 已有标记块 → 委托给 Python 更新 (bat 不擅长多行替换)
findstr /C:"ArtClaw Bridge START" "%SETUP_DST%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [更新] userSetup.py 中已有 ArtClaw 标记块，通过 install.py 更新...
    where python >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        python "%ROOT_DIR%\install.py" --maya --maya-version %MAYA_VER% --force 2>nul
    ) else (
        echo [跳过] 未找到 Python，无法更新标记块。请运行 install.py
    )
    goto :eof
)

:: 检查是否已有 ArtClaw 代码 (非标记版)
findstr /I /C:"artclaw" "%SETUP_DST%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [跳过] userSetup.py 已包含 ArtClaw 代码 (非标记块)，请手动检查
    goto :eof
)

:: 追加标记块到现有文件末尾
echo.>> "%SETUP_DST%"
echo.>> "%SETUP_DST%"
echo %INJECT_START%>> "%SETUP_DST%"
type "%SETUP_SRC%" >> "%SETUP_DST%"
echo.>> "%SETUP_DST%"
echo %INJECT_END%>> "%SETUP_DST%"
echo [追加] ArtClaw 启动代码已追加到 userSetup.py
goto :eof

:: ============================================================
:: 卸载 Maya 插件
:: ============================================================
:uninstall_maya
echo.
echo  ── Maya 插件卸载 ───────────────────────────────────
echo.
set "MAYA_VER=2023"
echo  请输入 Maya 版本 (默认 2023):
set /p MAYA_VER_INPUT="  > "
if not "%MAYA_VER_INPUT%"=="" set "MAYA_VER=%MAYA_VER_INPUT%"

set "MAYA_SCRIPTS=%USERPROFILE%\Documents\maya\%MAYA_VER%\scripts"
set "DCC_DST=%MAYA_SCRIPTS%\DCCClawBridge"

:: 删除 DCCClawBridge 目录
if exist "%DCC_DST%" (
    rmdir /S /Q "%DCC_DST%"
    echo [删除] 已删除: %DCC_DST%
) else (
    echo [跳过] DCCClawBridge 不存在: %DCC_DST%
)

:: 从 userSetup.py 移除 ArtClaw 块 (委托给 install.py)
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%ROOT_DIR%\install.py" --uninstall --maya --maya-version %MAYA_VER% --force 2>nul
    echo [OK] userSetup.py 中的 ArtClaw 代码已清理
) else (
    echo [提示] 请手动编辑 %MAYA_SCRIPTS%\userSetup.py
    echo        删除 "ArtClaw Bridge START" 到 "ArtClaw Bridge END" 之间的内容
)

echo [完成] Maya 插件卸载完成
echo [提示] OpenClaw 配置需手动修改 ~/.openclaw/openclaw.json
goto :summary

:: ============================================================
:: 安装 3ds Max 插件
:: ============================================================
:install_max
call :do_install_max
goto :summary

:do_install_max
echo.
echo  ── 3ds Max 插件安装 ────────────────────────────────
echo.

:: 获取 Max 版本
set "MAX_VER=2024"
echo  请输入 3ds Max 版本 (默认 2024):
set /p MAX_VER_INPUT="  > "
if not "%MAX_VER_INPUT%"=="" set "MAX_VER=%MAX_VER_INPUT%"

set "MAX_SCRIPTS=%LOCALAPPDATA%\Autodesk\3dsMax\%MAX_VER%\ENU\scripts"
set "MAX_STARTUP=%MAX_SCRIPTS%\startup"
set "DCC_DST=%MAX_SCRIPTS%\DCCClawBridge"

echo  目标目录: %DCC_DST%
echo.

:: 检查目标已存在
if exist "%DCC_DST%" (
    echo [提示] 目标目录已存在: %DCC_DST%
    set /p OVERWRITE="       是否覆盖？(Y/N, 默认 Y): "
    if /I "!OVERWRITE!"=="N" (
        echo [跳过] Max 插件安装
        exit /b 0
    )
)

:: 创建目录
if not exist "%MAX_SCRIPTS%" (
    mkdir "%MAX_SCRIPTS%"
    echo [创建] %MAX_SCRIPTS%
)
if not exist "%MAX_STARTUP%" (
    mkdir "%MAX_STARTUP%"
    echo [创建] %MAX_STARTUP%
)

:: 复制 DCCClawBridge (robocopy /MIR 保证幂等)
echo [复制] DCCClawBridge...
robocopy "%DCC_BRIDGE_SRC%" "%DCC_DST%" /MIR /NFL /NDL /NJH /NJS /NC /NS /NP >nul 2>&1
if %ERRORLEVEL% GTR 7 (
    echo [错误] 复制 DCCClawBridge 失败
    exit /b 1
)
echo [OK] DCCClawBridge 已安装到: %DCC_DST%

:: 复制 bridge_core 共享模块到 DCCClawBridge/core/
echo [复制] bridge_core 共享模块到 core/...
copy /Y "%BRIDGE_MODULES_SRC%\bridge_core.py" "%DCC_DST%\core\" >nul
copy /Y "%BRIDGE_MODULES_SRC%\bridge_config.py" "%DCC_DST%\core\" >nul
copy /Y "%BRIDGE_MODULES_SRC%\bridge_diagnostics.py" "%DCC_DST%\core\" >nul
echo [OK] 共享模块已打包 (自包含部署)

:: 处理 startup.py (幂等注入)
call :inject_max_startup

echo [完成] 3ds Max 插件安装成功!
exit /b 0

:: ============================================================
:: Max startup.py 幂等注入
:: ============================================================
:inject_max_startup
set "STARTUP_DST=%MAX_STARTUP%\artclaw_startup.py"
set "STARTUP_SRC=%DCC_BRIDGE_SRC%\max_setup\startup.py"

:: 目标不存在 → 创建新文件
if not exist "%STARTUP_DST%" (
    echo %INJECT_START%> "%STARTUP_DST%"
    type "%STARTUP_SRC%" >> "%STARTUP_DST%"
    echo.>> "%STARTUP_DST%"
    echo %INJECT_END%>> "%STARTUP_DST%"
    echo [创建] artclaw_startup.py (新建)
    goto :eof
)

:: 已有标记块 → 委托给 Python 更新
findstr /C:"ArtClaw Bridge START" "%STARTUP_DST%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [更新] artclaw_startup.py 中已有 ArtClaw 标记块，通过 install.py 更新...
    where python >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        python "%ROOT_DIR%\install.py" --max --max-version %MAX_VER% --force 2>nul
    ) else (
        echo [跳过] 未找到 Python，无法更新标记块。请运行 install.py
    )
    goto :eof
)

:: 检查已有 ArtClaw 代码
findstr /I /C:"artclaw" "%STARTUP_DST%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [跳过] artclaw_startup.py 已包含 ArtClaw 代码，请手动检查
    goto :eof
)

:: 追加标记块
echo.>> "%STARTUP_DST%"
echo.>> "%STARTUP_DST%"
echo %INJECT_START%>> "%STARTUP_DST%"
type "%STARTUP_SRC%" >> "%STARTUP_DST%"
echo.>> "%STARTUP_DST%"
echo %INJECT_END%>> "%STARTUP_DST%"
echo [追加] ArtClaw 启动代码已追加到 artclaw_startup.py
goto :eof

:: ============================================================
:: 卸载 3ds Max 插件
:: ============================================================
:uninstall_max
echo.
echo  ── 3ds Max 插件卸载 ────────────────────────────────
echo.
set "MAX_VER=2024"
echo  请输入 3ds Max 版本 (默认 2024):
set /p MAX_VER_INPUT="  > "
if not "%MAX_VER_INPUT%"=="" set "MAX_VER=%MAX_VER_INPUT%"

set "MAX_SCRIPTS=%LOCALAPPDATA%\Autodesk\3dsMax\%MAX_VER%\ENU\scripts"
set "DCC_DST=%MAX_SCRIPTS%\DCCClawBridge"

:: 删除 DCCClawBridge 目录
if exist "%DCC_DST%" (
    rmdir /S /Q "%DCC_DST%"
    echo [删除] 已删除: %DCC_DST%
) else (
    echo [跳过] DCCClawBridge 不存在: %DCC_DST%
)

:: 从 startup 移除 ArtClaw 块
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%ROOT_DIR%\install.py" --uninstall --max --max-version %MAX_VER% --force 2>nul
    echo [OK] startup 中的 ArtClaw 代码已清理
) else (
    set "STARTUP_FILE=%MAX_SCRIPTS%\startup\artclaw_startup.py"
    if exist "!STARTUP_FILE!" (
        echo [提示] 请手动编辑 !STARTUP_FILE!
        echo        删除 "ArtClaw Bridge START" 到 "ArtClaw Bridge END" 之间的内容
    )
)

echo [完成] 3ds Max 插件卸载完成
echo [提示] OpenClaw 配置需手动修改 ~/.openclaw/openclaw.json
goto :summary

:: ============================================================
:: 配置 OpenClaw
:: ============================================================
:install_openclaw
call :do_install_openclaw
goto :summary

:do_install_openclaw
echo.
echo  ── OpenClaw mcp-bridge 配置 ────────────────────────
echo.

:: 复制 mcp-bridge 插件
set "OPENCLAW_EXT=%USERPROFILE%\.openclaw\extensions\mcp-bridge"
if not exist "%USERPROFILE%\.openclaw\extensions" mkdir "%USERPROFILE%\.openclaw\extensions"
if not exist "%OPENCLAW_EXT%" mkdir "%OPENCLAW_EXT%"

echo [复制] mcp-bridge 插件...
copy /Y "%MCP_BRIDGE_SRC%\index.ts" "%OPENCLAW_EXT%\" >nul
copy /Y "%MCP_BRIDGE_SRC%\openclaw.plugin.json" "%OPENCLAW_EXT%\" >nul
echo [OK] mcp-bridge 已复制到: %OPENCLAW_EXT%

:: 运行配置脚本
echo [配置] 运行 setup_openclaw_config.py...
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%BRIDGE_MODULES_SRC%\setup_openclaw_config.py" --ue --maya --max
    if !ERRORLEVEL! EQU 0 (
        echo [OK] OpenClaw 配置已更新
    ) else (
        echo [警告] 配置脚本执行失败，请手动配置
    )
) else (
    echo [警告] 未找到 Python，请手动运行:
    echo        python "%BRIDGE_MODULES_SRC%\setup_openclaw_config.py"
)

echo [完成] OpenClaw 配置成功!
exit /b 0

:: ============================================================
:: 辅助函数: 查找 UE Python
:: ============================================================
:find_ue_python
set "UE_PYTHON="
for %%v in (5.7 5.6 5.5 5.4 5.3) do (
    if exist "C:\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" (
        set "UE_PYTHON=C:\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
        echo       找到 UE %%v Python: !UE_PYTHON!
        goto :eof
    )
    if exist "C:\Program Files\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" (
        set "UE_PYTHON=C:\Program Files\Epic Games\UE_%%v\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
        echo       找到 UE %%v Python: !UE_PYTHON!
        goto :eof
    )
)
echo [警告] 未自动找到 UE Python
goto :eof

:: ============================================================
:: 安装总结
:: ============================================================
:summary
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║              操作完成!                                ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  后续步骤:
echo.
echo    UE:
echo      1. 打开 UE 项目，启用 "UE Claw Bridge" 插件
echo      2. 重启编辑器
echo      3. Window 菜单 → UE Claw Bridge
echo      4. 输入 /diagnose 验证连接
echo.
echo    Maya:
echo      1. 启动 Maya → ArtClaw 菜单自动出现
echo      2. ArtClaw → 打开 Chat Panel
echo      3. 点击 连接 或输入 /connect
echo.
echo    3ds Max:
echo      1. 启动 Max → ArtClaw 自动加载
echo      2. 菜单栏 → ArtClaw → Chat Panel
echo      3. 点击 连接 或输入 /connect
echo.
echo    OpenClaw:
echo      1. 重启 Gateway: openclaw gateway restart
echo      2. 确认 mcp-bridge 已加载
echo.
echo  提示: 更完整的功能 (卸载、跨平台、CLI) 请使用:
echo        python install.py --help
echo.

:exit_ok
pause
exit /b 0
