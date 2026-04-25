# ArtClaw Tool Manager - 工具触发机制设计

> 版本: 2.0
> 日期: 2026-04-14
> 说明: 定义工具的触发方式、条件筛选、参数预设、路径变量、manifest 同步的架构设计

---

## 1. 概述

### 1.1 问题

当前工具只有"手动点击运行"一种触发方式。实际使用中，用户需要：

- **事件触发**: UE 保存资源时自动运行检查工具、Maya 导出 FBX 时自动运行规范校验
- **定时触发**: 每隔 30 分钟自动备份、每天凌晨自动清理临时文件
- **条件过滤**: 只对 `/Characters/` 目录下的资源运行、只对命名匹配 `SM_*` 的对象运行

### 1.2 核心概念

```
工具触发机制 = 触发方式（When） + 条件筛选（What） + 参数预设（How）

触发方式: 手动 / 事件 / 定时 / 文件监听
条件筛选: 路径($variable) / 命名 / 类型 / 选择对象 等
参数预设: 工具参数的默认值组合
```

### 1.3 关键设计原则

| 原则 | 说明 |
|------|------|
| **路径统一** | 所有路径声明统一在 `filters.path` 中，watch trigger 不含 `paths` 字段 |
| **$variable 路径变量** | filters.path 支持 `$skills_installed`、`$project_root` 等变量前缀，运行时解析 |
| **脚本不硬编码** | 工具脚本从自身 manifest 的 filters.path 读取路径，不在代码中硬编码 |
| **manifest 自动同步** | manifest.json 中的 triggers 在服务启动时自动同步到 triggers.json |
| **DCC 类型一致性** | event trigger 的 dcc 必须与 targetDCCs 兼容，通用工具不绑定 DCC 事件 |
| **筛选条件分场景** | 文件路径筛选适用于 watch/所有类型，场景对象筛选仅适用于 event/manual |

---

## 2. 触发方式（Trigger）

### 2.1 触发方式分类

| 类型 | 说明 | 示例 |
|------|------|------|
| **event** | DCC 事件触发 | UE 保存资源时、Maya 导出 FBX 时 |
| **schedule** | 定时/周期触发 | 每30分钟、每天凌晨2点 |
| **watch** | 文件/目录监听触发 | 目录下有新文件时自动运行 |

> **手动执行**不是触发规则，直接点击工具的"运行"按钮即可。

### 2.2 事件触发（Event Trigger）

**事件时机**:

| 时机 | 说明 | 用途 |
|------|------|------|
| **pre** | 事件发生前（可拦截） | 保存前检查命名规范，不通过则阻止保存 |
| **post** | 事件发生后 | 保存后自动生成缩略图、导出后自动上传 |

**DCC 事件列表**:

| DCC | 事件 | 时机 | 说明 |
|-----|------|------|------|
| **UE** | `asset.save` | pre/post | 资源保存 |
| **UE** | `asset.import` | pre/post | 资源导入 |
| **UE** | `asset.delete` | pre/post | 资源删除 |
| **UE** | `level.save` | pre/post | 关卡保存 |
| **UE** | `level.load` | post | 关卡加载 |
| **UE** | `build.lighting` | pre/post | 烘焙光照 |
| **UE** | `editor.startup` | post | 编辑器启动 |
| **Maya** | `file.save` | pre/post | 文件保存 |
| **Maya** | `file.export` | pre/post | 文件导出 |
| **Maya** | `file.import` | pre/post | 文件导入 |
| **Maya** | `file.open` | post | 文件打开 |
| **Maya** | `scene.new` | post | 新建场景 |
| **Maya** | `render.start` | pre/post | 开始渲染 |
| **ComfyUI** | `workflow.queue` | pre/post | 提交工作流 |
| **ComfyUI** | `workflow.complete` | post | 工作流完成 |
| **SD** | `graph.compute` | pre/post | 图表计算 |

**pre 事件拦截机制**:

```
事件发生前 → 运行 pre 触发器 → 工具返回结果
                                     │
                          ┌──────────┤
                          │          │
                   通过(allow)   拒绝(reject)
                          │          │
                          ▼          ▼
                     继续执行     阻止事件
                     原操作       + 显示原因
```

### 2.3 定时触发（Schedule Trigger）

| 模式 | 说明 | 示例 |
|------|------|------|
| **interval** | 固定间隔 | 每 30 分钟 |
| **cron** | Cron 表达式 | `0 2 * * *`（每天凌晨2点） |
| **once** | 一次性定时 | 2026-04-11 10:00:00 |

### 2.4 文件监听触发（Watch Trigger）

**监听路径由 filters.path 统一指定**（不在 trigger 中重复声明 `paths`），watch 只声明监听哪些文件事件和防抖时间。

| 事件 | 说明 |
|------|------|
| `file.created` | 新文件创建 |
| `file.modified` | 文件修改 |
| `file.deleted` | 文件删除 |

