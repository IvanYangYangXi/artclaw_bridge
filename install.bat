@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================
::  ArtClaw Bridge - Unified Installer [Windows]
::
::  Usage:
::    Run this script, select platform and installation target.
::
::  Targets:
::    UE / Maya / Max / Blender / Houdini / SP / SD / ComfyUI
::    Platform config, Tool Manager deps, Uninstall
::
::  Notes:
::    userSetup.py / startup.py - append mode, safe to re-run.
::    For full CLI features: python install.py --help
:: ============================================================

:: ----- 定位项目根目录 -----
set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "DCC_BRIDGE_SRC=%ROOT_DIR%\subprojects\DCCClawBridge"
set "UE_PLUGIN_SRC=%ROOT_DIR%\subprojects\UEDAgentProj\Plugins\UEClawBridge"
set "BRIDGE_MODULES_SRC=%ROOT_DIR%\core"
set "PLATFORMS_DIR=%ROOT_DIR%\platforms"
set "SKILLS_SRC=%ROOT_DIR%\skills"

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

:: ── Python 环境预检 ──
where python >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  ============================================================
    echo    [错误] 未检测到 Python 环境
    echo  ============================================================
    echo.
    echo  本安装器需要 Python 3.10+ 环境。
    echo.
    echo  推荐安装 Python 3.11 ^(稳定且兼容性最佳^):
    echo    https://www.python.org/downloads/
    echo.
    echo  安装时请勾选 "Add Python to PATH"。
    echo.
    echo  或通过 winget 快速安装:
    echo    winget install Python.Python.3.11
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo    ArtClaw Bridge - Unified Installer v2.1
echo    UE / Maya / Max / Blender / Houdini / SP / SD / ComfyUI
echo  ============================================================
echo.
echo  项目目录: %ROOT_DIR%
echo.

:: ============================================================
:: 平台选择（默认 openclaw）
:: ============================================================
set "PLATFORM=openclaw"
echo  当前平台: openclaw (默认)
echo  支持的平台: openclaw / workbuddy / claude / lobster
echo.
set /p PLATFORM_INPUT="  更改平台? (直接回车使用默认): "
if not "%PLATFORM_INPUT%"=="" (
    if /I "%PLATFORM_INPUT%"=="openclaw" set "PLATFORM=openclaw"
    if /I "%PLATFORM_INPUT%"=="workbuddy" set "PLATFORM=workbuddy"
    if /I "%PLATFORM_INPUT%"=="claude" set "PLATFORM=claude"
    if /I "%PLATFORM_INPUT%"=="lobster" set "PLATFORM=lobster"
    if /I not "%PLATFORM_INPUT%"=="openclaw" if /I not "%PLATFORM_INPUT%"=="workbuddy" if /I not "%PLATFORM_INPUT%"=="claude" if /I not "%PLATFORM_INPUT%"=="lobster" (
        echo [警告] 未知平台: %PLATFORM_INPUT%，使用默认 openclaw
        set "PLATFORM=openclaw"
    )
)
set "PLATFORM_SRC=%ROOT_DIR%\platforms\!PLATFORM!"
set "MCP_BRIDGE_SRC=!PLATFORM_SRC!\gateway"
echo.
echo  选定平台: !PLATFORM!
echo.

:: ============================================================
:: 交互菜单
:: ============================================================
:main_menu
echo  请选择操作:
echo.
echo    [1] 安装 Unreal Engine 插件
echo    [2] 安装 Maya 插件
echo    [3] 安装 3ds Max 插件
echo    [4] 安装 Blender 插件
echo    [5] 安装 Houdini 插件
echo    [6] 安装 Substance Painter 插件
echo    [7] 安装 Substance Designer 插件
echo    [8] 安装 ComfyUI 插件 (含节点包+依赖)
echo    [9] 配置平台 (Gateway + Skills + config)
echo    [T] 安装 Tool Manager 依赖 (Python + Node.js)
echo    [A] 全部安装 (所有 DCC + 平台配置)
echo    [U] 卸载菜单
echo    [0] 退出
echo.
set /p CHOICE="  请输入选项: "

