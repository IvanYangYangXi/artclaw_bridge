# DCC 触发器本地执行层开发文档

> 版本：1.1  
> 日期：2026-04-26  
> 依据：`UEClawBridge/Content/Python/dcc_event_intercept.py` 实际实现（已校验）  
> 适用：为新 DCC（Blender / Maya / Max 等）实现等价的触发器本地执行层

---

## 1. 架构概述

UE 侧的触发器执行**完全在本地（DCC 内部）完成**，不经过 Tool Manager HTTP 服务：

```
DCC 原生事件 (C++ delegate / bpy.app.handlers / MSceneMessage)
    │
    ▼
DCC Python 层入口函数（如 check_pre_save / handle_actor_placed）
    │  ① 可选：_dedup_event() 去重保护
    ▼  读取本地文件
~/.artclaw/config.json   → project_root（SDK路径、工具根目录）
~/.artclaw/triggers.json ← Tool Manager 启动时同步写入
    │
    ▼  _match_event() 精确匹配 event_type == "{base}.{timing}"
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
- 所有检查在 DCC 进程内同步完成，pre 事件可真正拦截
- `triggers.json` 是唯一数据源，Tool Manager 写，DCC 读，**DCC 不写**
- `config.json` 提供 `project_root`，用于定位 SDK 和工具目录
- 工具脚本通过 `_execute_tool_generic` 动态 import + 调用，无需注册
- pre 事件：第一个 reject 即拦截，后续规则不再执行（break）
- post 事件：所有匹配规则都执行，结果汇总返回

---

## 2. triggers.json 规则格式

```json
{
  "id": "uuid",
  "tool_id": "marketplace/SM命名检查",
  "name": "SM保存检查",
  "trigger_type": "event",
  "event_type": "asset.save.pre",
  "execution_mode": "notify",
  "is_enabled": true,
  "use_default_filters": true,
  "conditions": {}
}
```

| 字段 | 说明 |
|------|------|
| `tool_id` | `"{source}/{tool_name}"`，source 来自 manifest 的 `source` 字段 |
| `event_type` | 完整格式 `"{base}.{timing}"`，**不分离** |
| `execution_mode` | `silent` / `notify` / `interactive` |
| `use_default_filters` | `true` = 用 `manifest.defaultFilters`；`false` = 用 `conditions` |
| `conditions` | `use_default_filters=false` 时的自定义条件（path + typeFilter） |

### 2.1 event_type 格式约定（单一规范）

```
event_type = "{base}.{timing}"
```

| 示例 | base | timing |
|------|------|--------|
| `asset.save.pre` | `asset.save` | `pre` |
| `asset.save.post` | `asset.save` | `post` |
| `asset.place.post` | `asset.place` | `post` |
| `asset.delete.pre` | `asset.delete` | `pre` |
| `asset.import.post` | `asset.import` | `post` |
| `file.save.pre` | `file.save` | `pre` |

匹配逻辑（`_match_event`）：
```python
trigger.get("event_type", "") == f"{event_base}.{timing}"  # 精确等于，无兼容逻辑
```

---

## 3. 核心公共函数说明

新 DCC 实现时需要复用或参考以下函数（均来自 UE `dcc_event_intercept.py`）：

### 3.1 `_load_config()` / `_load_triggers()`

```python
# 读 ~/.artclaw/config.json → 提供 project_root
config = _load_config()
# 读 ~/.artclaw/triggers.json → 所有触发器规则列表
triggers = _load_triggers()
```

### 3.2 `_ensure_sdk_path(config)`

```python
# 将 {project_root}/subprojects/DCCClawBridge/core 加入 sys.path
# 必须在 import artclaw_sdk 之前调用
_ensure_sdk_path(config)
```

### 3.3 `_resolve_tool_path(tool_id, config)`

```python
# tool_id = "marketplace/SM命名检查"
# 搜索 {project_root}/tools/{source}/**/{tool_name}/
# 匹配策略：① 目录名直接匹配 ② manifest id/name 字段匹配（处理空格差异）
tool_path = _resolve_tool_path(tool_id, config)  # 返回绝对路径或 None
```

### 3.4 `_match_filters(conditions, asset_path, asset_name, asset_class)`

```python
# 空 conditions → 全部匹配（返回 True）
# path: 支持 startswith 前缀 + fnmatch glob
# typeFilter.types: asset_class 必须在列表中
matched = _match_filters(conditions, "/Game/Foo/Bar", "Bar", "StaticMesh")
```

### 3.5 `_execute_tool_generic(tool_path, manifest, event_data)`

```python
# 从 manifest.implementation.entry/function 读取入口
# importlib.reload 支持热更新
# 函数签名自适应（见下方说明）
result = _execute_tool_generic(tool_path, manifest, event_data)
# 返回: {"action": "allow"/"reject"/"error", "reason": str}
```

**函数签名自适应规则**（按优先级）：
1. 函数有 `params` 和 `event_data` 参数 → `fn(params={}, event_data=event_data)`
2. 函数只有 `event_data` 参数 → `fn(event_data=event_data)`
3. 函数有其他参数（`**kwargs`） → `fn(**event_data.get("data", {}), event_data=event_data)`
4. 无参数 → `fn()`

---

## 4. 事件入口函数规范

每个 DCC 事件对应一个入口函数，负责：
1. （可选）`_dedup_event()` 去重
2. 组装标准 `event_data` 字典
3. 调用 `_check_pre_event` 或 `_handle_post_event`

### 4.1 标准 event_data 结构

```python
event_data = {
    "dcc_type": "ue5",           # DCC 标识字符串，与 triggers.json dcc 字段一致
    "event_type": "asset.save",  # 基础名（不含 timing）——仅供工具脚本 sdk.event.parse() 读取
    "timing": "pre",             # "pre" | "post"
    "data": {                    # 工具脚本通过 sdk.event.parse() 读取的具体字段
        "asset_path":  str,      # 完整资产路径，如 /Game/Foo/Bar.Bar（含资产名后缀）
        "asset_name":  str,      # 资产名，如 Bar
        "asset_class": str,      # 资产类型，如 StaticMesh（可为空）
        # 其他事件特有字段（见各入口函数）
    }
}
```

> **注意**：`asset_path` 应为 `PackageName.AssetName` 格式（`/Game/Foo/Bar.Bar`），
> 如果 C++ 只传 PackageName（`/Game/Foo/Bar`），需在入口函数里补全。

### 4.2 Pre 事件入口模板

```python
def check_pre_save(asset_path: str, asset_name: str, file_name: str = "") -> Dict[str, Any]:
    """返回 {"blocked": bool, "reason": str, "execution_mode": str}"""
    # 补全 asset_path（如 C++ 只传 package path）
    if "." not in asset_path.rsplit("/", 1)[-1]:
        asset_path = f"{asset_path}.{asset_name}"

    asset_class = _get_asset_class(asset_path)  # UE 专用，其他 DCC 按需实现

    event_data = {
        "dcc_type": "ue5",
        "event_type": "asset.save",
        "timing": "pre",
        "data": {
            "asset_path":   asset_path,
            "asset_name":   asset_name,
            "asset_class":  asset_class,
            "file_name":    file_name,    # UE 特有额外字段
            "package_path": asset_path.split(".")[0],
        },
    }
    return _check_pre_event("asset.save", event_data)
