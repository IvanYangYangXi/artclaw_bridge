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

## AI 运行指南

### 参数预处理

AI 在调用工具 Execute API 前，应按以下规则预处理参数：

#### 路径格式转换

| DCC | 正确格式 | 示例 | 常见错误 |
|-----|----------|------|----------|
| UE | `/Game/路径/资产名`（不含 `.uasset`） | `/Game/Props/SM_Chair` | `D:\Project\Content\Props\SM_Chair.uasset` |
| Blender | 对象 name（唯一标识） | `Cube.001` | `bpy.data.objects["Cube"]` |
| Maya | DAG 路径或短名 | `\|group1\|pCube1` | — |

**AI 应做的事**:
- UE 磁盘路径 → 转为 `/Game/...` 格式（去掉 `Content/` 前缀和 `.uasset` 后缀）
- UE 路径含 `.ObjectName` 后缀（如 `/Game/.../MI_Foo.MI_Foo`）→ 去掉 `.ObjectName`
- 用户给相对路径 → 提示需要完整路径

#### 多目标输入

| 场景 | AI 应做的事 |
|------|------------|
| 用户用换行分隔多个路径 | 转换为逗号分隔 |
| 用户说"选中的 XX" | 告知工具会自动读取选中对象，无需手动填路径 |
| 用户说"文件夹下所有 XX" | 如工具不支持目录扫描，提示先选中资产或列出路径 |

#### 类型转换

| 场景 | AI 应做的事 |
|------|------------|
| number 参数但用户给文字 | 转换（如 "一千" → 1000） |
| boolean 参数但用户说 "是/否" | 转换为 true/false |
| select 参数但用户值不在 options 里 | 列出可选项供选择 |

### 批处理策略

#### 判断规则

| manifest 特征 | 策略 |
|---------------|------|
| 有路径参数且 description 含"逗号分隔" | 工具自带批处理 → 一次传入多个 |
| 路径参数不支持多值 | AI 需循环调用 → 每次传一个 |
| `defaultFilters.typeFilter.source == "selection"` | 提示用户先选中目标 |
| `defaultFilters.typeFilter.source == "parameter"` | 必须手动传入路径 |

#### 判断示例

```json
// ✅ 工具自带批处理（参数支持逗号分隔）
{
  "id": "mesh_paths",
  "description": "Mesh 资产路径，多个用逗号分隔",
  "type": "string"
}
// → AI 一次传入所有路径

// ❌ 工具不支持批处理（单路径参数）
{
  "id": "material_instance_path",
  "description": "材质实例 UE 路径",
  "type": "string"
}
// → AI 如需处理多个，循环调用
```

### 运行结果解读

#### 标准返回字段

| 字段 | 含义 | AI 应展示 |
|------|------|-----------|
| `success: true` + `message` | 成功 | 展示 message |
| `success: true` + `data` | 成功 | 格式化 data 中关键信息 |
| `success: false` + `error` | 失败 | 展示 error + 建议修复方案 |
| `dry_run: true` | 预演模式 | 展示 report，告知未实际执行 |
| `modified_assets: [...]` | 已修改资产列表 | 提醒用户保存 |

#### 常见错误处理

| error | 含义 | AI 建议 |
|-------|------|---------|
| `NO_INPUT` | 未指定目标且无选中 | "请在 Content Browser 中选中要处理的资产" |
| `DCC_NOT_CONNECTED` | DCC 未连接 | "请先打开 UE/Maya 并启动 ArtClaw Bridge 插件" |
| `EXECUTION_TIMEOUT` | 超时 | "处理数据量可能过大，建议减少处理数量" |
| `MISSING_INPUT` | 必填参数缺失 | 列出缺失参数名 |

### 执行前检查清单

AI 在调用 Execute API 前应完成：

1. ✅ 所有 `required=true` 参数有值
2. ✅ `select` 类型参数值在 `options` 范围内
3. ✅ `number` 类型参数值在 `min`/`max` 范围内
4. ✅ 路径格式符合目标 DCC 规范
5. ✅ 如有 `agentHint`，已阅读并遵循
6. ✅ `dry_run` 参数已确认（首次建议 true 预览）

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
