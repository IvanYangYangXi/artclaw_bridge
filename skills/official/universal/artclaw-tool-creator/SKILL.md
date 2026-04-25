---
name: artclaw-tool-creator
description: "ArtClaw Tool Creator - AI 引导创建自定义 DCC 工具。支持三种创建方式：包装 Skill、编写脚本、组合工具。"
metadata:
  artclaw:
    version: 1.1.0
    author: ArtClaw
    target-dccs: []
    source: official
---

# ArtClaw Tool Creator

AI 引导创建自定义 DCC 工具的特殊 Skill。用户通过对话界面完成工具创建流程。

## 触发条件

- **命令触发**：用户在 ArtClaw Tool Manager 对话面板中输入 `/create tool` 
- **UI 触发**：用户点击工具管理器页面的"创建工具"按钮自动发送命令

## 创建流程状态机

```
start → select_method → collect_info → generate → preview → confirm → save → complete
```

### 流程说明

1. **start**: 初始状态，展示创建方式选择
2. **select_method**: 用户选择创建方式（包装 Skill / 编写脚本 / 组合工具）
3. **collect_info**: 根据选择方式收集必要信息
4. **generate**: 生成 manifest.json 和脚本文件
5. **preview**: 展示预览，用户确认或修改
6. **confirm**: 用户确认保存
7. **save**: 写入文件到 `~/.artclaw/tools/user/{tool-name}/`
8. **complete**: 创建完成

## 三种创建方式

### 1. 包装 Skill (skill_wrapper)

将现有 Skill 包装为固定参数的快捷工具。

**对话模板**：
```
Agent: 选择要包装的 Skill：
[列出可用 Skills，如：comfyui-txt2img, maya-operation-rules, 等]

用户: comfyui-txt2img

Agent: 该 Skill 有以下参数：prompt, width, height, steps, sampler
暴露哪些参数给用户？其他参数的固定值？

用户: 只暴露 prompt 和 steps，width/height 固定为 1024，sampler 固定为 euler

Agent: [生成预览] 确认创建工具"快速文生图"？
[保存] [修改] [取消]
```

**生成的 manifest.json 结构**：
```json
{
  "id": "user/{tool-name}",
  "implementation": {
    "type": "skill_wrapper",
    "skill": "comfyui-txt2img",
    "fixedParams": { "width": 1024, "height": 1024, "sampler": "euler" }
  },
  "inputs": [
    { "id": "prompt", "name": "提示词", "type": "string", "required": true },
    { "id": "steps", "name": "采样步数", "type": "number", "default": 20 }
  ]
}
```

### 2. 编写脚本 (script)

使用 DCC 原生 Python API 创建自定义脚本工具。

> ⛔ **禁止使用 `artclaw_sdk`** — 该模块尚未实现，导入会直接报错。所有脚本必须使用 DCC 原生 API。

**对话模板**：
```
Agent: 请描述工具功能：

用户: 批量导出选中模型为 FBX，支持指定导出路径和文件前缀

Agent: 需要哪些参数？
- 导出路径（必需）
- 文件前缀（可选，默认为空）
- 包含动画（可选，默认 false）

用户: 是的

Agent: [生成脚本预览] 确认创建工具？
[保存] [修改] [取消]
```

**生成的脚本必须遵循以下规则**：

- MUST 优先使用 `artclaw_sdk` 统一 API（参数解析、对象筛选、结果上报）
- 对于 `artclaw_sdk` 不覆盖的 DCC 专有操作，使用原生 API（UE: `import unreal`，Maya: `import maya.cmds`，Blender: `import bpy`）
- ⛔ MUST NOT `import subprocess` — 会被 UE 安全扫描器拦截
- MUST 入口函数使用 `**kwargs` 签名（Tool Manager 通过 keyword arguments 调用）
- MUST 返回 dict 结果（`{"success": True/False, ...}`）
- 可以使用 `PIL`/`Pillow`（UE Python 环境已内置）
- 可以使用 `os`, `json`, `math` 等标准库（除 subprocess）
- 如果工具有筛选条件需求，优先使用 `artclaw_sdk.filters` 和 manifest 的 `defaultFilters` 机制
- 如果工具有参数校验需求，优先使用 `artclaw_sdk.params.parse_params(manifest_inputs, raw_params)`