if "%CHOICE%"=="0" goto :exit_ok
if "%CHOICE%"=="1" goto :install_ue
if "%CHOICE%"=="2" goto :install_maya
if "%CHOICE%"=="3" goto :install_max
if "%CHOICE%"=="4" goto :install_blender
if "%CHOICE%"=="5" goto :install_houdini
if "%CHOICE%"=="6" goto :install_sp
if "%CHOICE%"=="7" goto :install_sd
if "%CHOICE%"=="8" goto :install_comfyui
if "%CHOICE%"=="9" goto :install_openclaw
if /I "%CHOICE%"=="T" goto :install_tool_manager_deps
if /I "%CHOICE%"=="A" goto :install_all
if /I "%CHOICE%"=="U" goto :uninstall_menu
echo [错误] 无效选项: %CHOICE%
pause
exit /b 1

:: ============================================================
:: 安装全部
:: ============================================================
:install_all
echo.
echo  ── 全部安装 ────────────────────────────────────────
echo.

set "UE_PROJECT_DIR="
echo  请输入 UE 项目路径 (包含 .uproject 文件的目录，不需要 UE 可留空):
set /p UE_PROJECT_DIR="  > "

set "COMFYUI_PATH="
echo  请输入 ComfyUI 安装目录 (不需要 ComfyUI 可留空):
set /p COMFYUI_PATH="  > "

set "INSTALL_ARGS=--maya --max --blender --houdini --sp --sd --openclaw --platform !PLATFORM! --force"
if not "!UE_PROJECT_DIR!"=="" set "INSTALL_ARGS=!INSTALL_ARGS! --ue --ue-project "!UE_PROJECT_DIR!""
if not "!COMFYUI_PATH!"=="" set "INSTALL_ARGS=!INSTALL_ARGS! --comfyui --comfyui-path "!COMFYUI_PATH!""

where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" !INSTALL_ARGS!
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --all
)
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

:: 委托给 install.py [精细化引用安装: junction/symlink]
echo [安装] 正在安装 UE 插件 (精细引用模式)...
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --ue --ue-project "!UE_PROJECT_DIR!" --platform !PLATFORM! --force
    if !ERRORLEVEL! EQU 0 (
        echo [完成] UE 插件安装成功!
    ) else (
        echo [错误] UE 插件安装失败
    )
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --ue --ue-project "path"
)
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

:: 委托给 install.py [精细化引用安装: junction/symlink]
echo [安装] 正在安装 Maya !MAYA_VER! 插件 (精细引用模式)...
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --maya --maya-version !MAYA_VER! --platform !PLATFORM! --force
    if !ERRORLEVEL! EQU 0 (
        echo [完成] Maya 插件安装成功!
    ) else (
        echo [错误] Maya 插件安装失败
    )
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --maya
)
exit /b 0

:: ============================================================
:: Maya userSetup.py 幂等注入
:: ============================================================
:inject_maya_startup
set "TARGET_DIR=%~1"
set "SETUP_DST=%TARGET_DIR%\userSetup.py"
set "SETUP_SRC=%DCC_BRIDGE_SRC%\maya_setup\userSetup.py"

:: 目标不存在 -> 创建新文件 [带标记块]
if not exist "%SETUP_DST%" (
    echo %INJECT_START%> "%SETUP_DST%"
    type "%SETUP_SRC%" >> "%SETUP_DST%"
    echo.>> "%SETUP_DST%"
    echo %INJECT_END%>> "%SETUP_DST%"
    echo [创建] userSetup.py ^(新建^)
    goto :eof
)

:: 已有标记块 -> 委托给 Python 更新 [bat 不擅长多行替换]
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

:: 检查是否已有 ArtClaw 代码 [非标记版]
findstr /I /C:"artclaw" "%SETUP_DST%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [跳过] userSetup.py 已包含 ArtClaw 代码 ^(非标记块^)，请手动检查
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

:: 检测 locale 目录 [同安装逻辑]
set "MAYA_BASE=%USERPROFILE%\Documents\maya\%MAYA_VER%"
set "MAYA_SCRIPTS=%MAYA_BASE%\scripts"
for /D %%D in ("%MAYA_BASE%\*") do (
    if exist "%%D\scripts\DCCClawBridge" (
        set "MAYA_SCRIPTS=%%D\scripts"
    )
)
set "DCC_DST=%MAYA_SCRIPTS%\DCCClawBridge"

:: 删除 DCCClawBridge 目录
if exist "%DCC_DST%" (
    rmdir /S /Q "%DCC_DST%"
    echo [删除] 已删除: %DCC_DST%
) else (
    echo [跳过] DCCClawBridge 不存在: %DCC_DST%
)

