@echo off
setlocal enabledelayedexpansion

echo ========================================
echo UE Editor Agent 自动化测试脚本
echo 版本: 1.0.0-alpha
echo 测试日期: 2026-03-15
echo ========================================
echo.

:: 配置路径
set PROJECT_PATH=D:\MyProject\ArtClaw\subprojects\UEDAgentProj
set PROJECT_FILE=%PROJECT_PATH%\UEDAgentProj.uproject
set PLUGIN_PATH=%PROJECT_PATH%\Plugins\UEEditorAgent
set UE_ENGINE_PATH=C:\Program Files\Epic Games\UE_5.3
set UBT_PATH=%UE_ENGINE_PATH%\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe

echo [1] 检查环境配置...
echo ========================================

:: 检查UE引擎
if not exist "%UE_ENGINE_PATH%" (
    echo [错误] 未找到UE引擎: %UE_ENGINE_PATH%
    echo 请确认UE 5.3+已安装
    goto :error
)
echo [成功] 找到UE引擎: %UE_ENGINE_PATH%

:: 检查项目文件
if not exist "%PROJECT_FILE%" (
    echo [错误] 未找到项目文件: %PROJECT_FILE%
    goto :error
)
echo [成功] 找到项目文件: %PROJECT_FILE%

:: 检查插件文件
if not exist "%PLUGIN_PATH%" (
    echo [错误] 未找到插件目录: %PLUGIN_PATH%
    goto :error
)
echo [成功] 找到插件目录: %PLUGIN_PATH%

:: 检查关键源文件
set FILES_TO_CHECK=^
%PLUGIN_PATH%\Source\UEEditorAgent\Public\UEAgentSubsystem.h;^n%PLUGIN_PATH%\Source\UEEditorAgent\Private\UEEditorAgent.cpp;^n%PLUGIN_PATH%\Content\Python\mcp_server.py;^n%PLUGIN_PATH%\Content\Python\init_unreal.py

(for %%F in ("%FILES_TO_CHECK:;=\" "}") do (
    if not exist "%%~F" (
        echo [错误] 缺少文件: %%~F
        goto :error
    ) else (
        echo [成功] 找到文件: %%~nxF
    )
))

echo.
echo [2] 检查端口占用...
echo ========================================

:: 检查8080端口
netstat -ano | findstr ":8080" >nul
if %ERRORLEVEL% equ 0 (
    echo [警告] 端口8080已被占用
    echo 将自动切换到其他端口
) else (
    echo [信息] 端口8080可用
)

echo.
echo [3] 准备启动UE编辑器...
echo ========================================
echo 项目: %PROJECT_FILE%
echo 引擎: %UE_ENGINE_PATH%
echo.
echo 重要提示:
echo - 请确保Visual Studio 2022已安装
echo - 首次编译可能需要5-15分钟
echo - 请耐心等待编译完成
echo.

:: 询问是否继续
set /p CONFIRM="是否继续启动UE编辑器? (y/n): "
if /i not "%CONFIRM%"=="y" goto :end

echo.
echo [4] 启动UE编辑器...
echo ========================================
echo 正在启动: %PROJECT_FILE%
echo 请观察Output Log中的日志输出...
echo.

:: 启动UE项目
start "" "%PROJECT_FILE%"

:: 等待编辑器启动
timeout /t 10 /nobreak >nul

echo.
echo [5] 检查启动状态...
echo ========================================

:: 检查进程
tasklist | findstr /i "UnrealEditor" >nul
if %ERRORLEVEL% equ 0 (
    echo [成功] UE编辑器进程已启动
) else (
    echo [警告] 未检测到UE编辑器进程，可能仍在启动中
)

echo.
echo ========================================
echo 启动完成！
echo ========================================
echo.
echo 下一步操作:
echo 1. 等待UE编辑器完全启动
echo 2. 检查Output Log中的日志
echo 3. 查看工具栏是否出现Agent按钮
echo 4. 按照测试指南执行功能测试
echo.
echo 日志文件位置:
echo %LOCALAPPDATA%\UnrealEngine\5.3\Saved\Logs\UEDAgentProj.log
echo.
goto :end

:error
echo.
echo ========================================
echo [错误] 测试准备失败
echo ========================================
echo 请解决上述错误后重试
echo.
exit /b 1

:end
echo.
echo 按任意键退出...
pause >nul
exit /b 0
