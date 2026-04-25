# artclaw_sdk 工具运行时 API 规范

> 版本: 1.0  
> 日期: 2026-04-25  
> 关联: [SDK/API 标准化总览](./sdk-api-standardization-overview.md) · [工具合规改造计划](./artclaw-sdk-tool-compliance-plan.md)

---

## 1. 定位

`artclaw_sdk`（路径 `core/artclaw_sdk/`）是**工具脚本的运行时 SDK**，运行在 DCC 进程内部。

它与项目中另外两套接口的关系：

| 接口 | 调用方 | 职责 |
|------|--------|------|
| `BaseDCCAdapter`（sdk-dcc-interface-spec.md） | MCP Server / Bridge 框架 | DCC 插件的基础设施（生命周期、主线程调度、MCP 注册） |
| `PlatformAdapter`（sdk-platform-adapter-spec.md） | Bridge Core | AI 平台对接（OpenClaw/LobsterAI 等） |
| **`artclaw_sdk`（本文档）** | **工具脚本 main.py** | **工具开发者面向的统一 API（参数、筛选、结果、日志、进度）** |

`artclaw_sdk` 自动检测当前 DCC 环境，加载对应适配器。工具脚本只需 `import artclaw_sdk as sdk`，无需关心底层 DCC 差异。

---

## 2. 模块总览

```
artclaw_sdk/
├── __init__.py       # 入口 + 顶层便捷 API
├── params.py         # 参数解析
├── filters.py        # 对象筛选
├── context.py        # 上下文查询
├── result.py         # 结果上报
├── progress.py       # 进度上报
├── logger.py         # 日志
└── dcc/              # DCC 适配器
    ├── base.py       # 抽象基类
    ├── ue.py
    ├── blender.py
    ├── maya.py
    ├── max.py
    ├── houdini.py
    ├── comfyui.py
    ├── substance_designer.py
    └── substance_painter.py
```

---

## 3. 顶层 API（`import artclaw_sdk as sdk`）

工具脚本可通过 `sdk.xxx` 直接访问以下 API：

### 3.1 子模块

| 访问方式 | 类型 | 说明 |
|----------|------|------|
| `sdk.params` | module | 参数解析（§4） |
| `sdk.filters` | module | 对象筛选（§5） |
| `sdk.context` | module | 上下文查询（§6） |
| `sdk.result` | module | 结果上报（§7） |
| `sdk.progress` | module | 进度上报（§8） |
| `sdk.log` | module | 日志（§9）。⚠️ 当前导出名为 `logger`，需新增 `log` 别名 |

### 3.2 顶层便捷函数

| 函数 | 等价于 | 说明 |
|------|--------|------|
| `sdk.parse_params(inputs, raw)` | `sdk.params.parse_params(inputs, raw)` | ⚠️ 当前未导出，需新增 |
| `sdk.get_context()` | `sdk.context.get_context()` | 已导出 ✅ |
| `sdk.get_selected()` | `sdk.context.get_selected()` | 已导出 ✅ |
| `sdk.filter_objects(objs, **kw)` | `sdk.filters.filter_objects(objs, **kw)` | 已导出 ✅ |
| `sdk.get_current_dcc()` | — | 返回 DCC 标识符字符串 ✅ |
| `sdk.is_available()` | — | SDK 是否已初始化 ✅ |

---

## 4. params — 参数解析

### API

```python
sdk.params.parse_params(manifest_inputs: list[dict], raw_params: dict) -> dict
```

- 按 manifest `inputs` 定义做**类型转换** + **必填校验** + **默认值填充**
- 多余参数（manifest 中未定义的）透传保留
- 必填缺失时抛 `ValueError`

```python
sdk.params.get_default_values(manifest_inputs: list[dict]) -> dict
sdk.params.merge_with_defaults(params: dict, manifest_inputs: list[dict]) -> dict
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

### API

```python
# 组合筛选（同时按 type + name + path）
sdk.filters.filter_objects(
    objects: list[dict],
    type: str | list[str] = None,       # 类型过滤
    name_pattern: str = None,            # 名称 pattern
    path_pattern: str = None,            # 路径 pattern  
    use_regex: bool = True,              # True=正则, False=通配符
) -> list[dict]

