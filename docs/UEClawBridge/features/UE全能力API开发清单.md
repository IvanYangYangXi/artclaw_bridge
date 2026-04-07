# UE 全能力 C++ API 开发清单

> 状态图例: ⬜ 未开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 暂缓

## 架构规范

### 模块结构
```
UEClawBridge/
├── Source/UEClawBridge/           （现有模块：UI/Dashboard/MCP）
└── Source/UEClawBridgeAPI/        （新模块：Python-callable C++ API）
    ├── UEClawBridgeAPI.Build.cs
    ├── Public/
    │   ├── UEClawBridgeAPI.h       （模块定义）
    │   ├── BlueprintGraphAPI.h
    │   ├── PIEControlAPI.h
    │   ├── ActorReflectionAPI.h
    │   ├── AssetManagementAPI.h
    │   ├── StateTreeAPI.h
    │   ├── WidgetBlueprintAPI.h
    │   ├── BuildSystemAPI.h
    │   ├── PerformanceAPI.h
    │   ├── DataTableAPI.h
    │   ├── LoggingAPI.h
    │   └── ProjectInfoAPI.h
    └── Private/
        ├── UEClawBridgeAPIModule.cpp
        ├── BlueprintGraphAPI.cpp
        ├── BlueprintGraphQuery.cpp    （查询拆分，防超 500 行）
        ├── BlueprintGraphEdit.cpp     （编辑拆分）
        ├── PIEControlAPI.cpp
        ├── ActorReflectionAPI.cpp
        ├── AssetManagementAPI.cpp
        ├── AssetQueryAPI.cpp          （查询拆分）
        ├── StateTreeAPI.cpp
        ├── WidgetBlueprintAPI.cpp
        ├── BuildSystemAPI.cpp
        ├── PerformanceAPI.cpp
        ├── DataTableAPI.cpp
        ├── LoggingAPI.cpp
        ├── ProjectInfoAPI.cpp
        └── Utils/
            ├── PropertySerializer.h/.cpp   （属性序列化工具）
            ├── AssetModifier.h/.cpp        （资产修改工具）
            └── GraphLayoutUtil.h/.cpp      （节点布局工具）
```

### 代码规范要求
- 每文件 100-300 行（黄金区间），硬性上限 500 行
- 单一职责：一个 .cpp 一个功能域
- `UFUNCTION(BlueprintCallable, Category="ArtClaw|XXX")` 暴露给 Python
- 返回值：复杂结果返回 JSON FString，简单结果用基本类型
- 错误处理：UE_LOG + 返回空串/false，不抛异常
- 移植文件：保留原始 copyright + 添加 ArtClaw 修改声明
- **禁止 AI 使用 `// ... existing code ...` 省略**

### Python 调用约定
```python
import unreal
# 所有 API 都是 BlueprintFunctionLibrary 的静态方法
result_json = unreal.BlueprintGraphAPI.query_blueprint_graph(
    asset_path="/Game/BP_Player",
    graph_name="EventGraph"
)
result = json.loads(result_json)
```

---

## Phase 0: 基础设施（前置依赖）

### 0.1 ⬜ 创建 UEClawBridgeAPI 模块骨架
- [ ] UEClawBridgeAPI.Build.cs（依赖声明）
- [ ] UEClawBridgeAPI.h / UEClawBridgeAPIModule.cpp（模块注册）
- [ ] .uplugin 添加新模块
- [ ] 编译验证

### 0.2 ⬜ 移植通用工具类
- [ ] PropertySerializer.h/.cpp — 属性序列化/反序列化（移植自 BridgePropertySerializer，~700行→拆2文件）
  - SerializePropertyValue(): FProperty → FJsonValue
  - DeserializePropertyValue(): FJsonValue → FProperty
  - ResolveClass(): 类名字符串 → UClass*
  - 支持嵌套结构体、数组、Map、软引用
- [ ] AssetModifier.h/.cpp — 资产修改通用工具（移植自 BridgeAssetModifier，~500行→拆2文件）
  - LoadAssetByPath(): 统一资产加载
  - BeginTransaction(): 撤销事务
  - MarkModified() / MarkPackageDirty()
  - FindNodeByGuid(): 全图搜索节点
  - FindPropertyByPath(): 嵌套属性路径查找
  - CompileBlueprint()
  - RefreshMaterial()
