# Phase 1: 基础框架

> 版本: 2.0
> 日期: 2026-04-10
> 工期: 3周

---

## 目标

搭建可运行的基础框架，实现对话面板和 Skills 列表展示。

**交付标准**:
- 后端服务可启动，API 文档可访问
- 前端可运行，对话面板功能完整
- Skills 列表页面可展示数据
- 支持官方/市集/我的三个标签切换
- 支持搜索和分页

---

## 参考文档

- **架构设计**: [architecture-design.md](../specs/architecture-design.md)
- **UI 设计**: [ui-design.md](../ui/ui-design.md)
- **API 设计**: [api-design.md](../api/api-design.md)
- **OpenClaw Gateway 集成**: [gateway-forwarding-roadmap.md](../../../../docs/features/gateway-forwarding-roadmap.md)
- **ComfyUI MCP 集成**: [comfyui-mcp-integration.md](../../../../docs/features/comfyui-mcp-integration.md)

---

## Week 1: 后端基础

### Day 1-2: 项目初始化

**任务**:
1. 创建 FastAPI 项目结构
2. 配置 Python 虚拟环境和依赖
3. 实现基础路由和健康检查
4. 配置 WebSocket 支持（对话功能）

**相关代码参考**:
- `bridge_core.py` - Gateway WebSocket 客户端实现
- `mcp_server.py` - MCP Server 实现
- 详见: [gateway-forwarding-roadmap.md](../../../../docs/features/gateway-forwarding-roadmap.md)

**交付物**:
- 项目目录结构
- `requirements.txt`
- 可启动的服务（`GET /health` 返回 `{"status": "ok"}`）

**验收标准**:
- [ ] `python -m app.main` 可启动
- [ ] `http://localhost:9876/docs` 可访问 Swagger UI
- [ ] `GET /health` 返回 200

**错误处理规范**:
```typescript
{
  "success": false,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "服务启动失败",
    "details": "..."
  }
}
```

---

### Day 3-4: 数据模型

**任务**:
1. 定义 Pydantic 模型（ToolItem, SkillData, ChatMessage, ChatSession）
2. 实现本地存储读写
3. 创建 mock 数据

**交付物**:
- `app/models/schemas.py` - 数据模型定义
- `app/models/chat.py` - 对话相关模型
- `app/services/storage.py` - 存储服务
- `app/data/mock_skills.py` - 不少于 10 条 mock 数据

**验收标准**:
- [ ] 模型可通过 Pydantic 验证
- [ ] 存储可读写 JSON 文件
- [ ] mock 数据包含官方/市集/我的三种来源

**错误处理规范**:
- 模型验证失败返回 422，包含具体字段错误
- 文件读写失败返回 500，记录日志

---

### Day 5-6: Skills API

**任务**:
1. 实现 Skills 列表 API（支持筛选、搜索、分页、排序）
2. 实现 Skill 详情 API
3. 统一错误处理

### Day 7: 批量操作 API（新增）

**任务**:
1. 实现批量操作 API
2. 支持多选后的批量操作

**批量操作 API 规范**:

| 端点 | 方法 | 功能 | 请求体 |
|------|------|------|--------|
| `/api/v1/skills/batch/install` | POST | 批量安装 | `{ "ids": ["id1", "id2"] }` |
| `/api/v1/skills/batch/uninstall` | POST | 批量卸载 | `{ "ids": ["id1", "id2"] }` |
| `/api/v1/skills/batch/enable` | POST | 批量启用 | `{ "ids": ["id1", "id2"] }` |
| `/api/v1/skills/batch/disable` | POST | 批量禁用 | `{ "ids": ["id1", "id2"] }` |
| `/api/v1/skills/batch/pin` | POST | 批量钉选 | `{ "ids": ["id1", "id2"] }` |
| `/api/v1/skills/batch/unpin` | POST | 批量取消钉选 | `{ "ids": ["id1", "id2"] }` |

