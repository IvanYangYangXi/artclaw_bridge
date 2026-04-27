# artclaw_sdk 改造开发文档

> 本文档是给开发者（sub-agent）的执行指令，按顺序完成所有任务。

## 项目路径

- SDK 代码: `D:\MyProject_D\artclaw_bridge\subprojects\DCCClawBridge\core\artclaw_sdk\`
- 工具目录: `D:\MyProject_D\artclaw_bridge\tools\`
- tool-creator Skill: `D:\MyProject_D\artclaw_bridge\skills\official\universal\artclaw-tool-creator\SKILL.md`
- tool-executor Skill: `D:\MyProject_D\artclaw_bridge\skills\official\universal\artclaw-tool-executor\SKILL.md`
- 合规检查器: `D:\MyProject_D\artclaw_bridge\tools\official\universal\tool-compliance-checker\main.py`
- 规范文档: `D:\MyProject_D\artclaw_bridge\docs\specs\artclaw-sdk-api-spec.md`
- 合规计划: `D:\MyProject_D\artclaw_bridge\docs\specs\artclaw-sdk-tool-compliance-plan.md`
- executor 指南: `D:\MyProject_D\artclaw_bridge\docs\specs\artclaw-sdk-executor-guide.md`

## 开发前必读

1. 先读 `docs/specs/artclaw-sdk-api-spec.md` — SDK API 完整规范
2. 先读 `docs/specs/artclaw-sdk-tool-compliance-plan.md` — 改造计划（含模板和检查规则）
3. 先读 `docs/specs/artclaw-sdk-executor-guide.md` — AI 运行指南

---

## Task 1: 修复 SDK 核心（`core/artclaw_sdk/`）

### 1.1 修改 `__init__.py`

在现有代码基础上做以下修改（不要重写整个文件）：

**a) 新增 `log` 别名**（在 `from . import context` 那块之后）:
```python
# log 别名（兼容 sdk.log.info() 调用方式）
from . import logger as log
```

**b) 新增 `parse_params` 顶层导出**:
```python
from .params import parse_params
```

**c) 新增 `get_selected_assets` 和 `get_selected_objects` 便捷函数**:
```python
def get_selected_assets() -> List[Dict[str, Any]]:
    """获取资源管理器中选中的资产文件（UE Content Browser 等）。
    非 UE 的 DCC 如无资源管理器对接，返回空列表。"""
    if _current_adapter:
        return _current_adapter.get_selected_assets()
    return []

def get_selected_objects() -> List[Dict[str, Any]]:
    """获取场景/视口中选中的对象（UE Actor、Blender Object 等）。"""
    if _current_adapter:
        return _current_adapter.get_selected_objects()
    return []
```

**d) 更新 `__all__`**:
把 `get_selected_assets`、`get_selected_objects`、`parse_params`、`log` 加入 `__all__`。

### 1.2 修改 `result.py`

在文件末尾（`print_result` 函数之后）新增:
```python
# error 别名（兼容 sdk.result.error() 调用方式）
error = fail
```

### 1.3 修改 `context.py`

新增两个函数:
```python
def get_selected_assets() -> List[Dict[str, Any]]:
    """获取资源管理器中选中的资产文件。"""
    if not _current_adapter:
        return []
    try:
        return _current_adapter.get_selected_assets()
    except Exception as e:
        logger.error(f"Failed to get selected assets: {e}")
        return []

def get_selected_objects() -> List[Dict[str, Any]]:
    """获取场景/视口中选中的对象。"""
    if not _current_adapter:
        return []
    try:
        return _current_adapter.get_selected_objects()
    except Exception as e:
        logger.error(f"Failed to get selected objects: {e}")
        return []
```

注意: context.py 中引用 `_current_adapter` 是从 `__init__.py` 导入的。检查现有的 import 方式，保持一致。

### 1.4 修改 `dcc/base.py`

**a) 新增两个抽象方法**:
```python
@abstractmethod
def get_selected_assets(self) -> List[Dict[str, Any]]:
    """获取资源管理器中选中的资产。
    UE: Content Browser 选中的资产。
    其他 DCC: 如无资源管理器对接，返回空列表。"""
    pass