- [ ] GraphLayoutUtil.h/.cpp — 节点自动布局（移植自 BridgeGraphLayoutUtil，~350行）
  - CalculateBlueprintNodePosition()
  - CalculateMaterialExpressionPosition()
  - 避让已有节点

**来源: soft-ue-cli Utils/ 目录，~1,550 行 → 改造为 ~1,200 行**

---

## Phase 1: Blueprint 图操作（P0 最高优先级）

### 1.1 ⬜ Blueprint 图查询
**文件: BlueprintGraphQuery.cpp (~400 行)**
- [ ] QueryBlueprintGraph(AssetPath, GraphName, GraphType, NodeGuid, Search, bIncludePositions) → JSON
  - 列出所有图（Event/Function/Macro/Interface）
  - 按 GUID 查询特定节点
  - 按名称查询特定 callable
  - 节点信息：GUID、类名、标题、Pin 列表、连接关系
- [ ] ListBlueprintCallables(AssetPath) → JSON
  - 列出所有事件/函数/宏（轻量版，不含节点细节）
  - 返回参数签名

**来源: 移植 QueryBlueprintGraphTool.cpp + QueryBlueprintTool.cpp**

### 1.2 ⬜ Blueprint 图查询 — AnimBlueprint 扩展
**文件: AnimBlueprintQuery.cpp (~300 行)**
- [ ] AnimBlueprint 特化查询
  - AnimGraph / StateMachine / State / Transition / BlendStack 图类型
  - 状态机层级结构（states/transitions/conduits）
  - FAnimNode 内嵌结构体属性读取
  - 目标骨架信息

**来源: 移植 QueryBlueprintGraphTool.cpp 的 AnimBP 部分**

### 1.3 ⬜ Blueprint 节点增删
**文件: BlueprintGraphEdit.cpp (~400 行)**
- [ ] AddGraphNode(AssetPath, NodeClass, GraphName, Position, AutoPosition, ConnectToNode, Properties) → JSON
  - Blueprint 节点：K2Node_CallFunction / K2Node_VariableGet / K2Node_Event 等
  - Material 表达式：MaterialExpressionAdd 等（与现有 Material Skill 互补）
  - AnimLayerFunction 创建（完整 AnimGraph + Root + InputPose）
  - 自动布局 + 属性设置
- [ ] RemoveGraphNode(AssetPath, NodeGuid) → bool
  - 删除节点并清理连接
- [ ] SetNodePosition(AssetPath, Positions[]) → JSON
  - 批量设置节点位置

**来源: 移植 AddGraphNodeTool.cpp + RemoveGraphNodeTool.cpp + SetNodePositionTool.cpp**

### 1.4 ⬜ Blueprint 节点连接
**文件: BlueprintGraphConnect.cpp (~350 行)**
- [ ] ConnectGraphPins(AssetPath, SourceNode, SourcePin, TargetNode, TargetPin) → JSON
  - Blueprint Pin 连接（含 Schema 验证）
  - Material 表达式连接
- [ ] DisconnectGraphPin(AssetPath, NodeGuid, PinName, TargetNode, TargetPin) → JSON
  - 断开特定连接或全部连接
- [ ] InsertGraphNode(AssetPath, NodeClass, SourceGuid, SourcePin, TargetGuid, TargetPin, GraphName) → JSON
  - 在两个已连接节点之间原子性插入新节点

**来源: 移植 ConnectGraphPinsTool.cpp + DisconnectGraphPinTool.cpp + InsertGraphNodeTool.cpp**

### 1.5 ⬜ Blueprint 属性与编译
**文件: BlueprintNodeProperty.cpp (~300 行)**
- [ ] SetNodeProperty(AssetPath, NodeGuid, Properties{}) → JSON
  - 通过 GUID 设置节点 UPROPERTY
  - 支持内嵌结构体、Pin 默认值 fallback
  - AnimGraphNode 的内嵌 FAnimNode 属性
- [ ] CompileBlueprint(AssetPath) → JSON
  - 编译并返回结果（成功/失败/警告）
- [ ] ModifyInterface(AssetPath, Action, InterfaceName) → JSON
  - 添加/移除 Blueprint 实现的接口

**来源: 移植 SetNodePropertyTool.cpp + CompileBlueprintTool.cpp + ModifyInterfaceTool.cpp**

### 1.6 ⬜ OpenClaw Skill: ue57_blueprint_graph
- [ ] SKILL.md — Blueprint 图查询/编辑操作指南
- [ ] 安装到 ~/.openclaw/skills/

