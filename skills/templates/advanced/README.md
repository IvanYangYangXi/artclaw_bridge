# TODO_skill_name

> TODO: 一句话描述

## 功能

TODO: 详细描述 Skill 的功能和用途。

### 暴露的工具

| 工具名 | 风险级别 | 说明 |
|--------|----------|------|
| `TODO_primary_tool` | medium | TODO: 主工具，支持批量操作和撤销 |
| `TODO_secondary_tool` | low | TODO: 辅助查询工具 |

## 使用方式

由 AI Agent 通过 MCP 协议自动调用。

### TODO_primary_tool

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `target_path` | string | ⚠️ | - | 单个目标资产路径（与 items 二选一） |
| `items` | array | ⚠️ | [] | 批量目标列表（与 target_path 二选一） |
| `dry_run` | bool | ❌ | false | 仅预览，不执行实际操作 |

#### 返回值

```json
{
  "success": true,
  "processed": 5,
  "failed": 0,
  "results": [...],
  "errors": [],
  "dry_run": false
}
```

### TODO_secondary_tool

#### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `query` | string | ❌ | "" | 搜索关键词 |
| `filter_type` | string | ❌ | "all" | 过滤类型 |
| `limit` | int | ❌ | 50 | 最大返回数量（上限 500） |

## 特性

- ✅ **批量操作**: 支持一次处理多个目标
- ✅ **撤销支持**: 使用 `ScopedEditorTransaction`，操作可撤销
- ✅ **Dry Run**: 预览模式，不做实际修改
- ✅ **错误隔离**: 单个失败不影响其他项

## 适用版本

- **软件**: Unreal Engine
- **版本**: 5.3 - 5.5

## 依赖

- `artclaw.universal.utils >= 1.0.0`

## 开发

```bash
# 从高级模板创建
artclaw skill create my_skill --template advanced --category asset

# 测试
artclaw skill test my_skill --dry-run
```

## 许可证

MIT