> ⚠️ watch trigger 不包含 `paths` 字段。监听范围等同于该触发规则的 `filters.path`。
> 如果没有 filters.path，则 watch 无法确定监听范围，规则无效。

---

## 3. 条件筛选（Filter）

### 3.1 筛选维度

| 维度 | 说明 | 示例 |
|------|------|------|
| **path** | 目录路径匹配（glob） | `$skills_installed/**/*.md`、`/Game/Characters/**` |
| **name** | 命名正则匹配 | `^SM_.*`、`*_LOD0` |
| **type** | 资源/对象类型 | `StaticMesh`、`Material`、`mesh`、`joint` |
| **selection** | 当前选中对象 | 只对选中的对象运行 |
| **property** | 属性条件 | `vertex_count > 10000`、`has_uv2 == false` |
| **tag** | 标签匹配 | `production`、`wip` |

### 3.1.1 路径变量（Path Variables）

filters.path 的 pattern 支持 `$variable` 前缀，运行时由引擎解析为实际路径。

| 变量 | 解析来源 | 示例值 |
|------|----------|--------|
| `$skills_installed` | `~/.openclaw/workspace/skills` 或平台配置 | `C:/Users/x/.openclaw/workspace/skills` |
| `$project_root` | `~/.artclaw/config.json` → `project_root` | `D:/MyProject_D/artclaw_bridge` |
| `$tools_dir` | `~/.artclaw/tools` | `C:/Users/x/.artclaw/tools` |
| `$home` | 用户主目录 | `C:/Users/x` |

**解析规则**:
1. `$variable/...` → 替换为对应绝对路径
2. 不含 `$` 前缀的路径视为 DCC 内资源路径（如 `/Game/Characters/**`）
3. 变量不存在或路径不存在 → 跳过该 filter 条目，不报错

**运行时统一读取**: 无论手动运行还是自动触发，工具执行时都应从 manifest 的 `defaultFilters`（工具级）或 `triggers[].filters`（规则级）读取目标路径范围，**不在脚本中硬编码路径**。

详见独立文档: [路径变量参考](path-variables.md)

### 3.1.2 工具级默认筛选条件（defaultFilters）

manifest 顶层支持 `defaultFilters` 字段，定义工具级的默认筛选条件：

```json
{
  "defaultFilters": {
    "path": [
      { "pattern": "$project_root/tools/**/*" },
      { "pattern": "$tools_dir/**/*" }
    ]
  }
}
```

触发规则可通过 `useDefaultFilters: true` 继承此条件，或设为 `false` 自定义覆盖：

```json
{
  "triggers": [
    {
      "id": "on-change",
      "useDefaultFilters": true,
      "filters": {}
    },
    {
      "id": "special",
      "useDefaultFilters": false,
      "filters": { "path": [{ "pattern": "$tools_dir/user/**/*" }] }
    }
  ]
}
```

**脚本读取**: 脚本运行时只从 `defaultFilters.path` 读取路径范围。`triggers[].filters` 由触发引擎处理，脚本不关心。

### 3.2 筛选组合逻辑

```
筛选条件之间的关系:
- 同一维度内: OR（满足任一即可）
- 不同维度间: AND（必须全部满足）

示例:
  path: ["/Characters/**", "/Props/**"]     ← OR: Characters 或 Props 目录
  AND
  type: ["StaticMesh"]                      ← AND: 必须是 StaticMesh
  AND
  name: ["^SM_.*"]                          ← AND: 必须以 SM_ 开头
```

### 3.3 筛选预设（Filter Preset）

常用筛选条件可保存为预设：

| 预设名 | 条件 | 用途 |
|--------|------|------|
| 角色资源 | path:`/Characters/**`, type:`SkeletalMesh` | 筛选角色模型 |
| 场景静态网格 | path:`/Levels/**`, type:`StaticMesh` | 筛选场景模型 |
| 高面数模型 | type:`StaticMesh`, property:`vertex_count > 50000` | 筛选需要优化的模型 |
| WIP 资源 | tag:`wip` | 筛选开发中的资源 |
| FBX 导出文件 | path:`/export/**`, name:`*.fbx` | 筛选导出的 FBX |

---

## 4. 参数预设（Parameter Preset）

### 4.1 概念

参数预设 = 工具参数的一组默认值组合，用于不同场景快速切换。

```
工具: 资源命名检查器
├── 预设: 角色命名规范
│   └── prefix: "SK_", pattern: "^SK_[A-Z][a-z]+_.*"
├── 预设: 道具命名规范
│   └── prefix: "SM_", pattern: "^SM_[A-Z][a-z]+_.*"
└── 预设: 材质命名规范
    └── prefix: "M_", pattern: "^M_[A-Z][a-z]+_.*"
```

### 4.2 预设管理

| 操作 | 说明 |
|------|------|
| 创建预设 | 填写参数后保存为预设 |
| 应用预设 | 选择预设自动填充参数 |
| 修改预设 | 编辑已有预设 |
| 删除预设 | 删除不需要的预设 |
| 导出/导入 | 分享预设配置 |

