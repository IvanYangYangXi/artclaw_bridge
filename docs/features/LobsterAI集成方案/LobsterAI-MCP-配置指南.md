# LobsterAI MCP 配置指南

**日期**: 2026-04-03  
**状态**: ✅ 已验证通过  
**配置方式**: stdio 桥接模式

---

## 前置条件

1. **UE 已启动且 UEClawBridge 插件已启用**
   - UE MCP Server 会自动监听 `ws://127.0.0.1:8080`

2. **LobsterAI 客户端已安装**

---

## 配置步骤（通过 LobsterAI 客户端界面）

### 步骤 1：打开 LobsterAI MCP 管理界面

1. 打开 LobsterAI 客户端
2. 进入 **设置** → **MCP 服务**（或类似菜单）
3. 点击 **添加 MCP 服务** 或 **编辑现有服务**

### 步骤 2：配置 ArtClaw MCP Server

根据截图，正确的配置如下：

| 字段 | 值 | 说明 |
|------|-----|------|
| **服务名称** | `artclaw-ue` | 自定义，建议用此名称 |
| **描述** | `UE Editor MCP Server` | 可选 |
| **传输类型** | **标准输入输出 (stdio)** | ⚠️ 关键：使用 stdio 桥接 |
| **命令** | `python` | ⚠️ 运行桥接脚本的系统 Python |
| **参数** | `D:\MyProject_D\artclaw_bridge\platforms\claude\artclaw_stdio_bridge.py --port 8080` | 桥接脚本路径 + 端口 |
| **环境变量** | （可选） | 如需要可添加 |

**配置说明（重要）**：

1. **工作流程**：
   ```
   LobsterAI 客户端
     ↓ stdio (MCP 协议)
   artclaw_stdio_bridge.py (桥接脚本，由系统 Python 运行)
     ↓ WebSocket (ws://127.0.0.1:8080)
   UE MCP Server (UEClawBridge 插件，在 UE 内部运行)
     ↓
   执行 Python 代码（使用 UE 内置 Python 环境）
   ```

2. **关键说明**：
   - **`命令：python`**：运行桥接脚本的 Python 解释器（**系统 Python**）
   - **桥接脚本作用**：只是协议转换器（stdio ↔ WebSocket），**不执行 Python 代码**
   - **真正执行 UE Python 的地方**：UE MCP Server（在 UE Editor 进程内部，使用 UE 内置 Python）

3. **传输类型选择 stdio**：
   - LobsterAI 通过 stdio 调用桥接脚本
   - 桥接脚本将 stdio 转换为 WebSocket
   - WebSocket 连接到 UE MCP Server（端口 8080）

4. **参数说明**：
   - `D:\MyProject_D\artclaw_bridge\platforms\claude\artclaw_stdio_bridge.py`：桥接脚本路径
   - `--port 8080`：指定 UE MCP Server 的 WebSocket 端口

5. **路径注意**：
   - 如果你的路径不同，请修改为实际路径
   - 确保路径中使用双反斜杠 `\\` 或正斜杠 `/`

6. **前提条件**：
   - ✅ 系统已安装 Python（能运行桥接脚本）
   - ✅ UE 已启动且 UEClawBridge 插件已启用
   - ✅ 桥接脚本已安装 `websockets` 库（`pip install websockets`）

### 步骤 3：保存配置

1. 点击 **保存** 按钮
2. 等待服务状态变为 **已连接**（可能需要几秒）
3. 在 LobsterAI 的工具列表中查看是否出现 `run_ue_python`

### 步骤 4：重启 LobsterAI（如需要）

如果保存后工具未立即出现：
1. 完全退出 LobsterAI 客户端（包括系统托盘图标）
2. 等待 3 秒
3. 重新启动 LobsterAI

### 步骤 5：测试配置

在 LobsterAI 聊天中发送：
```
使用 run_ue_python 执行：print("Hello from ArtClaw!")
```

预期结果：
```
Hello from ArtClaw!
```

---

## 配置原理

```
LobsterAI 客户端
  ↓ stdio
artclaw_stdio_bridge.py
  ↓ WebSocket (ws://127.0.0.1:8080)
UE MCP Server (UEClawBridge 插件)
  ↓
run_ue_python 工具
```

**工作流程**：
1. LobsterAI 通过 stdio 调用 `artclaw_stdio_bridge.py`
2. 桥接脚本启动并建立 WebSocket 连接到 UE
3. LobsterAI 发送 MCP 请求（如 `tools/list`）
4. 桥接脚本转发请求到 UE MCP Server
5. UE 返回工具列表（包括 `run_ue_python`）
6. LobsterAI 注册工具，用户可以使用