# 单维度筛选
sdk.filters.filter_by_type(objects, type_filter: str | list[str]) -> list[dict]
sdk.filters.filter_by_name(objects, pattern: str, use_regex=False) -> list[dict]
sdk.filters.filter_by_path(objects, pattern: str, use_regex=False) -> list[dict]

# 查找
sdk.filters.find_objects_by_name(objects, name: str, exact_match=False) -> list[dict]

# 分组
sdk.filters.group_by_type(objects) -> dict[str, list[dict]]
```

### 对象字典格式（约定）

筛选函数操作的 `objects` 列表中，每个字典必须包含以下 key：

| key | 类型 | 说明 | 示例 (UE) | 示例 (Blender) |
|-----|------|------|-----------|----------------|
| `name` | str | 短名称 | `"SM_Chair"` | `"Cube.001"` |
| `type` | str | 对象类型 | `"StaticMesh"` | `"MESH"` |
| `path` | str | 完整路径 | `"/Game/Props/SM_Chair"` | `"Cube.001"` |

其他 key（`class`、`location`、`vertices` 等）是 DCC 特有的附加信息，筛选函数不依赖。

### 类型筛选：不同 DCC 的 type 值

| 概念 | UE type | Blender type | Maya type |
|------|---------|-------------|-----------|
| 网格 | `"StaticMesh"` / `"SkeletalMesh"` | `"MESH"` | `"mesh"` / `"transform"` |
| 灯光 | `"PointLight"` / `"DirectionalLight"` | `"LIGHT"` | `"pointLight"` |
| 相机 | `"CameraActor"` | `"CAMERA"` | `"camera"` |
| 材质 | `"MaterialInstanceConstant"` | — | `"lambert"` / `"blinn"` |
| 贴图 | `"Texture2D"` | `"IMAGE"` | `"file"` |

> 筛选时大小写不敏感（SDK 内部统一 `.lower()` 比较）。

---

## 6. context — 上下文查询

### API

```python
sdk.context.get_context() -> dict
sdk.context.get_selected() -> list[dict]
sdk.context.get_scene_path() -> str | None
sdk.context.get_scene_info() -> dict
sdk.context.get_viewport_info() -> dict
```

### get_selected() 返回格式

每个 DCC 的适配器实现 `get_selected()`，返回统一格式的对象列表。

**UE 适配器返回**:
```python
[
    {
        "name": "SM_Chair",
        "path": "/Game/Props/SM_Chair",       # UE 资产路径
        "type": "asset",                       # "asset" 或 "actor"
        "class": "StaticMesh",                 # UE class 名
        "is_level_actor": False,
    }
]
```

**Blender 适配器返回**:
```python
[
    {
        "name": "Cube.001",
        "long_name": "Cube.001",
        "type": "MESH",                        # Blender object type
        "location": [0.0, 0.0, 0.0],
        "is_active": True,
        "vertices": 8,
    }
]
```

### get_context() 返回格式

```python
{
    "software": {
        "name": "ue",         # DCC 标识符
        "version": "5.4.4",
        "python_version": "3.11"
    },
    "scene_info": { ... },    # get_scene_info() 结果
    "selected": [ ... ],      # get_selected() 结果
    "viewport": { ... },      # get_viewport_info() 结果
}
```

---

## 7. result — 结果上报

### API

```python
sdk.result.success(data=None, message=None) -> dict
# 返回 {"success": True, "data": ..., "error": None, "message": ...}

sdk.result.fail(error=None, message=None, data=None) -> dict
# 返回 {"success": False, "data": ..., "error": ..., "message": ...}

sdk.result.error(error=None, message=None, data=None) -> dict
# ⚠️ 当前不存在，需新增为 fail() 的别名

sdk.result.from_exception(exc: Exception, message=None) -> dict
# 从异常生成 fail 结果