@abstractmethod
def get_selected_objects(self) -> List[Dict[str, Any]]:
    """获取场景/视口中选中的对象。"""
    pass
```

**b) 移除操作类方法**（以下方法全部删除）:
- `rename_object`
- `delete_objects`
- `duplicate_objects`
- `export_selected`
- `import_file`

保留 `execute_on_main_thread`、`is_main_thread`、`filter_objects`（这些是查询/调度类）。

### 1.5 修改 `dcc/ue.py`

**a) 拆分现有 `get_selected` 为两个方法**:

```python
def get_selected_assets(self) -> List[Dict[str, Any]]:
    """获取 Content Browser 中选中的资产。"""
    try:
        selected_assets = self.unreal.EditorUtilityLibrary.get_selected_assets()
        result = []
        for asset in selected_assets:
            result.append({
                "name": asset.get_name(),
                "path": asset.get_path_name().split(".")[0],
                "type": "asset",
                "class": asset.get_class().get_name(),
            })
        return result
    except Exception as e:
        logger.error(f"Failed to get UE selected assets: {e}")
        return []

def get_selected_objects(self) -> List[Dict[str, Any]]:
    """获取 Viewport 中选中的 Actor。"""
    try:
        selected_level_actors = self.unreal.EditorLevelLibrary.get_selected_level_actors()
        result = []
        for actor in selected_level_actors:
            result.append({
                "name": actor.get_name(),
                "path": actor.get_path_name(),
                "type": "actor",
                "class": actor.get_class().get_name(),
                "is_level_actor": True,
                "location": tuple(actor.get_actor_location()),
                "rotation": tuple(actor.get_actor_rotation()),
            })
        return result
    except Exception as e:
        logger.error(f"Failed to get UE selected objects: {e}")
        return []
```

**b) 更新 `get_selected` 调用两个新方法**:
```python
def get_selected(self) -> List[Dict[str, Any]]:
    """获取全部选中（资产 + Actor 合并）。"""
    return self.get_selected_assets() + self.get_selected_objects()
```

**c) 删除操作类方法**: `rename_object`、`delete_objects`、`duplicate_objects`、`export_selected`、`import_file`。

**d) 注意 UE 路径**: `get_path_name()` 返回 `/Game/Path/Asset.Asset`，需要 `.split(".")[0]` 去掉后缀（在 get_selected_assets 中）。Actor 路径保留原样。

### 1.6 修改 `dcc/blender.py`

**a) 新增 `get_selected_assets`**:
```python
def get_selected_assets(self) -> List[Dict[str, Any]]:
    """Blender 无内置资源管理器，返回空列表。"""
    return []
```

**b) 把现有 `get_selected` 的内容移到 `get_selected_objects`**:
```python
def get_selected_objects(self) -> List[Dict[str, Any]]:
    """获取场景中选中的 Blender 对象。"""
    # （把现有 get_selected 的代码搬过来，不改逻辑）
```

**c) 更新 `get_selected`**:
```python
def get_selected(self) -> List[Dict[str, Any]]:
    return self.get_selected_assets() + self.get_selected_objects()
```

**d) 删除操作类方法**: `rename_object`、`delete_objects`、`duplicate_objects`、`export_selected`、`import_file`。

### 1.7 修改其他 DCC 适配器（maya/max/houdini/sp/sd/comfyui）

这些适配器都是骨架，做最小改动：

```python
def get_selected_assets(self) -> List[Dict[str, Any]]:
    """暂未对接资源管理器。"""
    return []

def get_selected_objects(self) -> List[Dict[str, Any]]:
    """暂未实现，返回空列表。"""
    # 如果现有 get_selected 有实现，把内容搬过来
    # 如果是空的，直接返回 []
    return []
