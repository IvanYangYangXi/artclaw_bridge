# C++ 接口需求记录

> 记录 Skill 开发中发现的需要 C++ 支持的功能。
> 在用户确认后再修改 C++ 代码。

## 当前状态：无阻塞性需求

---

## generate_material_documentation

### 已实现功能（纯 Python）

以下功能均通过 Python API 实现，无需 C++ 支持：

| 功能 | API | 状态 |
|------|-----|------|
| 加载材质 | `unreal.load_asset()` | ✅ |
| 基本信息 | `get_editor_property()` | ✅ |
| Scalar 参数 | `MaterialEditingLibrary.get_scalar_parameter_names/value` | ✅ |
| Vector 参数 | `MaterialEditingLibrary.get_vector_parameter_names/value` | ✅ |
| Texture 参数 | `MaterialEditingLibrary.get_texture_parameter_names/value` | ✅ |
| Static Switch | `MaterialEditingLibrary.get_static_switch_parameter_names/value` | ✅ |
| 保存文档 | Python `open()` 写文件 | ✅ |

### 可能需要 C++ 的功能（非阻塞，已优雅降级）

| 功能 | 说明 | 当前状态 |
|------|------|---------|
| 材质图表节点 | `MaterialEditingLibrary.get_material_expressions()` 在部分 UE 版本不可用 | ⚠️ 优雅降级为空，不阻塞 |
| 参数分组信息 | 获取参数的 Group 和 Sort Priority | ⚠️ 需要确认 Python API 可用性 |
| 材质实例列表 | 查找引用此材质的所有 MaterialInstance | ⚠️ 可能需要 Asset Registry 查询 |

### 结论

当前样板 Skill 的核心功能均可通过纯 Python 实现。
上述"可能需要 C++"的功能已通过 `try/except` 优雅降级处理，不影响基本使用。
后续如需增强这些功能，可通过以下方式：

1. **UFunction 暴露** — 在 C++ 中添加 `UFUNCTION(BlueprintCallable)` 并 `UPROPERTY` 标记
2. **弹窗确认** — 通过 Slate 弹窗让用户确认 C++ 修改
3. **渐进增强** — 先用 Python fallback，C++ 接口就绪后自动启用

---

_最后更新: 2026-03-17_