---

## 5. 工具触发规则（Trigger Rule）

### 5.1 概念

**触发规则 = 触发方式 + 条件筛选 + 参数预设** 的组合

一个工具可以有多个触发规则，每个规则定义了"在什么条件下、以什么参数运行"。

### 5.2 数据模型

```typescript
interface TriggerRule {
  id: string;
  name: string;                  // 规则名称
  enabled: boolean;              // 是否启用
  toolId: string;                // 关联的工具 ID
  
  // 触发方式（不含 manual，手动执行直接点运行按钮）
  trigger: EventTrigger | ScheduleTrigger | WatchTrigger;
  
  // 默认筛选条件继承
  useDefaultFilters?: boolean;   // true = 继承工具级 defaultFilters，false/省略 = 使用下方 filters
  
  // 条件筛选（useDefaultFilters=true 时可为空）
  filters?: FilterConfig;
  
  // 参数预设（可选，不指定则使用工具默认参数）
  parameterPresetId?: string;
  
  // 执行配置
  execution: {
    mode: 'silent' | 'notify' | 'interactive';  // 静默/通知/交互
    timeout: number;             // 超时时间（秒）
    retryCount: number;          // 失败重试次数
    onError: 'ignore' | 'notify' | 'block';     // 错误处理
  };
}

// 事件触发
interface EventTrigger {
  type: 'event';
  dcc: string;                   // ue5/maya2024/comfyui
  event: string;                 // asset.save/file.export/...
  timing: 'pre' | 'post';       // 事件前/事件后
}

// 定时触发
interface ScheduleTrigger {
  type: 'schedule';
  mode: 'interval' | 'cron' | 'once';
  interval?: number;             // 间隔毫秒（interval 模式）
  cron?: string;                 // Cron 表达式（cron 模式）
  at?: string;                   // ISO 时间（once 模式）
}

// 文件监听触发（监听路径由 filters.path 统一指定）
interface WatchTrigger {
  type: 'watch';
  events: ('created' | 'modified' | 'deleted')[];
  debounceMs?: number;           // 防抖时间
}

// 条件筛选配置（path 支持 $variable 前缀，watch 和手动运行共用）
interface FilterConfig {
  path?: PathFilter[];
  name?: NameFilter[];
  type?: TypeFilter[];
  selection?: boolean;           // true = 只处理选中对象
  property?: PropertyFilter[];
  tag?: string[];
}

interface PathFilter {
  pattern: string;               // glob 模式: /Characters/**
  exclude?: boolean;             // true = 排除匹配的
}

interface NameFilter {
  pattern: string;               // 正则: ^SM_.*
  exclude?: boolean;
}

interface TypeFilter {
  types: string[];               // StaticMesh, Material, ...
  exclude?: boolean;
}

interface PropertyFilter {
  field: string;                 // vertex_count, has_uv2, ...
  operator: '==' | '!=' | '>' | '<' | '>=' | '<=';
  value: any;
}

// 参数预设
interface ParameterPreset {
  id: string;
  name: string;
  toolId: string;
  parameters: Record<string, any>;   // 参数名→值
  description?: string;
}
```

### 5.3 执行模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **silent** | 静默运行，不打扰用户 | 定时备份、后台检查 |
| **notify** | 运行后通知结果 | 保存后自动检查，有问题时通知 |
| **interactive** | 跳转对话面板，AI 协助 | 需要用户确认参数的场景 |

---

## 6. 范式架构

### 6.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       触发规则引擎                               │
│                    (Trigger Rule Engine)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐    │
│  │ 事件监听器    │  │ 定时调度器    │  │  文件监听器       │    │
│  │ EventListener │  │ Scheduler     │  │  FileWatcher      │    │
│  └───────┬───────┘  └───────┬───────┘  └────────┬──────────┘    │
│          │                  │                    │               │
│          └──────────────────┼────────────────────┘               │
│                             │                                    │
│                    ┌────────▼─────────┐                          │
│                    │  规则匹配器      │                          │
│                    │  RuleMatcher     │                          │
│                    │                  │                          │
│                    │  1. 匹配触发方式 │                          │
│                    │  2. 评估筛选条件 │                          │
│                    │  3. 加载参数预设 │                          │
│                    └────────┬─────────┘                          │
│                             │                                    │
│                    ┌────────▼─────────┐                          │
│                    │  执行调度器      │                          │
│                    │  Executor        │                          │
│                    │                  │                          │
│                    │  silent → 后台   │                          │
│                    │  notify → 通知   │                          │
│                    │  interactive → AI│                          │
│                    └──────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 DCC 端事件注册

