# ArtClaw 触发器事件开发指南

> 版本：1.0
> 日期：2026-04-26
> 依据：`DCCClawBridge/core/dcc_event_manager.py` 实际实现 + `ArtClawToolManager` API 设计
> 适用：工具开发者（写 manifest.json）、DCC 适配器开发者（实现新 DCC 的事件注册）

---

## 1. 核心概念：event_type + timing 分离

**这是最重要的约定，所有地方必须统一遵守。**

系统在整条链路上始终将事件名和时机分开传递：

```
DCC 原生回调 → _on_event(event_type, timing, data) → POST /api/v1/dcc-events
                                                          ↓
                                                  TriggerEngine 匹配规则
```

### ✅ 正确格式（含 timing 后缀）

```json
"trigger": {
  "type": "event",
  "event": "asset.save.pre",
  "dcc": "ue5"
}
```

**约定**：`event` 字段使用 `{base}.{timing}` 格式，`timing` 内嵌在字段末段，不单独拆分为字段。
这与 Tool Manager UI 创建触发器时的行为一致，也是 `trigger_service._manifest_trigger_to_rule` 读取的格式。

TriggerEngine 的 `_event_matches` 会自动将 `"asset.save.pre"` 拆分为 base=`"asset.save"` + timing=`"pre"`，
与 DCCClawBridge 发来的 `event_type="asset.save"` + `event_data.timing="pre"` 做正确比对。

---

## 2. API 数据结构

### 2.1 DCCClawBridge → Tool Manager（发送方）

```python
# dcc_event_manager.py _on_event()
payload = {
    "dcc_type":   "unreal_engine5.4.0",   # adapter.get_software_name() + get_software_version()
    "event_type": "asset.save",            # 基础事件名，不含 timing
    "timing":     "pre",                   # "pre" 或 "post"
    "data":       { ... }                  # 事件携带的上下文数据（见第 4 节）
}
POST http://localhost:9876/api/v1/dcc-events
```

### 2.2 Tool Manager 响应（接收方）

```json
{
  "success": true,
  "data": {
    "triggered": true,
    "rules_matched": 1,
    "rules_executed": 1,
    "blocked": false,
    "block_reason": null
  }
}
```

`blocked: true` 时，DCCClawBridge 应阻止 DCC 继续执行原操作（仅 `timing=pre` 有效）。

---

## 3. 支持的事件列表

### 3.1 Unreal Engine（`dcc: "ue5"`）

| event | timing | 数据来源 | event_data 字段 |
|-------|--------|---------|----------------|
| `asset.save` | `pre` | C++ Subsystem `on_asset_pre_save` delegate | `asset_path: str` |
| `asset.save` | `post` | C++ Subsystem `on_asset_post_save` delegate | `asset_path: str`, `success: bool` |
| `asset.import` | `post` | C++ Subsystem `on_asset_imported` delegate | `asset_path: str`, `asset_class: str` |
| `asset.delete` | `pre` | C++ Subsystem `on_asset_pre_delete` delegate | `asset_path: str` |
| `level.save` | `pre` | C++ Subsystem `on_level_pre_save` delegate | `level_path: str` |
| `level.save` | `post` | C++ Subsystem `on_level_post_save` delegate | `level_path: str`, `success: bool` |
| `level.load` | `post` | C++ Subsystem `on_level_loaded` delegate | `level_path: str` |
| `editor.startup` | `post` | 注册时立即触发（one-shot） | `immediate: true` |

> `asset.save.pre` 支持拦截：`blocked: true` 时可阻止 UE 保存资源。

### 3.2 Blender（`dcc: "blender"`）

| event | timing | 数据来源 | event_data 字段 |
|-------|--------|---------|----------------|
| `file.save` | `pre` | `bpy.app.handlers.save_pre` | `scene: str`（场景名） |
| `file.save` | `post` | `bpy.app.handlers.save_post` | `scene: str` |
| `file.load` | `post` | `bpy.app.handlers.load_post` | `scene: str` |
| `render.start` | `pre` | `bpy.app.handlers.render_pre` | `scene: str` |
| `file.export` | — | ⚠️ 有限支持，无法拦截所有导出操作 | — |

