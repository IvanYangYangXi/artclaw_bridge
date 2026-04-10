# 创建 ArtClaw Tool Manager 快捷方式的 PowerShell 脚本
# 运行方式: 右键 -> 使用 PowerShell 运行

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$PSScriptRoot\ArtClawToolManager.lnk")

# 目标: 启动脚本
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-WindowStyle Hidden -ExecutionPolicy Bypass -Command `"& '$PSScriptRoot\src\server\start_server.ps1'`""

# 工作目录
$Shortcut.WorkingDirectory = "$PSScriptRoot"

# 图标 (使用系统图标或自定义图标)
$Shortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,14"

# 描述
$Shortcut.Description = "ArtClaw Tool Manager - 统一工具管理器"

# 保存
$Shortcut.Save()

Write-Host "快捷方式已创建: ArtClawToolManager.lnk" -ForegroundColor Green
Write-Host "双击快捷方式即可启动 Tool Manager" -ForegroundColor Yellow

# 可选: 创建桌面快捷方式
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$DesktopShortcut = $WshShell.CreateShortcut("$DesktopPath\ArtClawToolManager.lnk")
$DesktopShortcut.TargetPath = "$PSScriptRoot\ArtClawToolManager.lnk"
$DesktopShortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,14"
$DesktopShortcut.Description = "ArtClaw Tool Manager - 统一工具管理器"
$DesktopShortcut.Save()

Write-Host "桌面快捷方式也已创建" -ForegroundColor Green

pause