```

**`_check_pre_event` 返回格式**：
```python
{"blocked": bool, "reason": str, "execution_mode": str}
```
- `blocked=True` 时 DCC 应阻止原操作（仅支持真正拦截的 DCC，如 UE）
- `execution_mode` 决定通知方式（`silent/notify/interactive`）

### 4.3 Post 事件入口模板

```python
def handle_actor_placed(actor_path: str, actor_name: str, actor_class: str) -> Dict[str, Any]:
    """返回 {"executed": int, "issues": list}"""
    # ⚠️ 去重：UE OnActorSpawned 一次操作触发两次，key 用源资产路径（不含实例名）
    dedup_key = f"asset.place.post::{actor_path}"
    if _dedup_event(dedup_key):
        return {"executed": 0, "issues": []}

    event_data = {
        "dcc_type": "ue5",
        "event_type": "asset.place",
        "timing": "post",
        "data": {
            "asset_path":  actor_path,
            "asset_name":  actor_name,
            "asset_class": actor_class,
        },
    }
    return _handle_post_event("asset.place", event_data)
```

**`_handle_post_event` 返回格式**：
```python
{"executed": int, "issues": [{"tool": str, "reason": str}, ...]}
```
- `executed`：实际执行的工具数量
- `issues`：所有 reject 的工具和原因（不拦截，只收集）

---

## 5. 去重保护（防重复触发）

部分 DCC 事件在单次用户操作时会多次触发，需加去重保护：

```python
import time

