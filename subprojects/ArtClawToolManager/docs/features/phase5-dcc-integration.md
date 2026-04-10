# Phase 5: DCC 集成

> 版本: 2.0
> 日期: 2026-04-10
> 工期: 2-3周
> 依赖: Phase 1-4

---

## 参考文档

- **架构设计**: [architecture-design.md](../specs/architecture-design.md)
- **UI 设计**: [ui-design.md](../ui/ui-design.md)
- **OpenClaw Gateway**: [gateway-forwarding-roadmap.md](../../../../docs/features/gateway-forwarding-roadmap.md)
- **ComfyUI MCP 集成**: [comfyui-mcp-integration.md](../../../../docs/features/comfyui-mcp-integration.md)
- **DCCClawBridge 架构**: [架构.md](../../../../docs/DCCClawBridge/specs/架构.md) (编码问题，实际文件名为乱码)
- **实现路径图**: [实现路径图.md](../../../../docs/DCCClawBridge/specs/实现路径图.md) (编码问题)

---

## 目标

在 DCC 中提供快捷入口面板，与 Web 管理器形成互补联动。

**交付标准**:
- UE Slate 面板
- Maya Qt 面板
- ComfyUI 按钮扩展
- DCC 插件分发机制
- 上下文传递与联动

---

## 设计原则

### 1. 功能边界明确

| 功能 | DCC 面板 | Web 面板 |
|------|----------|----------|
| **快捷入口** | ✅ 最近使用、常用工具 | ❌ 不重复 |
| **完整对话** | ❌ 不提供 | ✅ 完整对话能力 |
| **工具管理** | ❌ 只读展示 | ✅ 安装/卸载/创建 |
| **参数配置** | ❌ 简单执行 | ✅ 完整参数编辑 |
| **会话历史** | ❌ 不提供 | ✅ 完整历史 |

**核心原则**: DCC 面板是**快捷入口**，Web 面板是**完整管理器**，两者不重叠、互相补充。

### 2. 轻量优先

- DCC 面板只展示核心功能（最近使用 + 常用工具）
- 不实现复杂交互，点击后唤起 Web 界面处理

### 3. 上下文感知

- 自动识别当前 DCC 类型和版本
- 传递选中对象、当前文件等上下文信息
- Web 界面根据上下文自动过滤相关工具

---

## Week 1: DCC 插件分发机制

### Day 1-2: 插件分发架构设计

#### 分发机制概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    ArtClaw Tool Manager                          │
│                      (Web 后端服务)                               │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   UE 插件分发   │  │  Maya 插件分发  │  │ ComfyUI 扩展分发 │
│                 │  │                 │  │                 │
│ • 自动安装脚本   │  │ • 模块安装      │  │ • 节点复制      │
│ • 更新检测      │  │ • shelf 配置    │  │ • 菜单注册      │
│ • 版本管理      │  │ • 插件管理器    │  │ • 热重载        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

#### 安装方式

| DCC | 安装方式 | 安装路径 |
|-----|----------|----------|
| **UE** | 自动复制到 Plugins 目录 | `{Project}/Plugins/ArtClawPanel/` |
| **Maya** | 模块安装 + shelf 配置 | `{Maya}/modules/` 和 `prefs/shelves/` |
| **ComfyUI** | 复制到 custom_nodes | `ComfyUI/custom_nodes/artclaw_panel/` |

#### 安装流程

**UE 安装**:
```
1. 用户点击"安装 UE 面板"
2. 后端检测 UE 安装路径（注册表/环境变量）
3. 复制插件文件到 Plugins 目录
4. 注册菜单入口（Tools → ArtClaw Tool Manager）
5. 提示重启 UE 或热重载
```

**Maya 安装**:
```
1. 用户点击"安装 Maya 面板"
2. 后端检测 Maya 安装路径
3. 创建模块描述文件（.mod）
4. 复制 Python 脚本到模块目录
5. 创建/更新 shelf 按钮
6. 提示重启 Maya
```

**ComfyUI 安装**:
```
1. 用户点击"安装 ComfyUI 扩展"
2. 后端检测 ComfyUI 路径（配置或自动发现）
3. 复制 JS/Python 文件到 custom_nodes
4. 注册侧边栏按钮
5. 提示刷新浏览器或重启 ComfyUI
```

### Day 3-4: 更新与卸载机制