---

## Phase 2: PIE 控制（P0）

### 2.1 ⬜ PIE 会话管理
**文件: PIEControlAPI.cpp (~350 行)**
- [ ] PIEStart(Mode, MapPath, Timeout) → JSON
  - 启动 PIE（viewport/new_window/standalone）
  - 可选加载指定地图
  - 等待 PIE 就绪
- [ ] PIEStop() → JSON
- [ ] PIEPause() / PIEResume() → JSON
- [ ] PIEGetState(Include[]) → JSON
  - World 信息 + 玩家信息 + 暂停状态
- [ ] PIEWaitFor(ActorName, Property, Operator, Expected, Timeout) → JSON
  - 轮询等待条件满足（用于自动化测试）

**来源: 移植 PieSessionTool.cpp**

### 2.2 ⬜ 输入注入
**文件: InputInjectionAPI.cpp (~250 行)**
- [ ] TriggerKeyInput(Key, Action) → JSON
  - 发送按键事件到 PIE
- [ ] TriggerMouseInput(X, Y, Button) → JSON
- [ ] TriggerAxisInput(AxisName, Value) → JSON

**来源: 移植 TriggerInputTool.cpp**

### 2.3 ⬜ OpenClaw Skill: ue57_pie_control
- [ ] SKILL.md — PIE 控制 + 输入注入 + 自动化测试指南

---

## Phase 3: 通用反射与 Actor 操作（P1）

### 3.1 ⬜ 通用反射调用
**文件: ActorReflectionAPI.cpp (~400 行)**
- [ ] CallFunction(ActorName, FunctionName, Args{}) → JSON
  - 调用任意 BlueprintCallable UFUNCTION
  - 支持参数序列化/反序列化
  - 返回值提取
- [ ] GetProperty(ActorOrAsset, PropertyPath) → JSON
  - 读取 UPROPERTY（支持嵌套路径 "Component.SubProp.Field"）
  - 支持数组/Map/结构体
- [ ] SetProperty(ActorOrAsset, PropertyPath, Value) → JSON
  - 写入 UPROPERTY（同上嵌套支持）

**来源: 移植 CallFunctionTool.cpp + GetPropertyTool.cpp + SetPropertyTool.cpp**

### 3.2 ⬜ 高级 Actor 操作
**文件: ActorOpsAPI.cpp (~350 行)**
- [ ] SpawnActorAdvanced(Class, Location, Rotation, Properties{}, WorldType) → JSON
  - 支持 Editor World 和 PIE World
  - 创建后立即设置属性
- [ ] AddComponent(ActorName, ComponentClass, Properties{}) → JSON
- [ ] BatchSpawnActors(Actors[]) → JSON
  - 批量生成（减少 tool call 次数）
- [ ] BatchModifyActors(Modifications[]) → JSON
- [ ] BatchDeleteActors(ActorNames[]) → JSON

**来源: 移植 SpawnActorTool.cpp(Editor) + AddComponentTool.cpp + Batch*Tool.cpp**

### 3.3 ⬜ OpenClaw Skill: ue57_actor_reflection
- [ ] SKILL.md — 通用反射 + Actor 高级操作指南

---

## Phase 4: 资产管理增强（P1）

### 4.1 ⬜ 资产查询与搜索
**文件: AssetQueryAPI.cpp (~350 行)**
- [ ] QueryAsset(Name, ClassFilter, PathFilter, Limit) → JSON
  - Content Browser 搜索
  - DataTable 行查询
  - 类过滤 + 路径过滤 + 通配符
- [ ] FindReferences(AssetPath, ReferenceType) → JSON
  - 查找引用/被引用关系
  - 支持变量/函数级引用
- [ ] ClassHierarchy(ClassName, Direction) → JSON
  - 类继承链查询（祖先/后代/双向）

**来源: 移植 QueryAssetTool.cpp + FindReferencesTool.cpp + ClassHierarchyTool.cpp**
**注: ClassHierarchy Python 也可做，但 C++ 版更完整（包含非反射类）**

### 4.2 ⬜ 资产创建与修改
**文件: AssetManagementAPI.cpp (~400 行)**
- [ ] CreateAsset(AssetPath, AssetClass, Properties{}) → JSON
  - 创建 Blueprint / Material / DataTable / World / 其他