**脚本模板**：
```python
"""
工具名称
工具描述（一行）。
"""
import os
import json

# artclaw_sdk: 参数解析 + 对象筛选 + 结果上报
from artclaw_sdk import params, filters, result, context
# DCC 原生 API（按需导入）
# import unreal  # UE
# import maya.cmds as cmds  # Maya
# import bpy  # Blender


def _helper_function():
    """内部辅助函数。"""
    pass


def main_function(**kwargs):
    """入口函数。kwargs 由 Tool Manager 传入。"""
    # 参数解析（自动类型转换 + required 校验）
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    parsed = params.parse_params(manifest.get("inputs", []), kwargs)
    
    param1 = parsed.get("param1", "")
    dry_run = parsed.get("dry_run", False)

    # 对象筛选（如果工具有筛选需求）
    # selected = context.get_selected()
    # meshes = filters.filter_by_type(selected, "MESH")

    # ... 业务逻辑 ...

    return {"success": True, "message": "完成", "data": {...}}
```

### 3. 组合工具 (composite)

将多个现有工具串联成管线。

**对话模板**：
```
Agent: 选择要组合的工具：
[列出已有工具]

用户: 先运行"命名检查"，通过后运行"批量导出 FBX"

Agent: 确认管线流程：
命名检查 → (通过) → 批量导出 FBX

参数映射建议：
- 命名检查.prefix → 批量导出.file_prefix

[保存] [修改] [取消]
```

## manifest.json Schema

核心字段定义：

```json
{
  "id": "user/{tool-name}",
  "name": "工具显示名称",
  "description": "工具描述",
  "version": "1.0.0",
  "author": "创建者名称",
  "createdAt": "2026-04-13 21:00:00",
  "updatedAt": "2026-04-13 21:00:00",
  "targetDCCs": [],
  
  "implementation": {
    "type": "script|skill_wrapper|composite",
    "entry": "main.py",
    "function": "main_function",
    "skill": null,
    "aiPrompt": "AI 执行提示词"
  },
  
  "inputs": [...],
  "outputs": [...],
  "triggers": [],
  "presets": []
}
```

### 触发规则范式（triggers）

`triggers` 数组定义工具的自动触发规则。触发类型有三种：`event`（DCC事件）、`schedule`（定时）、`watch`（文件监听）。

> ⚠️ **不支持 manual 类型**：手动执行直接点"运行"按钮即可，不需要创建触发规则。

#### 工具级默认筛选条件（defaultFilters）

manifest 顶层支持 `defaultFilters` 字段，定义工具级的统一筛选条件。**脚本运行时从此处读取路径范围**。

```json
{
  "defaultFilters": {
    "path": [
      { "pattern": "$project_root/tools/**/*" },
      { "pattern": "$tools_dir/**/*" }
    ]
  }
}
```

触发规则通过 `useDefaultFilters` 选择继承或自定义：
- `useDefaultFilters: true` → 继承工具默认筛选（filters 可为空 `{}`）
- `useDefaultFilters: false`（或省略）→ 使用触发规则自定义的 filters

#### watch 类型 — 路径统一走 filters.path

watch trigger **不含 `paths` 字段**。监听路径统一写在 `filters.path` 中，使用 `$variable` 路径变量。

```json
{
  "id": "on-file-change",
  "name": "文件变化时运行",
  "enabled": true,
  "trigger": {
    "type": "watch",
    "events": ["created", "modified"],
    "debounceMs": 3000
  },
  "useDefaultFilters": true,
  "filters": {},
  "execution": { "mode": "notify", "timeout": 30 }
}
```

自定义精细过滤时设 `useDefaultFilters: false`：

```json
{
  "id": "on-json-change",
  "useDefaultFilters": false,
  "filters": {
    "path": [{ "pattern": "$tools_dir/**/*.json" }]
  }
}
```

⛔ **禁止**：`trigger.paths`（旧字段，已废弃）
✅ **正确**：`useDefaultFilters: true` 或 `filters.path` + `$variable` 前缀