**批量操作响应**:
```json
{
  "success": true,
  "data": {
    "total": 3,
    "succeeded": 2,
    "failed": 1,
    "results": [
      { "id": "id1", "success": true },
      { "id": "id2", "success": true },
      { "id": "id3", "success": false, "error": "NOT_FOUND" }
    ]
  }
}
```

**前端多选交互**:
- 列表项悬停显示复选框
- 顶部工具栏显示 [全选] [取消全选] [批量操作]
- 选中后底部显示浮动操作栏
- 批量操作确认对话框显示影响数量

**API 规范**:

| 端点 | 方法 | 功能 | 参数 |
|------|------|------|------|
| `/api/v1/skills` | GET | 列表 | source, search, page, limit, sort_by, sort_order |
| `/api/v1/skills/{id}` | GET | 详情 | - |

**响应格式**:
```json
{
  "success": true,
  "data": [...],
  "meta": { "page": 1, "limit": 20, "total": 50 }
}
```

**错误响应格式**:
```json
{
  "success": false,
  "error": {
    "code": "SKILL_NOT_FOUND",
    "message": "Skill 不存在",
    "details": "..."
  }
}
```

**错误码规范**:
| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| SKILL_NOT_FOUND | Skill 不存在 | 404 |
| INVALID_SOURCE | 无效的来源参数 | 400 |
| VALIDATION_ERROR | 参数验证失败 | 422 |

**验收标准**:
- [ ] `GET /api/v1/skills` 返回列表
- [ ] 支持 source 筛选（official/marketplace/user/all）
- [ ] 支持 search 关键词搜索
- [ ] 支持分页（page/limit）
- [ ] 支持排序（sort_by/sort_order）
- [ ] `GET /api/v1/skills/{id}` 返回详情
- [ ] 错误返回统一格式（success: false, error: {...}）
- [ ] 批量操作 API 可用
- [ ] 批量操作支持部分成功/失败

---

## Week 2: 对话面板（核心功能）

### Day 1-2: WebSocket 基础

**任务**:
1. 实现 WebSocket 连接管理
2. 设计消息协议（发送/接收/流式）
3. 集成 OpenClaw Gateway 通信

**WebSocket 消息协议**:
```typescript
// 客户端 → 服务端
interface ClientMessage {
  type: 'chat' | 'stop' | 'set_context';
  sessionId: string;
  payload: any;
}

// 服务端 → 客户端
interface ServerMessage {
  type: 'chunk' | 'tool_call' | 'error' | 'done';
  sessionId: string;
  payload: any;
}
```

**交付物**:
- `app/websocket/manager.py` - WebSocket 连接管理
- `app/websocket/handlers.py` - 消息处理器
- `app/services/gateway_client.py` - Gateway 客户端

**验收标准**:
- [ ] WebSocket 连接可建立
- [ ] 支持发送消息并接收流式响应
- [ ] 支持中断生成

**错误处理规范**:
- 连接断开自动重连（最多3次）
- Gateway 不可用时返回 `GATEWAY_UNAVAILABLE` 错误
- 消息格式错误返回 `INVALID_MESSAGE_FORMAT`

---

### Day 3-4: 会话管理 API

**任务**:
1. 实现会话 CRUD API
2. 实现会话历史查询
3. 实现会话切换逻辑