> Blender 的 `bpy.app.handlers.save_pre` **不支持返回值拦截**（Blender 不提供取消保存的机制），
> `timing=pre` 触发后 Tool Manager 的 `blocked` 字段在 Blender 侧无法生效。

### 3.3 Maya（`dcc: "maya2024"`）

| event | timing | 数据来源 | event_data 字段 |
|-------|--------|---------|----------------|
| `file.save` | `pre` | `om.MSceneMessage.addCallback(kBeforeSave)` | `client_data: str` |
| `file.save` | `post` | `om.MSceneMessage.addCallback(kAfterSave)` | `client_data: str` |
| `file.export` | `pre` | `kBeforeExport` | `client_data: str` |
| `file.export` | `post` | `kAfterExport` | `client_data: str` |
| `file.import` | `pre` | `kBeforeImport` | `client_data: str` |
| `file.import` | `post` | `kAfterImport` | `client_data: str` |
| `file.open` | `post` | `kAfterOpen` | `client_data: str` |
| `scene.new` | `post` | `kAfterNew` | `client_data: str` |

### 3.4 3ds Max（`dcc: "max2024"`）

| event | timing | event_data 字段 |
|-------|--------|----------------|
| `file.save` | `pre` | `{}` |
| `file.save` | `post` | `{}` |

### 3.5 Houdini（`dcc: "houdini"`）

| event | timing | event_data 字段 |
|-------|--------|----------------|
| `file.save` | `pre` | `hip_file: str` |
| `file.save` | `post` | `hip_file: str` |

### 3.6 ComfyUI / SD（其他 DCC）

| DCC | event | timing |
|-----|-------|--------|
| comfyui | `workflow.queue` | `pre` / `post` |
| comfyui | `workflow.complete` | `post` |

---

## 4. 工具脚本中读取事件数据

### 4.1 sdk.event.parse()

event trigger 工具通过 `sdk.event.parse(kwargs)` 读取 Tool Manager 传入的上下文，
**不直接调用 DCC 原生 API**。

```python
import artclaw_sdk as sdk

def check_naming(**kwargs):
    evt = sdk.event.parse(kwargs)

    asset_path  = evt.asset_path   # str | None，来自 event_data["asset_path"]
    asset_class = evt.asset_class  # str | None，来自 event_data["asset_class"]
    asset_name  = evt.asset_name   # str | None，资产名（路径末段）
    timing      = evt.timing       # "pre" | "post"
    dcc_type    = evt.dcc_type     # 如 "unreal_engine5.4.0"

    # 业务逻辑...
    return sdk.result.allow("通过")
    # 或
    return sdk.result.reject(reason="命名不合规", data={...})
```

### 4.2 返回值约定

| 情景 | 返回 | 效果 |
|------|------|------|
| pre 事件，检查通过 | `sdk.result.allow(message)` | Tool Manager 返回 `blocked: false` |
| pre 事件，检查不通过 | `sdk.result.reject(reason, data)` | Tool Manager 返回 `blocked: true`，DCC 侧阻止操作（UE 支持，Blender 不支持） |
| post 事件，执行完成 | `sdk.result.success(data, message)` | 正常完成通知 |
| post 事件，执行失败 | `sdk.result.fail(error, message)` | 失败通知 |

---

## 5. manifest.json 触发器配置规范

### 5.1 完整字段说明

```json
{
  "triggers": [
    {
      "id":      "uuid-v4",          // 必填，全局唯一，用于 triggers.json 去重
      "name":    "触发器名称",        // 显示用
      "enabled": true,               // false 时 Tool Manager 不加载此规则

      "trigger": {
        "type":  "event",            // 必须为 "event"（event trigger）
        "event": "asset.save.pre",   // {base}.{timing} 格式，⚠️ timing 内嵌在末段
        "dcc":   "ue5"               // 与 targetDCCs 一致
      },

      "execution": {
        "mode": "silent"             // silent | notify | interactive
      },

      "useDefaultFilters": true      // true = 复用 manifest.defaultFilters
    }
  ]
}
```