_recent_events: Dict[str, float] = {}
_DEDUP_WINDOW_SEC = 0.5   # 500ms 内同 key 只处理一次

def _dedup_event(key: str) -> bool:
    """返回 True 表示重复（应跳过），False 表示首次（应处理）。"""
    now = time.monotonic()
    if key in _recent_events and (now - _recent_events[key]) < _DEDUP_WINDOW_SEC:
        return True
    _recent_events[key] = now
    return False
```

**去重 key 的选取原则**：
- 用**稳定不变**的内容做 key，不用每次生成不同的 ID（如 UE UAID 实例名）
- 推荐格式：`"{event_type}::{asset_path}"` 或 `"{event_type}::{blend_file_path}"`

**需要去重的已知场景**：

| DCC | 事件 | 原因 |
|-----|------|------|
| UE | `asset.place.post` | `OnActorSpawned` 在单次拖入时触发两次（preview + real actor） |
| Blender | `file.save.pre` | 部分 Blender 版本 `save_pre` 触发两次 |
| 任何 DCC | 批量操作 | 逐项触发，需考虑是否应合并处理 |

**代码层额外保护**（`_check_pre_event` / `_handle_post_event` 内置）：
- 同一次事件调用内，相同 `tool_id` 的规则只执行第一条（防 triggers.json 数据污染）

---

## 6. 通知策略

| execution_mode | UE 行为 | 新 DCC 参考实现 |
|---------------|---------|----------------|
| `silent` | `unreal.log_warning` + 写 pending 文件（C++ 弹气泡） | 打印日志，可选写通知队列 |
| `notify` | `EditorDialog.show_message` 阻塞弹窗 | 主线程弹窗（Blender 用 `bpy.app.timers`） |
| `interactive` | 写 pending 文件，由 C++ 弹确认对话框 | DCC 特有实现 |

**UE 特有的 pending 文件机制**：
- pending 文件路径：`~/.artclaw/_pending_notify.json`
- `notify` 模式弹窗后必须写 `{"mode": "handled"}` 防止 C++ 二次弹窗
- `silent` 模式写 `{"mode": "silent", "message": "...", "asset_path": "..."}` 由 C++ `FlushPendingNotify` 弹气泡
- 新 DCC 无 C++ 端，不需要实现 pending 文件机制，直接用 DCC 原生通知 API

---

## 7. 为新 DCC 实现等价层的步骤

以 Blender 为例：

### Step 1：创建 `blender_event_intercept.py`

放在 Blender addon 的 Python 目录中。直接复用 UE 版的公共函数（`_load_config`、
`_load_triggers`、`_resolve_tool_path`、`_ensure_sdk_path`、`_match_filters`、
`_match_event`、`_check_pre_event`、`_handle_post_event`、`_execute_tool_generic`、
`_dedup_event`），只实现 Blender 特有的入口函数和通知函数：

```python
import bpy
import time
from typing import Any, Dict

# 复用公共函数（从共享层 import，见第 8 节）
from dcc_event_intercept_shared import (
    _load_config, _load_triggers, _resolve_tool_path, _ensure_sdk_path,
    _match_filters, _match_event, _check_pre_event, _handle_post_event,
    _execute_tool_generic, _dedup_event,
)

