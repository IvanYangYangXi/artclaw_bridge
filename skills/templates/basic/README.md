# TODO_skill_name

> TODO: 一句话描述

## 功能

TODO: 详细描述 Skill 的功能和用途。

## 使用方式

由 AI Agent 通过 MCP 协议自动调用，无需手动触发。

### 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `example_param` | string | ✅ | - | TODO: 参数说明 |

### 返回值

```json
{
  "success": true,
  "data": {}
}
```

## 适用版本

- **软件**: Unreal Engine
- **版本**: 5.3 - 5.5

## 开发

```bash
# 从模板创建
artclaw skill create my_skill --template basic --category material

# 测试
artclaw skill test my_skill --dry-run
```

## 许可证

MIT