- [ ] DeleteAsset(AssetPath) → bool
- [ ] SaveAsset(AssetPath, bCheckout) → JSON
  - 保存 + 可选源码控制 checkout
- [ ] OpenAsset(AssetPath) → bool
  - 在编辑器中打开
- [ ] SetAssetProperty(AssetPath, ComponentName, PropertyPath, Value) → JSON
  - 设置 Blueprint CDO 或组件默认属性
- [ ] GetAssetDiff(AssetPath) → JSON
  - 与源码控制版本对比属性差异
- [ ] GetAssetPreview(AssetPath, OutputPath) → JSON
  - 导出缩略图

**来源: 移植 CreateAssetTool.cpp + DeleteAssetTool.cpp + SaveAssetTool.cpp + OpenAssetTool.cpp + SetPropertyTool.cpp(Editor) + GetAssetDiffTool.cpp + GetAssetPreviewTool.cpp**

### 4.3 ⬜ DataTable 操作
**文件: DataTableAPI.cpp (~200 行)**
- [ ] AddDataTableRow(AssetPath, RowName, Values{}) → JSON
  - 添加或更新 DataTable 行
- [ ] QueryDataTable(AssetPath, RowFilter) → JSON
  - 查询行数据 + 结构体 schema

**来源: 移植 AddDataTableRowTool.cpp + QueryAssetTool.cpp(DataTable 部分)**

### 4.4 ⬜ OpenClaw Skill: ue57_asset_management
- [ ] SKILL.md — 资产管理全流程指南

---

## Phase 5: StateTree + Widget Blueprint（P2）

### 5.1 ⬜ StateTree 操作
**文件: StateTreeAPI.cpp (~400 行)**
- [ ] QueryStateTree(AssetPath) → JSON
  - 查询 states / tasks / transitions 结构
- [ ] AddStateTreeState(AssetPath, ParentState, StateName, StateType) → JSON
- [ ] AddStateTreeTask(AssetPath, StateName, TaskClass, Properties{}) → JSON
- [ ] AddStateTreeTransition(AssetPath, SourceState, TargetState, Condition) → JSON
- [ ] RemoveStateTreeState(AssetPath, StateName) → JSON

**来源: 移植 StateTree/ 目录 5 个文件**

### 5.2 ⬜ Widget Blueprint 操作
**文件: WidgetBlueprintAPI.cpp (~400 行)**
- [ ] InspectWidgetBlueprint(AssetPath) → JSON
  - Widget 层级结构 + 绑定 + 属性
- [ ] InspectRuntimeWidgets() → JSON
  - PIE 运行时活跃 Widget 几何信息
- [ ] AddWidget(AssetPath, ParentSlot, WidgetClass, Properties{}) → JSON
  - 向 Widget Blueprint 添加控件

**来源: 移植 Widget/ 目录 4 个文件**

### 5.3 ⬜ OpenClaw Skill: ue57_statetree / ue57_widget_blueprint
- [ ] 各自 SKILL.md

---

## Phase 6: 编译系统 + 日志 + 性能（P2）

### 6.1 ⬜ 编译与构建
**文件: BuildSystemAPI.cpp (~250 行)**
- [ ] BuildAndRelaunch(bWait) → JSON
  - 触发完整 C++ 重编译
  - 可选等待完成并返回结果
- [ ] TriggerLiveCoding() → JSON
  - 触发 Live Coding（热重载）
  - 等待编译结果

**来源: 移植 BuildAndRelaunchTool.cpp + TriggerLiveCodingTool.cpp**

### 6.2 ⬜ 日志与 CVar
**文件: LoggingAPI.cpp (~250 行)**
- [ ] GetLogs(Category, TextFilter, Limit, Severity) → JSON
  - 读取 UE 输出日志（过滤/搜索）
- [ ] GetConsoleVar(VarName) → JSON
- [ ] SetConsoleVar(VarName, Value) → JSON

**来源: 移植 GetLogsTool.cpp + ConsoleVarTool.cpp**

### 6.3 ⬜ 性能分析
**文件: PerformanceAPI.cpp (~250 行)**
- [ ] InsightsCapture(Action, Channels) → JSON
  - 启动/停止 Trace 捕获
- [ ] InsightsListTraces() → JSON
  - 列出可用 trace 文件
- [ ] InsightsAnalyze(TraceFile, AnalysisType) → JSON
  - 分析 CPU/GPU/内存热点