```python
# DCC Adapter 中注册事件钩子

class DCCEventManager:
    """DCC 事件管理器 — 在各 DCC 中注册事件回调"""
    
    def __init__(self, adapter):
        self._adapter = adapter
        self._rules: List[TriggerRule] = []
    
    def register_events(self):
        """根据已启用的触发规则注册 DCC 事件"""
        dcc = self._adapter.get_software_name()
        
        for rule in self._rules:
            if not rule.enabled:
                continue
            
            if rule.trigger.type == 'event':
                if rule.trigger.dcc != dcc:
                    continue
                self._register_dcc_event(rule)
            elif rule.trigger.type == 'watch':
                self._register_file_watch(rule)
    
    def _register_dcc_event(self, rule):
        """注册具体 DCC 事件"""
        event = rule.trigger.event
        timing = rule.trigger.timing
        
        if self._adapter.get_software_name() == 'ue5':
            self._register_ue_event(event, timing, rule)
        elif self._adapter.get_software_name() == 'maya2024':
            self._register_maya_event(event, timing, rule)
    
    def _register_ue_event(self, event, timing, rule):
        """UE 事件注册"""
        import unreal
        
        if event == 'asset.save':
            if timing == 'pre':
                # UE: FEditorDelegates::OnAssetPreSave
                unreal.register_callback('on_asset_pre_save',
                    lambda asset: self._on_event(rule, {'asset': asset}))
            else:
                # UE: FEditorDelegates::OnAssetPostSave
                unreal.register_callback('on_asset_post_save',
                    lambda asset, success: self._on_event(rule, {
                        'asset': asset, 'success': success
                    }))
    
    def _register_maya_event(self, event, timing, rule):
        """Maya 事件注册"""
        import maya.api.OpenMaya as om
        
        if event == 'file.save':
            if timing == 'pre':
                om.MSceneMessage.addCallback(
                    om.MSceneMessage.kBeforeSave,
                    lambda *_: self._on_event(rule, {}))
            else:
                om.MSceneMessage.addCallback(
                    om.MSceneMessage.kAfterSave,
                    lambda *_: self._on_event(rule, {}))
        
        elif event == 'file.export':
            if timing == 'pre':
                om.MSceneMessage.addCallback(
                    om.MSceneMessage.kBeforeExport,
                    lambda *_: self._on_event(rule, {}))
            else:
                om.MSceneMessage.addCallback(
                    om.MSceneMessage.kAfterExport,
                    lambda *_: self._on_event(rule, {}))
    
    def _register_file_watch(self, rule):
        """
        注册文件监听 — 监听路径从 rule.filters.path 解析（$variable 展开）。
        watch trigger 自身不含 paths，统一由 filters.path 驱动。
        """
        evaluator = FilterEvaluator()
        watch_dirs = evaluator.get_watch_paths(rule.filters)
        
        if not watch_dirs:
            return  # 没有有效路径，规则无效
        
        events = rule.trigger.events  # ['created', 'modified', 'deleted']
        debounce = rule.trigger.debounceMs or 1000
        
        for watch_dir in watch_dirs:
            self._file_watcher.add_watch(
                path=watch_dir,
                events=events,
                debounce_ms=debounce,
                callback=lambda changed_file: self._on_event(rule, {
                    'asset_path': changed_file,
                    'asset_name': os.path.basename(changed_file),
                }),
            )
    
    def _on_event(self, rule, context):
        """事件触发回调"""
        # 1. 评估筛选条件
        if not self._evaluate_filters(rule.filters, context):
            return True  # 条件不满足，放行
        
        # 2. 加载参数预设
        params = self._load_preset(rule.parameterPresetId)
        
        # 3. 根据执行模式运行
        if rule.execution.mode == 'silent':
            result = self._execute_silent(rule.toolId, params, context)
        elif rule.execution.mode == 'notify':
            result = self._execute_notify(rule.toolId, params, context)
        elif rule.execution.mode == 'interactive':
            self._execute_interactive(rule.toolId, params, context)
            return True  # 交互模式不阻塞
        
        # 4. pre 事件：根据结果决定是否阻止
        if rule.trigger.timing == 'pre':
            if not result.get('allow', True):
                self._show_block_reason(result.get('reason', ''))
                return False  # 阻止原操作
        
        return True  # 放行
```

### 6.3 筛选器实现