#### 更新检测

```python
# 版本检查流程
def check_update(dcc_type: str, current_version: str) -> UpdateInfo:
    """
    1. 查询远程版本清单
    2. 对比本地版本
    3. 返回更新信息
    """
    remote_version = fetch_remote_manifest(dcc_type)
    if semver_compare(remote_version, current_version) > 0:
        return {
            "has_update": True,
            "current": current_version,
            "latest": remote_version,
            "changelog": fetch_changelog(dcc_type, remote_version)
        }
```

#### 更新流程

| DCC | 更新方式 | 注意事项 |
|-----|----------|----------|
| **UE** | 关闭 UE → 替换文件 → 重启 | UE 运行时不允许修改插件 |
| **Maya** | 卸载旧版 → 安装新版 | 需重启 Maya |
| **ComfyUI** | 热更新（JS）+ 重启（Python）| JS 可热重载，Python 需重启 |

#### 卸载流程

```
1. 用户点击"卸载面板"
2. 检测 DCC 是否运行（运行中则提示关闭）
3. 删除插件文件
4. 清理配置文件
5. 移除菜单/shelf 入口
6. 完成提示
```

### Day 5-7: 分发后端实现

#### API 设计

```typescript
// 安装 DCC 面板
POST /api/dcc-panels/install
{
  "dccType": "ue57" | "maya2024" | "comfyui",
  "installPath": "string"  // 可选，自动检测
}

// 检查更新
GET /api/dcc-panels/check-update?dccType={type}&version={version}

// 执行更新
POST /api/dcc-panels/update
{
  "dccType": "string",
  "targetVersion": "string"
}

// 卸载
POST /api/dcc-panels/uninstall
{
  "dccType": "string"
}

// 获取安装状态
GET /api/dcc-panels/status
```

#### 安装状态管理

```json
{
  "dccPanels": {
    "ue57": {
      "installed": true,
      "version": "1.0.0",
      "installPath": "C:/.../Plugins/ArtClawPanel",
      "hasUpdate": false,
      "lastCheck": "2026-04-10T10:00:00Z"
    },
    "maya2024": {
      "installed": false,
      "version": null,
      "installPath": null,
      "hasUpdate": false
    },
    "comfyui": {
      "installed": true,
      "version": "1.0.0",
      "installPath": "C:/.../custom_nodes/artclaw_panel",
      "hasUpdate": true,
      "latestVersion": "1.1.0"
    }
  }
}
```

**验收标准**:
- [ ] 支持 UE/Maya/ComfyUI 三种 DCC 的安装
- [ ] 自动检测 DCC 安装路径
- [ ] 版本检查与更新提示
- [ ] 完整卸载功能
- [ ] 安装状态持久化

---

## Week 2: DCC 面板实现

### Day 1-3: UE Slate 面板

#### 面板功能

**面板内容**:

```
┌─────────────────────────────────────────┐
│ 🔧 ArtClaw 工具                [_][X]  │
├─────────────────────────────────────────┤
│                                         │
│  📌 最近使用                            │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐           │
│  │ 🖼️ │ │ 🖼️ │ │ 🖼️ │ │ 🖼️ │           │
│  │节点 │ │材质 │ │导出 │ │修复 │           │
│  └────┘ └────┘ └────┘ └────┘           │
│                                         │
│  ⭐ 常用工具                            │
│  ┌─────────────────────────────────┐   │
│  │ 🔧 节点安装器          [运行]   │   │
│  ├─────────────────────────────────┤   │
│  │ 🔧 Workflow 修复器     [运行]   │   │
│  ├─────────────────────────────────┤   │
│  │ 🔧 批量重命名          [运行]   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  [打开完整管理器 →]                     │
│                                         │
└─────────────────────────────────────────┘
```

**实现文件**:

```
src/dcc-panels/ue/
├── ArtClawToolPanel/
│   ├── ArtClawToolPanel.h          # 面板主类
│   ├── ArtClawToolPanel.cpp        # 面板实现
│   ├── SArtClawToolPanel.h         # Slate UI 定义
│   ├── SArtClawToolPanel.cpp       # Slate UI 实现
│   ├── ArtClawToolButton.h         # 工具按钮
│   └── ArtClawToolButton.cpp
├── ArtClawToolPanelCommands.h      # 菜单命令
├── ArtClawToolPanelStyle.h         # 样式定义
└── ArtClawToolPanel.Build.cs       # 构建配置
```

