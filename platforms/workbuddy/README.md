# WorkBuddy 平台适配

ArtClaw Bridge 的 WorkBuddy (CodeBuddy) 平台适配。通过 stdio→WebSocket 桥接器，让 WorkBuddy 能调用 DCC (UE/Maya/Max/Blender/Houdini/SP/SD/ComfyUI) 的 MCP 工具。

## ⚠️ 接入模式限制

WorkBuddy 是 **MCP-only** 模式，仅支持工具调用，**不支持 DCC 内嵌聊天面板**。

| 能力 | WorkBuddy | OpenClaw / LobsterAI |
|------|-----------|---------------------|
| 工具调用（run_python 等） | ✅ 通过 MCP stdio bridge | ✅ 通过 WebSocket MCP |
| DCC 内嵌聊天面板 | ❌ 不支持 | ✅ 支持 |
| AI 多轮对话操作 DCC | ❌ 仅在 WorkBuddy 编辑器内对话 | ✅ DCC 内直接对话 |
| Skill 上下文注入 | ❌ 无（WorkBuddy 不读 SKILL.md） | ✅ OpenClaw 自动加载 |
| Agent 切换 | ❌ 用 WorkBuddy 自带模型 | ✅ 可选多个 Agent |
| 消息历史/会话管理 | ❌ WorkBuddy 自行管理 | ✅ Gateway 统一管理 |
| 停止/取消请求 | ❌ 不可从 DCC 侧控制 | ✅ DCC 面板可停止 |

### 适用场景

- 已在 WorkBuddy 中编写代码，顺手调用 DCC 执行脚本
- 不需要 DCC 内嵌 AI 聊天面板
- 仅需简单的工具调用（如批量处理资产、查询场景信息）

### 推荐

如需完整的 AI + DCC 交互体验（内嵌聊天面板、Skill 自动加载、多轮对话操作 DCC），建议使用带 Gateway 的平台：**OpenClaw** 或 **LobsterAI**。

## 架构

```
WorkBuddy (stdio MCP Client)
  └── artclaw_stdio_bridge.py (stdio→WebSocket bridge)
        └── DCC MCP Server (port 8080-8087)
```

WorkBuddy 使用自己的 AI 模型，MCP 仅提供工具调用能力。
DCC 端的 AI 聊天面板无法与 WorkBuddy 的 AI 通信。

## 快速配置

### 手动编辑配置文件

编辑 `~/.workbuddy/mcp.json`，参考 `config/workbuddy-config-snippet.json`，将 `${ARTCLAW_BRIDGE_ROOT}` 替换为实际路径。

> **注意**：配置应写入 `mcp.json`，而不是 `config.json`。

## 配置文件示例

```json
{
  "mcpServers": {
    "artclaw-ue": {
      "command": "python",
      "args": ["D:/MyProject/artclaw_bridge/platforms/common/artclaw_stdio_bridge.py", "--port", "8080"]
    }
  }
}
```

## DCC 端口映射

| DCC 软件 | 端口 | MCP Server 名称 |
|----------|------|-----------------|
| Unreal Engine | 8080 | artclaw-ue |
| Maya | 8081 | artclaw-maya |
| 3ds Max | 8082 | artclaw-max |
| Blender | 8083 | artclaw-blender |
| Houdini | 8084 | artclaw-houdini |
| Substance Painter | 8085 | artclaw-sp |
| Substance Designer | 8086 | artclaw-sd |
| ComfyUI | 8087 | artclaw-comfyui |

## 文件说明

| 文件 | 说明 |
|------|------|
| `workbuddy_adapter.py` | WorkBuddy 平台适配器 |
| `config/workbuddy-config-snippet.json` | MCP 配置模板 |