#### 可用路径变量

| 变量 | 解析值 | 说明 |
|------|--------|------|
| `$skills_installed` | `~/.openclaw/workspace/skills` | 已安装 Skill 目录 |
| `$project_root` | config.json → project_root | 项目源码根目录 |
| `$tools_dir` | `~/.artclaw/tools` | 工具存储目录 |
| `$home` | 用户主目录 | — |

#### ⛔ filters.path 语法限制

路径 pattern 使用标准 **fnmatch/gitignore glob** 语法，**不支持 bash 花括号扩展**。

| 写法 | 是否合法 |
|------|---------|
| `$skills_installed/**/*.md` | ✅ |
| `$skills_installed/**/*.py` | ✅ |
| `$skills_installed/**/*.{py,md,json}` | ❌ 花括号不支持，watch 将静默失效 |

多扩展名必须**拆为多条独立 pattern**，每个扩展名单独一行：
```json
"path": [
  { "pattern": "$skills_installed/**/*.py" },
  { "pattern": "$skills_installed/**/*.md" },
  { "pattern": "$skills_installed/**/*.json" }
]
```

**工具合规检查器会将花括号语法标记为 error 级别问题。**

#### event 类型 — dcc 必须匹配 targetDCCs

```json
{
  "trigger": { "type": "event", "dcc": "maya", "event": "file.save", "timing": "post" }
}
```

- event trigger 的 `dcc` 必须在 `targetDCCs` 范围内
- `targetDCCs` 为 `[]`（通用工具）时**不能用** event trigger（没有绑定的 DCC）
- `targetDCCs` 为 `["general"]` 时**不能用** event trigger

#### schedule 类型

```json
{
  "trigger": { "type": "schedule", "mode": "interval", "interval": 1800000 }
}
```

支持 `interval`（毫秒间隔）、`cron`（表达式）、`once`（一次性）。

#### 脚本读取 defaultFilters

工具脚本**不硬编码路径**，从自身 manifest 的 `defaultFilters.path` 读取扫描范围：

```python
import json
from pathlib import Path

def _get_scan_dirs():
    manifest = json.loads((Path(__file__).parent / "manifest.json").read_text())
    default_filters = manifest.get("defaultFilters", {})
    dirs = []
    for pf in default_filters.get("path", []):
        base = pf["pattern"].split("/**")[0]
        # 解析 $variable → 实际路径
        resolved = _resolve_variable(base)
        if resolved: dirs.append(resolved)
    return dirs or [default_dir]
```

#### 脚本中的对象筛选（artclaw_sdk.filters + manifest 联动）

当工具需要在 DCC 场景中筛选对象时，**优先使用 `artclaw_sdk.filters`**，而不是硬编码筛选逻辑。manifest 中 `defaultFilters.typeFilter.types` 定义的类型列表可直接传给 SDK：

```python
import json, os
from artclaw_sdk import filters, context

# 从 manifest 读取类型筛选
manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

type_filter = manifest.get("defaultFilters", {}).get("typeFilter", {}).get("types", [])
selected = context.get_selected()

if type_filter:
    matched = filters.filter_by_type(selected, type_filter)
else:
    matched = selected  # 无类型筛选，全选

# 可叠加 name/path 筛选
name_rules = manifest.get("defaultFilters", {}).get("sceneRules", [])
for rule in name_rules:
    matched = filters.filter_by_name(matched, rule["pattern"], use_regex=rule.get("isRegex", False))
```

**关键原则**：筛选逻辑来自 manifest `defaultFilters`，不是脚本硬编码。用户通过 Tool Manager UI 修改筛选条件后，脚本行为自动跟随变化。

### targetDCCs 推断规则

`targetDCCs` 表示工具适用的 DCC 范围。**AI 必须根据工具功能自动推断，不要让用户手动选择。**

| 场景 | targetDCCs 值 | 示例 |
|------|--------------|------|
| 不涉及任何 DCC API 的通用工具 | `[]`（空数组） | 获取时间、文件处理、数据转换 |
| 使用 artclaw_sdk 跨 DCC 通用 API | `[]`（空数组） | 批量重命名（sdk.rename_object）|
| 仅适用于特定 DCC | `["maya"]` 等 | Maya MEL 命令封装 |
| 适用于多个但非全部 DCC | `["maya", "blender"]` 等 | 仅支持部分 DCC 的导出格式 |

