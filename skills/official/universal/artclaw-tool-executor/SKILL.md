---
name: artclaw-tool-executor
description: "ArtClaw Tool Executor - 执行 ArtClaw Tool Manager 中的工具。当用户请求运行工具时，根据工具类型选择正确的执行方式。"
metadata:
  artclaw:
    version: 1.0.0
    author: ArtClaw
    target-dccs: []
    source: official
---

# ArtClaw Tool Executor

当用户在 ArtClaw Tool Manager 中点击「运行」或发送 `/run tool:{id}` 时激活。

## 触发条件

消息包含以下任一特征：
- `请帮我运行工具` + `[当前正在配置 Tool: ...]`
- `/run tool:{id}`
- 用户明确要求执行某个 ArtClaw 工具

## 核心规则

### 1. 获取工具详情

先通过 Tool Manager API 获取工具信息：

```python
import requests, json
resp = requests.get("http://localhost:9876/api/v1/tools/{tool_id_url_encoded}")
tool = resp.json()["data"]
manifest = tool["manifest"]
impl_type = manifest["implementation"]["type"]  # script / skill_wrapper / composite
target_dccs = manifest.get("targetDCCs", [])
agent_hint = manifest.get("agentHint", "")
```

### 2. 遵循 Manifest 范式

每个工具的 manifest.json 定义了完整的执行契约，Agent 必须遵循：

#### 参数校验（inputs）
- **required=true** 的参数必须有值才能执行，不能跳过
- **type** 决定了参数类型：`string/number/boolean/select/image/object/array`
- **select** 类型的值必须在 `options` 列表范围内
- **number** 类型需检查 `min`/`max` 范围
- 参数名/id 必须与 manifest 一致，不能自行编造参数名

#### agentHint（AI 执行指引）
如果 manifest 中有 `agentHint` 字段，**优先遵循其指引**。它可能包含：
- 指定的 API 端点
- 禁止执行的命令
- 特殊的执行注意事项

#### 筛选条件（defaultFilters）
如果 manifest 有 `defaultFilters`，工具执行范围受此约束：
- `path[].pattern` 定义了文件路径 glob 规则（支持 `$project_root` 等变量）
- Agent 不应超出筛选范围执行操作

#### 触发规则（triggers）
Manifest 中的 `triggers` 定义自动触发场景，Agent 不需要手动处理（由 Trigger Engine 管理），但应了解工具的触发上下文以便在对话中解释。

### 3. 根据类型选择执行方式

| 条件 | 执行方式 |
|------|----------|
| `impl_type == "script"` 且 `targetDCCs` 为空或仅含 `"general"` | **调用 execute API**（本地执行） |
| `impl_type == "script"` 且 `targetDCCs` 含真实 DCC | **调用 execute API**（DCC 执行） |
| `impl_type == "skill_wrapper"` | **在对话中引导**：读取被包装的 Skill，按 Skill 指引操作 |
| `impl_type == "composite"` | **在对话中引导**：按管线顺序执行各子工具 |

### DCC MCP Tool Name

当 Agent 需要直接在 DCC 中执行代码时（如 skill_wrapper 执行），必须使用正确的 MCP tool name：

| DCC | MCP Tool Name |
|-----|--------------|
| `ue5` | `run_ue_python`（⚠️ 不是 `run_python`！） |
| 其他所有 DCC | `run_python` |

### 3. 调用 Execute API（推荐方式）

```python
import requests, json, urllib.parse

tool_id = "official/artclaw-skill-compliance-checker"  # 示例
encoded_id = urllib.parse.quote(tool_id, safe="")
params = {"key": "value"}  # 用户填写的参数

resp = requests.post(
    f"http://localhost:9876/api/v1/tools/{encoded_id}/execute",
    json={"parameters": params},
    timeout=120
)
result = resp.json()
```

**用 exec 工具执行**（Agent 没有 requests 时的替代方案）：
```bash
curl -s -X POST "http://localhost:9876/api/v1/tools/{encoded_id}/execute" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {}}'
```

### 4. 结果处理

Execute API 返回格式：
```json
{
  "success": true,
  "data": {
    "action": "executed",
    "exit_code": 0,
    "stdout": "...",
    "stderr": "...",
    "success": true
  }
}
```

- `exit_code == 0` 且 `success == true`：执行成功，向用户展示 stdout 结果
- `exit_code != 0`：执行失败，展示 stderr 错误信息
- 如果 stdout 包含 JSON，解析后格式化展示

### 5. 参数处理

当消息中包含 `<!--artclaw:params {...}-->` 格式时：
- 这是**前端参数表单的回填指令**，Agent 可以在回复末尾附带此标签来帮用户预填参数
- 用户说"执行"/"运行"时，使用消息中的 `当前参数值` 作为实际参数调用 API
- 用户说"帮我填参数"时，用 `<!--artclaw:params {...}-->` 回填，**不要执行**

### 6. agentHint

如果 manifest 中有 `agentHint` 字段，**优先遵循其指引**。它可能包含：
- 指定的 API 端点
- 禁止执行的命令
- 特殊的执行注意事项

## 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `DCC_NOT_CONNECTED` | 工具需要 DCC 但未连接 | 提示用户启动对应 DCC |
| `ENTRY_NOT_FOUND` | 脚本文件缺失 | 检查 tool_path 目录 |
| `EXECUTION_TIMEOUT` | 脚本超时（120s） | 建议用户检查脚本逻辑 |
| `TOOL_NOT_FOUND` | tool_id 错误 | 检查 URL 编码是否正确 |

## ⛔ 禁止事项

- **禁止编造执行结果** — 必须实际调用 API，不能凭记忆回复
- **禁止直接运行 `openclaw skills check`** — 用 Tool Manager API
- **禁止在 DCC 未连接时假装执行成功**