**菜单入口**:

- 菜单栏: `Tools → ArtClaw Tool Manager`
- 工具栏按钮（可选）: 可配置的快捷按钮
- 快捷键: `Ctrl+Shift+A`（可配置）

**与 Web 联动**:

```cpp
// 点击"打开完整管理器"
void SArtClawToolPanel::OnOpenFullManager()
{
    FString Url = FString::Printf(
        TEXT("http://localhost:9876/chat?dcc=ue57&version=%s&session=%s"),
        *FEngineVersion::Current().ToString(),
        *GetOrCreateSessionId()
    );
    
    // 添加选中对象上下文
    if (GEditor)
    {
        TArray<FString> SelectedObjects;
        for (auto* Actor : GEditor->GetSelectedActors()->GetArray())
        {
            SelectedObjects.Add(Actor->GetName());
        }
        if (SelectedObjects.Num() > 0)
        {
            Url += FString::Printf(TEXT("&selected=%s"), 
                *FString::Join(SelectedObjects, TEXT(",")));
        }
    }
    
    // 添加当前关卡
    if (ULevel* CurrentLevel = GWorld->GetCurrentLevel())
    {
        Url += FString::Printf(TEXT("&level=%s"), *CurrentLevel->GetName());
    }
    
    FPlatformProcess::LaunchURL(*Url, nullptr, nullptr);
}
```

**验收标准**:
- [ ] 面板可正常打开和关闭
- [ ] 最近使用正确显示（2x2 网格）
- [ ] 常用工具列表可点击运行
- [ ] 点击"打开完整管理器"唤起浏览器
- [ ] URL 参数正确传递 DCC 上下文

### Day 4-5: Maya Qt 面板

#### 面板功能

与 UE 面板功能一致:
- 最近使用（2x2 图标网格）
- 常用工具列表
- 打开完整管理器按钮

**实现文件**:

```
src/dcc-panels/maya/
├── artclaw_tool_panel.py      # 主面板实现
├── artclaw_tool_button.py     # 工具按钮组件
├── artclaw_recent_grid.py     # 最近使用网格
├── artclaw_context.py         # 上下文获取
└── install.py                 # 安装脚本
```

**菜单入口**:

- 菜单: `ArtClaw → Tool Manager`
- Shelf 按钮: 可拖拽的图标按钮

**与 Web 联动**:

```python
# 点击"打开完整管理器"
def open_full_manager():
    base_url = "http://localhost:9876/chat"
    
    # 构建上下文参数
    params = {
        "dcc": "maya2024",
        "session": get_or_create_session_id(),
        "version": cmds.about(version=True)
    }
    
    # 添加选中对象
    selected = cmds.ls(selection=True)
    if selected:
        params["selected"] = ",".join(selected)
    
    # 添加当前文件
    current_file = cmds.file(query=True, sceneName=True)
    if current_file:
        params["file"] = current_file
    
    # 构建 URL
    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"
    
    # 打开浏览器
    webbrowser.open(url)
```

**验收标准**:
- [ ] 面板可正常打开和关闭
- [ ] 菜单和 shelf 入口正常
- [ ] 最近使用可显示
- [ ] 点击唤起浏览器并传递上下文

### Day 6-7: ComfyUI 按钮扩展

#### 面板功能

**侧边栏按钮**:

```
┌──────────────────────────────────────────┐
│  ComfyUI              [ArtClaw 🔧]       │
│                                          │
│  ┌──────────┐                            │
│  │ Queue    │                            │
│  │ History  │                            │
│  │ Node Lib │                            │
│  │ ...      │                            │
│  ├──────────┤                            │
│  │ ArtClaw  │ ← 新增按钮                 │
│  │   🔧     │                            │
│  └──────────┘                            │
│                                          │
```

**展开面板**:

```
┌──────────────────────────────────────────┐
│  🔧 ArtClaw 工具                         │
├──────────────────────────────────────────┤
│                                          │
│  📌 最近使用的 Workflows                 │
│  ┌────┐ ┌────┐ ┌────┐                   │
│  │ 🖼️ │ │ 🖼️ │ │ 🖼️ │                   │
│  └────┘ └────┘ └────┘                   │
│                                          │
│  ⭐ 快捷工具                             │
│  • 节点安装器              [运行]        │
│  • Workflow 修复器         [运行]        │
│  • 高清修复预设            [运行]        │
│                                          │
│  [打开完整管理器 →]                      │
│                                          │
└──────────────────────────────────────────┘
```