```python
class FilterEvaluator:
    """条件筛选评估器"""
    
    # 路径变量映射（运行时由引擎从配置解析）
    PATH_VARIABLES = {
        "$skills_installed": "~/.openclaw/workspace/skills",   # 或平台配置值
        "$project_root": "",                          # ~/.artclaw/config.json
        "$tools_dir": "~/.artclaw/tools",
        "$home": "~",
    }
    
    def resolve_path_variable(self, pattern: str) -> str:
        """解析 $variable 前缀为绝对路径"""
        for var, value in self.PATH_VARIABLES.items():
            if pattern.startswith(var):
                import os
                resolved = os.path.expanduser(pattern.replace(var, value, 1))
                return resolved
        return pattern
    
    def get_watch_paths(self, filters: FilterConfig) -> list[str]:
        """
        从 filters.path 中提取并解析监听路径（供 FileWatcher 使用）。
        watch trigger 的监听范围 = filters.path 解析后的目录列表。
        """
        if not filters or not filters.path:
            return []
        paths = []
        for pf in filters.path:
            if pf.exclude:
                continue
            # 取 glob 之前的基础目录
            base = pf.pattern.split("/**")[0].split("/*")[0]
            resolved = self.resolve_path_variable(base)
            if resolved:
                paths.append(resolved)
        return paths
    
    def evaluate(self, filters: FilterConfig, context: dict) -> bool:
        """评估筛选条件，返回 True 表示通过"""
        if not filters:
            return True
        
        # 各维度之间是 AND 关系
        if filters.path and not self._match_path(filters.path, context):
            return False
        if filters.name and not self._match_name(filters.name, context):
            return False
        if filters.type and not self._match_type(filters.type, context):
            return False
        if filters.selection and not self._check_selection(context):
            return False
        if filters.property and not self._match_property(filters.property, context):
            return False
        if filters.tag and not self._match_tag(filters.tag, context):
            return False
        
        return True
    
    def _match_path(self, path_filters, context):
        """目录路径匹配（glob 模式，支持 $variable 解析）"""
        import fnmatch
        asset_path = context.get('asset_path', '')
        
        for pf in path_filters:
            resolved_pattern = self.resolve_path_variable(pf.pattern)
            matched = fnmatch.fnmatch(asset_path, resolved_pattern)
            if pf.exclude:
                if matched:
                    return False
            else:
                if matched:
                    return True
        return False
    
    def _match_name(self, name_filters, context):
        """命名正则匹配"""
        import re
        asset_name = context.get('asset_name', '')
        
        for nf in name_filters:
            matched = bool(re.match(nf.pattern, asset_name))
            if nf.exclude:
                if matched:
                    return False
            else:
                if matched:
                    return True
        return False
    
    def _match_type(self, type_filters, context):
        """资源类型匹配"""
        asset_type = context.get('asset_type', '')
        
        for tf in type_filters:
            if asset_type in tf.types:
                return not tf.exclude
        return False
```

---

## 7. 触发规则管理 API

### 7.1 REST API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/tools/{toolId}/triggers` | GET | 获取工具的触发规则列表 |
| `/api/v1/tools/{toolId}/triggers` | POST | 创建触发规则 |
| `/api/v1/tools/{toolId}/triggers/{ruleId}` | GET | 获取触发规则详情 |
| `/api/v1/tools/{toolId}/triggers/{ruleId}` | PUT | 更新触发规则 |
| `/api/v1/tools/{toolId}/triggers/{ruleId}` | DELETE | 删除触发规则 |
| `/api/v1/tools/{toolId}/triggers/{ruleId}/enable` | POST | 启用触发规则 |
| `/api/v1/tools/{toolId}/triggers/{ruleId}/disable` | POST | 禁用触发规则 |
| `/api/v1/tools/{toolId}/presets` | GET | 获取参数预设列表 |
| `/api/v1/tools/{toolId}/presets` | POST | 创建参数预设 |
| `/api/v1/tools/{toolId}/presets/{presetId}` | PUT | 更新参数预设 |
| `/api/v1/tools/{toolId}/presets/{presetId}` | DELETE | 删除参数预设 |
| `/api/v1/filter-presets` | GET | 获取筛选预设列表（全局） |
| `/api/v1/filter-presets` | POST | 创建筛选预设 |

### 7.2 创建触发规则请求示例

```json
{
  "name": "保存时检查命名规范",
  "enabled": true,
  "trigger": {
    "type": "event",
    "dcc": "ue5",
    "event": "asset.save",
    "timing": "pre"
  },
  "filters": {
    "path": [{ "pattern": "/Game/Characters/**" }],
    "type": [{ "types": ["StaticMesh", "SkeletalMesh"] }]
  },
  "parameterPresetId": "preset-character-naming",
  "execution": {
    "mode": "notify",
    "timeout": 10,
    "retryCount": 0,
    "onError": "notify"
  }
}
```

---

## 8. 工具 manifest.json 统一定义

一个工具的所有信息集中在一个 `manifest.json` 中，通过这个文件就知道如何运行、用哪个脚本、给 AI 什么提示词。

