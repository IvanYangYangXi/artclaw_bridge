# ArtClaw Bridge 快速安装参考

## 前置依赖

桥接脚本需要 Python 3.10+ 和 `websockets` 包：

```bash
pip install websockets
```

验证：
```bash
python -c "import websockets; print('OK', websockets.__version__)"
```

---

## 一键安装

```bash
# 完整安装（Maya + Max + UEClawBridge）
python install.py --maya --max --force

# 安装特定 DCC
python install.py --ue --ue-project "D:\MyProject" --force

# 验证安装
python verify_sync.py
```

---

## LobsterAI MCP 手动配置

> **注意：** 自定义 stdio MCP 配置存储在 LobsterAI 客户端本地数据库，无法通过配置文件自动注入。安装完插件后需在客户端 UI 中手动添加 MCP 服务。

### 方式一：运行配置指南脚本（推荐）

```bash
python platforms\lobster\setup_lobster_mcp.py
```

脚本会自动检测 Python 环境并输出完整的配置步骤，照着填写即可。

### 方式二：手动填写

在 LobsterAI 客户端中操作：
1. 打开 **设置 → MCP 服务**
2. 点击 **「添加 MCP 服务」**
3. 填写以下信息：

#### UE

| 字段 | 值 |
|------|-----|
| 服务名称 | `artclaw-ue` |
| 描述 | ArtClaw UE Editor MCP Bridge |
| 传输类型 | 标准输入输出 (stdio) |
| 命令 | `<你的 Python 路径>`（需已安装 websockets） |
| 参数 | `<ArtClaw目录>\platforms\common\artclaw_stdio_bridge.py --port 8080` |

#### Maya

| 字段 | 值 |
|------|-----|
| 服务名称 | `artclaw-maya` |
| 描述 | ArtClaw Maya MCP Bridge |
| 传输类型 | 标准输入输出 (stdio) |
| 命令 | `<你的 Python 路径>` |
| 参数 | `<ArtClaw目录>\platforms\common\artclaw_stdio_bridge.py --port 8081` |

#### 3ds Max

| 字段 | 值 |
|------|-----|
| 服务名称 | `artclaw-max` |
| 描述 | ArtClaw 3ds Max MCP Bridge |
| 传输类型 | 标准输入输出 (stdio) |
| 命令 | `<你的 Python 路径>` |
| 参数 | `<ArtClaw目录>\platforms\common\artclaw_stdio_bridge.py --port 8082` |

> **关于 `<你的 Python 路径>`：** 必须是已安装 `websockets` 的 Python 解释器。可运行 `python platforms\lobster\setup_lobster_mcp.py` 自动检测。

---

## 验证连接

### UI 验证

配置保存后，在 LobsterAI 聊天中输入：
```
获取 UE 中选中的物体
```
AI 应能调用 `run_ue_python` 并返回选中物体列表。

### 命令行验证

```bash
# 测试 UE（需 UE 运行中）
python tests\test_ue_ws.py --port 8080

# 测试 Maya
python tests\test_ue_ws.py --port 8081

# 测试 Max
python tests\test_ue_ws.py --port 8082
```

---

## MCP 端口映射

| DCC | 端口 |
|-----|------|
| UE | 8080 |
| Maya | 8081 |
| 3ds Max | 8082 |
| Blender | 8083 |
| Houdini | 8084 |
| Substance Painter | 8085 |
| Substance Designer | 8086 |
| ComfyUI | 8087 |

---

## 故障排查

```bash
# 检查端口占用（需 DCC 运行中）
netstat -ano | findstr :8080

# 检查 websockets 是否已安装
python -c "import websockets; print('OK')"

# 安装 websockets
pip install websockets

# 运行完整环境检测 + 配置指南
python platforms\lobster\setup_lobster_mcp.py

# 直接测试 WebSocket 连接
python tests\test_ue_ws.py --port 8080

# 重新安装 DCC 插件
python install.py --ue --ue-project "D:\MyProject" --force
```

---

## 已知问题

### websockets 未安装

```
ModuleNotFoundError: No module named 'websockets'
```

**解决：**
```bash
pip install websockets
```

如果默认 `python` 的 pip 不可用，找一个有 pip 的系统 Python 安装，然后把 LobsterAI MCP 配置中的「命令」改为该 Python 的完整路径。

### reasoning_content 400 错误

```
The reasoning_content in the thinking mode must be passed back to the API
```

**解决：** 关闭 reasoning/thinking 模式，或重建新对话。

---

## 配置文件位置

| 内容 | 路径 |
|------|------|
| OpenClaw 网关配置 | `%APPDATA%\LobsterAI\openclaw\state\openclaw.json` |
| LobsterAI Skills | `%APPDATA%\LobsterAI\SKILLs\` |
| ArtClaw Bridge 根目录 | 本仓库根目录 |

---

## 安装命令参考

```bash
# 只安装 Maya 插件
python install.py --maya --force

# 安装 UE + Maya + Max 插件
python install.py --ue --ue-project "D:\MyProject" --maya --max --force

# 卸载所有
python install.py --uninstall --all

# 修复文件同步
python verify_sync.py --fix
```