### 5.2 execution.mode 说明

| mode | 行为 |
|------|------|
| `silent` | 静默执行，不弹通知 |
| `notify` | 执行完成后弹通知（Toast） |
| `interactive` | 执行前弹确认对话框（pre 事件常用） |

### 5.3 常见错误

| 错误写法 | 正确写法 | 后果 |
|---------|---------|------|
| `"event": "asset.save"` (缺少 timing 后缀) | `"event": "asset.save.pre"` 或 `"asset.save.post"` | engine 匹配时 timing 不确定，可能误触发 post 规则 |
| `"event": "file.save"` (Blender，缺后缀) | `"event": "file.save.pre"` 或 `"file.save.post"` | 同上 |
| `"dcc": "Blender"` 大写 | `"dcc": "blender"` 小写，与 `get_software_name()` 一致 | 静默不触发 |
| 缺少 `"id"` 字段 | 补充 UUID v4 | 触发器无法被 triggers.json 去重，重启后重复插入 |

---

## 6. 新增 DCC 支持（适配器开发者）

实现步骤：

**1. 在 `_get_handler_map()` 的 dcc 分支里返回 handler 字典**

```python
elif dcc_name == "your_dcc":
    return self._get_your_dcc_handlers()
```

**2. 实现 handler 字典**

```python
def _get_your_dcc_handlers(self) -> Dict[str, Callable]:
    return {
        "file.save": lambda et: self._register_your_dcc_file_save(),
        # 其他事件...
    }
```

**3. 实现注册函数，调用 `_on_event`**

```python
def _register_your_dcc_file_save(self) -> Optional[str]:
    try:
        def on_pre_save(*args):
            # ⚠️ event_type 和 timing 必须分开传，不要拼接
            self._on_event("file.save", "pre", {"extra_data": ...})

        def on_post_save(*args):
            self._on_event("file.save", "post", {"extra_data": ...})

        # 用 DCC 原生 API 注册回调
        your_dcc.register_pre_save(on_pre_save)
        your_dcc.register_post_save(on_post_save)

        # ⚠️ 必须保存引用，否则无法反注册
        self._handler_refs["your_dcc.file.save.pre"] = on_pre_save
        self._handler_refs["your_dcc.file.save.post"] = on_post_save

        return "your_dcc_file_save"

    except Exception as e:
        logger.error(f"Failed to register file.save: {e}")
        return None   # 返回 None 表示注册失败，引擎会记录警告
```

**4. 实现反注册（可选但推荐）**

在 `_unregister_single_event` 中处理你的 DCC 类型，从 `_handler_refs` 取出引用并清理。

**5. 关键约定**

- `_on_event(event_type, timing, data)` — **永远分开传 event_type 和 timing**
- 注册失败返回 `None`，成功返回任意非空字符串（作为 callback_id）
- handler 函数引用必须存到 `self._handler_refs`，key 建议用 `"{dcc}.{event}.{timing}"` 格式
- DCC 原生模块用 lazy import（在函数体内 `import your_dcc`），不在模块顶层 import

---

## 7. 调试检查清单

触发器不生效时，按顺序排查：

1. **manifest.json 格式** — 用 tool-compliance-checker 运行一次，Rule 25.7 会检查 event 格式
2. **triggers.json 同步** — 重启 Tool Manager，确认 `~/.artclaw/triggers.json` 里有这条规则
3. **load_rules() 结果** — 在 DCC 控制台查看 `artclaw.events` 日志，确认加载到规则
4. **event_types_to_register** — 确认加载的规则中有对应的 `event_type`（不含 timing）
5. **bpy.app.handlers / DCC callbacks** — 确认 DCC 原生回调已注册（不是 None）
6. **Tool Manager 连接** — 确认 `http://localhost:9876` 可访问
7. **dcc_type 匹配** — 查看 API 日志，确认发送的 `dcc_type` 与规则的 `dcc` 能被 TriggerEngine 匹配