```

同样删除操作类方法（如果有的话）。

---

## Task 2: 更新 tool-creator Skill

文件: `skills/official/universal/artclaw-tool-creator/SKILL.md`

### 修改点

1. **删除矛盾描述**: 搜索 "⛔ **禁止使用 `artclaw_sdk`**" 整段，删除

2. **更新脚本模板**: 把 "编写脚本 (script)" 章节下的脚本模板替换为:

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
    """入口函数。kwargs 由 Tool Manager 传入。"""
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
            # 根据工具需求选择:
            # sdk.context.get_selected_assets()  — Content Browser / 资源管理器
            # sdk.context.get_selected_objects()  — 场景 / 视口
            objects = sdk.context.get_selected_assets()
        if types:
            objects = sdk.filters.filter_by_type(objects, types)
        if not objects:
            return sdk.result.fail("NO_INPUT", "未指定目标，且当前无选中对象。")

    # ── 3. 业务逻辑（DCC 原生 API）──
    # import unreal  # UE
    # import bpy     # Blender
    # ...

    # ── 4. 结果上报（必须）──
    return sdk.result.success(data={...}, message="完成")
```

3. **修复 artclaw_sdk 速查**章节中的 `result.error()`:
   - 搜索 `result.error(`，替换为 `result.fail(`

4. **新增 "创建完成后自动合规检查" 说明**:
   在 "验证清单" 章节之后加:
```markdown
### 创建后自动合规检查

工具创建保存后，自动调用合规检查器验证脚本结构：
- `import artclaw_sdk` 是否存在
- 入口函数是否调用 `parse_params`
- 返回值是否包含 `success` 字段
- DCC 工具是否有 `defaultFilters.typeFilter`

如检查不通过，提示用户修复后再保存。
```

5. **新增 `defaultFilters.typeFilter.source` 说明**:
   在 "manifest.json Schema" 的 defaultFilters 部分，加:
```markdown
#### typeFilter.source

| source | 含义 |
|--------|------|
| `"selection"` | 从 DCC 当前选中获取 + 按类型过滤（默认值） |
| `"parameter"` | 只从参数输入获取，不读选中 |

`types` 中的值必须与目标 DCC 的实际 type 值一致。
```

---

## Task 3: 更新 tool-executor Skill

文件: `skills/official/universal/artclaw-tool-executor/SKILL.md`

在 "常见错误" 章节之前，新增完整的 **"AI 运行指南"** 章节。

内容直接从 `docs/specs/artclaw-sdk-executor-guide.md` 搬入（全部 4 节：参数预处理、批处理策略、运行结果解读、执行前检查清单）。

先 `read` 该文件获取内容，然后插入到 SKILL.md 中。

---

## Task 4: 改造现有工具脚本

### 4.1 UE 资产批量重命名

文件: `tools/marketplace/unreal/` 下找包含 `rename_assets` 函数的工具目录。

改造:
```python
"""UE 资产批量重命名 — 为选中的资产添加前缀或后缀。"""
# ── SDK 头 ──
import os, json
import artclaw_sdk as sdk

def _load_manifest():
    return json.loads(
        open(os.path.join(os.path.dirname(__file__), "manifest.json"),
             encoding="utf-8").read()
    )
# ── SDK 头结束 ──

import unreal


def rename_assets(**kwargs):
    """入口函数。"""
    manifest = _load_manifest()
    parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)

    prefix = parsed.get("prefix", "")
    suffix = parsed.get("suffix", "")
    separator = parsed.get("separator", "_")

    # 通过 SDK 获取选中资产
    selected = sdk.context.get_selected_assets()
    if not selected:
        return sdk.result.fail("NO_INPUT", "没有选中任何资产，请在 Content Browser 中选择要重命名的资产。")

    if not prefix and not suffix:
        return sdk.result.fail("NO_PARAMS", "前缀和后缀均为空，无需操作。")

    renamed = []
    for asset_info in selected:
        old_name = asset_info["name"]
        old_path = asset_info["path"]
        new_name = old_name

        if prefix:
            new_name = prefix + separator + new_name
        if suffix:
            new_name = new_name + separator + suffix

        new_path = old_path.rsplit("/", 1)[0] + "/" + new_name
        success = unreal.EditorAssetLibrary.rename_asset(old_path, new_path)
        if success:
            renamed.append({"old": old_name, "new": new_name})

    return sdk.result.success(
        data={"renamed_count": len(renamed), "renamed_assets": renamed},
        message=f"成功重命名 {len(renamed)} 个资产"
    )
```