:: 从 userSetup.py 移除 ArtClaw 块 [委托给 install.py]
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%ROOT_DIR%\install.py" --uninstall --maya --maya-version %MAYA_VER% --force 2>nul
    echo [OK] userSetup.py 中的 ArtClaw 代码已清理
) else (
    echo [提示] 请手动编辑 %MAYA_SCRIPTS%\userSetup.py
    echo        删除 "ArtClaw Bridge START" 到 "ArtClaw Bridge END" 之间的内容
)

echo [完成] Maya 插件卸载完成
echo [提示] 平台配置需手动修改（参考 ~/.artclaw/config.json）
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

:: 委托给 install.py [精细化引用安装: junction/symlink]
echo [安装] 正在安装 3ds Max !MAX_VER! 插件 (精细引用模式)...
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --max --max-version !MAX_VER! --platform !PLATFORM! --force
    if !ERRORLEVEL! EQU 0 (
        echo [完成] 3ds Max 插件安装成功!
    ) else (
        echo [错误] 3ds Max 插件安装失败
    )
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --max
)
exit /b 0

:: ============================================================
:: Max startup.py 幂等注入
:: ============================================================
:inject_max_startup
set "STARTUP_DST=%MAX_STARTUP%\artclaw_startup.py"
set "STARTUP_SRC=%DCC_BRIDGE_SRC%\max_setup\startup.py"

:: 目标不存在 -> 创建新文件
if not exist "%STARTUP_DST%" (
    echo %INJECT_START%> "%STARTUP_DST%"
    type "%STARTUP_SRC%" >> "%STARTUP_DST%"
    echo.>> "%STARTUP_DST%"
    echo %INJECT_END%>> "%STARTUP_DST%"
    echo [创建] artclaw_startup.py ^(新建^)
    goto :eof
)

:: 已有标记块 -> 委托给 Python 更新
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

set "MAX_BASE=%LOCALAPPDATA%\Autodesk\3dsMax\%MAX_VER%"
set "MAX_SCRIPTS="
:: 自动检测 locale 目录
for %%L in (CHS ENU JPN KOR FRA DEU) do (
    if exist "%MAX_BASE%\%%L\scripts\DCCClawBridge" (
        if "!MAX_SCRIPTS!"=="" set "MAX_SCRIPTS=%MAX_BASE%\%%L\scripts"
    )
)
if "!MAX_SCRIPTS!"=="" set "MAX_SCRIPTS=%MAX_BASE%\ENU\scripts"
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
echo [提示] 平台配置需手动修改（参考 ~/.artclaw/config.json）
goto :summary

:: ============================================================
:: 安装 Blender 插件 [委托 install.py]
:: ============================================================
:install_blender
call :do_install_blender
goto :summary

:do_install_blender
echo.
echo  -- Blender 插件安装 --
echo.
set "BLENDER_VER=5.1"
echo  请输入 Blender 版本 (默认 5.1):
set /p BLENDER_VER_INPUT="  > "
if not "!BLENDER_VER_INPUT!"=="" set "BLENDER_VER=!BLENDER_VER_INPUT!"
echo [安装] 正在安装 Blender !BLENDER_VER! 插件...
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --blender --blender-version !BLENDER_VER! --platform !PLATFORM! --force
    if !ERRORLEVEL! EQU 0 (
        echo [完成] Blender 插件安装成功!
    ) else (
        echo [错误] Blender 插件安装失败
    )
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --blender
)
exit /b 0

:: ============================================================
:: 安装 Houdini 插件 [委托 install.py]
:: ============================================================
:install_houdini
call :do_install_houdini
goto :summary

:do_install_houdini
echo.
echo  -- Houdini 插件安装 --
echo.
set "HOUDINI_VER=20.5"
echo  请输入 Houdini 版本 (默认 20.5):
set /p HOUDINI_VER_INPUT="  > "
if not "!HOUDINI_VER_INPUT!"=="" set "HOUDINI_VER=!HOUDINI_VER_INPUT!"
echo [安装] 正在安装 Houdini !HOUDINI_VER! 插件...
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --houdini --houdini-version !HOUDINI_VER! --platform !PLATFORM! --force
    if !ERRORLEVEL! EQU 0 (
        echo [完成] Houdini 插件安装成功!
    ) else (
        echo [错误] Houdini 插件安装失败
    )
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --houdini
)
exit /b 0

