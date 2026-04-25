# artclaw-tool-executor AI 运行指南规范

> 版本: 1.0  
> 日期: 2026-04-25  
> 关联: [SDK API 规范](./artclaw-sdk-api-spec.md) · [工具合规改造计划](./artclaw-sdk-tool-compliance-plan.md)

本文档定义 artclaw-tool-executor Skill 中应新增的 **"AI 运行指南"** 章节内容。

---

## 1. 参数预处理

AI 在调用工具 Execute API 前，应按以下规则预处理参数：

### 1.1 路径格式转换

| DCC | 正确格式 | 示例 | 常见错误 |
|-----|----------|------|----------|
| UE | `/Game/路径/资产名`（不含 `.uasset`） | `/Game/Props/SM_Chair` | `D:\Project\Content\Props\SM_Chair.uasset` |
| Blender | 对象 name（唯一标识） | `Cube.001` | `bpy.data.objects["Cube"]` |
| Maya | DAG 路径或短名 | `\|group1\|pCube1` | — |

**AI 应做的事**:
- UE 磁盘路径 → 转为 `/Game/...` 格式（去掉 `Content/` 前缀和 `.uasset` 后缀）
- UE 路径含 `.ObjectName` 后缀（如 `/Game/.../MI_Foo.MI_Foo`）→ 去掉 `.ObjectName`
- 用户给相对路径 → 提示需要完整路径

### 1.2 多目标输入

| 场景 | AI 应做的事 |
|------|------------|
| 用户用换行分隔多个路径 | 转换为逗号分隔 |
| 用户说"选中的 XX" | 告知工具会自动读取选中对象，无需手动填路径 |
| 用户说"文件夹下所有 XX" | 如工具不支持目录扫描，提示先选中资产或列出路径 |

### 1.3 类型转换

| 场景 | AI 应做的事 |
|------|------------|
| number 参数但用户给文字 | 转换（如 "一千" → 1000） |
| boolean 参数但用户说 "是/否" | 转换为 true/false |
| select 参数但用户值不在 options 里 | 列出可选项供选择 |

---

## 2. 批处理策略

### 2.1 判断规则

| manifest 特征 | 策略 |
|---------------|------|
| 有路径参数且 description 含"逗号分隔" | 工具自带批处理 → 一次传入多个 |
| 路径参数不支持多值 | AI 需循环调用 → 每次传一个 |
| `defaultFilters.typeFilter.source == "selection"` | 提示用户先选中目标 |
| `defaultFilters.typeFilter.source == "parameter"` | 必须手动传入路径 |

### 2.2 判断示例

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

---

## 3. 运行结果解读

### 3.1 标准返回字段

| 字段 | 含义 | AI 应展示 |
|------|------|-----------|
| `success: true` + `message` | 成功 | 展示 message |
| `success: true` + `data` | 成功 | 格式化 data 中关键信息 |
| `success: false` + `error` | 失败 | 展示 error + 建议修复方案 |
| `dry_run: true` | 预演模式 | 展示 report，告知未实际执行 |
| `modified_assets: [...]` | 已修改资产列表 | 提醒用户保存 |

### 3.2 常见错误处理

| error | 含义 | AI 建议 |
|-------|------|---------|
| `NO_INPUT` | 未指定目标且无选中 | "请在 Content Browser 中选中要处理的资产" |
| `DCC_NOT_CONNECTED` | DCC 未连接 | "请先打开 UE/Maya 并启动 ArtClaw Bridge 插件" |
| `EXECUTION_TIMEOUT` | 超时 | "处理数据量可能过大，建议减少处理数量" |
| `MISSING_INPUT` | 必填参数缺失 | 列出缺失参数名 |

---

## 4. 执行前检查清单

AI 在调用 Execute API 前应完成：

1. ✅ 所有 `required=true` 参数有值
2. ✅ `select` 类型参数值在 `options` 范围内
3. ✅ `number` 类型参数值在 `min`/`max` 范围内
4. ✅ 路径格式符合目标 DCC 规范
5. ✅ 如有 `agentHint`，已阅读并遵循
6. ✅ `dry_run` 参数已确认（首次建议 true 预览）
