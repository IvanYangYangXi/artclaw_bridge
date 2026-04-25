# artclaw_sdk 工具运行时 API 规范

> 版本: 2.0  
> 日期: 2026-04-25  
> 关联: [SDK/API 标准化总览](./sdk-api-standardization-overview.md) · [工具合规改造计划](./artclaw-sdk-tool-compliance-plan.md)

---

## 1. 定位

`artclaw_sdk`（路径 `core/artclaw_sdk/`）是**工具脚本的运行时 SDK**，运行在 DCC 进程内部。

| 接口 | 调用方 | 职责 |
|------|--------|------|
| `BaseDCCAdapter`（sdk-dcc-interface-spec.md） | MCP Server / Bridge 框架 | DCC 插件基础设施 |
| `PlatformAdapter`（sdk-platform-adapter-spec.md） | Bridge Core | AI 平台对接 |
| **`artclaw_sdk`（本文档）** | **工具脚本 main.py** | **参数解析、上下文查询、对象筛选、结果上报、日志、进度** |

SDK **只包含查询和上报类 API**，不包含操作类 API（rename/delete/duplicate/export/import）。操作类逻辑由工具脚本使用 DCC 原生 API 直接实现，因为每个工具的操作需求差异大，强行抽象反而限制灵活性。

---

## 2. 模块总览

```
artclaw_sdk/
├── __init__.py       # 入口 + 顶层便捷 API
├── params.py         # 参数解析
├── filters.py        # 对象筛选
├── context.py        # 上下文查询（选中对象、场景信息）
├── result.py         # 结果上报
├── progress.py       # 进度上报
├── logger.py         # 日志
└── dcc/              # DCC 适配器（查询层，非操作层）
    ├── base.py       # 抽象基类
    ├── ue.py         # ✅ 完整实现
    ├── blender.py    # ✅ 完整实现
    └── ...           # 🔧 骨架（按需补充）
```

---

## 3. 顶层 API（`import artclaw_sdk as sdk`）

### 3.1 子模块

| 访问方式 | 说明 |
|----------|------|
| `sdk.params` | 参数解析（§4） |
| `sdk.filters` | 对象筛选（§5） |
| `sdk.context` | 上下文查询（§6） |
| `sdk.result` | 结果上报（§7） |
| `sdk.progress` | 进度上报（§8） |
| `sdk.log` | 日志（§9）。⚠️ 当前导出名为 `logger`，需新增 `log` 别名 |

### 3.2 顶层便捷函数

| 函数 | 等价于 | 状态 |
|------|--------|------|
| `sdk.parse_params(inputs, raw)` | `sdk.params.parse_params()` | ⚠️ 需新增 |
| `sdk.get_context()` | `sdk.context.get_context()` | ✅ |
| `sdk.get_selected_assets()` | `sdk.context.get_selected_assets()` | ⚠️ 需新增 |
| `sdk.get_selected_objects()` | `sdk.context.get_selected_objects()` | ⚠️ 需新增 |
| `sdk.filter_objects(objs, **kw)` | `sdk.filters.filter_objects()` | ✅ |
| `sdk.get_current_dcc()` | — | ✅ |

---

## 4. params — 参数解析

```python
sdk.params.parse_params(manifest_inputs: list[dict], raw_params: dict) -> dict
```

按 manifest `inputs` 做类型转换 + 必填校验 + 默认值填充。必填缺失抛 `ValueError`。

```python
sdk.params.get_default_values(manifest_inputs) -> dict
sdk.params.merge_with_defaults(params, manifest_inputs) -> dict
sdk.params.cast_value(value, target_type: str) -> Any
```

### 支持的类型转换

| target_type | Python 类型 | 转换规则 |
|-------------|-------------|----------|
| `"string"` | str | `str(value)` |
| `"number"` / `"float"` | int/float | 字符串自动解析 |
| `"integer"` / `"int"` | int | 浮点截断 |
| `"boolean"` / `"bool"` | bool | `"true"/"1"/"yes"` → True |
| `"array"` | list | JSON 解析或逗号分隔 |
| `"object"` | dict | JSON 解析 |

---

## 5. filters — 对象筛选

```python
# 组合筛选
sdk.filters.filter_objects(objects, type=None, name_pattern=None, path_pattern=None, use_regex=True) -> list[dict]

# 单维度筛选
sdk.filters.filter_by_type(objects, type_filter: str | list[str]) -> list[dict]
sdk.filters.filter_by_name(objects, pattern: str, use_regex=False) -> list[dict]
sdk.filters.filter_by_path(objects, pattern: str, use_regex=False) -> list[dict]

# 查找 + 分组
sdk.filters.find_objects_by_name(objects, name, exact_match=False) -> list[dict]
sdk.filters.group_by_type(objects) -> dict[str, list[dict]]
```

### 对象字典格式

筛选函数依赖以下 key：

| key | 类型 | 说明 |
|-----|------|------|
| `name` | str | 短名称 |
| `type` | str | 对象类型（DCC 特有值，大小写不敏感比较） |
| `path` | str | 完整路径/标识符 |

### type 值：动态获取

不同 DCC 的 type 值差异大，**不硬编码映射表**。工具脚本应通过 MCP 运行 Python 动态查询当前 DCC 中可用的类型列表：

```python
# UE: 查询选中资产的 class 名
selected = sdk.context.get_selected_assets()
types = set(obj["class"] for obj in selected)
# 常见: "StaticMesh", "SkeletalMesh", "Texture2D", "MaterialInstanceConstant"

# Blender: 查询场景中的对象类型
selected = sdk.context.get_selected_objects()
types = set(obj["type"] for obj in selected)
# 常见: "MESH", "LIGHT", "CAMERA", "EMPTY", "ARMATURE"
```