```json
{
  "id": "user/batch-rename",
  "name": "批量重命名",
  "description": "批量重命名选中对象，支持前缀和编号",
  "version": "1.0.0",
  "targetDCCs": ["maya2024", "ue5"],
  
  "implementation": {
    "type": "script",
    "entry": "main.py",
    "function": "batch_rename",
    "skill": null,
    "aiPrompt": "你是一个 Maya/UE 批量重命名工具。用户提供前缀和编号规则，你负责生成重命名脚本并执行。"
  },
  
  "inputs": [
    { "id": "prefix", "name": "前缀", "type": "string", "required": true, "default": "SM_" },
    { "id": "useNumber", "name": "使用编号", "type": "boolean", "default": true }
  ],
  
  "outputs": [
    { "id": "renamedCount", "name": "重命名数量", "type": "number" }
  ],
  
  "triggers": [
    {
      "id": "rule-001",
      "name": "导入后自动重命名",
      "enabled": true,
      "trigger": { "type": "event", "dcc": "ue5", "event": "asset.import", "timing": "post" },
      "filters": {
        "path": [{ "pattern": "/Game/Props/**" }],
        "type": [{ "types": ["StaticMesh"] }]
      },
      "presetId": "preset-props",
      "execution": { "mode": "notify", "timeout": 10, "onError": "notify" }
    }
  ],
  
  "presets": [
    {
      "id": "preset-props",
      "name": "道具命名",
      "parameters": { "prefix": "SM_Prop_", "useNumber": true }
    },
    {
      "id": "preset-characters",
      "name": "角色命名",
      "parameters": { "prefix": "SK_Char_", "useNumber": false }
    }
  ],
  
  "filterPresets": [
    {
      "id": "fp-props",
      "name": "道具资源",
      "filters": {
        "path": [{ "pattern": "/Game/Props/**" }],
        "type": [{ "types": ["StaticMesh"] }]
      }
    }
  ]
}
```

**字段说明**:

| 字段 | 说明 |
|------|------|
| `implementation.entry` | 脚本入口文件 |
| `implementation.function` | 入口函数名 |
| `implementation.skill` | 包装的 Skill ID（skill_wrapper 类型时） |
| `implementation.aiPrompt` | 给 AI 的提示词（AI 协助运行时使用） |
| `inputs` | 参数定义 |
| `triggers` | 触发规则（内嵌在 manifest 中） |
| `presets` | 参数预设 |
| `filterPresets` | 工具专属筛选预设 |

**存储结构**:

```
~/.artclaw/tools/{source}/{tool-name}/
├── manifest.json          # 唯一配置文件，包含全部元信息
├── main.py                # 脚本入口（implementation.entry 指向）
└── lib/                   # 辅助模块（可选）

~/.artclaw/filter-presets/  # 全局筛选预设（跨工具共享）
├── character-assets.json
└── scene-meshes.json
```

---

## 9. 工具运行时 SDK（Tool Runtime SDK）

### 9.1 问题

AI 创建工具脚本时，需要调用统一的基础能力（获取上下文、筛选对象、报告结果等）。如果每个工具都自己写这些逻辑，代码重复且容易出错。

### 9.2 SDK 模块设计

提供一组固定代码模块，工具脚本通过 `import artclaw_sdk` 引用：

```
artclaw_sdk/                       # 安装在 DCC Python 环境中
├── __init__.py                    # 导出所有公共 API
├── context.py                     # DCC 上下文获取
├── filters.py                     # 对象/资源筛选
├── params.py                      # 参数解析与验证
├── result.py                      # 结果报告
├── progress.py                    # 进度报告
├── logger.py                      # 日志
└── dcc/                           # DCC 适配层
    ├── base.py                    # 抽象接口
    ├── ue.py                      # UE 适配
    ├── maya.py                    # Maya 适配
    └── comfyui.py                 # ComfyUI 适配
```

### 9.3 核心 API

```python
import artclaw_sdk as sdk

# ── 上下文 ──
ctx = sdk.get_context()           # 当前 DCC、选中对象、当前文件等
selected = sdk.get_selected()     # 当前选中对象列表
scene_path = sdk.get_scene_path() # 当前场景/关卡路径

# ── 筛选 ──
meshes = sdk.filter_objects(
    objects=selected,
    type="StaticMesh",
    name_pattern="^SM_.*",
    path_pattern="/Game/Characters/**"
)

# ── 参数 ──
params = sdk.parse_params(manifest_inputs, raw_params)  # 验证+类型转换+默认值

# ── 进度 ──
sdk.progress.start(total=len(meshes))
for i, mesh in enumerate(meshes):
    # ... 处理 ...
    sdk.progress.update(i + 1, message=f"处理 {mesh.name}")
sdk.progress.finish()

# ── 结果 ──
sdk.result.success(data={"renamedCount": 5}, message="成功重命名 5 个对象")
sdk.result.fail(error="TOOL_INVALID_SELECTION", message="请先选择对象")

# ── pre 事件拦截 ──
sdk.result.allow()                 # 放行
sdk.result.reject("命名不符合规范: 应以 SM_ 开头")  # 阻止

# ── 日志 ──
sdk.log.info("开始处理...")
sdk.log.warning("跳过无效对象: %s", obj.name)
```

### 9.4 工具脚本范式

AI 创建工具时，生成的脚本遵循以下范式：

