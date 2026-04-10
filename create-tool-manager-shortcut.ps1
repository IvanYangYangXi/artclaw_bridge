# 创建 ArtClaw Tool Manager 桌面快捷方式
# 将此脚本放在 ArtClaw Bridge 根目录运行

$WshShell = New-Object -comObject WScript.Shell

# 项目路径
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolManagerPath = Join-Path $ProjectDir "subprojects\ArtClawToolManager"
$StartBatPath = Join-Path $ToolManagerPath "start.bat"

# 检查子项目是否存在
if (-not (Test-Path $ToolManagerPath)) {
    Write-Host "错误: 未找到 ArtClawToolManager 子项目" -ForegroundColor Red
    Write-Host "请确保此脚本放在 ArtClaw Bridge 根目录" -ForegroundColor Yellow
    pause
    exit 1
}

# 创建根目录快捷方式
$RootShortcut = $WshShell.CreateShortcut("$ProjectDir\ArtClawToolManager.lnk")
$RootShortcut.TargetPath = $StartBatPath
$RootShortcut.WorkingDirectory = $ToolManagerPath
$RootShortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,14"
$RootShortcut.Description = "ArtClaw Tool Manager - 统一工具管理器"
$RootShortcut.Save()

Write-Host "✅ 已创建快捷方式: ArtClawToolManager.lnk" -ForegroundColor Green

# 创建桌面快捷方式
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$DesktopShortcut = $WshShell.CreateShortcut("$DesktopPath\ArtClaw Tool Manager.lnk")
$DesktopShortcut.TargetPath = $StartBatPath
$DesktopShortcut.WorkingDirectory = $ToolManagerPath
$DesktopShortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,14"
$DesktopShortcut.Description = "ArtClaw Tool Manager - 统一工具管理器"
$DesktopShortcut.Save()

Write-Host "✅ 已创建桌面快捷方式: ArtClaw Tool Manager.lnk" -ForegroundColor Green
Write-Host ""
Write-Host "使用说明:" -ForegroundColor Cyan
Write-Host "  1. 双击快捷方式启动 Tool Manager" -ForegroundColor White
Write-Host "  2. 浏览器会自动打开 http://localhost:9876" -ForegroundColor White
Write-Host "  3. 按任意键关闭服务" -ForegroundColor White
Write-Host ""

pause