---

## 验证配置

### 前置验证（配置前必做）

```powershell
# 1. 验证系统 Python 可用（用于运行桥接脚本）
python --version

# 2. 验证桥接脚本可运行
python D:\MyProject_D\artclaw_bridge\platforms\claude\artclaw_stdio_bridge.py --help

# 3. 验证 UE MCP Server 已启动
netstat -ano | FindStr ":8080"
# 应显示：TCP 127.0.0.1:8080 LISTENING
```

### 方法 1：检查工具列表

在 LobsterAI 中查看可用工具，应该包含：
- `run_ue_python` - 在 UE 中执行 Python 代码

### 方法 2：测试简单命令

```
使用 run_ue_python 执行：print("Test")
```

预期输出：
```
Test
```

### 方法 3：测试 UE API（验证 UE 内置 Python 环境）

```
使用 run_ue_python 执行：
import unreal
world = unreal.EditorLevelLibrary.get_editor_world()
print(f"当前关卡：{world.get_path_name()}")
```

预期输出：
```
当前关卡：/Game/Maps/xxx
```

> ⚠️ 如果能成功导入 `unreal` 模块，说明代码确实是在 UE 内置 Python 环境中执行的（系统 Python 没有 unreal 模块）

### 方法 4：检查日志

```powershell
# 查看 LobsterAI 日志
Get-Content "$env:APPDATA\LobsterAI\openclaw\logs\gateway.log" -Tail 50 | Select-String "artclaw|mcp"

# 查看桥接脚本日志（stderr）
# 桥接脚本会将日志输出到 stderr，可在 LobsterAI 客户端控制台查看
```

---

## 常见问题

### Q1: 工具未出现

**可能原因**：
- 配置未保存成功
- LobsterAI 未重启
- 桥接脚本路径错误

**解决方法**：
1. 检查配置是否正确保存
2. 完全重启 LobsterAI
3. 确认桥接脚本路径正确

### Q2: 执行失败 "command not found" 或 "python 不是内部命令"

**原因**：系统找不到 `python` 命令

**解决方法**：
1. 使用 Python 完整路径，如：
   ```
   命令：C:\Python39\python.exe
   参数：D:\MyProject_D\artclaw_bridge\platforms\claude\artclaw_stdio_bridge.py --port 8080
   ```
2. 或将 Python 添加到系统 PATH

### Q3: UE 未响应

**原因**：UE 未启动或 UEClawBridge 插件未启用

**解决方法**：
1. 启动 UE Editor
2. 确认 UEClawBridge 插件已启用
3. 检查 UE 输出日志，确认 MCP Server 已启动

### Q4: 连接超时

**原因**：桥接脚本无法连接到 UE MCP Server

**解决方法**：
1. 确认 UE 已启动
2. 检查端口 8080 是否被占用：
   ```powershell
   netstat -ano | FindStr ":8080"
   ```
3. 确认防火墙未阻止连接

### Q5: 配置被还原

**原因**：LobsterAI 可能有配置同步机制

**解决方法**：
1. 确保通过 LobsterAI 客户端界面配置
2. 不要直接编辑 `openclaw.json`
3. 配置后完全退出 LobsterAI 再重启

---

## Maya/Max 配置（可选）

### Maya MCP Server

| 字段 | 值 |
|------|-----|
| 服务名称 | `artclaw-maya` |
| 传输类型 | stdio |
| 命令 | `python` |
| 参数 | `D:\MyProject_D\artclaw_bridge\platforms\claude\artclaw_stdio_bridge.py --port 8081` |

### 3ds Max MCP Server

| 字段 | 值 |
|------|-----|
| 服务名称 | `artclaw-max` |
| 传输类型 | stdio |
| 命令 | `python` |
| 参数 | `D:\MyProject_D\artclaw_bridge\platforms\claude\artclaw_stdio_bridge.py --port 8082` |

---

## 参考

- 桥接脚本：[`D:\MyProject_D\artclaw_bridge\platforms\claude\artclaw_stdio_bridge.py`](file:///D:/MyProject_D/artclaw_bridge/platforms/common/artclaw_stdio_bridge.py)
- LobsterAI 配置指南：[`LobsterAI 平台接入方案.md`](file:///D:/MyProject_D/artclaw_bridge/docs/features/LobsterAI平台接入方案.md)
- Phase 10 诊断：[`Phase 10 问题诊断与修正方案.md`](file:///D:/MyProject_D/artclaw_bridge/docs/features/Phase 10 问题诊断与修正方案.md)
