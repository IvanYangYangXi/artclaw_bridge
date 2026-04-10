@echo off
chcp 65001 >nul
title ArtClaw Tool Manager

echo ==========================================
echo    ArtClaw Tool Manager 启动器
echo ==========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

:: 检查依赖
echo [1/3] 检查依赖...
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -q -r requirements.txt

:: 启动后端
echo [2/3] 启动后端服务...
start "ArtClaw Tool Manager Server" cmd /k "call venv\Scripts\activate.bat && python -m src.server.main"

:: 等待后端启动
timeout /t 3 /nobreak >nul

:: 打开浏览器
echo [3/3] 打开浏览器...
start http://localhost:9876

echo.
echo ==========================================
echo    ArtClaw Tool Manager 已启动
echo    访问: http://localhost:9876
echo ==========================================
echo.
echo 按任意键关闭服务...
pause >nul

:: 关闭后端
taskkill /FI "WINDOWTITLE eq ArtClaw Tool Manager Server" /F >nul 2>&1

echo 服务已关闭
