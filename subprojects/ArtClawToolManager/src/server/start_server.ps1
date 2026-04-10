# 启动 ArtClaw Tool Manager Server
# 此脚本由快捷方式调用

$ErrorActionPreference = "Stop"

# 切换到脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

# 检查虚拟环境
if (-not (Test-Path "venv")) {
    Write-Host "创建虚拟环境..." -ForegroundColor Yellow
    python -m venv venv
}

# 激活虚拟环境
& "venv\Scripts\Activate.ps1"

# 安装依赖
Write-Host "检查依赖..." -ForegroundColor Yellow
pip install -q -r requirements.txt

# 启动服务器
Write-Host "启动 ArtClaw Tool Manager Server..." -ForegroundColor Green
Write-Host "访问: http://localhost:9876" -ForegroundColor Cyan

python -m src.server.main
