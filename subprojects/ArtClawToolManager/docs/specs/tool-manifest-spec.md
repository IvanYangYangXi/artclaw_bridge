# Tool Manifest 规范 (tool-manifest-spec.md)

> 版本: 1.0  
> 日期: 2026-04-14  
> 位置: docs/specs/tool-manifest-spec.md

---

## 1. 概述

每个工具目录下的 `manifest.json` 是工具的唯一权威描述文件。  
Tool Manager、合规检查器、触发引擎、AI 执行层均以此文件为准。

---

## 2. 完整字段定义

### 2.1 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 格式 `{source}/{name}`，其中 name 必须为 kebab-case |
| `name` | string | ✅ | 人类可读显示名，非空 |
| `description` | string | ✅ | 功能描述，非空，建议 20–200 字 |
| `version` | string | ✅ | 语义化版本 `MAJOR.MINOR.PATCH`，如 `1.0.0` |
| `author` | string | ✅ | 作者名称，非空。官方工具用 `ArtClaw`，个人工具用真实名 |
| `source` | string | ✅ | 枚举：`official` / `marketplace` / `user`，必须与文件夹层级一致 |
| `targetDCCs` | string[] | ✅ | 目标 DCC 列表；通用工具用 `[]` 或 `["general"]`。有效值见下表 |
| `implementation` | object | ✅ | 工具实现，详见 §2.2 |
| `inputs` | object[] | ✅ | 参数定义数组（可为空数组 `[]`） |
| `outputs` | object[] | ✅ | 输出定义数组（可为空数组 `[]`） |
| `agentHint` | string | ⚠️ 推荐 | AI 执行提示，告知 AI 如何调用此工具 |
| `defaultFilters` | object | ⚠️ 推荐 | 工具级默认筛选条件，watch trigger 依赖此字段 |
| `triggers` | object[] | ⚠️ 推荐 | 触发规则定义（可为空数组 `[]`） |
| `presets` | object[] | ⚠️ 推荐 | 参数预设定义（可为空数组 `[]`） |
| `createdAt` | string | ⚠️ 推荐 | 创建时间，格式 `YYYY-MM-DD HH:MM:SS`（UTC） |
| `updatedAt` | string | ⚠️ 推荐 | 最后更新时间，格式同上 |

#### targetDCCs 有效值

| 值 | 说明 |
|----|------|
| `"general"` | 通用工具，不依赖特定 DCC |
| `"ue57"` | Unreal Engine 5.7+ |
| `"maya2024"` | Maya 2024+ |
| `"max2024"` | 3ds Max 2024+ |
| `"blender"` | Blender |
| `"comfyui"` | ComfyUI |
| `"sp"` | Substance Painter |
| `"sd"` | Substance Designer |
| `"houdini"` | Houdini |

> `targetDCCs` 为空数组 `[]` 等同于 `["general"]`，表示通用工具。

---

### 2.2 implementation 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 枚举：`script` / `skill_wrapper` / `composite` |
| `entry` | string | 当 type=script | 入口脚本文件名，如 `main.py` |
| `function` | string | 当 type=script | 入口函数名，如 `check_compliance` |
| `skill` | string | 当 type=skill_wrapper | 被包装的 Skill ID |
| `fixedParams` | object | 当 type=skill_wrapper | 固定参数键值对 |
| `steps` | object[] | 当 type=composite | 管线步骤列表 |
| `aiPrompt` | string | ⚠️ 推荐 | AI 执行时的提示词（也可放顶层） |

> `type=script` 时，`entry` 指定的文件必须存在于工具目录中。

---

### 2.3 inputs / outputs 元素字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 参数唯一标识，kebab-case 或 snake_case |
| `name` | string | ✅ | 显示名称，非空 |
| `type` | string | ✅ | 数据类型，有效值见下表 |
| `required` | boolean | ✅ | 是否必填（outputs 可省略此字段） |
| `default` | any | ⚠️ | 非必填参数建议提供默认值 |
| `description` | string | ⚠️ 推荐 | 参数说明 |
| `options` | string[] | 当 type=select | 可选值列表 |
| `min` | number | 当 type=number | 最小值 |
| `max` | number | 当 type=number | 最大值 |

#### 参数类型有效值

| 类型 | 说明 |
|------|------|
| `string` | 字符串 |
| `number` | 数字 |
| `boolean` | 布尔值 |
| `select` | 枚举选择（需配套 `options`） |
| `image` | 图片路径/URL |
| `object` | JSON 对象 |
| `array` | 数组 |

---

### 2.4 triggers 元素字段

详见 [trigger-mechanism.md](trigger-mechanism.md)。核心约束：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 触发规则唯一 ID，用于 manifest → triggers.json 去重同步 |
| `name` | string | ✅ | 显示名称 |
| `enabled` | boolean | ✅ | 是否启用 |
| `trigger` | object | ✅ | 触发方式，含 `type` 字段（watch/event/schedule） |
| `execution` | object | ✅ | 执行配置，必须含 `mode` 字段（silent/notify/interactive） |
| `useDefaultFilters` | boolean | ⚠️ | watch 类型推荐显式声明 |
| `filters` | object | 条件 | watch 类型无 useDefaultFilters 时必须有 `filters.path` |

**触发类型约束**：