**推断原则**：
- 不调用任何 DCC API → `[]`
- 只用 `artclaw_sdk` 通用 API → `[]`
- 用了 DCC 专有 API（如 `cmds.*`, `bpy.*`, `unreal.*`）→ 写对应的 DCC
- **skill_wrapper 类型**：继承被包装 Skill 的 `target-dccs`；如果 Skill 的 target-dccs 为空或包含所有 DCC，则设为 `[]`
- **composite 类型**：取所有子工具 `targetDCCs` 的交集；如果有任一子工具为 `[]`（通用），该子工具不限制交集

**有效的 DCC 标识符**：`ue5`, `maya`, `max`, `blender`, `comfyui`, `substance-designer`, `substance-painter`, `houdini`

### DCC MCP Tool Name 映射

不同 DCC 的 MCP 执行工具名称不同，生成脚本或 AI 执行时必须使用正确的 tool name：

| DCC | MCP Tool Name | 说明 |
|-----|--------------|------|
| `ue5` | `run_ue_python` | UE 专用，注意不是 run_python |
| `maya` | `run_python` | — |
| `max` | `run_python` | — |
| `blender` | `run_python` | — |
| `comfyui` | `run_python` | — |
| `substance-designer` | `run_python` | — |
| `substance-painter` | `run_python` | — |
| `houdini` | `run_python` | — |

> ⛔ **常见错误**：对 UE 工具使用 `run_python` 会报 `Unknown tool: run_python`。UE 的 MCP tool 名是 `run_ue_python`。

### inputs 参数类型

| type | 说明 | 额外字段 |
|------|------|----------|
| `string` | 文本输入 | `multiline`, `placeholder` |
| `number` | 数值输入 | `min`, `max`, `step` |
| `boolean` | 勾选框 | — |
| `select` | 下拉选择 | `options`（字符串数组，必填） |
| `image` | 图片上传 | — |
| `file` | 文件路径选择 | — |

> **注意**：下拉选择统一使用 `select`，不要用 `enum`。

## 验证清单

保存前必须验证：

- [ ] manifest.json 包含所有必需字段（id, name, implementation.type）
- [ ] targetDCCs 已按推断规则正确设置（通用工具为 `[]`，非通用列出具体 DCC）
- [ ] 脚本优先使用 `artclaw_sdk`（params 解析、filters 筛选、result 上报）
- [ ] 脚本 DCC 专有操作使用原生 API（UE: `unreal`，Maya: `maya.cmds`，Blender: `bpy`）
- [ ] ⛔ 脚本不包含 `import subprocess`（UE 安全扫描器会拦截）
- [ ] 入口函数使用 `**kwargs` 签名（不是 `raw_params` 或固定参数名）
- [ ] 入口函数返回 dict（`{"success": True/False, ...}`）
- [ ] 脚本使用 DCC 原生 API（UE: `unreal`，Maya: `maya.cmds`，Blender: `bpy`）
- [ ] 参数类型有效（string/number/boolean/select/file）
- [ ] implementation.type 匹配创建方式
- [ ] 触发规则合规：
  - [ ] 不含 `manual` 类型（手动执行不需要触发规则）
  - [ ] watch trigger 不含 `trigger.paths`，路径走 `filters.path` + `$variable` 或 `useDefaultFilters: true`
  - [ ] watch trigger 使用 `useDefaultFilters: true` 时工具必须有 `defaultFilters.path`
  - [ ] **filters.path pattern 无花括号语法**（`*.{py,md}` 是错的，必须拆为多条）
  - [ ] event trigger 的 `dcc` 在 `targetDCCs` 范围内
  - [ ] `targetDCCs=[]` 的通用工具不使用 event trigger
  - [ ] 每个 trigger 有 `id`（用于去重同步）

## 前端-Agent 交互协议

使用结构化消息与前端 UI 通信：

