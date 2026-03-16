# OpenClaw 集成方案

> **定位**：OpenClaw 是 ArtClaw 面向通用 AI Agent 工作流的核心接入平台之一。相较于 WorkBuddy 偏 IDE 内嵌式协作，OpenClaw 更强调独立客户端、技能编排与后续生态分发能力。本文档定义 OpenClaw 接入 ArtClaw / UE Editor Agent 的目标链路、配置方式、阶段拆解与 features 建设目标，并与《开发路线图.md》的阶段规划保持一一呼应。

---

## 一、在总架构中的位置

```
OpenClaw（独立 AI Agent 客户端）
       │ MCP over stdio / WebSocket
       │
Platform Manager（ArtClaw）
       │ 平台注册 / 路由 / 健康监控
       │
openclaw-mcp-bridge（MCP Server @ per DCC instance）
       │
UEEditorAgent Plugin
       │ 命令队列 → 主线程调度 → 风险确认 → 审计日志
       │
UE Editor API（C++ + Python）
```

OpenClaw 作为 MCP Client，不直接感知 UE 内部线程模型、事务系统或 Slate UI，而是通过 ArtClaw 的桥接层访问标准化的 Tool / Resource / Notification 能力。

---

## 二、集成目标

OpenClaw 集成的目标不是“能连上”这么简单，而是形成一套可扩展、可审计、可分发的 AI ↔ DCC 协作链路：

1. **连接统一**：OpenClaw 通过标准 MCP 配置接入 UE 实例，无需为 UE 写平台特化协议。
2. **能力统一**：所有 UE Skill 仍由 UE 插件侧注册，OpenClaw 通过 `tools/list` 自动发现。
3. **上下文统一**：OpenClaw 通过 `resources/*` 获取编辑器状态，通过通知感知关键变化。
4. **安全统一**：高风险操作必须经过静态预审、事务保护、主线程调度与人工确认。
5. **生态统一**：后续 Skill 包、知识库、团队同步与远程分发优先围绕 OpenClaw 打磨为标准方案。

---

## 三、与 WorkBuddy 的关系

WorkBuddy 与 OpenClaw 属于 ArtClaw 的**平行平台接入**，共享底层桥接和 Skill 体系，但侧重点不同：

| 维度 | WorkBuddy | OpenClaw |
|------|-----------|----------|
| 平台形态 | IDE/工作台集成 | 独立 Agent 客户端 |
| 当前定位 | 第一条验证链路 | 标准化生态接入重点 |
| 连接方式 | stdio / WebSocket | stdio / WebSocket |
| Skill 来源 | UE 插件统一注册 | UE 插件统一注册 |
| 优势 | 调试闭环快 | 轻量、可封装、便于分发 |
| 后续重点 | 验证能力 | 沉淀标准、扩展 features |

结论：**WorkBuddy 负责优先打通，OpenClaw 负责标准沉淀与生态放大。**

---

## 四、连接配置

### 4.1 本地开发期推荐：stdio

```json
{
  "mcpServers": {
    "ue-editor-agent": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server"],
      "env": {
        "PYTHONPATH": "D:/MyProject_D/artclaw/openclaw-mcp-bridge"
      }
    }
  }
}
```

适用场景：
- 本机开发调试
- 单用户单实例验证
- 排查 Skill 注册与参数问题

### 4.2 多实例/远程协同时：WebSocket

```json
{
  "mcpServers": {
    "ue-editor-agent": {
      "type": "websocket",
      "url": "ws://127.0.0.1:7001"
    }
  }
}
```

适用场景：
- 多 DCC 实例共存
- Platform Manager 参与路由
- 团队环境中的统一接入

> 推荐策略：阶段 0~1 优先使用 `stdio`，阶段 2 以后逐步验证 `WebSocket + Platform Manager` 形态。

---

## 五、OpenClaw 侧能力约定

OpenClaw 接入后，应优先消费以下三类能力：

### 5.1 Tools

由 UE 插件暴露、OpenClaw 可直接调用：

- `run_ue_python`
- `focus_on_actor`
- `highlight_actors`
- 后续各类 scene / asset / material / render Skill

### 5.2 Resources

由 UE 状态映射而来，供 OpenClaw 按需读取：

- `unreal://level/selection`
- `unreal://level/actors`
- `unreal://editor/mode`
- `unreal://viewport/camera`
- `unreal://asset/current`
- `unreal://project/preferences`

### 5.3 Notifications

由 UE 关键事件主动推送，避免 OpenClaw 盲目轮询：

- `notifications/skills/reloaded`
- `notifications/editor/mode_changed`
- `notifications/level/loaded`
- `notifications/transaction/committed`
- `notifications/connection/status_changed`

---

## 六、UE / ArtClaw 侧设计要点

### 6.1 Skill Hub 统一注册

