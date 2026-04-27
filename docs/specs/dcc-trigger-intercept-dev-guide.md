# DCC 触发器本地执行层开发文档

> 版本：1.2  
> 日期：2026-04-27  
> 适用：为新 DCC（Blender / Maya / Max 等）实现触发器本地执行层  
> 已验证：Blender 5.1 完整流程 ✅

---

## 1. 架构概述

触发器执行**完全在本地（DCC 内部）完成**，不经过 Tool Manager HTTP 服务：

```
DCC 原生事件 (bpy.app.handlers / MSceneMessage / C++ delegate)
    │
    ▼
持久化 Wrapper 函数（跨 reload 保持同一函数 id，见第 7 节）
    │
    ▼
实现函数（每次调用时从 sys.modules 取最新模块，支持热更新）
    │  ① 可选：_dedup_event() 去重保护
    ▼  读取本地文件
~/.artclaw/config.json   → project_root（SDK路径、工具根目录）
~/.artclaw/triggers.json ← Tool Manager 启动时同步写入
    │
    ▼  _match_event() 精确匹配 event_type == "{base}.{timing}"
    │  dcc 字段过滤：只执行当前 DCC 的规则
    │  tool_id 去重：同一次事件同一工具只执行一次
_check_pre_event / _handle_post_event
    │  ② _match_filters() 过滤路径/类型
    ▼  解析条件、加载 manifest、执行工具脚本
_execute_tool_generic(tool_path, manifest, event_data)
    │  动态 import + importlib.reload（热更新支持）
    │  函数签名自适应：event_data / **kwargs 均可
    ▼  工具返回 {"action": "allow"/"reject"/"error", "reason": "..."}
DCC 通知机制（弹窗 / 气泡 / log）
```

**关键点**：
- 所有检查在 DCC 进程内同步完成
- `triggers.json` 是唯一数据源，Tool Manager 写，DCC 读，**DCC 不写**
- `config.json` 提供 `project_root`，用于定位 SDK 和工具目录
- 工具脚本通过 `_execute_tool_generic` 动态 import + 调用，无需注册
- pre 事件：第一个 reject 即拦截，后续规则不再执行（break）
- post 事件：所有匹配规则都执行，结果汇总返回
- **Blender `save_pre` 不支持真正拦截**，不要用 `pre` 事件做强制拦截，推荐 `post`

---

## 2. 文件结构

```
DCCClawBridge/
├── __init__.py                        # Blender addon 入口，负责 sys.path 和 handler 注册
├── blender_addon.py                   # Blender UI / Operator（不含 handler 注册）
├── blender_event_intercept.py         # Blender 触发器执行层
└── core/
    └── dcc_event_intercept_shared.py  # 所有 DCC 共享的公共函数（P0 已完成）
```

各 DCC 遵循同样的结构：
```
{dcc}_event_intercept.py  ← import shared + 实现 wrapper/impl/notify
```

---

## 3. triggers.json 规则格式

Tool Manager 写入 `~/.artclaw/triggers.json`，格式如下：

```json
[
  {
    "id": "uuid",
    "tool_id": "marketplace/Blender对象命名规范检查",
    "name": "Blender保存时命名检查",
    "trigger_type": "event",
    "event_type": "file.save.post",
    "execution_mode": "notify",
    "dcc": "blender",
    "is_enabled": true,
    "use_default_filters": true,
    "conditions": {}
  }
]
```

| 字段 | 说明 |
|------|------|
| `tool_id` | `"{source}/{tool_name}"`，与 manifest 的 `name` 或目录名匹配 |
| `event_type` | 完整格式 `"{base}.{timing}"`，如 `file.save.post` |
| `dcc` | DCC 标识字符串，与 `event_data.dcc_type` 一致，用于跨 DCC 过滤 |
| `execution_mode` | `silent` / `notify` / `interactive` |
| `use_default_filters` | `true` = 用 `manifest.defaultFilters`；`false` = 用 `conditions` |

### 3.1 event_type 格式约定

```
event_type = "{base}.{timing}"
```

| 示例 | 说明 |
|------|------|
| `file.save.post` | Blender 保存后（推荐） |
| `file.open.post` | Blender 文件打开后 |
| `asset.save.pre` | UE 资产保存前（可拦截） |
| `asset.save.post` | UE 资产保存后 |
| `asset.place.post` | UE Actor 放置后 |

匹配逻辑：
```python
trigger.get("event_type", "") == f"{event_base}.{timing}"  # 精确等于
```

### 3.2 Blender 支持的事件类型