```python
"""批量重命名工具 — 由 ArtClaw Tool Creator 生成"""
import artclaw_sdk as sdk

def batch_rename(prefix: str = "SM_", use_number: bool = True):
    """入口函数，参数与 manifest.json inputs 对应"""
    
    # 1. 获取上下文
    selected = sdk.get_selected()
    if not selected:
        return sdk.result.fail("TOOL_INVALID_SELECTION", "请先选择要重命名的对象")
    
    # 2. 筛选（可选）
    targets = sdk.filter_objects(selected, type="StaticMesh")
    
    # 3. 执行
    sdk.progress.start(total=len(targets))
    renamed = []
    for i, obj in enumerate(targets):
        new_name = f"{prefix}{i+1:03d}" if use_number else f"{prefix}{obj.name}"
        sdk.rename_object(obj, new_name)
        renamed.append(new_name)
        sdk.progress.update(i + 1)
    sdk.progress.finish()
    
    # 4. 报告结果
    return sdk.result.success(
        data={"renamedCount": len(renamed), "names": renamed},
        message=f"成功重命名 {len(renamed)} 个对象"
    )
```

### 9.5 SDK 存储与读取

| 项目 | 路径 | 说明 |
|------|------|------|
| SDK 源码 | `artclaw_bridge/core/artclaw_sdk/` | 项目仓库中维护 |
| DCC 部署 | 各 DCC 的 Python site-packages | install.py 部署时复制 |
| AI 引用 | Skill 中包含 SDK API 速查 | AI 创建工具时参考 |

**AI 如何知道 SDK API**：

Tool Creator Skill 的 SKILL.md 中包含 SDK API 速查表，AI 创建脚本时直接引用：

```markdown
## artclaw_sdk API 速查

### 上下文
- `sdk.get_context()` → dict: dcc, version, scene, selected
- `sdk.get_selected()` → List[Object]
- `sdk.get_scene_path()` → str

### 筛选
- `sdk.filter_objects(objects, type=, name_pattern=, path_pattern=)` → List

### 结果
- `sdk.result.success(data=, message=)` → ResultSuccess
- `sdk.result.fail(error=, message=)` → ResultFail
- `sdk.result.allow()` / `sdk.result.reject(reason)` — pre 事件

### 进度
- `sdk.progress.start(total=)` / `.update(current, message=)` / `.finish()`
```

## 10. 使用场景示例

```yaml
工具: 命名规范检查器
触发规则:
  name: "保存前检查角色命名"
  trigger:
    type: event
    dcc: ue5
    event: asset.save
    timing: pre              # 保存前拦截
  filters:
    path: ["/Game/Characters/**"]
    type: ["StaticMesh", "SkeletalMesh"]
  execution:
    mode: notify
    onError: block           # 不通过则阻止保存

用户体验:
1. 用户在 UE 中保存角色资源
2. 触发规则引擎拦截保存事件
3. 运行命名规范检查器
4. 如果命名不规范 → 阻止保存 + 弹出提示 "命名不符合规范: 应以 SK_ 开头"
5. 如果命名规范 → 放行，继续保存
```

### 9.2 Maya 导出 FBX 后自动上传（post）

```yaml
工具: 自动上传到资源库
触发规则:
  name: "FBX 导出后上传"
  trigger:
    type: event
    dcc: maya2024
    event: file.export
    timing: post             # 导出后运行
  filters:
    name: [".*\\.fbx$"]
  parameterPreset: "production-upload"
  execution:
    mode: silent             # 静默运行，不打扰用户

用户体验:
1. 用户在 Maya 中导出 FBX
2. 导出完成后触发规则
3. 静默运行上传工具
4. 上传成功后在状态栏显示 "✅ 已上传到资源库"
```

### 9.3 定时自动备份

```yaml
工具: 场景备份器
触发规则:
  name: "每30分钟自动备份"
  trigger:
    type: schedule
    mode: interval
    interval: 1800000        # 30分钟
  execution:
    mode: silent

用户体验:
1. 用户不需要做任何操作
2. 每 30 分钟自动运行
3. 状态栏显示 "最近备份: 10:30"
```

### 9.4 高面数模型检测（AI 协助）

```yaml
工具: 模型优化建议器
触发规则:
  name: "导入后检查面数"
  trigger:
    type: event
    dcc: ue5
    event: asset.import
    timing: post
  filters:
    type: ["StaticMesh"]
    property: [{ field: "vertex_count", operator: ">", value: 100000 }]
  execution:
    mode: interactive        # 跳转对话面板，让 AI 给优化建议

用户体验:
1. 用户导入一个高面数模型
2. 触发规则检测到面数 > 100000
3. 跳转对话面板
4. AI: "检测到导入的模型 SM_Building 有 150,000 个顶点，建议优化..."
5. 用户与 AI 讨论优化方案
```

---

## 10. 与现有架构的集成

### 10.1 触发规则引擎在 DCC Adapter 中初始化

