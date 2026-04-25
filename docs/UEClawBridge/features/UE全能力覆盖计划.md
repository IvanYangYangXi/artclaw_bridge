# UE 全能力覆盖计划 — AI Agent 通过 Python 控制 UE 全部开发工作

> 目标：让 AI Agent 通过 `run_ue_python` 处理 UE 里开发游戏的**所有**工作。Python 不支持的，先通过 C++ 开发 API 暴露给 Python。
>
> 参考项目：[soft-ue-cli](https://github.com/softdaddy-o/soft-ue-cli)（MIT 协议，140 文件 ~20,500 行 C++）

---

## 一、能力矩阵总览

| 领域 | 当前状态 | Python 原生可行 | 需要 C++ API | 来源 |
|------|---------|:-:|:-:|------|
| **Blueprint 图查询** | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **Blueprint 图编辑**（增删改连节点） | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **AnimBlueprint 图操作** | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **PIE 控制**（启停/暂停/状态查询） | ❌ 没有 | ⚠️ 部分 | ✅ 完整版必须 | 移植 soft-ue-cli |
| **PIE 输入注入** | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **PIE 运行时 Actor 查询** | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **StateTree 操作** | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **Widget Blueprint 操作** | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **Insights 性能分析** | ❌ 没有 | ⚠️ 启停可以 | ✅ 分析必须 | 移植 soft-ue-cli |
| **资产操作**（创建/删除/查询/引用） | ⚠️ 基础 | ✅ 大部分 | ⚠️ Diff/Preview | 混合 |
| **Material 节点图** | ✅ 已有 | ❌ 原生不行 | ✅ 已完成 | 自有 |
| **Actor 操作**（Spawn/查询/属性） | ⚠️ 基础 | ✅ 大部分 | — | Python 已够 |
| **反射调用**（CallFunction/属性读写） | ❌ 没有 | ⚠️ 部分 | ✅ 通用版必须 | 移植 soft-ue-cli |
| **Viewport 截图/相机** | ✅ 已有 | ⚠️ | ✅ 已完成 | 自有 |
| **日志/CVar 读写** | ❌ 没有 | ⚠️ CVar 可以 | ✅ 日志过滤 | 移植 soft-ue-cli |
| **C++ 编译**（Live Coding/重编译） | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **源码控制集成** | ❌ 没有 | ❌ | ✅ 必须 | 移植 soft-ue-cli |
| **类继承链查询** | ❌ 没有 | ✅ 可以 | — | Python 自行实现 |
| **DataTable 操作** | ❌ 没有 | ⚠️ 部分 | ✅ 完整版 | 移植 soft-ue-cli |
| **MPC 读写** | ❌ 没有 | ✅ 可以 | — | Python 自行实现 |
| **Sequencer 控制** | ❌ 没有 | ⚠️ 部分 | ✅ 完整版 | 自行开发 |
| **关卡流式加载** | ❌ 没有 | ✅ 可以 | — | Python 自行实现 |
| **AI/行为树** | ❌ 没有 | ❌ | ✅ 必须 | 自行开发 |
| **物理/碰撞配置** | ❌ 没有 | ✅ 大部分 | — | Python 自行实现 |
| **Niagara 粒子系统** | ❌ 没有 | ⚠️ 参数可以 | ✅ 图编辑 | 自行开发 |
| **音频系统** | ❌ 没有 | ✅ 大部分 | — | Python 自行实现 |
| **导航网格** | ❌ 没有 | ✅ 基础 | ⚠️ | Python 先行 |

---

## 二、架构设计

### 不移植 soft-ue-cli 的通信层

soft-ue-cli 使用 HTTP JSON-RPC Server（`FBridgeServer`）+ Tool Registry 模式。我们**不移植这套通信层**：
- 我们已有 WebSocket MCP Server + `run_ue_python` 的成熟架构
- 只移植它的 **C++ Tool 业务逻辑**，改造为 **Python-callable C++ API**

### Python-callable C++ API 设计

```
UEClawBridge 插件
├── Source/UEClawBridge/          （现有：UI/Dashboard/MCP/平台桥接）
└── Source/UEClawBridgeAPI/       （新增：Python-callable C++ API 模块）
    ├── Public/
    │   └── UEClawBridgeAPI.h     （UCLASS + UFUNCTION 入口）
    ├── Private/
    │   ├── BlueprintGraphAPI.cpp   （BP 图查询/编辑）
    │   ├── PIEControlAPI.cpp       （PIE 控制）
    │   ├── StateTreeAPI.cpp        （StateTree 操作）
    │   ├── WidgetBlueprintAPI.cpp  （Widget BP 操作）
    │   ├── AssetManagementAPI.cpp  （资产增强操作）
    │   ├── BuildSystemAPI.cpp      （编译/Live Coding）
    │   ├── PerformanceAPI.cpp      （Insights 分析）
    │   ├── ReflectionAPI.cpp       （通用反射调用）
    │   ├── LoggingAPI.cpp          （日志/CVar）
    │   └── DataTableAPI.cpp        （DataTable 操作）
    └── UEClawBridgeAPI.Build.cs
```

每个 API 函数标记 `UFUNCTION(BlueprintCallable)` → UE Python 自动绑定 → AI 通过 `run_ue_python` 调用：

```python
import unreal
api = unreal.UEClawBridgeAPI()
result = api.query_blueprint_graph("/Game/BP_Player", graph_name="EventGraph")
```

---

## 三、分阶段计划

### Phase 1：Blueprint 图操作（P0，最高优先级）

**这是 soft-ue-cli 最有价值的能力，也是我们最大的缺口。**

| 功能 | 来源 | soft-ue-cli 参考文件 | 预估行数 |
|------|------|---------------------|---------|
| query_blueprint_graph | 移植 | QueryBlueprintGraphTool.cpp (700行) | ~500 |
| query_blueprint_info | 移植 | QueryBlueprintTool.cpp (~1000行) | ~600 |
| add_graph_node | 移植 | AddGraphNodeTool.cpp (500行) | ~400 |
| remove_graph_node | 移植 | RemoveGraphNodeTool.cpp | ~150 |
| connect_graph_pins | 移植 | ConnectGraphPinsTool.cpp (300行) | ~250 |
| disconnect_graph_pin | 移植 | DisconnectGraphPinTool.cpp | ~150 |
| insert_graph_node | 移植 | InsertGraphNodeTool.cpp | ~200 |
| set_node_position | 移植 | SetNodePositionTool.cpp | ~100 |
| set_node_property | 移植 | SetNodePropertyTool.cpp | ~200 |
| compile_blueprint | 移植 | CompileBlueprintTool.cpp | ~100 |
| modify_interface | 移植 | ModifyInterfaceTool.cpp | ~200 |

**依赖工具类（必须一起移植）：**
| 工具类 | 参考文件 | 说明 |
|--------|---------|------|
| BridgeAssetModifier | Utils/BridgeAssetModifier.cpp (500行) | 资产修改通用工具 |
| BridgePropertySerializer | Utils/BridgePropertySerializer.cpp (700行) | 属性序列化/反序列化 |
| BridgeGraphLayoutUtil | Utils/BridgeGraphLayoutUtil.cpp (350行) | 节点自动布局 |

**总量：~4,400 行 C++ 移植改造**

**改造要点：**
- 去掉 `UBridgeToolBase` 继承，改为 `UFUNCTION` 静态函数
- 去掉 JSON 参数解析层（Python 端直接传参）
- 返回值从 `FBridgeToolResult` 改为结构化返回（FString JSON 或 USTRUCT）
- 保留核心业务逻辑不变

**配套 OpenClaw Skill：**
- `ue57_blueprint_graph` — SKILL.md 指导 AI 如何查询/编辑 BP 图

---

### Phase 2：PIE 控制 + 输入注入（P0）

| 功能 | 来源 | soft-ue-cli 参考文件 | 预估行数 |
|------|------|---------------------|---------|
| pie_start | 移植 | PieSessionTool.cpp (584行) | ~150 |
| pie_stop | 移植 | 同上 | ~50 |
| pie_pause / pie_resume | 移植 | 同上 | ~60 |
| pie_get_state | 移植 | 同上 | ~100 |
| pie_wait_for | 移植 | 同上 | ~150 |
| trigger_input | 移植 | TriggerInputTool.cpp | ~200 |

**总量：~710 行**

**配套 OpenClaw Skill：**
- `ue57_pie_control` — SKILL.md 指导 AI 如何启动/控制/调试 PIE

---

### Phase 3：通用反射 + 高级 Actor 操作（P1）

| 功能 | 来源 | 预估行数 |
|------|------|---------|
| call_function（通用 UFUNCTION 调用） | 移植 CallFunctionTool.cpp | ~300 |
| get_property（反射属性读取） | 移植 GetPropertyTool.cpp | ~200 |
| set_property（反射属性设置） | 移植 SetPropertyTool.cpp | ~200 |
| spawn_actor（增强版） | 移植 SpawnActorTool.cpp (Editor版) | ~200 |
| add_component | 移植 AddComponentTool.cpp | ~200 |
| batch_spawn_actors | 移植 BatchSpawnActorTool.cpp | ~150 |
| batch_modify_actors | 移植 BatchModifyActorTool.cpp | ~150 |
| batch_delete_actors | 移植 BatchDeleteActorTool.cpp | ~100 |

**总量：~1,500 行**

**说明：** 我们已有 Python 层的基础 Actor 操作，但 soft-ue-cli 的版本更完整：
- `call_function` 支持任意 BlueprintCallable UFUNCTION 调用
- `get/set_property` 支持嵌套属性路径、结构体、数组
- Batch 操作大幅减少 AI 的 tool call 次数

**配套 OpenClaw Skill：**
- `ue57_actor_ops` — SKILL.md 指导 AI 如何操作 Actor/Component

---

### Phase 4：资产管理增强（P1）

| 功能 | 来源 | 预估行数 |
|------|------|---------|
| query_asset（增强搜索） | 移植 QueryAssetTool.cpp | ~300 |
| create_asset | 移植 CreateAssetTool.cpp | ~300 |
| delete_asset | 移植 DeleteAssetTool.cpp | ~100 |
| save_asset | 移植 SaveAssetTool.cpp | ~100 |
| open_asset | 移植 OpenAssetTool.cpp | ~80 |
| find_references | 移植 FindReferencesTool.cpp | ~200 |
| get_asset_diff | 移植 GetAssetDiffTool.cpp | ~200 |
| get_asset_preview | 移植 GetAssetPreviewTool.cpp | ~150 |
| set_asset_property（CDO 属性） | 移植 SetPropertyTool.cpp (Editor版) | ~200 |

**总量：~1,630 行**

**说明：** Python `unreal.EditorAssetLibrary` 能做部分，但 soft-ue-cli 增加了：
- DataTable 行查询/结构体检查
- Source Control diff
- 缩略图导出
- CDO 属性修改（不需要实例化 Actor）

**配套 OpenClaw Skill：**
- `ue57_asset_management` — SKILL.md 指导 AI 如何管理资产

---

### Phase 5：StateTree + Widget Blueprint（P2）

| 功能 | 来源 | 预估行数 |
|------|------|---------|
| query_statetree | 移植 QueryStateTreeTool.cpp | ~250 |
| add_statetree_state | 移植 AddStateTreeStateTool.cpp | ~200 |
| add_statetree_task | 移植 AddStateTreeTaskTool.cpp | ~200 |
| add_statetree_transition | 移植 AddStateTreeTransitionTool.cpp | ~200 |
| remove_statetree_state | 移植 RemoveStateTreeStateTool.cpp | ~100 |
| inspect_widget_blueprint | 移植 WidgetBlueprintTool.cpp | ~400 |
| inspect_runtime_widgets | 移植 InspectRuntimeWidgetsTool.cpp | ~300 |
| add_widget | 移植 AddWidgetTool.cpp | ~300 |

**总量：~1,950 行**

**配套 OpenClaw Skill：**
- `ue57_statetree` — StateTree 操作指南
- `ue57_widget_blueprint` — Widget BP 操作指南

---

### Phase 6：编译系统 + 日志 + 性能分析（P2）

| 功能 | 来源 | 预估行数 |
|------|------|---------|
| build_and_relaunch | 移植 BuildAndRelaunchTool.cpp | ~150 |
| trigger_live_coding | 移植 TriggerLiveCodingTool.cpp | ~100 |
| get_logs（过滤/搜索） | 移植 GetLogsTool.cpp | ~200 |
| get/set_console_var | 移植 ConsoleVarTool.cpp | ~100 |
| insights_capture | 移植 InsightsCaptureTool.cpp | ~100 |
| insights_list_traces | 移植 InsightsListTracesTool.cpp | ~80 |
| insights_analyze | 移植 InsightsAnalyzeTool.cpp | ~150 |
| class_hierarchy | 移植 ClassHierarchyTool.cpp | ~200 |
| project_info | 移植 ProjectInfoTool.cpp | ~200 |

**总量：~1,280 行**

**配套 OpenClaw Skill：**
- `ue57_build_system` — 编译/Live Coding 指南
- `ue57_performance` — 性能分析指南

---

### Phase 7：UE 原生领域扩展（P3，自行开发）

这些是 soft-ue-cli 也没覆盖的领域，需要自行开发 C++ API：

| 功能 | Python 可行性 | 需要 C++ | 预估行数 |
|------|:---:|:---:|---------|
| **Sequencer 控制**（创建轨道/关键帧/播放） | ⚠️ 基础可以 | ✅ 完整版 | ~800 |
| **AI/行为树**（创建/编辑 BT 节点/黑板） | ❌ | ✅ | ~600 |
| **Niagara 模块图编辑** | ❌ | ✅ | ~800 |
| **Gameplay Ability System**（创建 GA/GE） | ⚠️ | ⚠️ | ~400 |
| **数据驱动 Gameplay**（Curve/CurveTable） | ✅ | — | Python 足够 |
| **Enhanced Input 配置** | ⚠️ | ⚠️ | ~300 |
| **World Partition 管理** | ⚠️ | ⚠️ | ~300 |

**总量：~3,200 行（预估）**

---

## 四、工作量汇总

| Phase | 内容 | C++ 行数 | Skill 数 | 优先级 | 预估工时 |
|-------|------|---------|---------|--------|---------|
| **P1** | Blueprint 图操作 | ~4,400 | 1 | P0 | 3-4 天 |
| **P2** | PIE 控制 | ~710 | 1 | P0 | 1 天 |
| **P3** | 通用反射 + Actor | ~1,500 | 1 | P1 | 1-2 天 |
| **P4** | 资产管理增强 | ~1,630 | 1 | P1 | 1-2 天 |
| **P5** | StateTree + Widget | ~1,950 | 2 | P2 | 2 天 |
| **P6** | 编译/日志/性能 | ~1,280 | 2 | P2 | 1 天 |
| **P7** | 原生领域扩展 | ~3,200 | 3-5 | P3 | 3-5 天 |
| **合计** | | **~14,670** | **11-13** | | **12-20 天** |

---

## 五、移植改造规范

### 5.1 从 soft-ue-cli 移植的改造清单

1. **去掉通信层**
   - 删除 `UBridgeToolBase` 继承、`BridgeToolRegistry`、`BridgeServer`
   - 删除 JSON 参数解析样板代码（`GetStringArg` 等）
   - 删除 `FBridgeToolResult` 返回包装

2. **改为 UFUNCTION 接口**
   ```cpp
   // 移植前 (soft-ue-cli)
   class UQueryBlueprintGraphTool : public UBridgeToolBase {
       FBridgeToolResult Execute(const TSharedPtr<FJsonObject>& Args, ...) override;
   };
   
   // 移植后 (UEClawBridge)
   UCLASS()
   class UBlueprintGraphAPI : public UBlueprintFunctionLibrary {
       UFUNCTION(BlueprintCallable, Category="ArtClaw|Blueprint")
       static FString QueryBlueprintGraph(
           const FString& AssetPath,
           const FString& GraphName = TEXT(""),
           const FString& NodeGuid = TEXT(""),
           bool bIncludePositions = false);
   };
   ```

3. **返回值策略**
   - 复杂结果返回 JSON 字符串（Python 端 `json.loads()`）
   - 简单结果用基本类型（bool/FString/int）
   - 错误用 `UE_LOG` + 返回空字符串/false

4. **保留核心逻辑**
   - `BridgeAssetModifier` 的资产修改逻辑 → 改为 `UAssetModifierLib`
   - `BridgePropertySerializer` 的属性序列化 → 改为 `UPropertySerializerLib`
   - `BridgeGraphLayoutUtil` 的节点布局 → 改为 `UGraphLayoutLib`

### 5.2 代码规范

- 每个文件 100-300 行，硬性上限 500 行
- 一个功能域一个 .cpp（如 `BlueprintGraphAPI.cpp`）
- UFUNCTION 用英文，日志用英文，Python Skill 用中文
- MIT 协议兼容，移植文件保留原始 copyright + 添加我们的修改声明

### 5.3 模块依赖

```
UEClawBridgeAPI.Build.cs 需要的模块：
- UnrealEd
- BlueprintGraph
- KismetCompiler
- Kismet
- AnimGraph
- AnimationBlueprintEditor（AnimBP 支持）
- UMG（Widget）
- StateTreeModule + StateTreeEditor（StateTree）
- MaterialEditor（已有）
- TraceAnalysis + TraceServices（Insights）
- SourceControl（Diff）
```

---

## 六、与现有架构的集成

```
                    ┌─────────────────────────────────┐
                    │         OpenClaw Agent           │
                    │  (加载 SKILL.md 获知 API 用法)     │
                    └──────────┬──────────────────────┘
                               │ run_ue_python
                    ┌──────────▼──────────────────────┐
                    │      MCP Server (port 8080)      │
                    │   run_ue_python → exec Python     │
                    └──────────┬──────────────────────┘
                               │ import unreal
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
 ┌──────────────┐   ┌──────────────┐    ┌──────────────────┐
 │ Python 原生   │   │ 现有 ArtClaw │    │ 新 C++ API 模块   │
 │ unreal 模块   │   │ Material/    │    │ UEClawBridgeAPI  │
 │ (Actor/Asset) │   │ Viewport/    │    │ (BP/PIE/ST/...)  │
 └──────────────┘   │ Highlight    │    └──────────────────┘
                    └──────────────┘
```

**关键：AI 调用方式完全不变**——都是通过 `run_ue_python` 执行 Python 代码，只是 Python 代码里调用的 API 从 `unreal.EditorAssetLibrary` 扩展到 `unreal.BlueprintGraphAPI` 等新模块。

---

## 七、验收标准

每个 Phase 完成后：
1. ✅ C++ 编译通过（UE 5.7）
2. ✅ Python 可调用（`import unreal; unreal.XXX.method()` 正常返回）
3. ✅ 配套 SKILL.md 写完并安装到 `~/.openclaw/workspace/skills/`
4. ✅ AI Agent 端到端测试：给 AI 一个任务描述，AI 能通过 Skill 引导完成操作
5. ✅ 文档更新：troubleshooting + feature 文档

---

## 附录：soft-ue-cli 源码统计

| 目录 | 文件数 | 行数 | 说明 |
|------|-------|------|------|
| Blueprint | 2 | 1,695 | 查询 BP/图结构 |
| Write (Graph ops) | 20 | 4,515 | 增删改连节点 |
| Utils | 3 | 1,553 | 资产修改/属性序列化/布局 |
| Asset | 5 | 1,741 | 资产管理 |
| PIE | 1 | 584 | PIE 控制 |
| StateTree | 5 | 988 | StateTree |
| Widget | 4 | 1,151 | Widget BP |
| Runtime Tools | 21 | 2,068 | Actor/属性/日志 |
| 其他(Material/Build/Perf...) | 9 | 2,258 | 各类工具 |
| **合计** | **140** | **20,553** | |

其中**我们需要移植的核心代码**约 ~11,500 行（去掉通信层 ~3,000 行 + 我们已有的 Material ~600 行 + 重复/样板代码）。