| event_type | 说明 | 是否支持拦截 |
|------------|------|------------|
| `file.save.post` | 文件保存后 ✅ 推荐 | 不需要拦截 |
| `file.open.post` | 文件打开后 ✅ | 不需要拦截 |
| ~~`file.save.pre`~~ | ~~文件保存前~~ ❌ 已移除 | Blender 不支持拦截 |

> **`file.save.pre` 已从 Tool Manager UI 和实现中删除。**  
> Blender 的 `save_pre` handler 即使在保存前执行，也无法阻止保存操作。
> 所有命名检查、规范验证应挂 `file.save.post`，保存后通知用户。

---

## 4. 核心公共函数（dcc_event_intercept_shared.py）

所有公共逻辑已提取到 `core/dcc_event_intercept_shared.py`，新 DCC 直接 import：

```python
from dcc_event_intercept_shared import (
    _load_config, _load_triggers, _resolve_tool_path, _ensure_sdk_path,
    _match_filters, _match_event, _check_pre_event, _handle_post_event,
    _execute_tool_generic, _dedup_event,
)
```

### 4.1 工具路径解析 `_resolve_tool_path(tool_id, config)`

搜索路径：`{project_root}/tools/{source}/{dcc_dir}/{tool_name}/`

匹配策略（按顺序）：
1. 目录名直接匹配（含/不含空格差异兼容）
2. 遍历 `manifest.json` 的 `id` 或 `name` 字段匹配

### 4.2 DCC 过滤

`_check_pre_event` / `_handle_post_event` 内置 DCC 过滤：

```python
rule_dcc = t.get("dcc", "")
event_dcc = event_data.get("dcc_type", "")
if rule_dcc and event_dcc and rule_dcc != event_dcc:
    continue  # 跳过其他 DCC 的规则
```

triggers.json 里 UE 的规则不会在 Blender 里执行，反之亦然。

### 4.3 工具脚本函数签名自适应

`_execute_tool_generic` 支持以下签名（按优先级）：

1. `fn(params={}, event_data=event_data)` — 有 `params` 和 `event_data` 参数
2. `fn(event_data=event_data)` — 只有 `event_data` 参数（推荐触发器工具用此签名）
3. `fn(**event_data.get("data", {}), event_data=event_data)` — 其他参数或 `**kwargs`
4. `fn()` — 无参数

---

## 5. event_data 标准结构

```python
event_data = {
    "dcc_type": "blender",        # DCC 标识，与 triggers.json dcc 字段一致
    "event_type": "file.save",    # 基础名（不含 timing）
    "timing": "post",             # "pre" | "post"
    "data": {
        "asset_path":  str,       # 文件路径（Blender 为 .blend 完整路径）
        "asset_name":  str,       # 场景名或文件名
        "asset_class": str,       # 资产类型（Blender 为 "BlendFile"）
        # 各 DCC 特有字段...
    }
}
```

---

## 6. Blender 实现详解

### 6.1 文件结构

```
artclaw_bridge/              ← Blender addon 包目录（安装到 addons/）
├── __init__.py              ← 包入口，负责 sys.path + handler 注册
├── blender_addon.py         ← UI / Operator（不含 handler 注册逻辑）
├── blender_event_intercept.py
└── core/
    └── dcc_event_intercept_shared.py
```

### 6.2 `__init__.py` 关键设计

```python
def _ensure_path():
    """必须同时把 addon_dir 和 core_dir 都加入 sys.path。"""
    import os, sys
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    core_dir = os.path.join(addon_dir, "core")
    for d in [addon_dir, core_dir]:
        if d not in sys.path:
            sys.path.insert(0, d)

def register():
    _ensure_path()  # ① 先确保路径，再 import
    # ② 清除旧缓存，避免 Blender reload 时使用旧模块
    for mod_name in list(sys.modules.keys()):
        if mod_name in ('blender_event_intercept', 'dcc_event_intercept_shared'):
            del sys.modules[mod_name]
    import blender_event_intercept as _bei
    _bei.register_handlers()          # ③ 注册 persistent wrapper
    from .blender_addon import register as _register
    _register()                       # ④ 注册 Blender 类
```

> ⚠️ **坑：路径顺序**  
> `_ensure_path()` 必须在所有 `import blender_event_intercept` 之前调用，  
> 且必须同时加 `addon_dir`（含 `blender_event_intercept.py`）和 `core_dir`（含 `dcc_event_intercept_shared.py`）。

### 6.3 `blender_event_intercept.py` Wrapper 模式

