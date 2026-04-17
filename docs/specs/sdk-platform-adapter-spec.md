<!-- Ref: docs/specs/sdk-platform-adapter-spec.md -->
# 平台适配器标准化规范

> 定义 AI Agent 平台适配器的统一接口，为接入新平台提供明确的接入标准。
> 索引文档：[SDK/API 标准化总览](./sdk-api-standardization-overview.md)

## 概述

ArtClaw Bridge 通过平台适配器连接不同的 AI Agent 平台。每个平台的通信协议不同，
但对 DCC 侧暴露的接口应当统一。

### 已接入平台

| 平台 | 连接方式 | 状态 | 实现位置 |
|------|---------|------|---------|
| OpenClaw | WebSocket RPC | ✅ 生产 | `platforms/openclaw/` |
| LobsterAI | WebSocket RPC（同 OpenClaw） | ✅ 已验证 | 共用 OpenClaw 适配器 |
| Claude Desktop | stdio MCP (通过 bridge) | 🧪 POC | `platforms/claude/` |

## P1 — PlatformAdapter 抽象基类

### 当前问题

**不存在抽象基类**。OpenClaw 直接实现，Claude 仅有 config 桩。
新平台接入需要复制粘贴 `openclaw_chat.py` 并大量修改。

### 标准化方案

在 `core/interfaces/platform_adapter.py` 中定义：

```python
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator

class PlatformAdapter(ABC):
    """AI Agent 平台适配器抽象基类。
    每个 AI 平台（OpenClaw, Claude, Cursor 等）实现此接口。"""

    # --- P2: 连接管理 ---
    @abstractmethod
    def connect(self, gateway_url: str, token: str, **kwargs) -> bool:
        """建立与平台的连接"""

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接"""

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""

    # --- P3: 消息发送 ---
    @abstractmethod
    def send_message(self, message: str, timeout: float = 1800.0) -> str:
        """同步发送消息并等待完整回复"""

    @abstractmethod
    def send_message_async(self, message: str, callback: Callable[[str], None]) -> None:
        """异步发送消息，通过回调接收回复"""

    @abstractmethod
    def cancel_current_request(self) -> None:
        """取消当前进行中的请求"""

    # --- P5: 会话管理 ---
    @abstractmethod
    def reset_session(self) -> None:
        """重置当前会话"""

    @abstractmethod
    def set_session_key(self, key: str) -> None:
        """设置会话 key"""

    @abstractmethod
    def get_session_key(self) -> str:
        """获取当前会话 key"""

    # --- P7: 诊断 ---
    @abstractmethod
    def diagnose_connection(self, gateway_url: str) -> str:
        """诊断到指定网关 URL 的连接状况，返回格式化报告"""

    # --- P6: Agent 管理（可选） ---
    def list_agents(self) -> list[dict]:
        """列出可用的 AI Agent（不是所有平台都有此概念）
        返回: [{"id": str, "name": str, "emoji": str}]"""
        return []

    def set_agent(self, agent_id: str) -> None:
        """切换当前 Agent"""
        pass

    def fetch_history(self, session_key: str, limit: int = 50) -> list[dict]:
        """获取会话历史"""
        return []

    # --- 生命周期 ---
    def shutdown(self) -> None:
        """关闭适配器，释放资源"""
        self.disconnect()
```

## P4 — 流事件格式 StreamEvent

### 标准 JSONL Schema

DCC 侧读取 stream 文件时，每行一个 JSON 事件：

```python
# 事件类型枚举
EVENT_TYPES = {
    "delta",        # 增量文本
    "tool_call",    # AI 发起工具调用
    "tool_result",  # 工具调用结果
    "final",        # 完整响应
    "error",        # 错误
    "session_key",  # 会话 key 确认
    "usage",        # Token 用量
}
```

### 事件格式

```json
{"type": "delta", "text": "增量文本内容"}
{"type": "tool_call", "tool_name": "run_python", "tool_id": "tc_01", "arguments": {}}
{"type": "tool_result", "tool_id": "tc_01", "content": "结果", "is_error": false}
{"type": "final", "text": "完整响应文本"}
{"type": "error", "text": "[Error] 错误描述"}
{"type": "session_key", "key": "agent:qi:abc123"}
{"type": "usage", "input_tokens": 1500, "output_tokens": 800}
```

## P8 — 平台配置 Schema

### 统一配置结构 (`~/.artclaw/config.json`)