**实现文件**:

```
src/dcc-panels/comfyui/
├── artclaw_panel.js           # 前端 JS 实现
├── artclaw_panel.py           # 后端 API 扩展
├── artclaw_context.py         # 上下文获取
└── __init__.py                # 节点注册
```

**与 Web 联动**:

```javascript
// 点击"打开完整管理器"
function openFullManager() {
    const baseUrl = 'http://localhost:9876/chat';
    
    // 获取当前工作流信息
    const workflow = app.graph.serialize();
    const workflowName = app.getWorkflowName() || 'untitled';
    
    const params = new URLSearchParams({
        dcc: 'comfyui',
        session: getOrCreateSessionId(),
        version: '1.0.0',
        workflow: workflowName
    });
    
    // 如果有选中的节点，传递节点类型
    const selectedNodes = app.graph._nodes
        .filter(n => n.is_selected)
        .map(n => n.type);
    if (selectedNodes.length > 0) {
        params.set('selected_nodes', selectedNodes.join(','));
    }
    
    const url = `${baseUrl}?${params.toString()}`;
    window.open(url, '_blank');
}
```

**验收标准**:
- [ ] 按钮显示在侧边栏
- [ ] 面板可展开/收起
- [ ] 最近使用的 Workflows 显示正确
- [ ] 点击唤起浏览器并传递上下文

---

## Week 3: 上下文传递与错误处理

### Day 1-2: URL 参数格式规范

#### 标准参数格式

```
http://localhost:9876/chat?dcc={type}&version={ver}&session={id}&[上下文参数]
```

**基础参数**:

| 参数 | 说明 | 示例 |
|------|------|------|
| `dcc` | DCC 类型和版本 | `ue57`, `maya2024`, `comfyui` |
| `version` | DCC 版本号 | `5.4.0`, `2024.0` |
| `session` | 会话 ID（用于关联） | `uuid` |
| `timestamp` | 时间戳（防缓存） | `1712736000` |

**上下文参数（UE）**:

| 参数 | 说明 | 示例 |
|------|------|------|
| `level` | 当前关卡名 | `MainLevel` |
| `selected` | 选中对象列表（逗号分隔） | `Cube,Sphere,Light` |
| `selected_count` | 选中对象数量 | `3` |
| `map_path` | 当前地图路径 | `/Game/Maps/Main` |

**上下文参数（Maya）**:

| 参数 | 说明 | 示例 |
|------|------|------|
| `file` | 当前文件路径 | `/project/scene.ma` |
| `selected` | 选中对象列表 | `pCube1,pSphere1` |
| `selection_mode` | 选择模式 | `object`, `component` |

**上下文参数（ComfyUI）**:

| 参数 | 说明 | 示例 |
|------|------|------|
| `workflow` | 当前工作流名称 | `portrait_workflow` |
| `selected_nodes` | 选中节点类型 | `KSampler,VAELoader` |
| `queue_size` | 队列大小 | `0` |

#### 完整 URL 示例

**UE**:
```
http://localhost:9876/chat?dcc=ue57&version=5.4.0&session=abc-123&level=MainLevel&selected=Cube,Sphere&selected_count=2
```

**Maya**:
```
http://localhost:9876/chat?dcc=maya2024&version=2024.0&session=abc-123&file=/project/scene.ma&selected=pCube1,pSphere1
```

**ComfyUI**:
```
http://localhost:9876/chat?dcc=comfyui&version=1.0.0&session=abc-123&workflow=portrait&selected_nodes=KSampler
```

### Day 3-4: Web 端上下文响应

#### 上下文解析与处理

