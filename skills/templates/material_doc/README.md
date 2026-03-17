# generate_material_documentation (参考实现)

> 读取母材质的材质蓝图，提取所有参数，生成 Markdown 格式文档。

## ⚠️ 这是一个参考实现

此模板直接来自 ArtClaw 的样板 Skill：

```
skills/unreal_engine/material/generate_material_documentation/
```

用于展示一个完整的、生产级的 Skill 是什么样子。新开发者应参考此实现来理解
ArtClaw Skill 的最佳实践。

## 展示的核心模式

### 1. MaterialEditingLibrary 使用

```python
mel = unreal.MaterialEditingLibrary
names = mel.get_scalar_parameter_names(material)
value = mel.get_scalar_parameter_value(material, name)
```

### 2. 四种参数类型提取

| 类型 | API | 返回值 |
|------|-----|--------|
| Scalar | `get_scalar_parameter_names/value` | float |
| Vector | `get_vector_parameter_names/value` | LinearColor (r,g,b,a) |
| Texture | `get_texture_parameter_names/value` | Texture asset |
| StaticSwitch | `get_static_switch_parameter_names/value` | bool |

### 3. 优雅降级

```python
# 不可用的 API 不阻塞整体功能
if hasattr(mel, 'get_material_expressions'):
    # 使用高级功能
else:
    # 降级：跳过此部分
```

### 4. 标准返回格式

```json
{
  "success": true,
  "material_name": "M_Master",
  "documentation": "# M_Master 材质文档\n...",
  "output_path": "Saved/MaterialDocs/M_Master.md",
  "parameter_count": 12,
  "texture_count": 4,
  "expression_count": 8
}
```

## 输入参数

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `material_path` | string | ✅ | - | 母材质的资产路径（如 `/Game/Materials/M_Master`） |
| `output_format` | string | ❌ | "markdown" | 输出格式 |
| `include_parameters` | bool | ❌ | true | 是否包含参数说明 |
| `include_graph` | bool | ❌ | true | 是否包含节点图 |

## 适用版本

- **软件**: Unreal Engine
- **版本**: 5.1 - 5.5

## 许可证

MIT