OpenClaw 不维护一份独立 Skill 清单，仍以 UE 插件侧注册为唯一事实来源。这样可以确保：

- Skill 元数据只维护一处
- 平台切换不会产生功能漂移
- 统一做参数校验、日志与权限管控

### 6.2 主线程安全执行

OpenClaw 发来的请求先进入命令队列，再由主线程消费执行，避免跨线程直接调用 `unreal` API：

```
OpenClaw → MCP Request → Command Queue → GameThread Execute → Result / Error
```

### 6.3 风险控制链路

对 OpenClaw 发起的写操作统一应用以下保护：

1. **静态预审**：AST 黑名单扫描危险指令。
2. **事务封装**：写操作放入可撤销事务。
3. **主线程执行**：避免线程模型错误导致崩溃。
4. **风险确认**：删除、大范围修改、保存资产等高危行为弹框确认。
5. **日志审计**：记录原始指令、执行代码、影响对象与结果。

### 6.4 上下文最小化输出

OpenClaw 获取编辑器状态时，应返回精简后的结构化 JSON，而非原始 `UObject` 全量属性，以控制 token 成本并减少幻觉。

---

## 七、features 阶段拆解（与《开发路线图》呼应）

以下 features 规划按阶段组织，直接对应 `docs/UE_Editor_Agent/specs/开发路线图.md` 的阶段 0~4。

### Phase 0：接入预设与最小可连通能力

**对应路线图**：阶段 0：环境预设与工程初始化

**阶段目标对齐**：让 OpenClaw 能识别 UE Agent、建立最小链路，并看到基本状态反馈。

**features**：
- `feature/openclaw-config-bootstrap`
  - 提供 OpenClaw 接入示例配置
  - 明确 `stdio` / `WebSocket` 两种模式的最小参数
  - 输出环境检查清单
- `feature/openclaw-connection-status`
  - 将 OpenClaw 连接状态接入 `UUEAgentSubsystem`
  - 驱动工具栏图标颜色变化
  - 提供连接成功/断开日志
- `feature/openclaw-dependency-bootstrap`
  - 补齐 OpenClaw 接入依赖说明
  - 对桥接层 Python 依赖进行最小化安装指引
- `feature/openclaw-log-observability`
  - 打通 OpenClaw 请求 → UE Output Log 的可观察链路
  - 保证请求 ID、时间、执行结果可追踪

**完成标准**：
- OpenClaw 可以成功列出 UE 暴露的基础能力
- UE 插件 UI 可反映连接状态
- 开发者能在日志里追踪一次完整连接过程

---

### Phase 1：执行网关与安全沙盒

**对应路线图**：阶段 1：开放网关与安全沙盒

**阶段目标对齐**：让 OpenClaw 真正能驱动 UE 执行代码，同时具备“能回滚、不易崩、可拦截”的安全底座。

**features**：
- `feature/openclaw-run-ue-python`
  - 暴露 `run_ue_python(code: str)` 为核心入口
  - 返回标准化执行结果 / Traceback
- `feature/openclaw-static-guard`
  - 执行前做 AST 静态预审
  - 拦截系统级危险调用
- `feature/openclaw-undo-transaction-guard`
  - 自动包裹 `ScopedEditorTransaction`
  - 保证 Ctrl+Z 可撤销
- `feature/openclaw-main-thread-dispatch`
  - 所有 UE API 调用切回主线程
  - 避免 WebSocket/异步线程直接触达引擎 API
- `feature/openclaw-context-shortcuts`
  - 注入 `S`、`W`、`L` 等快捷上下文
  - 降低 OpenClaw 代码生成复杂度

**完成标准**：
- OpenClaw 可执行中等复杂度 UE Python 指令
- 脚本报错可被回传并用于二次修复
- 场景修改可撤销，且执行过程中不发生线程崩溃

---

### Phase 2：上下文感知与原生交互闭环

**对应路线图**：阶段 2：感知增强与原生交互

**阶段目标对齐**：让 OpenClaw 从“能执行”升级为“看得见上下文、知道风险、能给用户反馈”。

**features**：
- `feature/openclaw-in-editor-chat-entry`
  - 预留从 UE 内打开 OpenClaw 对话入口的承接位
  - 明确后续嵌入式面板或外部唤起方式
- `feature/openclaw-resource-context-sync`
  - 将选中对象、当前资产、相机位置映射为 MCP Resources
  - 支持 OpenClaw 按需拉取上下文
- `feature/openclaw-risk-confirmation`
  - 高危指令触发 UE 原生确认框
  - 将确认结果反馈给 OpenClaw
- `feature/openclaw-viewport-feedback`
  - 支持执行后自动高亮/聚焦受影响 Actor
  - 提升结果可见性
- `feature/openclaw-editor-mode-filter`
  - 根据材质/蓝图/关卡编辑器上下文动态收缩能力提示