```typescript
// Web 端 URL 参数解析
interface DCCContext {
  dccType: 'ue57' | 'maya2024' | 'comfyui' | 'sd' | 'sp';
  version: string;
  sessionId: string;
  context: {
    // UE 特有
    level?: string;
    selected?: string[];
    selectedCount?: number;
    mapPath?: string;
    
    // Maya 特有
    file?: string;
    selectionMode?: string;
    
    // ComfyUI 特有
    workflow?: string;
    selectedNodes?: string[];
    queueSize?: number;
  };
}

// 解析函数
function parseDCCContext(): DCCContext | null {
  const params = new URLSearchParams(window.location.search);
  const dcc = params.get('dcc');
  if (!dcc) return null;
  
  return {
    dccType: dcc as DCCType,
    version: params.get('version') || 'unknown',
    sessionId: params.get('session') || generateSessionId(),
    context: {
      level: params.get('level') || undefined,
      selected: params.get('selected')?.split(',') || [],
      selectedCount: parseInt(params.get('selected_count') || '0'),
      file: params.get('file') || undefined,
      workflow: params.get('workflow') || undefined,
      selectedNodes: params.get('selected_nodes')?.split(',') || [],
    }
  };
}
```

#### 界面适配

**平台自动切换**:

```typescript
// 根据 DCC 上下文自动切换平台
useEffect(() => {
  const context = parseDCCContext();
  if (context) {
    // 自动切换到对应平台
    setCurrentPlatform(context.dccType);
    
    // 显示上下文信息
    setDCCContext(context);
    
    // 过滤相关工具
    filterToolsByDCC(context.dccType);
  }
}, []);
```

**上下文显示**:

```
┌─────────────────────────────────────────────────────────────┐
│ 🔧 ArtClaw Tool Manager                          [最小化]   │
├─────────────────────────────────────────────────────────────┤
│ 🟢 已连接: Unreal Engine 5.4                                │
│ 📁 当前关卡: MainLevel  |  🎯 选中: 2 个对象                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [消息流区域...]                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**工具过滤**:

- 根据 `dccType` 自动过滤只显示支持该 DCC 的工具
- 根据选中对象类型推荐相关工具
- 根据当前文件/关卡推荐上下文相关工具

### Day 5: 会话关联

#### 会话关联机制

```
DCC 面板 ──sessionId──→ Web 面板
    │                       │
    │◄────关联确认──────────┘
    │
    └── 后续通信使用同一 sessionId
```

**会话状态同步**:

```typescript
// WebSocket 连接时携带 sessionId
const ws = new WebSocket(`ws://localhost:9876/ws?session=${sessionId}`);

// 会话状态
interface SessionState {
  sessionId: string;
  dccType: string;
  connected: boolean;
  lastActivity: Date;
  context: DCCContext;
}

// 心跳维持
setInterval(() => {
  ws.send(JSON.stringify({
    type: 'heartbeat',
    sessionId: sessionId,
    timestamp: Date.now()
  }));
}, 30000);
```

### Day 6-7: 错误处理

#### Web 服务未启动（离线模式）

**检测机制**:

```typescript
// 检测 Web 服务是否可用
async function checkWebService(): Promise<boolean> {
  try {
    const response = await fetch('http://localhost:9876/health', {
      method: 'HEAD',
      signal: AbortSignal.timeout(2000)
    });
    return response.ok;
  } catch {
    return false;
  }
}
```

**DCC 面板离线模式**:

```
┌─────────────────────────────────────────┐
│ 🔧 ArtClaw 工具                [_][X]  │
├─────────────────────────────────────────┤
│                                         │
│  ⚠️  Web 服务未启动                      │
│                                         │
│  请确保 ArtClaw Tool Manager 正在运行。   │
│                                         │
│  [启动 Web 服务]  [重试连接]             │
│                                         │
│  ─────────────────────────────────────  │
│                                         │
│  📌 最近使用（缓存）                     │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐           │
│  │ 🖼️ │ │ 🖼️ │ │ 🖼️ │ │ 🖼️ │           │
│  └────┘ └────┘ └────┘ └────┘           │
│                                         │
│  （离线模式下仅显示缓存，无法运行）        │
│                                         │
└─────────────────────────────────────────┘
```

**离线模式行为**:

| 功能 | 在线模式 | 离线模式 |
|------|----------|----------|
| 最近使用 | 实时获取 | 读取本地缓存 |
| 运行工具 | 正常执行 | 提示启动 Web 服务 |
| 打开管理器 | 唤起浏览器 | 提示启动 Web 服务 |
| 工具列表 | 实时同步 | 显示缓存 |

#### DCC 连接失败处理

**Web 端连接状态**:

```
┌─────────────────────────────────────────────────────────────┐
│ 🔧 ArtClaw Tool Manager                          [最小化]   │
├─────────────────────────────────────────────────────────────┤
│ 🔴 已断开: Unreal Engine (上次连接: 2分钟前)                 │
│                                                             │
│  可能原因:                                                  │
│  • UE 已关闭                                                │
│  • DCC 插件被禁用                                           │
│  • 网络连接中断                                             │
│                                                             │
│  [重新连接]  [忽略]  [切换到独立模式]                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [消息流区域（独立模式）]                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**连接状态管理**:

```typescript
enum ConnectionStatus {
  CONNECTED = 'connected',       // 已连接
  DISCONNECTED = 'disconnected', // 已断开
  CONNECTING = 'connecting',     // 连接中
  ERROR = 'error'                // 错误
}

// 自动重连
function setupReconnect() {
  let retryCount = 0;
  const maxRetries = 5;
  
  const attemptReconnect = () => {
    if (retryCount >= maxRetries) {
      setConnectionStatus(ConnectionStatus.ERROR);
      return;
    }
    
    setConnectionStatus(ConnectionStatus.CONNECTING);
    
    setTimeout(() => {
      connect().then(success => {
        if (success) {
          retryCount = 0;
          setConnectionStatus(ConnectionStatus.CONNECTED);
        } else {
          retryCount++;
          attemptReconnect();
        }
      });
    }, Math.min(1000 * Math.pow(2, retryCount), 30000)); // 指数退避
  };
  
  return attemptReconnect;
}
```

**错误提示规范**:

| 错误场景 | 提示方式 | 用户操作 |
|----------|----------|----------|
| Web 服务未启动 | 面板内警告 + Toast | 启动服务/重试 |
| DCC 连接断开 | 顶部横幅 | 重新连接/忽略 |
| 工具执行失败 | Toast + 详情展开 | 重试/查看日志 |
| 网络超时 | Toast | 重试 |
| 版本不兼容 | 弹窗提示 | 更新插件 |

---

## 验收标准汇总

### 功能验收

#### 分发机制
- [ ] UE 插件可自动安装/更新/卸载
- [ ] Maya 插件可自动安装/更新/卸载
- [ ] ComfyUI 扩展可自动安装/更新/卸载
- [ ] 安装状态正确检测和显示
- [ ] 版本检查与更新提示正常

#### DCC 面板
- [ ] UE 面板可正常打开和关闭
- [ ] Maya 面板可正常打开和关闭
- [ ] ComfyUI 按钮可点击展开
- [ ] 最近使用正确显示
- [ ] 常用工具列表可点击

#### 上下文传递
- [ ] URL 参数格式符合规范
- [ ] Web 端正确解析 DCC 上下文
- [ ] 平台自动切换正确
- [ ] 工具根据 DCC 类型过滤
- [ ] 会话 ID 正确关联

#### 联动功能
- [ ] 点击"打开完整管理器"唤起浏览器
- [ ] URL 参数正确传递
- [ ] Web 界面识别 DCC 上下文
- [ ] 上下文信息显示正确

#### 错误处理
- [ ] Web 服务未启动时显示离线模式
- [ ] DCC 连接断开时正确提示
- [ ] 自动重连机制正常
- [ ] 错误提示清晰明确

### 集成验收
- [ ] 所有 DCC 面板与 Web 服务正常通信
- [ ] 上下文传递完整准确
- [ ] 离线模式可用（显示缓存数据）
- [ ] 错误恢复机制正常

---

## 项目完成

Phase 1-5 完成后，ArtClaw Tool Manager 基础功能全部实现：

- ✅ Phase 1: 基础框架（Server + Web）+ 对话面板
- ✅ Phase 2: Skill 管理完整功能
- ✅ Phase 3: 工具管理器 + Tool Creator
- ✅ Phase 4: Workflow 库（ComfyUI）
- ✅ Phase 5: DCC 内嵌面板 + 分发机制 + 上下文联动

后续可选:
- Phase 6: 市集功能（评分、评论、收益）
- Phase 7: 高级功能（团队协作、企业版）

---

## 更新记录

### v2.0 (2026-04-10)
- 工期调整：1周 → 2-3周
- 明确 DCC 面板与 Web 功能边界
- 新增 DCC 插件分发机制（安装/更新/卸载）
- 新增上下文传递设计规范
- 新增与对话面板的联动机制
- 新增错误处理（离线模式、连接失败）
- 细化各 DCC 面板的实现细节