**核心问题**：Blender 检测到文件变化时会自动 reload 模块（`module changed on disk: reloading...`），  
reload 后函数对象 id 变化，但 `bpy.app.handlers` 列表里存的还是旧函数引用，导致 handler 失效。

**解决方案**：注册持久化 wrapper，wrapper 通过 `sys.modules` 动态查找最新实现：

```python
_REGISTRY_KEY = "__artclaw_blender_wrappers__"

def _get_or_create_wrappers():
    # registry 存在 sys.modules 里而非模块命名空间，跨 reload 存活
    registry = sys.modules.get(_REGISTRY_KEY)
    if registry is not None:
        return registry["save_post"], registry["load_post"]

    import bpy

    @bpy.app.handlers.persistent          # ← 必须加！否则打开文件后 handler 被清除
    def save_post_wrapper(scene=None, depsgraph=None):
        mod = sys.modules.get("blender_event_intercept")
        if mod:
            mod._save_post_impl(scene, depsgraph)  # 调用最新模块的实现

    @bpy.app.handlers.persistent
    def load_post_wrapper(scene=None, depsgraph=None):
        mod = sys.modules.get("blender_event_intercept")
        if mod:
            mod._load_post_impl(scene, depsgraph)

    registry = {"save_post": save_post_wrapper, "load_post": load_post_wrapper}
    sys.modules[_REGISTRY_KEY] = registry  # 存到 sys.modules 外部，不被 reload 重置
    return save_post_wrapper, load_post_wrapper
```

> ⚠️ **坑：`@bpy.app.handlers.persistent` 装饰器**  
> Blender 在每次打开文件（`load_post`）后，会自动清除所有**没有** `persistent` 标记的 handler。  
> 启动后 Blender 立即加载上次文件，此时非 persistent handler 全被清空，  
> 所以保存不会触发。**所有 handler 都必须加 `@bpy.app.handlers.persistent`。**

> ⚠️ **坑：`_WRAPPER_REGISTRY` 不能放在模块命名空间内**  
> 如果 registry dict 是模块级变量，Blender reload 模块时会重置为空，  
> wrapper 函数 id 变化，之前注册进 handler 列表的引用失效。  
> **必须存到 `sys.modules["__artclaw_blender_wrappers__"]`，脱离模块命名空间。**

### 6.4 Blender 5.x Handler 签名变化

Blender 5.x 中，`save_post` / `load_post` handler 的第一个参数**不再是 scene 对象**，而是**文件路径字符串**：

```python
# ❌ 旧写法（Blender 4.x）
def on_post_save(scene, depsgraph=None):
    scene_name = scene.name  # Blender 5.x 会报 AttributeError: 'str' has no 'name'

# ✅ 兼容写法
def on_post_save(scene=None, depsgraph=None):
    import bpy
    scene_name = scene.name if hasattr(scene, "name") else (
        bpy.context.scene.name if bpy.context.scene else ""
    )
```

### 6.5 工具脚本中的 `import bpy`

工具脚本（`main.py`）**不能在模块顶层 `import bpy`**，否则 `_execute_tool_generic` 用  
`importlib.import_module` 加载时，模块级 import 失败，整个工具返回 `{"action": "error"}`。

```python
# ❌ 错误：顶层 import
import bpy

def check_naming(event_data=None):
    objects = bpy.context.scene.objects  # bpy 在模块 import 时就被引用了

# ✅ 正确：在函数内延迟 import
def _get_objects(target):
    import bpy   # 只在 Blender 内部执行时才 import
    return list(bpy.context.scene.objects)
```

---

## 7. 触发器适用场景说明

| 场景 | 推荐挂点 | 工具类型 | 说明 |
|------|----------|----------|------|
| 命名规范检查 | `file.save.post` ✅ | 检查类 | 保存后告知，不阻断工作流 |
| 文件打开后初始化检查 | `file.open.post` ✅ | 检查类 | 打开后自动扫描问题 |
| 批量重命名（需参数输入） | ❌ 不适合触发器 | 操作类 | 需交互输入，适合手动运行 |
| 导入后自动处理 | `file.open.post` ✅ | Pipeline 类 | 如自动规范命名、添加材质 |
| 强制拦截（Blender） | ❌ 不支持 | — | Blender 的 `save_pre` 无法拦截保存 |
| 强制拦截（UE） | `asset.save.pre` ✅ | 检查类 | UE 支持真正的 pre 拦截 |

---

## 8. 通知策略