:: ============================================================
:: 安装 Substance Painter 插件 [委托 install.py]
:: ============================================================
:install_sp
call :do_install_sp
goto :summary

:do_install_sp
echo.
echo  -- Substance Painter 插件安装 --
echo.
echo [安装] 正在安装 Substance Painter 插件...
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --sp --platform !PLATFORM! --force
    if !ERRORLEVEL! EQU 0 (
        echo [完成] Substance Painter 插件安装成功!
    ) else (
        echo [错误] Substance Painter 插件安装失败
    )
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --sp
)
exit /b 0

:: ============================================================
:: 安装 Substance Designer 插件 [委托 install.py]
:: ============================================================
:install_sd
call :do_install_sd
goto :summary

:do_install_sd
echo.
echo  -- Substance Designer 插件安装 --
echo.
echo [安装] 正在安装 Substance Designer 插件...
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --sd --platform !PLATFORM! --force
    if !ERRORLEVEL! EQU 0 (
        echo [完成] Substance Designer 插件安装成功!
    ) else (
        echo [错误] Substance Designer 插件安装失败
    )
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --sd
)
exit /b 0

:: ============================================================
:: 安装 ComfyUI 插件 [委托 install.py]
:: ============================================================
:install_comfyui
call :do_install_comfyui
goto :summary

:do_install_comfyui
echo.
echo  -- ComfyUI 插件安装 --
echo.
set "COMFYUI_PATH="
echo  请输入 ComfyUI 安装目录 (包含 main.py 的目录):
set /p COMFYUI_PATH="  > "
if "!COMFYUI_PATH!"=="" (
    echo [错误] 未输入 ComfyUI 路径
    exit /b 1
)
echo [安装] 正在安装 ComfyUI 插件...
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --comfyui --comfyui-path "!COMFYUI_PATH!" --platform !PLATFORM! --force
    if !ERRORLEVEL! EQU 0 (
        echo [完成] ComfyUI 插件安装成功!
    ) else (
        echo [错误] ComfyUI 插件安装失败
    )
) else (
    echo [错误] 未找到 Python，请手动运行: python install.py --comfyui --comfyui-path "path"
)
exit /b 0

:: ============================================================
:: 卸载菜单
:: ============================================================
:uninstall_menu
echo.
echo  -- 卸载菜单 --
echo.
echo    [1] 卸载 Maya 插件
echo    [2] 卸载 3ds Max 插件
echo    [3] 卸载 UE 插件
echo    [4] 卸载 Blender 插件
echo    [5] 卸载 Houdini 插件
echo    [6] 卸载 Substance Painter 插件
echo    [7] 卸载 Substance Designer 插件
echo    [8] 卸载 ComfyUI 插件
echo    [0] 返回主菜单
echo.
set /p UCHOICE="  请输入选项: "
if "%UCHOICE%"=="0" goto :main_menu_return
if "%UCHOICE%"=="1" goto :uninstall_maya
if "%UCHOICE%"=="2" goto :uninstall_max
if "%UCHOICE%"=="3" goto :uninstall_ue
if "%UCHOICE%"=="4" goto :uninstall_blender_menu
if "%UCHOICE%"=="5" goto :uninstall_houdini_menu
if "%UCHOICE%"=="6" goto :uninstall_sp_menu
if "%UCHOICE%"=="7" goto :uninstall_sd_menu
if "%UCHOICE%"=="8" goto :uninstall_comfyui_menu
echo [错误] 无效选项
goto :uninstall_menu

:main_menu_return
goto :main_menu

:uninstall_blender_menu
echo.
set "BLENDER_VER=5.1"
echo  请输入 Blender 版本 (默认 5.1):
set /p BLENDER_VER_INPUT="  > "
if not "!BLENDER_VER_INPUT!"=="" set "BLENDER_VER=!BLENDER_VER_INPUT!"
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --uninstall --blender --blender-version !BLENDER_VER! --force
) else (
    echo [错误] 未找到 Python
)
goto :summary

:uninstall_houdini_menu
echo.
set "HOUDINI_VER=20.5"
echo  请输入 Houdini 版本 (默认 20.5):
set /p HOUDINI_VER_INPUT="  > "
if not "!HOUDINI_VER_INPUT!"=="" set "HOUDINI_VER=!HOUDINI_VER_INPUT!"
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --uninstall --houdini --houdini-version !HOUDINI_VER! --force
) else (
    echo [错误] 未找到 Python
)
goto :summary