同时更新该工具的 `manifest.json`，添加:
```json
"defaultFilters": {
    "typeFilter": {
        "source": "selection"
    }
}
```

### 4.2 Blender 模型重命名

文件: `tools/marketplace/blender/` 下的重命名工具。

改造思路同上:
- 加 SDK 头
- `bpy.context.selected_objects` → `sdk.context.get_selected_objects()`
- 返回值改用 `sdk.result.success/fail`
- manifest 加 `defaultFilters.typeFilter`

### 4.3 UV 重排工具

文件: `tools/marketplace/unreal/UV & 贴图利用率优化-UV重排/main.py`

改造:
- 加 SDK 头（import artclaw_sdk as sdk + _load_manifest）
- 删除 `_get_selected_meshes()` 函数
- 入口函数开头: `parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)`
- 选中对象获取: `sdk.context.get_selected_assets()` + `sdk.filters.filter_by_type(objects, ["StaticMesh"])`
  （用 `class` 字段进行过滤，因为 UE 资产的 type 都是 `"asset"`，真正的类型在 `class` 字段）
- **注意**: filter_by_type 匹配的是 dict 的 `type` key。但 UE 资产的 `type` 是 `"asset"`，实际类型在 `class`。
  所以改用: `[a for a in assets if a.get("class") in types]`（直接过滤，不走 filter_by_type）
  或者把 UE 适配器返回的 `type` 改为 class 值（更好的方案，但需要修改 ue.py 返回格式）。
  **选择方案**: 修改 UE `get_selected_assets()` 中 `type` 字段直接用 class 值（如 `"StaticMesh"`），不用 `"asset"` 这个无意义的值。同时保留 `class` 字段做兼容。这样 `filter_by_type` 就能直接用了。
- 返回值改用 `sdk.result.success/fail`
- manifest 加 `defaultFilters`

**⚠️ 重要**: 修改 `dcc/ue.py` 的 `get_selected_assets()` 中 `type` 字段值：
```python
"type": asset.get_class().get_name(),  # "StaticMesh" 而非 "asset"
```
同时保留 `class` 字段做向后兼容。`get_selected_objects()` 的 `type` 同理用 class 值。
这样 `filter_by_type(objects, ["StaticMesh"])` 就能直接工作。

### 4.4 贴图裁切工具

文件: `tools/marketplace/unreal/UV & 贴图利用率优化-贴图裁切/main.py`

改造:
- 加 SDK 头
- 入口函数参数解析改用 `sdk.params.parse_params`
- 返回值改用 `sdk.result.success/fail`
- manifest 加 `"defaultFilters": { "typeFilter": { "source": "parameter" } }`
- **不改选中逻辑**（此工具通过材质路径参数定位，不用选中）

### 4.5 三个通用工具

`tool-compliance-checker`、`artclaw-skill-compliance-checker`、`memory-promote-to-team`:
- 加 SDK 头
- 参数解析改用 `sdk.params.parse_params`
- 返回值改用 `sdk.result.success/fail`
- 不涉及 DCC 选中

---

## Task 5: 更新合规检查器

文件: `tools/official/universal/tool-compliance-checker/main.py`

在 `_check_tool_compliance` 函数中，在 Rule 29 之后新增 R30-R34:

### R30: main.py 必须 import artclaw_sdk

```python
# ── Rule 30: main.py 必须 import artclaw_sdk ──
entry_file = impl.get("entry", "main.py") if impl else "main.py"
entry_path = tool_dir / entry_file
if entry_path.exists() and impl.get("type") == "script":
    script_source = entry_path.read_text(encoding="utf-8")
    try:
        import ast
        tree = ast.parse(script_source)
        has_sdk_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "artclaw_sdk" or (alias.asname and alias.asname == "sdk"):
                        has_sdk_import = True
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("artclaw_sdk"):
                    has_sdk_import = True
        if not has_sdk_import:
            issues.append({"tool_id": tool_id, "severity": "error",
                          "message": "main.py 未 import artclaw_sdk（所有工具必须使用 SDK）"})
    except SyntaxError:
        pass  # 语法错误由其他检查覆盖
```