```python
# 在 DCC Adapter 启动时
class ComfyUIAdapter(BaseDCCAdapter):
    def on_startup(self):
        # 初始化事件管理器
        self._event_manager = DCCEventManager(self)
        
        # 从配置加载触发规则
        rules = self._load_trigger_rules()
        self._event_manager.set_rules(rules)
        
        # 注册 DCC 事件
        self._event_manager.register_events()
        
        # 启动定时调度器
        self._scheduler = ScheduleManager()
        self._scheduler.start(rules)
```

### 10.2 触发规则引擎在 Web 端管理

- 触发规则管理页面在工具详情页中
- 筛选预设管理在设置页面中
- 触发日志在对话面板的消息流中显示

---

## 11. Manifest 触发规则同步

### 11.1 同步机制

manifest.json 中声明的 `triggers` 在 Tool Manager 启动时自动同步到 `~/.artclaw/triggers.json`。

**同步流程**:
1. `main.py` lifespan → `scan_tools()` 扫描所有工具
2. `TriggerService.sync_manifest_triggers(tools)` 遍历每个工具的 manifest triggers
3. 按 `(tool_id, manifest_id)` 去重，已存在则跳过
4. `tool_id` 格式为 `{source}/{name}`（与 tool_service 一致，如 `official/artclaw-Skill合规检查器`）
5. manifest trigger 格式 → 内部格式映射（见下表）

**字段映射**:

| manifest 字段 | triggers.json 字段 | 说明 |
|---|---|---|
| `id` | `manifest_id` | 用于去重，不覆盖内部 `id`（UUID） |
| `trigger.type` | `trigger_type` | manual/event/schedule/watch |
| `trigger.dcc` | `dcc` | 仅 event 类型 |
| `trigger.event` | `event_type` | 仅 event 类型 |
| `trigger.timing` | `event_timing` | 仅 event 类型 |
| `filters` | `conditions` | 直接透传（path/name/type 等） |
| `execution.mode` | `execution_mode` | silent/notify/interactive |
| `enabled` | `is_enabled` | — |
| `trigger.events` + `trigger.debounceMs` | `schedule_config.watch_events` + `schedule_config.debounce_ms` | 仅 watch 类型 |

### 11.2 前端数据格式

后端 API 返回 snake_case，前端通过 `snakeToCamel()` 转换为 camelCase。

**编辑器数据映射**（ToolDetailDialog ↔ TriggerRuleEditor）:
- 打开编辑: `conditions.path` → `fileRules`，`conditions.name` → `sceneRules`
- 保存: watch 类型 `fileRules` → `conditions.path`，`sceneRules` → `conditions.name`

---

## 12. 合规性检查规则

`tool-compliance-checker` 对触发规则的检查项（第 9 类规则）:

| 编号 | 级别 | 检查项 | 说明 |
|------|------|--------|------|
| 9a | warning | trigger 缺少 `id` | manifest 同步去重需要 |
| 9a | error | trigger `id` 重复 | 同一工具内不能重复 |
| 9b | error | watch 使用 `trigger.paths` | 已废弃，改用 `filters.path` |
| 9b | error | watch 缺少 `filters.path` | 无法确定监听范围 |
| 9c | error | event 的 dcc 与 targetDCCs 不匹配 | 包括：通用工具绑定了特定 DCC |
| 9d | warning | execution 缺少 `mode` | — |

---

## 13. 筛选条件适用场景

| 筛选维度 | watch | event | schedule | manual |
|----------|-------|-------|----------|--------|
| **path**（文件路径，支持 $variable） | ✅ 主要用途 | ✅ | ❌ | ❌ |
| **name**（文件名正则） | ✅ | ✅ | ❌ | ❌ |
| **type**（场景对象类型） | ❌ | ✅ | ❌ | ❌ |
| **selection**（当前选中） | ❌ | ✅ | ❌ | ❌ |
| **property**（属性条件） | ❌ | ✅ | ❌ | ❌ |

> - **watch**: filters.path 决定监听哪些文件路径
> - **event**: filters 决定什么条件下响应 DCC 事件（路径/类型/选中对象）
> - **schedule/manual**: 不需要筛选条件。定时触发"到点就跑"，手动触发"用户主动运行"。扫描范围由工具脚本从 manifest 的其他触发规则的 filters.path 读取，或通过参数预设指定。

---

## 14. 更新记录

### v2.0 (2026-04-14)
- WatchTrigger 移除 `paths` 字段，监听路径统一由 `filters.path` 驱动
- 新增路径变量体系（$skills_installed / $project_root / $tools_dir / $home）
- FilterEvaluator 新增 `resolve_path_variable()` 和 `get_watch_paths()` 方法
- DCCEventManager 新增 `_register_file_watch()` 从 filters.path 解析监听目录
- 新增 manifest 触发规则自动同步机制（§11）
- 新增合规性检查规则（§12）
- 新增筛选条件适用场景矩阵（§13）
- 新增设计原则（§1.3）

### v1.0 (2026-04-10)
- 初始版本
- 定义触发方式、条件筛选、参数预设
- 范式架构和代码示例
- 使用场景示例