def on_pre_save(scene, depsgraph=None):
    """bpy.app.handlers.save_pre 回调入口。"""
    blend_path = bpy.data.filepath or ""
    scene_name = scene.name if scene else ""

    dedup_key = f"file.save.pre::{blend_path}"
    if _dedup_event(dedup_key):
        return

    event_data = {
        "dcc_type": "blender",
        "event_type": "file.save",
        "timing": "pre",
        "data": {
            "asset_path": blend_path,
            "asset_name": scene_name,
            "asset_class": "BlendFile",
        },
    }
    result = _check_pre_event("file.save", event_data)
    # ⚠️ Blender save_pre 不支持拦截，只能通知
    if result.get("blocked"):
        _notify_blender(result.get("reason", ""), result.get("execution_mode", "notify"))


def on_post_save(scene, depsgraph=None):
    """bpy.app.handlers.save_post 回调入口。"""
    blend_path = bpy.data.filepath or ""
    scene_name = scene.name if scene else ""

    event_data = {
        "dcc_type": "blender",
        "event_type": "file.save",
        "timing": "post",
        "data": {
            "asset_path": blend_path,
            "asset_name": scene_name,
            "asset_class": "BlendFile",
        },
    }
    _handle_post_event("file.save", event_data)


def _notify_blender(reason: str, mode: str) -> None:
    """Blender 通知：silent 打印日志，notify 延迟弹窗。"""
    print(f"[ArtClaw] {reason}")
    if mode == "notify":
        def show_popup():
            # 通过 bpy.context.window_manager.popup_menu 实现
            def draw(self, context):
                self.layout.label(text=reason)
            bpy.context.window_manager.popup_menu(draw, title="ArtClaw", icon="ERROR")
        bpy.app.timers.register(show_popup, first_interval=0.05)
```

### Step 2：在 addon 启动时注册

```python
import bpy
from . import blender_event_intercept as intercept

def register():
    if intercept.on_pre_save not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(intercept.on_pre_save)
    if intercept.on_post_save not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(intercept.on_post_save)

def unregister():
    if intercept.on_pre_save in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(intercept.on_pre_save)
    if intercept.on_post_save in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(intercept.on_post_save)
```

> **防重复注册**：Blender addon reload 时 `register()` 会再次调用，注册前检查避免 handler 重复。

---

## 8. 共享工具函数提取计划（P0 优先）

目前公共函数都在 UE 的 `dcc_event_intercept.py` 里，新 DCC 实现时需要复制代码。
建议先提取共享层，再开发各 DCC 的 intercept：

**目标文件**：
```
DCCClawBridge/core/dcc_event_intercept_shared.py
```

各 DCC intercept 脚本 import 共享层，只实现 DCC 特有部分：

```
blender_event_intercept.py  ← import shared + 实现 on_pre_save/on_post_save/_notify_blender
maya_event_intercept.py     ← import shared + 实现 MSceneMessage 回调 + _notify_maya
max_event_intercept.py      ← import shared + 实现 pymxs 回调 + _notify_max
```

**开发优先级**：

| 优先级 | 目标 | 依赖 | 预估工作量 |
|--------|------|------|----------|
| P0 | 提取 `dcc_event_intercept_shared.py` | 无 | 1-2h |
| P1 | `blender_event_intercept.py` | P0 | 2-3h |
| P2 | `maya_event_intercept.py` | P0 | 2-3h |
| P3 | `max_event_intercept.py` | P0 | 3-4h |

---

## 9. 调试检查清单

触发器不生效时，按顺序排查：

1. **`~/.artclaw/config.json` 存在且 `project_root` 正确** — 工具路径全依赖此字段
2. **`~/.artclaw/triggers.json` 有匹配规则** — `trigger_type="event"` + `event_type="{base}.{timing}"` + `is_enabled=true`
3. **`tool_id` 对应目录存在** — `_resolve_tool_path` 两种策略都失败时返回 None，工具静默跳过
4. **`use_default_filters` 与 manifest.defaultFilters 一致** — `true` 时读 manifest 条件，条件不匹配则跳过
5. **工具脚本 import 正确** — `_execute_tool_generic` 失败时返回 `{"action": "error"}`，看 log
6. **去重 key 是否过于严格** — 如果合法的连续操作被误跳过，调大 `_DEDUP_WINDOW_SEC` 或修改 key 构成
7. **Blender save_pre 不支持拦截** — `blocked=True` 只能通知，无法阻止保存