**来源: 移植 Insights*Tool.cpp 3 个文件**

### 6.4 ⬜ 项目信息
**文件: ProjectInfoAPI.cpp (~200 行)**
- [ ] GetProjectInfo() → JSON
  - 项目名、引擎版本、目标平台、模块列表
- [ ] GetEditorStatus() → JSON
  - 编辑器运行状态、内存使用、FPS

**来源: 移植 ProjectInfoTool.cpp**

### 6.5 ⬜ OpenClaw Skill: ue57_build_system / ue57_performance
- [ ] 各自 SKILL.md

---

## Phase 7: UE 原生领域扩展 — 自行开发（P3）

### 7.1 ⬜ Sequencer 控制
**文件: SequencerAPI.cpp (~400 行)**
- [ ] CreateLevelSequence(AssetPath) → JSON
- [ ] AddTrack(SequencePath, TrackType, ActorName) → JSON
- [ ] AddKeyframe(SequencePath, TrackName, Time, Value) → JSON
- [ ] PlaySequence(SequencePath) / StopSequence() → JSON
- [ ] GetSequenceInfo(SequencePath) → JSON

**来源: 自行开发，基于 ISequencer / ULevelSequence API**

### 7.2 ⬜ 行为树/AI
**文件: BehaviorTreeAPI.cpp (~300 行)**
- [ ] QueryBehaviorTree(AssetPath) → JSON
- [ ] AddBTNode(AssetPath, ParentNode, NodeClass) → JSON
- [ ] AddBlackboardKey(AssetPath, KeyName, KeyType) → JSON
- [ ] ConnectBTNodes(AssetPath, ParentGuid, ChildGuid) → JSON

**来源: 自行开发，基于 UBehaviorTree / UBTNode API**

### 7.3 ⬜ Niagara 粒子系统
**文件: NiagaraAPI.cpp (~400 行)**
- [ ] QueryNiagaraSystem(AssetPath) → JSON
- [ ] AddNiagaraModule(AssetPath, EmitterName, ModuleClass) → JSON
- [ ] SetNiagaraParameter(AssetPath, ParameterName, Value) → JSON

**来源: 自行开发，基于 UNiagaraSystem / UNiagaraEmitter API**

### 7.4 ⬜ Enhanced Input 配置
**文件: EnhancedInputAPI.cpp (~250 行)**
- [ ] QueryInputMappingContext(AssetPath) → JSON
- [ ] AddInputAction(AssetPath, ActionName, ValueType) → JSON
- [ ] AddInputMapping(ContextPath, ActionPath, Key, Modifiers[]) → JSON

**来源: 自行开发，基于 UInputMappingContext / UInputAction API**

### 7.5 ⬜ GAS (Gameplay Ability System)
**文件: GameplayAbilityAPI.cpp (~300 行)**
- [ ] CreateGameplayAbility(AssetPath, ParentClass) → JSON
- [ ] CreateGameplayEffect(AssetPath) → JSON
- [ ] SetGEModifier(AssetPath, Attribute, ModOp, Value) → JSON
- [ ] QueryAbilityInfo(AssetPath) → JSON

**来源: 自行开发，基于 UGameplayAbility / UGameplayEffect API**

### 7.6 ⬜ OpenClaw Skills
- [ ] ue57_sequencer / ue57_behavior_tree / ue57_niagara / ue57_enhanced_input / ue57_gas

---

## 统计汇总

| Phase | 文件数 | 预估行数 | Skill 数 | 优先级 |
|-------|-------|---------|---------|--------|
| P0 基础设施 | 6 | ~1,200 | 0 | 前置 |
| P1 Blueprint 图 | 5+1 | ~1,750 | 1 | P0 |
| P2 PIE 控制 | 2+1 | ~600 | 1 | P0 |
| P3 反射+Actor | 2+1 | ~750 | 1 | P1 |
| P4 资产管理 | 3+1 | ~950 | 1 | P1 |
| P5 StateTree+Widget | 2+2 | ~800 | 2 | P2 |
| P6 编译/日志/性能 | 4+2 | ~950 | 2 | P2 |
| P7 自研扩展 | 5+5 | ~1,650 | 5 | P3 |
| **合计** | **~40** | **~8,650** | **13** | |

> 注: 行数已按代码规范压缩（去掉通信层样板代码 + 拆分过大文件）