sdk.result.allow(message=None, data=None) -> dict
sdk.result.reject(reason=None, data=None) -> dict
# 用于触发规则的 pre-event 允许/拒绝
```

### 返回值契约

所有工具入口函数**必须**返回 dict，且包含 `success: bool` 字段。

---

## 8. progress — 进度上报

### API

```python
sdk.progress.start(total=100, message=None)
sdk.progress.update(current: int, message=None)
sdk.progress.increment(amount=1, message=None)
sdk.progress.finish(message=None)
sdk.progress.get_progress() -> dict
```

进度数据通过 HTTP POST 到 `http://localhost:9876/api/v1/progress`（best-effort，不阻塞业务）。

---

## 9. log — 日志

### API

```python
sdk.log.info(message)
sdk.log.warning(message)
sdk.log.error(message)
sdk.log.debug(message)
sdk.log.exception(message)

# 工具专属 logger
tool_log = sdk.log.get_tool_logger("my-tool")
tool_log.info("xxx")  # 输出 "[my-tool] xxx"
```

> ⚠️ 当前模块导出名为 `sdk.logger`，需在 `__init__.py` 中新增 `log = logger` 别名。

---

## 10. DCC 适配器接口

### 基类 `BaseDCCBackend`

所有 DCC 适配器必须继承并实现以下抽象方法：

```python
class BaseDCCBackend(ABC):
    # 必须实现
    @abstractmethod def get_dcc_name(self) -> str
    @abstractmethod def get_dcc_version(self) -> str
    @abstractmethod def get_context(self) -> dict
    @abstractmethod def get_selected(self) -> list[dict]
    @abstractmethod def get_scene_path(self) -> str | None
    @abstractmethod def get_scene_info(self) -> dict

    # 可选覆盖（有默认实现）
    def get_viewport_info(self) -> dict          # 默认 {}
    def rename_object(self, id, name) -> bool    # 默认 False
    def delete_objects(self, objects) -> int      # 默认 0
    def duplicate_objects(self, objects) -> list  # 默认 []
    def export_selected(self, path, fmt) -> bool  # 默认 False
    def import_file(self, path) -> list           # 默认 []
    def execute_on_main_thread(self, fn, *a)     # 默认直接调用
    def filter_objects(self, objects, **kw)       # 默认委托 filters 模块
```

### 各 DCC 实现状态

| DCC | 适配器 | get_selected | get_scene_info | rename | delete | duplicate | export | import |
|-----|--------|-------------|----------------|--------|--------|-----------|--------|--------|
| UE | ✅ 完整 | ✅ 资产+Actor | ✅ 关卡信息 | ✅ | ✅ | ✅ | ✅ FBX | ✅ |
| Blender | ✅ 完整 | ✅ 对象+属性 | ✅ 场景统计 | ✅ | ✅ | ✅ | ✅ 多格式 | ✅ 多格式 |
| Maya | 🔧 骨架 | 待实现 | 待实现 | — | — | — | — | — |
| Max | 🔧 骨架 | 待实现 | 待实现 | — | — | — | — | — |
| Houdini | 🔧 骨架 | 待实现 | 待实现 | — | — | — | — | — |
| SP | 🔧 骨架 | 待实现 | 待实现 | — | — | — | — | — |
| SD | 🔧 骨架 | 待实现 | 待实现 | — | — | — | — | — |
| ComfyUI | 🔧 骨架 | 待实现 | 待实现 | — | — | — | — | — |

**优先级**: 先 UE → Blender → 其他（按需）。

---

## 11. 需修复的问题清单

| # | 问题 | 修复方案 | 文件 |
|---|------|---------|------|
| F1 | `sdk.log` 不存在 | `__init__.py` 新增 `log = logger` | `__init__.py` |
| F2 | `sdk.parse_params()` 不在顶层 | `__init__.py` 新增 `from .params import parse_params` | `__init__.py` |
| F3 | `sdk.result.error()` 不存在 | `result.py` 新增 `error = fail` | `result.py` |
| F4 | UE 适配器 `get_selected` 用了不存在的 API | 改用 `EditorUtilityLibrary.get_selected_assets()` | `dcc/ue.py` |
| F5 | context.py 引用 `_current_adapter` 在模块加载时 | 改为运行时查找 | `context.py` |