### R31: 入口函数应调用 parse_params

```python
    # ── Rule 31: 入口函数应调用 parse_params ──
    func_name = impl.get("function", "") if impl else ""
    if func_name and has_sdk_import:
        has_parse_params = any(
            isinstance(node, ast.Attribute) and node.attr == "parse_params"
            for node in ast.walk(tree)
        )
        if not has_parse_params:
            issues.append({"tool_id": tool_id, "severity": "warning",
                          "message": "入口函数未调用 parse_params（建议使用 SDK 参数解析）"})
```

### R32: DCC 工具应有 defaultFilters.typeFilter

```python
# ── Rule 32: DCC 工具应有 defaultFilters.typeFilter ──
real_dccs = [d for d in target_dccs if d and d != "general"]
if real_dccs:
    type_filter = manifest.get("defaultFilters", {}).get("typeFilter", None)
    if type_filter is None:
        issues.append({"tool_id": tool_id, "severity": "warning",
                      "message": "DCC 工具建议设置 defaultFilters.typeFilter（声明对象类型筛选条件）"})
```

### R33: 不应包含与 SDK 功能重复的 DCC 原生调用

```python
    # ── Rule 33: 不应包含与 SDK 功能重复的 DCC 原生调用 ──
    if has_sdk_import:
        # 检测与 sdk.context.get_selected_assets/objects 功能重复的调用
        sdk_overlap_patterns = [
            "get_selected_assets",       # UE EditorUtilityLibrary
            "get_selected_level_actors",  # UE EditorLevelLibrary
            "selected_objects",           # Blender bpy.context.selected_objects
        ]
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in sdk_overlap_patterns:
                    issues.append({"tool_id": tool_id, "severity": "warning",
                                  "message": f"脚本直接调用 .{node.attr}()，建议改用 sdk.context 对应 API"})
                    break  # 每个工具只报一次
```

### R34: 返回值应包含 success 字段

```python
    # ── Rule 34: 返回值应包含 success 字段 ──
    # 检查入口函数的 return 语句是否返回包含 "success" 的 dict
    if func_name:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                has_success_return = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if child.func.attr in ("success", "fail", "error"):
                                has_success_return = True
                                break
                    if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                        for key in child.value.keys:
                            if isinstance(key, ast.Constant) and key.value == "success":
                                has_success_return = True
                                break
                if not has_success_return:
                    issues.append({"tool_id": tool_id, "severity": "warning",
                                  "message": "入口函数返回值建议使用 sdk.result.success/fail（确保包含 success 字段）"})
                break
```

---

## Task 6: Git 提交

完成所有修改后，执行:
```bash
cd D:\MyProject_D\artclaw_bridge
git add -A
git commit -m "artclaw_sdk 改造: SDK修复 + 工具合规改造 + Skill更新 + 合规检查器R30-R34"
```

---

## 注意事项

1. **不要重写整个文件** — 每个文件都有大量现有逻辑，只做增量修改
2. **先读后改** — 每个文件修改前先 `read` 完整内容，理解上下文
3. **保持编码一致** — 所有文件使用 UTF-8 编码
4. **不要改 UV 重排的核心逻辑** — 只改入口部分（SDK 头 + 参数解析 + 选中获取 + 返回值），不碰 `_collect_slot_info`、`uv_repack` 等内部函数
5. **不要改贴图裁切的核心逻辑** — 只加 SDK 头、参数解析改 SDK、返回值改 SDK
6. **UE 路径注意**: `get_path_name()` 返回 `"/Game/Path/Asset.Asset"`，`get_selected_assets()` 中要 `.split(".")[0]`
7. **type 字段统一**: UE 适配器 `get_selected_assets()` 和 `get_selected_objects()` 的 `type` 字段都改为实际 class 名（`"StaticMesh"` 而非 `"asset"`），同时保留 `class` 字段兼容