- `watch` trigger：禁止使用 `trigger.paths`（已废弃），路径统一走 `filters.path` + `$variable`
- `event` trigger：`dcc` 值必须在 `targetDCCs` 范围内；通用工具（`[]` 或 `["general"]`）禁止使用 event trigger
- `filters.path[].pattern`：禁止花括号扩展语法（`{py,md,json}`），fnmatch 不支持

---

### 2.5 defaultFilters 字段

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

- 当工具有 watch trigger 且 `useDefaultFilters: true` 时，此字段为**必填**
- `path[].pattern` 语法约束同 triggers filters.path

---

### 2.6 id 格式规则

`id` 格式为 `{source}/{name}`，其中：

- `source` 必须是 `official` / `marketplace` / `user` 之一
- `name` 部分建议 kebab-case（小写字母、数字、连字符），允许中文（历史兼容）
- `source` 必须与文件夹层级一致（文件夹才是权威来源）

---

## 3. 合规等级定义

| 等级 | 含义 | 颜色 |
|------|------|------|
| `error` | 必须修复，影响运行 | 🚨 红 |
| `warning` | 建议修复，影响质量 | ⚠️ 黄 |
| `info` | 自动修复通知 | ℹ️ 蓝 |

---

## 4. 合规检查规则索引

tool-compliance-checker 实施的完整检查规则：

| 规则 | 级别 | 字段 | 说明 |
|------|------|------|------|
| 1 | error | — | manifest.json 文件必须存在 |
| 2 | error | — | manifest.json 必须是合法 JSON |
| 3 | error | — | manifest.json 不得有重复键 |
| 4 | error | `name` | 必填，非空 |
| 5 | error | `implementation` | 必填，非空对象 |
| 6 | error | `implementation.type` | 必填，有效值 script/skill_wrapper/composite |
| 7 | error | `implementation.entry` | type=script 时必填；文件必须存在 |
| 8 | error | `implementation.skill` | type=skill_wrapper 时必填 |
| 9 | warning | `description` | 必填，非空 |
| 10 | warning | `version` | 必填，semver 格式 |
| 11 | warning | `author` | 必填，非空 |
| 12 | warning | `source` | 必填，枚举值；与文件夹层级一致 |
| 13 | warning | `id` | 必填，格式 `{source}/{name}` |
| 14 | warning | `targetDCCs` | 必填，数组；元素必须为有效 DCC 值 |
| 15 | warning | `inputs[].id/name/type` | 每个参数必须有 id、name、type |
| 16 | warning | `inputs[].type` | type 必须是有效参数类型 |
| 17 | warning | `inputs[].options` | type=select 时必须有 options 数组 |
| 18 | warning | `outputs[].id/name/type` | 每个输出必须有 id、name、type |
| 19 | error | `triggers[].id` | 每条触发规则必须有 id |
| 20 | error | `triggers[].id` | trigger id 不得重复 |
| 21 | error | `triggers[].trigger.type` | 必须是 watch/event/schedule 之一 |
| 22 | error | `triggers[].execution.mode` | 必须有 mode 字段 |
| 23 | error | watch trigger | 禁止 `trigger.paths`（已废弃） |
| 24 | error | watch trigger | 无 useDefaultFilters 时必须有 filters.path |
| 25 | error | watch trigger | useDefaultFilters=true 时工具必须有 defaultFilters.path |
| 26 | error | event trigger | 通用工具不能使用 event trigger |
| 27 | warning | event trigger | trigger.dcc 必须在 targetDCCs 范围内 |
| 28 | error | filters.path | 禁止花括号扩展语法 `{a,b}` |
| 29 | warning | `createdAt`/`updatedAt` | 建议填写时间戳，格式 `YYYY-MM-DD HH:MM:SS` |

---

## 5. 完整示例

```json
{
  "id": "official/my-tool",
  "name": "示例工具",
  "description": "演示完整合规 manifest 结构",
  "version": "1.0.0",
  "author": "ArtClaw",
  "source": "official",
  "targetDCCs": ["blender"],
  "agentHint": "通过 Tool Manager API 执行: POST /api/v1/tools/official%2Fmy-tool/execute",
  "createdAt": "2026-04-14 10:00:00",
  "updatedAt": "2026-04-14 10:00:00",
  "implementation": {
    "type": "script",
    "entry": "main.py",
    "function": "run_tool"
  },
  "inputs": [
    {
      "id": "prefix",
      "name": "前缀",
      "type": "string",
      "required": false,
      "default": "",
      "description": "添加到名称前的文本"
    },
    {
      "id": "mode",
      "name": "模式",
      "type": "select",
      "required": false,
      "default": "selected",
      "options": ["selected", "all"],
      "description": "处理范围"
    }
  ],
  "outputs": [
    {
      "id": "count",
      "name": "处理数量",
      "type": "number"
    }
  ],
  "defaultFilters": {
    "path": [
      { "pattern": "$project_root/tools/**/*" }
    ]
  },
  "triggers": [
    {
      "id": "on-change",
      "name": "文件变化时运行",
      "enabled": true,
      "trigger": {
        "type": "watch",
        "events": ["created", "modified"],
        "debounceMs": 3000
      },
      "useDefaultFilters": true,
      "filters": {},
      "execution": {
        "mode": "notify",
        "timeout": 30
      }
    }
  ],
  "presets": []
}
```

---

## 6. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-04-14 | 初始版本，对应 tool-compliance-checker v3.0 |
