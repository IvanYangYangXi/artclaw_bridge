# artclaw_sdk 工具合规改造计划

> 版本: 2.0  
> 日期: 2026-04-25  
> 关联: [SDK API 规范](./artclaw-sdk-api-spec.md) · [tool-manifest-spec](../ArtClawToolManager/docs/specs/tool-manifest-spec.md)

---

## 1. 问题总结

### 1.1 SDK 层

| # | 问题 | 影响 |
|---|------|------|
| F1 | `sdk.log` 不存在（模块名是 `logger`） | `sdk.log.info()` 报错 |
| F2 | `sdk.parse_params()` 未在顶层导出 | 需写 `sdk.params.parse_params()` |
| F3 | `sdk.result.error()` 不存在（正确是 `fail()`） | 调用报错 |

### 1.2 工具脚本层

| # | 问题 | 涉及工具 |
|---|------|----------|
| B1 | **零工具使用 artclaw_sdk** — 全部 7 个 main.py 没有一个 import sdk | 全部 |
| B2 | UV重排和资产重命名硬编码 `EditorUtilityLibrary.get_selected_assets()` | 2 个 UE 工具 |
| B3 | 返回值格式不统一 | 全部 |

### 1.3 Skill 层

| # | 问题 | 涉及 Skill |
|---|------|------------|
| C1 | tool-creator 有残留矛盾："⛔ 禁止 artclaw_sdk" vs "优先使用" | tool-creator |
| C2 | tool-executor 没有 AI 运行指南 | tool-executor |
| C3 | tool-creator 脚本模板中 `result.error()` 不存在 | tool-creator |

---

## 2. 工具脚本范式

所有工具脚本必须通过 artclaw_sdk 完成 4 件事：

| 步骤 | SDK API | 说明 |
|------|---------|------|
| 1. 参数解析 | `sdk.params.parse_params()` | 按 manifest inputs 定义做类型转换+校验 |
| 2. 对象获取 | `sdk.context.get_selected()` | 从 DCC 获取当前选中对象 |
| 3. 对象筛选 | `sdk.filters.filter_by_type()` | 按 manifest defaultFilters 过滤 |
| 4. 结果上报 | `sdk.result.success()` / `.fail()` | 标准化返回值 |

### 选中对象获取：统一规则

**核心原则**：脚本不硬编码 DCC API（如 `unreal.EditorUtilityLibrary`），改用 `sdk.context.get_selected()`。

> **为什么不允许脚本直接调 `EditorUtilityLibrary.get_selected_assets()`？**
>
> `EditorUtilityLibrary` 是 UE 的原生 API，直接调用没有技术问题。但如果每个工具各写各的获取选中逻辑，会出现：
> - 同样的功能，UV重排用 `EditorUtilityLibrary().get_selected_assets()`，资产重命名用 `unreal.EditorUtilityLibrary.get_selected_assets()`，写法不一致
> - 换 DCC（如 Blender）时每个工具都要改
> - 筛选逻辑（只要 StaticMesh）写死在脚本里，用户无法通过 manifest 修改
>
> **统一成 `sdk.context.get_selected()`** 后：SDK 适配器封装了各 DCC 的差异，工具脚本一行代码适配所有 DCC。筛选条件放在 manifest 中，用户可修改。

### manifest defaultFilters 扩展

manifest 新增 `defaultFilters.typeFilter.source` 字段：

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

| source | 含义 | 典型场景 |
|--------|------|----------|
| `"selection"` | 从 DCC 当前选中对象获取 + 按类型过滤 | UV重排、资产重命名 |
| `"parameter"` | 只从参数输入获取，不读选中 | 贴图裁切（用户填材质路径） |
| 不填 | 同 `"selection"` | 向后兼容 |

### 标准脚本模板

