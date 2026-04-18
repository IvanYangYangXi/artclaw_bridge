# ArtClaw Bridge 快速安装参考

## 一键安装命令

### LobsterAI 用户

```bash
# 完整安装（Maya + Max + LobsterAI 配置）
python install.py --maya --max --openclaw --platform lobster --force

# 验证 MCP 配置
python platforms\lobster\setup_lobster_config.py --status

# 重启 LobsterAI 后测试连接
```

### OpenClaw 用户

```bash
# 完整安装（Maya + Max + OpenClaw 配置）
python install.py --maya --max --openclaw --force

# 验证 MCP 配置
python platforms\openclaw\setup_openclaw_config.py --status

# 重启 Gateway
openclaw gateway restart
```

## 常用安装组合

```bash
# 只安装 Maya
python install.py --maya --openclaw --platform lobster --force

# 安装 Maya + Max
python install.py --maya --max --openclaw --platform lobster --force

# 安装 UE + Maya + Max
python install.py --ue --ue-project "C:\MyProject" --maya --max --openclaw --platform lobster --force

# 安装所有 DCC
python install.py --all --ue-project "C:\MyProject" --comfyui-path "C:\ComfyUI" --openclaw --platform lobster --force
```

## 平台配置命令

### LobsterAI

```bash
# 查看 MCP 配置状态
python platforms\lobster\setup_lobster_config.py --status

# 添加 MCP Servers
python platforms\lobster\setup_lobster_config.py --ue --maya --max

# 移除 MCP 配置
python platforms\lobster\setup_lobster_config.py --remove
```

### OpenClaw

```bash
# 查看 MCP 配置状态
python platforms\openclaw\setup_openclaw_config.py --status

# 添加 MCP Servers
python platforms\openclaw\setup_openclaw_config.py --ue --maya --max

# 移除 MCP 配置
python platforms\openclaw\setup_openclaw_config.py --remove
```

## 验证命令

```bash
# 验证文件同步
python verify_sync.py

# 修复文件同步
python verify_sync.py --fix

# 检查 LobsterAI 配置
python platforms\lobster\setup_lobster_config.py --status

# 检查 OpenClaw 配置
python platforms\openclaw\setup_openclaw_config.py --status
```

## 卸载命令

```bash
# 卸载 Maya 插件
python install.py --uninstall --maya

# 卸载所有 DCC 插件
python install.py --uninstall --all

# 移除 MCP 配置
python platforms\lobster\setup_lobster_config.py --remove
```

## 配置文件位置

| 平台 | 配置文件路径 |
|------|-------------|
| LobsterAI | `%APPDATA%\LobsterAI\openclaw\state\openclaw.json` |
| OpenClaw | `~/.openclaw/openclaw.json` |
| ArtClaw 全局 | `~/.artclaw/config.json` |

## MCP 端口映射

| DCC | 端口 |
|-----|------|
| UE | 8080 |
| Maya | 8081 |
| Max | 8082 |
| Blender | 8083 |
| Houdini | 8084 |
| SP | 8085 |
| SD | 8086 |
| ComfyUI | 8087 |

## 故障排查

```bash
# 检查端口占用
netstat -ano | findstr :8080

# 检查 Python 是否可用
python --version

# 检查桥接脚本是否存在
python -c "from pathlib import Path; print(Path('platforms/common/artclaw_stdio_bridge.py').exists())"

# 重新安装 Skills
python install.py --openclaw --platform lobster --force
```

## 帮助命令

```bash
# 查看 install.py 帮助
python install.py --help

# 查看 LobsterAI 配置脚本帮助
python platforms\lobster\setup_lobster_config.py --help

# 查看 OpenClaw 配置脚本帮助
python platforms\openclaw\setup_openclaw_config.py --help
```