:uninstall_sp_menu
echo.
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --uninstall --sp --force
) else (
    echo [错误] 未找到 Python
)
goto :summary

:uninstall_sd_menu
echo.
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --uninstall --sd --force
) else (
    echo [错误] 未找到 Python
)
goto :summary

:uninstall_comfyui_menu
echo.
set "COMFYUI_PATH="
echo  请输入 ComfyUI 安装目录:
set /p COMFYUI_PATH="  > "
if "!COMFYUI_PATH!"=="" (
    echo [跳过] 未输入路径
    goto :summary
)
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    python "%ROOT_DIR%\install.py" --uninstall --comfyui --comfyui-path "!COMFYUI_PATH!" --force
) else (
    echo [错误] 未找到 Python
)
goto :summary

:: ============================================================
:: 配置 OpenClaw
:: ============================================================
:install_openclaw
call :do_install_openclaw
goto :summary

:do_install_openclaw
echo.
echo  ── 平台配置 (!PLATFORM!) ────────────────────────────
echo.

:: ── 自动检测并安装 OpenClaw 环境 ──
if "!PLATFORM!"=="openclaw" (
    where openclaw >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo [检测] 未找到 OpenClaw，自动安装环境...
        echo.
        where python >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            python "%ROOT_DIR%\scripts\setup_openclaw_env.py"
            if !ERRORLEVEL! NEQ 0 (
                echo [警告] OpenClaw 环境安装未完成，继续配置插件...
            )
        ) else (
            echo [错误] 未找到 Python，无法自动安装 OpenClaw
            echo        请手动安装: npm install -g openclaw
        )
        echo.
    ) else (
        echo [OK] OpenClaw 已安装
    )
)

:: 如果选了不支持的平台，引导安装 OpenClaw
if "!PLATFORM!" NEQ "openclaw" if "!PLATFORM!" NEQ "lobster" (
    echo [提示] 平台 "!PLATFORM!" 不支持完整 Agent 功能
    echo        推荐使用 OpenClaw 作为 Agent 后端
    echo.
    set /p USE_OPENCLAW="  是否安装 OpenClaw? [Y/n]: "
    if /I "!USE_OPENCLAW!" NEQ "n" (
        where python >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            python "%ROOT_DIR%\scripts\setup_openclaw_env.py" --from-platform !PLATFORM!
            if !ERRORLEVEL! EQU 0 (
                set "PLATFORM=openclaw"
                set "PLATFORM_SRC=%ROOT_DIR%\platforms\openclaw"
                set "MCP_BRIDGE_SRC=!PLATFORM_SRC!\gateway"
            )
        ) else (
            echo [错误] 未找到 Python
        )
    )
    echo.
)

:: 复制 mcp-bridge 插件（仅 openclaw 有 gateway）
if "!PLATFORM!"=="openclaw" (
    set "OPENCLAW_EXT=%USERPROFILE%\.openclaw\extensions\mcp-bridge"
    if not exist "%USERPROFILE%\.openclaw\extensions" mkdir "%USERPROFILE%\.openclaw\extensions"
    if not exist "!OPENCLAW_EXT!" mkdir "!OPENCLAW_EXT!"

    echo [复制] mcp-bridge 插件...
    copy /Y "!MCP_BRIDGE_SRC!\index.ts" "!OPENCLAW_EXT!\" >nul
    copy /Y "!MCP_BRIDGE_SRC!\openclaw.plugin.json" "!OPENCLAW_EXT!\" >nul
    echo [OK] mcp-bridge 已复制到: !OPENCLAW_EXT!
) else (
    echo [跳过] 平台 !PLATFORM! 无 Gateway 插件
)

:: 安装 Skills + 写入配置（委托给 install.py，支持完整目录复制）
set "ARTCLAW_CFG_DIR=%USERPROFILE%\.artclaw"
if not exist "%ARTCLAW_CFG_DIR%" mkdir "%ARTCLAW_CFG_DIR%"
echo [配置] 安装 Skills + 写入配置...
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%ROOT_DIR%\install.py" --openclaw --platform !PLATFORM! --force 2>nul
    echo [OK] Skills + 平台配置已完成 ^(platform=!PLATFORM!^)
) else (
    echo [跳过] 未找到 Python，请手动运行: python install.py --openclaw --platform !PLATFORM!
)