| execution_mode | Blender 行为 | UE 行为 |
|---------------|-------------|---------|
| `silent` | `print()` 打印日志 | `unreal.log_warning` + C++ 气泡 |
| `notify` | `bpy.app.timers` 延迟 `popup_menu` 弹窗 | `EditorDialog.show_message` 阻塞弹窗 |
| `interactive` | 同 `notify`（Blender 无模态确认） | C++ 确认对话框 |

**Blender 弹窗注意事项**：
- 必须用 `bpy.app.timers.register(fn, first_interval=0.1)` 延迟到主线程执行
- 直接在 handler 里调用 `popup_menu` 会报 context 错误
- `persistent=False`（默认）确保 timer 只执行一次

---

## 9. 调试检查清单

触发器不生效时，按顺序排查：

### 基础配置

1. **`~/.artclaw/config.json` 存在且 `project_root` 正确**
2. **`~/.artclaw/triggers.json` 有匹配规则**  
   检查：`trigger_type="event"` + `event_type` 格式 + `is_enabled=true` + `dcc` 字段
3. **`tool_id` 可被解析**  
   `_resolve_tool_path` 两种策略都失败时返回 None，工具静默跳过

### Blender 特有检查

4. **Handler 是否注册成功**  
   System Console 应有：`[ArtClaw] Registered: save_post wrapper`

5. **Handler 是否被 Blender 清除**  
   在 Script Editor 运行：
   ```python
   import bpy
   for h in bpy.app.handlers.save_post:
       print(h.__name__, getattr(h, '_bpy_persistent', False))
   ```
   若没有 `save_post_wrapper` 或 `_bpy_persistent=False`，说明 persistent 装饰器未生效。

6. **模块缓存问题（reload 后 handler 不触发）**  
   Blender 自动 reload 后旧函数引用失效，解决方案见第 6.3 节 wrapper 模式。  
   临时修复：在 Script Editor 运行：
   ```python
   import sys
   # 清除旧 wrapper registry，强制重建
   sys.modules.pop("__artclaw_blender_wrappers__", None)
   import blender_event_intercept as bei
   bei.register_handlers()
   ```

7. **工具脚本 import 报错**  
   检查工具 `main.py` 是否有顶层 `import bpy`（见第 6.5 节），  
   改为函数内延迟 import。

8. **`artclaw_sdk` 未初始化**  
   工具脚本调用 `import artclaw_sdk as sdk` 时需要 Bridge 已启动。  
   若仅做触发器使用（不需要完整 Bridge），可在工具里做 try/except 降级处理。

### 工具匹配检查

9. **`dcc` 字段过滤**  
   triggers.json 中 `dcc` 字段必须与 `event_data["dcc_type"]` 完全一致（`"blender"` / `"ue5"` 等）。

10. **`use_default_filters` 与 `manifest.defaultFilters` 匹配**  
    `true` 时读 manifest 条件；条件不匹配则跳过该规则。

---

## 10. 为新 DCC 实现触发器层的步骤

以 Maya 为例：

### Step 1：创建 `maya_event_intercept.py`

```python
import sys
from pathlib import Path

_REGISTRY_KEY = "__artclaw_maya_wrappers__"

def _import_shared():
    try:
        import dcc_event_intercept_shared as s
        return s
    except ImportError:
        # 回退：从 config.json 读 project_root，手动加路径
        ...

def _save_impl():
    import maya.cmds as cmds
    shared = _import_shared()
    if not shared:
        return
    scene_path = cmds.file(q=True, sn=True) or ""
    event_data = {
        "dcc_type": "maya",
        "event_type": "file.save",
        "timing": "post",
        "data": {"asset_path": scene_path, "asset_name": "", "asset_class": "MayaFile"},
    }
    result = shared._handle_post_event("file.save", event_data)
    if result.get("issues"):
        _notify_maya_issues(result["issues"])

def register_callbacks():
    import maya.OpenMaya as om
    # Maya 的 callback id 需要保存，unregister 时使用
    ...
```

### Step 2：在 DCC 启动脚本中注册

```python
# userSetup.py (Maya)
import maya.utils
def _init_artclaw():
    from maya_event_intercept import register_callbacks
    register_callbacks()
maya.utils.executeDeferred(_init_artclaw)
```

### Step 3：考虑 DCC 特有的 reload 问题

- **Maya**：`userSetup.py` 只执行一次，无 reload 问题，直接存函数引用即可
- **Blender**：必须使用 wrapper + `sys.modules` 外部 registry + `@persistent` 装饰器（见第 6.3 节）
- **Max**：类似 Blender，需考虑脚本 reload 后回调失效问题