```json
{
  "platform": {
    "type": "openclaw",
    "gateway_url": "ws://127.0.0.1:18789",
    "token": "..."
  },
  "mcp": {
    "config_path": "~/.openclaw/openclaw.json",
    "config_key": "mcp.servers"
  },
  "skills": {
    "installed_path": "~/.openclaw/skills"
  },
  "disabled_skills": [],
  "pinned_skills": []
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `platform.type` | string | 平台类型，如 `"openclaw"`、`"claude"` |
| `platform.gateway_url` | string | WebSocket 网关 URL（stdio 平台留空） |
| `platform.token` | string | 认证令牌 |
| `mcp.config_path` | string | MCP 配置文件绝对路径 |
| `mcp.config_key` | string | 配置文件内 MCP servers 的 JSON 键路径 |
| `skills.installed_path` | string | Skill 安装目录路径 |
| `disabled_skills` | string[] | 被禁用的 Skill 名称列表（默认空数组） |
| `pinned_skills` | string[] | 被置顶的 Skill 名称列表，优先注入上下文（默认空数组） |

> 📎 **完整字段定义**请参考 `docs/specs/sdk-core-api-spec.md` C2 节，
> 包括 `last_agent_id` 等附加字段的说明及读写规范。

### 平台注册表 (`_PLATFORM_DEFAULTS`)

新平台接入时需在 `core/bridge_config.py` 中注册：

```python
_PLATFORM_DEFAULTS = {
    "openclaw": {
        "gateway_url": "ws://127.0.0.1:18789",
        "mcp_config_path": "~/.openclaw/openclaw.json",
        "mcp_config_key": "mcp.servers",
        "skills_path": "~/.openclaw/skills",
    },
    "claude": {
        "gateway_url": "",  # Claude 无 WebSocket 网关
        "mcp_config_path": "~/.claude/config.json",
        "mcp_config_key": "mcpServers",
        "skills_path": "~/.openclaw/skills",
    },
    # 新平台在此注册...
}
```

## P9 — MCP Tool 命名空间规范

### 命名规则

Gateway 将 DCC MCP 工具映射为平台工具时，使用以下命名：

```
mcp_{server-name}_{tool-name}
```

| 示例 | 说明 |
|------|------|
| `mcp_ue-editor_run_python` | UE 编辑器的 run_python 工具 |
| `mcp_maya-primary_run_python` | Maya 的 run_python 工具 |
| `mcp_comfyui_run_python` | ComfyUI 的 run_python 工具 |

### server-name 约定

| DCC | server-name |
|-----|-------------|
| UE | `ue-editor` |
| Maya | `maya-primary` |
| Max | `max-primary` |
| Blender | `blender-primary` |
| Houdini | `houdini-primary` |
| SP | `sp-primary` |
| SD | `sd-primary` |
| ComfyUI | `comfyui` |

## P10 — 文件协议路径规范

### 当前问题

文件名硬编码为 `_openclaw_*`，不适用于其他平台。

### 标准化方案

改为平台无关的命名，从配置读取：

| 用途 | 当前文件名 | 标准文件名 |
|------|-----------|-----------|
| 消息输入 | `_openclaw_msg_input.txt` | `_artclaw_msg_input.txt` |
| 流式输出 | `_openclaw_response_stream.jsonl` | `_artclaw_stream.jsonl` |
| 最终响应 | `_openclaw_response.txt` | `_artclaw_response.txt` |
| 连接状态 | `_bridge_status.json` | `_artclaw_status.json` |
| Token 用量 | `_session_usage.json` | `_artclaw_usage.json` |

## P11 — Gateway 插件接口规范

### 插件职责

1. 连接 DCC MCP Server（WebSocket）
2. 发现并注册 MCP 工具到平台
3. 处理工具调用转发
4. 管理重连与心跳

### 核心接口（TypeScript）

```typescript
interface GatewayPlugin {
  // 连接 MCP Server
  connect(serverName: string, url: string): Promise<void>;
  // 发现工具列表
  discoverTools(serverName: string): Promise<Tool[]>;
  // 调用工具
  callTool(serverName: string, toolName: string, args: any): Promise<any>;
  // 断开连接
  disconnect(serverName: string): void;
}
```

### 重连策略

- 指数退避：3s → 6s → 12s → 最大 30s
- 无限重试（DCC 可能晚启动）
- 心跳间隔：15s
- 重连时自动重新发现工具

## 新平台接入 Checklist

接入新 AI 平台时，需完成以下步骤：

1. **创建适配器目录** `platforms/{platform}/`
2. **实现 `PlatformAdapter`** 的 8 个必需方法 + 可选方法
3. **注册平台默认值** 在 `core/bridge_config.py._PLATFORM_DEFAULTS`
4. **创建配置脚本** `setup_{platform}_config.py`
5. **创建诊断模块** `{platform}_diagnose.py`
6. **（如有 Gateway）实现 Gateway 插件**
7. **（如无 WebSocket）使用 `artclaw_stdio_bridge.py`**
8. **添加配置模板** `platforms/{platform}/config/`
9. **编写接入文档** `platforms/{platform}/README.md`
10. **更新安装脚本** `install_platform.py`

## 参考实现

| 平台 | 适配器文件 | 状态 |
|------|----------|------|
| OpenClaw | `platforms/openclaw/openclaw_adapter.py` | ✅ 完整实现 |
| Claude Desktop | `platforms/claude/claude_adapter.py` | 🔴 POC 桩，待实现 |

创建新平台适配器时，请继承 `core/interfaces/platform_adapter.py` 中的 `PlatformAdapter` 基类，
并参考 `platforms/openclaw/openclaw_adapter.py` 的实现方式（委托模式）。

平台适配器工厂：`platforms/common/adapter_factory.py`
- 使用 `create_adapter("openclaw", ...)` 创建适配器实例
- 使用 `list_platforms()` 获取所有支持的平台列表