**API 规范**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/chat/sessions` | GET | 获取会话列表 |
| `/api/v1/chat/sessions` | POST | 创建新会话 |
| `/api/v1/chat/sessions/{id}` | GET | 获取会话详情 |
| `/api/v1/chat/sessions/{id}` | PUT | 更新会话（重命名） |
| `/api/v1/chat/sessions/{id}` | DELETE | 删除会话 |
| `/api/v1/chat/sessions/{id}/messages` | GET | 获取会话消息历史 |

**会话数据结构**:
```typescript
interface ChatSession {
  id: string;
  title: string;           // 自动提取前20字
  platform: string;        // ue57/maya2024/comfyui/sd/sp
  agent: string;           // claude/gpt/etc
  language: 'zh' | 'en';
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  pinnedSkills: string[];  // 钉选的 Skills
}
```

**验收标准**:
- [ ] 可创建新会话
- [ ] 可获取会话列表
- [ ] 可切换会话
- [ ] 可删除会话
- [ ] 可查询历史消息

**错误处理规范**:
| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| SESSION_NOT_FOUND | 会话不存在 | 404 |
| SESSION_LIMIT_REACHED | 会话数量达到上限 | 400 |

---

### Day 5-7: 对话上下文管理

**任务**:
1. 实现钉选 Skills 自动注入
2. 实现上下文添加/移除
3. 实现平台/Agent/语言切换

**上下文注入规则**:
- 钉选的 Skills 自动加入系统提示词
- 最多 5 个上下文 Skills
- 按优先级排序

**API 规范**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/chat/sessions/{id}/context` | POST | 添加上下文 Skill |
| `/api/v1/chat/sessions/{id}/context/{skillId}` | DELETE | 移除上下文 Skill |
| `/api/v1/chat/sessions/{id}/platform` | PUT | 切换平台 |
| `/api/v1/chat/sessions/{id}/agent` | PUT | 切换 Agent |
| `/api/v1/chat/sessions/{id}/language` | PUT | 切换语言 |

**验收标准**:
- [ ] 钉选 Skills 自动注入对话上下文
- [ ] 可动态添加/移除上下文
- [ ] 平台切换后连接状态更新
- [ ] Agent 切换后使用新模型
- [ ] 语言切换后界面和 AI 响应语言变化

**错误处理规范**:
| 错误码 | 说明 |
|--------|------|
| CONTEXT_LIMIT_EXCEEDED | 上下文数量超过5个 |
| PLATFORM_NOT_SUPPORTED | 不支持的平台 |
| AGENT_NOT_AVAILABLE | Agent 不可用 |

---

## Week 3: 前端基础

### Day 1-2: 项目初始化

**任务**:
1. 创建 Vite + React + TypeScript 项目
2. 配置 Tailwind CSS
3. 安装依赖（Zustand, React Query, Socket.io-client）

**交付物**:
- 项目目录结构
- `package.json`
- 可运行的前端（显示 "Hello ArtClaw"）

**验收标准**:
- [ ] `npm run dev` 可启动
- [ ] `http://localhost:5173` 可访问
- [ ] Tailwind 样式生效

---

### Day 3-4: 对话面板 UI

**任务**:
1. 实现会话列表侧边栏
2. 实现消息流区域
3. 实现输入区域
4. 实现底部工具栏（平台/Agent/语言切换）

**组件清单**:
- `ChatSidebar` - 会话列表
- `ChatMessageList` - 消息流
- `ChatMessage` - 单条消息（用户/AI）
- `ChatInput` - 输入框
- `ChatToolbar` - 底部工具栏
- `ToolCallCard` - 工具调用卡片
- `ConnectionStatus` - 连接状态指示器

**功能清单**:
- [ ] 会话列表显示（标题、时间）
- [ ] 新建/切换/删除会话
- [ ] 消息气泡（用户右/AI左）
- [ ] 流式输出（打字机效果）
- [ ] 工具调用卡片（可折叠/展开）
- [ ] 附件上传（图片、文件）
- [ ] 快捷输入（常用提示词下拉）
- [ ] 平台切换（UE/Maya/ComfyUI/SD/SP）
- [ ] Agent 切换
- [ ] 中英文切换
- [ ] 连接状态显示（🟢已连接/🟡连接中/🔴已断开）
- [ ] 编辑消息（右键菜单或悬停按钮）
- [ ] 搜索历史/建议（输入时显示历史提示）

**错误处理规范**:
- 发送失败显示 Toast 提示
- 连接断开显示顶部横幅警告
- 文件上传失败显示具体错误信息

---

### Day 5-6: 基础布局 + Skills 列表

**任务**:
1. 实现 Sidebar 导航组件
2. 实现 Header 组件
3. 实现主内容区域布局
4. 配置路由
5. 实现 Skills 列表页面

**导航项**:
- 对话 (/)
- Skills (/skills)
- Workflow 库 (/workflows)
- 工具管理器 (/tools)
- 设置 (/settings)