- `feature/openclaw-error-self-healing-loop`
  - 将 Traceback 自动带回 OpenClaw 上下文
  - 支持失败后重试修复

**完成标准**：
- OpenClaw 能读取而非猜测 UE 当前上下文
- 高危操作有可见确认链路
- 执行结果能在视口中被直接感知

---

### Phase 3：知识增强、记忆与适配层

**对应路线图**：阶段 3：自进化 Skill 与 RAG 知识库

**阶段目标对齐**：让 OpenClaw 不只是调用 UE，而是具备“项目知识 + 用户偏好 + 版本意识”的持续进化能力。

**features**：
- `feature/openclaw-skill-hot-reload`
  - Skill 变更后通知 OpenClaw 刷新缓存
  - 缩短技能迭代闭环
- `feature/openclaw-rag-integration`
  - 接入 UE API 文档、项目规范、代码样例索引
  - 为 OpenClaw 提供检索增强上下文
- `feature/openclaw-semantic-prompt-injection`
  - 执行前动态注入语义检索结果
  - 降低 API 幻觉
- `feature/openclaw-tiered-memory-sync`
  - 项目事实、用户偏好、本地记忆结构化存储
  - 必要信息同步到 OpenClaw 可消费的资源或记忆层
- `feature/openclaw-version-adapter`
  - 为 UE 5.3 / 5.4 / 5.5 提供兼容包装
  - 降低 OpenClaw 生成跨版本代码的失败率
- `feature/openclaw-auto-index-pipeline`
  - 支持 Wiki / 规范文档自动向量化

**完成标准**：
- OpenClaw 在生成 UE 脚本前可参考项目知识与正确 API 片段
- 能记住项目偏好与用户习惯
- 面对多 UE 版本时具备基本兼容能力

---

### Phase 4：标准封装、团队分发与生态化

**对应路线图**：阶段 4：分发、优化与生态

**阶段目标对齐**：把 OpenClaw 从“一个可用接入端”升级为“可复制、可部署、可运营”的标准集成方案。

**features**：
- `feature/openclaw-skill-package-standard`
  - 定义面向 OpenClaw 的 Skill 包清单结构
  - 包含 Prompt 增强、MCP 配置、Python 逻辑与说明材料
- `feature/openclaw-audit-and-performance`
  - 记录 OpenClaw 发起的完整执行链路与性能数据
  - 满足团队审计与问题回溯
- `feature/openclaw-team-sync`
  - 团队共享 Skill，隔离个人记忆
  - 支持与 Git 工作流协同
- `feature/openclaw-hub-distribution`
  - 对接 ClawHub 或内部制品库
  - 支持浏览、下载、热更新 Skill 包
- `feature/openclaw-one-click-deploy`
  - 面向非开发岗位的一键部署脚本
  - 自动完成插件安装、配置关联与依赖准备
- `feature/openclaw-health-check`
  - 提供连通性、依赖、延迟、索引完整性诊断

**完成标准**：
- OpenClaw 集成可被打包、共享和复用
- 团队可在不深入理解底层的情况下完成部署与协作
- 系统具备审计、诊断与远程分发能力

---

## 八、分阶段实施建议

| 阶段 | OpenClaw 侧重点 | 预期结果 |
|------|----------------|----------|
| Phase 0 | 配置接入、连接可见 | 能发现 UE Agent，状态可观测 |
| Phase 1 | 代码执行、安全沙盒 | 能安全执行 UE Python |
| Phase 2 | 资源感知、确认交互 | 能理解上下文并与用户形成闭环 |
| Phase 3 | RAG、记忆、版本适配 | 能更稳定地产出项目正确代码 |
| Phase 4 | 分发、审计、部署 | 成为可推广的标准接入方案 |

建议执行顺序：
1. 先复用 WorkBuddy 已验证的 MCP 接入方式，减少 OpenClaw 独立试错。
2. 在 Phase 1 前，不承诺复杂生态能力，优先打磨执行稳定性。
3. 从 Phase 2 起逐步把“资源、通知、确认框、视口反馈”沉淀成平台无关能力。
4. 将真正平台差异收敛到配置、分发和交互入口，而不是 Skill 实现层。

---

## 九、验证清单

- [ ] OpenClaw 能连接 UE Editor Agent
- [ ] `tools/list` 能返回可用 Skill 列表
- [ ] `run_ue_python` 可执行基础与中等复杂度脚本
- [ ] 执行失败时错误信息可回传给 OpenClaw
- [ ] 高风险操作能触发 UE 原生确认
- [ ] 事务写操作可通过 Ctrl+Z 撤销
- [ ] OpenClaw 能读取关键 MCP Resources
- [ ] Skill 热更新后 OpenClaw 能感知变更
- [ ] 审计日志能记录关键执行链路
- [ ] features 拆解与《开发路线图》阶段目标保持一致

---

**版本**：1.0 | **更新**：2026-03-16 | **状态**：新增集成方案草案