manifest `defaultFilters.typeFilter.types` 中填写的值必须与目标 DCC 的实际 type 值一致。

---

## 6. context — 上下文查询

### 核心区分：资产 vs 场景对象

DCC 中"选中的东西"分两类，SDK 必须区分：

| 概念 | UE 对应 | Blender 对应 | 说明 |
|------|---------|-------------|------|
| **资产（Asset）** | Content Browser 中选中的资产文件 | — (Blender 无独立资产管理器) | 文件级对象 |
| **场景对象（Object）** | Viewport 中选中的 Actor | Viewport 中选中的 Object | 场景实例 |

### API

```python
# 获取资源管理器中选中的资产（UE Content Browser 等）
sdk.context.get_selected_assets() -> list[dict]

# 获取场景/视口中选中的对象（UE Actor、Blender Object 等）
sdk.context.get_selected_objects() -> list[dict]

# 获取全部选中（资产 + 场景对象合并，向后兼容）
sdk.context.get_selected() -> list[dict]

# 场景信息
sdk.context.get_context() -> dict
sdk.context.get_scene_path() -> str | None
sdk.context.get_scene_info() -> dict
sdk.context.get_viewport_info() -> dict
```

### get_selected_assets() 返回格式

"资产"指资源管理器中选中的资产文件：UE 是 Content Browser，其他 DCC 是操作系统文件管理器中选中的文件（如果有对接的话）。

**UE**:
```python
[{
    "name": "SM_Chair",
    "path": "/Game/Props/SM_Chair",
    "type": "asset",
    "class": "StaticMesh",
}]
```

**Blender / Maya / 其他 DCC**: 如无资源管理器对接，返回 `[]`。未来可对接系统文件管理器选中的文件。

### get_selected_objects() 返回格式

**UE**:
```python
[{
    "name": "SM_Chair_01",
    "path": "/Game/Maps/Level.Level:SM_Chair_01",
    "type": "actor",
    "class": "StaticMeshActor",
    "location": (100.0, 200.0, 0.0),
    "rotation": (0.0, 0.0, 0.0),
}]
```

**Blender**:
```python
[{
    "name": "Cube.001",
    "long_name": "Cube.001",
    "type": "MESH",
    "location": [0.0, 0.0, 0.0],
    "is_active": True,
    "vertices": 8,
}]
```

---

## 7. result — 结果上报

```python
sdk.result.success(data=None, message=None) -> dict
# {"success": True, "data": ..., "error": None, "message": ...}

sdk.result.fail(error=None, message=None, data=None) -> dict
# {"success": False, "data": ..., "error": ..., "message": ...}

sdk.result.error(...)   # ⚠️ 需新增，fail() 的别名

sdk.result.from_exception(exc, message=None) -> dict
sdk.result.allow(message=None, data=None) -> dict   # 触发规则 pre-event
sdk.result.reject(reason=None, data=None) -> dict    # 触发规则 pre-event
```

返回值契约：工具入口函数**必须**返回 dict，且包含 `success: bool`。

---

## 8. progress — 进度上报

```python
sdk.progress.start(total=100, message=None)
sdk.progress.update(current: int, message=None)
sdk.progress.increment(amount=1, message=None)
sdk.progress.finish(message=None)
sdk.progress.get_progress() -> dict
```

---

## 9. log — 日志

```python
sdk.log.info(message)
sdk.log.warning(message)
sdk.log.error(message)
sdk.log.debug(message)
sdk.log.exception(message)

tool_log = sdk.log.get_tool_logger("my-tool")
tool_log.info("xxx")  # 输出 "[my-tool] xxx"
```

---

## 10. DCC 适配器接口

### 基类 `BaseDCCBackend`

适配器只负责**查询**，不负责操作（rename/delete 等从基类移除）。

```python
class BaseDCCBackend(ABC):
    @abstractmethod def get_dcc_name(self) -> str
    @abstractmethod def get_dcc_version(self) -> str
    @abstractmethod def get_context(self) -> dict
    @abstractmethod def get_selected_assets(self) -> list[dict]   # 新增
    @abstractmethod def get_selected_objects(self) -> list[dict]   # 新增
    @abstractmethod def get_selected(self) -> list[dict]           # 合并，向后兼容
    @abstractmethod def get_scene_path(self) -> str | None
    @abstractmethod def get_scene_info(self) -> dict
    def get_viewport_info(self) -> dict   # 可选，默认 {}
```

### 实现状态

| DCC | get_selected_assets | get_selected_objects | get_scene_info | 状态 |
|-----|--------------------|--------------------|----------------|------|
| UE | ✅ EditorUtilityLibrary | ✅ EditorLevelLibrary | ✅ | 完整 |
| Blender | ✅ (返回 []) | ✅ bpy.context.selected_objects | ✅ | 完整 |
| 其他 | 🔧 骨架 | 🔧 骨架 | 🔧 骨架 | 按需 |

优先级: UE → Blender → 其他。

---

## 11. 需修复清单

| # | 问题 | 修复 | 文件 |
|---|------|------|------|
| F1 | `sdk.log` 不存在 | 新增 `log = logger` | `__init__.py` |
| F2 | `sdk.parse_params()` 未导出 | 新增 `from .params import parse_params` | `__init__.py` |
| F3 | `sdk.result.error()` 不存在 | 新增 `error = fail` | `result.py` |
| F4 | context 无 `get_selected_assets/objects` 区分 | 拆分实现 | `context.py` + `dcc/*.py` |
| F5 | 基类含操作类方法 | 移除 rename/delete/duplicate/export/import | `dcc/base.py` |