```python
"""工具名称 — 一句话描述。"""
import os, json
import artclaw_sdk as sdk
# DCC 原生 API（仅 SDK 不覆盖的操作时使用）
# import unreal

def main_function(**kwargs):
    """入口函数。"""
    # ── 1. 参数解析 ──
    manifest = json.loads(
        open(os.path.join(os.path.dirname(__file__), "manifest.json"),
             encoding="utf-8").read()
    )
    parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)

    # ── 2. 对象获取 + 筛选 ──
    type_cfg = manifest.get("defaultFilters", {}).get("typeFilter", {})
    types = type_cfg.get("types", [])
    source = type_cfg.get("source", "selection")

    if source == "selection":
        # 优先用参数传入的路径，fallback 到当前选中
        explicit = parsed.get("target_paths", "")
        if explicit:
            objects = [{"path": p.strip(), "type": "", "name": p.strip().rsplit("/",1)[-1]}
                       for p in explicit.split(",") if p.strip()]
        else:
            objects = sdk.context.get_selected()
        if types:
            objects = sdk.filters.filter_by_type(objects, types)
        if not objects:
            return sdk.result.fail("NO_INPUT", "未指定目标，且当前无选中对象。")

    # ── 3. 业务逻辑（DCC 原生 API）──
    # ...

    # ── 4. 结果上报 ──
    return sdk.result.success(data={...}, message="完成")
```

---

## 3. 执行计划

### Phase 1: 修复 SDK（30min）

| 文件 | 改动 |
|------|------|
| `core/artclaw_sdk/__init__.py` | 新增 `log = logger` 别名 + `from .params import parse_params` |
| `core/artclaw_sdk/result.py` | 新增 `error = fail` 别名 |

### Phase 2: 更新 artclaw-tool-creator Skill（30min）

| 改动 | 说明 |
|------|------|
| 删除 "⛔ 禁止 artclaw_sdk" | SDK 已修复可用 |
| 更新脚本模板 | 用标准模板替换 |
| 修复 `result.error` → `result.fail` | 模板中的 API 名 |
| 新增 `defaultFilters.typeFilter.source` 说明 | 明确 selection vs parameter |
| 强化"对象获取范式"章节 | 强制 SDK 获取 + manifest 筛选 |

### Phase 3: 更新 artclaw-tool-executor Skill（30min）

新增 **"AI 运行指南"** 章节，详见 [artclaw-sdk-executor-guide.md](./artclaw-sdk-executor-guide.md)。

### Phase 4: 修复现有工具（2h）

**DCC 工具（4 个）**:

| 工具 | 改动要点 |
|------|----------|
| UV重排 | 删 `_get_selected_meshes()` → `sdk.context.get_selected()` + manifest typeFilter |
| 贴图裁切 | 加 `sdk.params.parse_params` + `sdk.result` + manifest `source: "parameter"` |
| 资产重命名(UE) | 同 UV重排 |
| 模型重命名(Blender) | 同 UV重排，适配 Blender |

**通用工具（3 个）**: 加 sdk 参数解析 + 返回值标准化。

### Phase 5: 更新合规检查器

新增规则：

| # | 规则 | 级别 | 说明 |
|---|------|------|------|
| R30 | main.py 必须 import artclaw_sdk | error | 确保所有工具使用 SDK |
| R31 | 入口函数应调用 params.parse_params | warning | 参数解析标准化 |
| R32 | DCC 工具应有 defaultFilters.typeFilter | warning | 筛选条件声明 |
| R33 | 不应硬编码 DCC 选中 API | error | 见下方说明 |
| R34 | 返回值应包含 success 字段 | warning | 结果格式标准化 |

**R33 检测的硬编码 API**（应改用 `sdk.context.get_selected()`）：
- UE: `EditorUtilityLibrary.get_selected_assets`, `EditorLevelLibrary.get_selected_level_actors`
- Blender: `bpy.context.selected_objects`
- Maya: `cmds.ls(selection=True)`

---

## 4. 不在本次范围

- SDK progress 对接 Tool Manager 前端实时进度条
- Maya/Max/Houdini/SP/SD/ComfyUI 适配器的完整实现（骨架已有，按需补充）
- Tool Manager 前端对 `typeFilter.source` 的 UI 展示
