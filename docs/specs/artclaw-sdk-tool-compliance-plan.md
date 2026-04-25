# artclaw_sdk 工具合规改造计划

> 版本: 3.0  
> 日期: 2026-04-25  
> 关联: [SDK API 规范](./artclaw-sdk-api-spec.md) · [AI 运行指南](./artclaw-sdk-executor-guide.md)

---

## 1. 问题总结

### 1.1 SDK 层

| # | 问题 |
|---|------|
| F1 | `sdk.log` 不存在（模块名是 `logger`） |
| F2 | `sdk.parse_params()` 未在顶层导出 |
| F3 | `sdk.result.error()` 不存在（正确是 `fail()`） |
| F4 | `get_selected()` 不区分资产和场景对象 |
| F5 | 基类含操作类方法（rename/delete 等），不属于 SDK 职责 |

### 1.2 工具脚本层

| # | 问题 |
|---|------|
| B1 | 全部 7 个工具零使用 artclaw_sdk |
| B2 | DCC 选中对象获取各自硬编码（应统一走 SDK） |
| B3 | 返回值格式不统一 |

### 1.3 Skill 层

| # | 问题 |
|---|------|
| C1 | tool-creator 有矛盾："⛔ 禁止 sdk" vs "优先使用" |
| C2 | tool-executor 没有 AI 运行指南 |
| C3 | tool-creator 脚本模板中 `result.error()` 不存在 |

---

## 2. 工具脚本范式

### 2.1 强制模板

所有工具脚本**必须**包含以下结构，由 tool-creator 在创建时自动注入头尾：

```python
"""工具名称 — 一句话描述。"""
# ── SDK 头（tool-creator 自动注入）──
import os, json
import artclaw_sdk as sdk

def _load_manifest():
    return json.loads(
        open(os.path.join(os.path.dirname(__file__), "manifest.json"),
             encoding="utf-8").read()
    )
# ── SDK 头结束 ──


def main_function(**kwargs):
    """入口函数。"""
    manifest = _load_manifest()
    
    # ── 1. 参数解析（必须）──
    parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)

    # ── 2. 对象获取 + 筛选（按需）──
    type_cfg = manifest.get("defaultFilters", {}).get("typeFilter", {})
    types = type_cfg.get("types", [])
    source = type_cfg.get("source", "selection")

    if source == "selection":
        explicit = parsed.get("target_paths", "")
        if explicit:
            objects = [{"path": p.strip(), "type": "", "name": p.strip().rsplit("/",1)[-1]}
                       for p in explicit.split(",") if p.strip()]
        else:
            # 根据工具需求选择 get_selected_assets() 或 get_selected_objects()
            objects = sdk.context.get_selected_assets()
        if types:
            objects = sdk.filters.filter_by_type(objects, types)
        if not objects:
            return sdk.result.fail("NO_INPUT", "未指定目标，且当前无选中对象。")

    # ── 3. 业务逻辑（DCC 原生 API）──
    # import unreal  / import bpy
    # ... 具体操作 ...

    # ── 4. 结果上报（必须）──
    return sdk.result.success(data={...}, message="完成")
```

### 2.2 合规检查点

工具创建完成后，由**合规检查器**（tool-compliance-checker）自动验证脚本结构：

| # | 检查项 | 级别 | 检测方式 |
|---|--------|------|----------|
| R30 | main.py 必须 `import artclaw_sdk` | error | AST 检查 import 语句 |
| R31 | 入口函数必须调用 `parse_params` | warning | AST 检查函数调用 |
| R32 | DCC 工具应有 `defaultFilters.typeFilter` | warning | manifest JSON 检查 |
| R33 | 不应包含与 SDK 功能重复的 DCC 原生调用 | warning | AST 检查（见下方） |
| R34 | 返回值应包含 `success` 字段 | warning | AST 检查 return 语句中的 dict key |

### 2.3 R33 检测逻辑

R33 检测的是**与 SDK 已提供的 API 功能重复的调用**，不是简单匹配 API 名：

| SDK 已覆盖的功能 | 对应的 DCC 原生调用（脚本中不应出现） |
|-----------------|--------------------------------------|
| `sdk.context.get_selected_assets()` | UE: `EditorUtilityLibrary.get_selected_assets()` / `get_selected_asset_data()` |
| `sdk.context.get_selected_objects()` | UE: `EditorLevelLibrary.get_selected_level_actors()` <br> Blender: `bpy.context.selected_objects` <br> Maya: `cmds.ls(selection=True)` |
| `sdk.context.get_scene_path()` | UE: `EditorLevelLibrary.get_editor_world()` 用于获取路径时 <br> Blender: `bpy.data.filepath` |

**检测方式**: 用 AST 解析脚本，匹配函数调用的 attribute chain（如 `*.get_selected_assets()`），而非简单文本搜索。这样不会误伤用了 `EditorUtilityLibrary` 做其他操作（如 `get_selected_asset_data` 获取 AssetData）的情况。

**级别为 warning 而非 error**：因为某些场景下脚本可能需要直接调用原生 API 获取 SDK 未返回的额外信息。

### 2.4 manifest defaultFilters.typeFilter

```json
{
  "defaultFilters": {
    "typeFilter": {
      "types": ["StaticMesh"],
      "source": "selection"
    }
  }
}
```

| source | 含义 |
|--------|------|
| `"selection"` | 从 DCC 当前选中获取 + 按类型过滤（默认值） |
| `"parameter"` | 只从参数输入获取，不读选中 |

`types` 中的值必须与目标 DCC 的实际 type 值一致（可通过 `sdk.context.get_selected_assets()` 返回的 `class` 字段查看）。

---

## 3. 执行计划

### Phase 1: 修复 SDK（30min）

| 文件 | 改动 |
|------|------|
| `__init__.py` | 新增 `log = logger` + `from .params import parse_params` + `get_selected_assets` / `get_selected_objects` 便捷函数 |
| `result.py` | 新增 `error = fail` |
| `context.py` | 新增 `get_selected_assets()` + `get_selected_objects()` |
| `dcc/base.py` | 拆分 `get_selected` 为 `get_selected_assets` + `get_selected_objects`；移除操作类方法 |
| `dcc/ue.py` | 实现 `get_selected_assets` / `get_selected_objects` |
| `dcc/blender.py` | 实现（assets 返回 `[]`，objects 返回场景选中） |

### Phase 2: 更新 tool-creator Skill（30min）

- 删除 "⛔ 禁止 artclaw_sdk"
- 更新为强制模板（头尾注入）
- 修复 `result.error` → `result.fail`
- 新增 `defaultFilters.typeFilter.source` 说明
- 创建完成后自动调用合规检查

### Phase 3: 更新 tool-executor Skill（30min）

新增 AI 运行指南，详见 [artclaw-sdk-executor-guide.md](./artclaw-sdk-executor-guide.md)。

### Phase 4: 修复现有工具（2h）

| 工具 | 改动 |
|------|------|
| UV重排 | 删 `_get_selected_meshes()` → SDK + manifest typeFilter |
| 贴图裁切 | 加 SDK 参数解析 + manifest `source: "parameter"` |
| 资产重命名(UE) | 同 UV重排 |
| 模型重命名(Blender) | 同上 |
| 3 个通用工具 | 加 SDK 参数解析 + 返回值标准化 |

### Phase 5: 更新合规检查器（1h）

新增 R30-R34 规则（AST 检测，非文本匹配）。

---

## 4. 不在本次范围

- SDK progress 对接 Tool Manager 前端
- 其他 DCC 适配器完整实现（Maya/Max 等，按需）
- Tool Manager 前端对 `typeFilter.source` 的 UI 展示