**Skills 页面元素**:
- 页面标题: "Skills"
- 标签页: 全部 | 官方 | 市集 | 我的
- 搜索框: placeholder "搜索 Skills..."
- 卡片网格: 3 列布局

**卡片内容**:
- 名称
- 描述（2行截断）
- 来源 · 版本 · 评分 · 下载量
- 状态标签（未安装/已安装/有更新/已禁用）
- 操作按钮（运行/安装/更新/卸载/启用/禁用/钉选/收藏/详情/文档）
- 复选框（支持多选批量操作）

**验收标准**:
- [ ] Sidebar 显示所有导航项
- [ ] 点击导航项切换路由
- [ ] 当前项高亮显示
- [ ] 布局响应式（Sidebar 固定宽度，内容区自适应）
- [ ] 页面加载时显示 Skills 列表
- [ ] 标签切换时筛选数据
- [ ] 搜索时过滤数据
- [ ] 卡片展示正确信息
- [ ] 加载状态显示"加载中..."
- [ ] 空状态显示"暂无数据"

---

### Day 7: 集成测试与优化

**任务**:
1. 前后端联调
2. 对话功能端到端测试
3. Skills 列表功能测试
4. 性能优化

**测试清单**:
- [ ] WebSocket 连接稳定性
- [ ] 流式输出流畅度
- [ ] 会话切换无数据残留
- [ ] 页面切换状态保持
- [ ] 大数据量列表滚动性能

---

## 验收标准汇总

### 功能验收
- [ ] 后端服务启动正常
- [ ] API 文档可访问
- [ ] Skills 列表 API 返回正确数据
- [ ] 前端页面可访问
- [ ] **对话面板功能完整**
  - [ ] 会话管理（新建、切换、删除、历史）
  - [ ] 平台切换（UE/Maya/ComfyUI/SD/SP）
  - [ ] Agent 切换
  - [ ] 中英文切换
  - [ ] 连接状态显示
  - [ ] 上下文管理（钉选 Skills 自动注入）
  - [ ] 附件上传（图片、文件）
  - [ ] 快捷输入（常用提示词）
  - [ ] 信息流送（实时显示 AI 思考）
  - [ ] 工具调用显示（折叠/展开）
- [ ] Skills 列表可展示
- [ ] 标签切换有效
- [ ] 搜索功能正常
- [ ] 分页功能正常
- [ ] 批量操作功能正常
- [ ] 编辑消息功能正常

### 代码验收
- [ ] 代码通过 lint 检查
- [ ] 类型检查无错误
- [ ] 代码格式化统一

### 文档验收
- [ ] API 文档完整
- [ ] 代码注释清晰
- [ ] 错误处理规范文档化

---

## 统一规范

### 操作按钮命名

| 功能 | 统一命名 |
|------|----------|
| 执行 Skill/Workflow/Tool | **运行** |
| 安装 | **安装** |
| 更新 | **更新** |
| 卸载 | **卸载** |
| 启用 | **启用** |
| 禁用 | **禁用** |
| 钉选 | **钉选** |
| 取消钉选 | **取消钉选** |
| 收藏 | **收藏** |
| 取消收藏 | **取消收藏** |
| 查看详情 | **详情** |
| 查看文档 | **文档** |

### 状态标签

| 状态 | 标签 | 颜色 |
|------|------|------|
| 未安装 | `[未安装]` | 灰色 #6B7280 |
| 已安装 | `[已安装 ✓]` | 绿色 #10B981 |
| 有更新 | `[有更新 ↑]` | 橙色 #F59E0B |
| 已禁用 | `[已禁用]` | 灰色 #6B7280 |

---

## 风险与应对

| 风险 | 应对 |
|------|------|
| mock 数据不足 | 提前准备 20+ 条数据 |
| API 响应慢 | 添加加载状态，后续优化 |
| 跨域问题 | 配置 CORS |
| WebSocket 稳定性 | 实现自动重连机制 |
| 流式输出卡顿 | 使用虚拟列表，优化渲染 |

---

## 下一步

Phase 2: Skill 管理完整功能（安装/更新/启用/禁用/钉选/收藏）