```typescript
// Agent → 前端：方法选择
{
  type: 'tool_creator.select_method',
  methods: ['skill_wrapper', 'script', 'composite']
}

// Agent → 前端：工具预览
{
  type: 'tool_creator.preview',
  manifest: { /* manifest.json 内容 */ },
  script?: "// 生成的脚本内容（仅 script 类型）",
  actions: ['save', 'modify', 'cancel']
}

// 前端 → Agent：用户确认
{
  type: 'tool_creator.confirm',
  action: 'save' | 'modify' | 'cancel'
}
```

## 工具存储架构

```
工具分三层，存储位置不同：

官方工具:   {project_root}/tools/official/{dcc}/{tool-name}/
市集工具:   {project_root}/tools/marketplace/{dcc}/{tool-name}/
用户工具:   ~/.artclaw/tools/user/{tool-name}/   ← AI 只能创建这一层
```

**重要限制**：
- AI 引导创建的工具**只能**写入 `~/.artclaw/tools/user/{tool-name}/`
- 官方和市集工具位于项目源码目录，**不由 Agent 直接创建**
- `id` 字段固定为 `"user/{tool-name}"`（小写 kebab-case）

## 文件输出

**保存路径**：`~/.artclaw/tools/user/{tool-name}/`（仅在发布前的编辑/测试阶段）

> 发布（publish）后工具会移入 `{project_root}/tools/{target}/{dcc}/` 源码目录，本地 user 副本自动删除。

**文件结构**：
```
{tool-name}/
├── manifest.json    # 工具定义
└── main.py         # 脚本文件（仅 script 类型）
```

## 实现说明

1. **状态管理**：使用对话上下文维护创建流程状态
2. **输入验证**：每个阶段验证用户输入的有效性
3. **错误处理**：提供清晰的错误信息和修正建议
4. **代码生成**：基于 artclaw_sdk 模板生成符合规范的脚本
5. **预览确认**：展示最终结果前让用户确认

## artclaw_sdk 速查

SDK 位于 `core/artclaw_sdk/`，自动检测当前 DCC 环境，提供跨平台统一 API。

### 参数解析
```python
from artclaw_sdk import params
# 根据 manifest inputs 定义自动校验+类型转换
parsed = params.parse_params(manifest_inputs, raw_kwargs)
# 获取默认值
defaults = params.get_default_values(manifest_inputs)
```

### 对象筛选
```python
from artclaw_sdk import filters, context
selected = context.get_selected()
# 按类型筛选
meshes = filters.filter_by_type(selected, ["MESH", "StaticMesh"])
# 按名称 pattern 筛选
matched = filters.filter_by_name(selected, "SM_Wall_*", use_regex=False)
# 按路径 pattern 筛选
found = filters.filter_by_path(selected, "/Game/Props/.*", use_regex=True)
# 组合筛选
result = filters.filter_objects(selected, type="MESH", name_pattern="SM_*")
```

### 结果上报
```python
from artclaw_sdk import result
result.success(data={"count": 10})
result.error("操作失败: xxx")
```

### 进度条
```python
from artclaw_sdk import progress
progress.start(total=100, label="处理中...")
progress.update(50, "已完成一半")
progress.finish()
```

## DCC 原生 API 快速参考（artclaw_sdk 不覆盖时使用）

### UE (targetDCCs: ["ue5"])
```python
import unreal
mesh = unreal.load_asset('/Game/Path/Mesh')
md = mesh.get_static_mesh_description(0)
unreal.EditorAssetLibrary.save_asset('/Game/Path/Asset')
```

### Maya (targetDCCs: ["maya"])
```python
import maya.cmds as cmds
selected = cmds.ls(selection=True)
```

### Blender (targetDCCs: ["blender"])
```python
import bpy
selected = bpy.context.selected_objects
```

> 对于 artclaw_sdk 可覆盖的操作（选中对象、类型筛选、参数解析），优先用 SDK。对于 DCC 专有操作（如 UE 的 build_from_mesh_descriptions），使用上述原生 API。

此 Skill 为 ArtClaw 工具生态的核心组件，通过 AI 引导大幅简化自定义工具创建流程。