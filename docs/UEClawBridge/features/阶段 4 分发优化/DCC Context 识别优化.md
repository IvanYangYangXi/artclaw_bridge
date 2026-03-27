# DCC Context 识别优化

> 版本: v1.0 | 日期: 2026-03-28 | 状态: 设计完成

## 问题描述

当 UE 和 Maya 的 Bridge 同时连接到同一个 OpenClaw Gateway 时，AI Agent 可能在 UE 对话中错误地调用 Maya 的 MCP 工具（`mcp_maya-primary_run_python`），尽管 DCC Context 已正确注入"用户正在 Unreal Engine 编辑器中与你对话"。

### 复现路径

1. UE 和 Maya 同时启动，两个 Bridge 都连接到 Gateway
2. 在 UE 面板中发送消息，DCC Context 正确标注 UE
3. AI Agent 忽略 DCC Context，调用了 `mcp_maya-primary_run_python` 的 `get_context: true`
4. 返回 Maya 的上下文信息，AI 误认为"当前连接的是 Maya"

### 根因分析

1. **弱模型不稳定**: kimi-k2.5 等非顶级模型对 DCC Context 的遵循度不够高
2. **DCC Context 提示词不够强**: 当前仅用 `[DCC Context]` 前缀，缺乏强制约束
3. **缺少负面约束**: 没有明确说"不要调用其他软件的工具，除非用户明确要求"

## 修复方案

### 方案 A: 强化 DCC Context 提示词 (Python)

修改 `openclaw_bridge.py` 的 `_enrich_with_briefing()` 和 `bridge_dcc.py` 的 `_enrich_with_briefing()`：

**旧提示词**:
```
[DCC Context] 用户正在 Unreal Engine 编辑器中与你对话。
当前软件的工具前缀为 mcp_ue-editor-agent_，应优先使用这些工具。
如需操作其他软件，可使用对应前缀的工具：mcp_maya-primary_（Maya）、mcp_max-primary_（Max）。
```

**新提示词**:
```
[DCC Context - 重要]
当前对话环境: Unreal Engine 编辑器
必须使用的工具前缀: mcp_ue-editor-agent_

⚠️ 约束规则:
1. 所有操作默认使用 mcp_ue-editor-agent_ 前缀的工具
2. 不要调用其他软件的工具（mcp_maya-primary_、mcp_max-primary_），除非用户明确要求操作其他软件
3. 如果需要获取编辑器上下文，使用 mcp_ue-editor-agent_run_ue_python 的 get_context=true
```

### 方案 B: 跨 DCC 工具互斥提示

在提示词中加入互斥警告：当检测到多个 DCC 同时在线时，明确标注当前对话绑定的 DCC。

### 涉及文件

| 文件 | 修改内容 |
|------|----------|
| `openclaw_bridge.py` | 强化 `_enrich_with_briefing()` 的 DCC Context 提示词 |
| `bridge_dcc.py` | 同步强化 DCC Context 提示词模板 |

### 不需要修改的

- `bridge_core.py`: 事件过滤已通过 `_active_run_id` 正确工作
- C++ 侧: 无需改动

## 测试验证

1. UE + Maya 同时连接，在 UE 面板中发送"获取编辑器上下文"
2. 验证 AI 调用 `mcp_ue-editor-agent_run_ue_python` 而非 `mcp_maya-primary_run_python`
3. 在 UE 面板中发送"查看 Maya 场景"，验证 AI 此时正确使用 Maya 工具