echo [完成] 平台配置成功 (!PLATFORM!)!
exit /b 0

:: ============================================================
:: 安装 Tool Manager 依赖
:: ============================================================
:install_tool_manager_deps
echo.
echo  ── Tool Manager 依赖安装 ──────────────────────────────
echo.

set "TM_DIR=%ROOT_DIR%\subprojects\ArtClawToolManager"

:: Python 依赖
echo [1/2] 安装 Python 依赖 (FastAPI, uvicorn, etc.)...
if exist "%TM_DIR%\requirements.txt" (
    python -m pip install -r "%TM_DIR%\requirements.txt" --quiet
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Python 依赖安装完成
    ) else (
        echo [错误] Python 依赖安装失败，请检查 pip 配置
    )
) else (
    echo [错误] 未找到 requirements.txt: %TM_DIR%\requirements.txt
)

echo.

:: Node.js + 前端依赖
echo [2/2] 安装前端依赖 (React, Vite, etc.)...
where node >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [错误] 未检测到 Node.js，前端依赖无法安装
    echo        请安装 Node.js 18+: https://nodejs.org/
    echo        或: winget install OpenJS.NodeJS.LTS
    goto :summary
)

set "TM_WEB_DIR=%TM_DIR%\src\web"
if exist "%TM_WEB_DIR%\package.json" (
    pushd "%TM_WEB_DIR%"
    call npm install --silent
    if !ERRORLEVEL! EQU 0 (
        echo [OK] 前端依赖安装完成
        echo [构建] 正在构建前端静态文件...
        call npm run build
        if !ERRORLEVEL! EQU 0 (
            echo [OK] 前端构建完成
        ) else (
            echo [警告] 前端构建失败，可稍后手动执行: cd %TM_WEB_DIR% ^&^& npm run build
        )
    ) else (
        echo [错误] npm install 失败
    )
    popd
) else (
    echo [错误] 未找到 package.json: %TM_WEB_DIR%\package.json
)

echo.
echo [完成] Tool Manager 依赖安装完成!
echo        启动: start-tool-manager.bat
goto :summary

:: ============================================================
:: 安装总结
:: ============================================================
:summary
echo.
echo  ============================================================
echo    操作完成!
echo  ============================================================
echo.
echo  后续步骤:
echo.
echo    UE:
echo      1. 打开 UE 项目，启用 "UE Claw Bridge" 插件
echo      2. 重启编辑器
echo      3. Window 菜单 -- UE Claw Bridge
echo      4. 输入 /diagnose 验证连接
echo.
echo    Maya:
echo      1. 启动 Maya -- ArtClaw 菜单自动出现
echo      2. ArtClaw -- 打开 Chat Panel
echo      3. 点击 连接 或输入 /connect
echo.
echo    3ds Max:
echo      1. 启动 Max -- ArtClaw 自动加载
echo      2. 菜单栏 -- ArtClaw -- Chat Panel
echo      3. 点击 连接 或输入 /connect
echo.
echo    Blender:
echo      1. Edit -- Preferences -- Add-ons -- 搜索 'ArtClaw'
echo      2. 勾选启用 ArtClaw Bridge 插件
echo      3. 侧栏 (N键) -- ArtClaw -- Start ArtClaw
echo.
echo    Houdini:
echo      1. 创建 Shelf Tool, Script: import houdini_shelf; houdini_shelf.toggle_artclaw()
echo      2. 点击 Shelf 按钮启动
echo.
echo    Substance Painter:
echo      1. 启动 SP -- Python -- 勾选 artclaw_bridge 插件
echo.
echo    Substance Designer:
echo      1. 启动 SD -- 插件自动加载
echo.
echo    ComfyUI:
echo      1. 启动 ComfyUI -- ArtClaw Bridge 自动加载
echo      2. 日志中应出现: ArtClaw: MCP Server started on port 8087
echo      3. 配置 OpenClaw 连接
echo      4. 重启 ComfyUI Desktop 加载额外节点包 (Manager, ControlNet)
echo      5. 如需 PBR 贴图生成，使用 workflow 文件
echo.
echo    平台 (!PLATFORM!):
echo      1. 参考 ~/.artclaw/config.json 确认配置
echo      2. 确认 artclaw-* Skills 已安装
echo.
echo  提示: 更完整的功能 (卸载、跨平台、CLI) 请使用:
echo        python install.py --help
echo.

:exit_ok
pause
exit /b 0
