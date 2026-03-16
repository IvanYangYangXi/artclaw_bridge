# OpenClaw 集成方案

> **文档定位**：本文件采用 PRD / Checklist 风格，直接服务于 OpenClaw × ArtClaw × UE Editor Agent 的落地实施、阶段验收与 features 管理。

---

## 1. 文档目标

本方案用于明确 OpenClaw 接入 ArtClaw 体系时的：

- 产品定位
- 集成边界
- 配置方式
- 核心能力清单
- 分阶段 features 目标
- 验收标准
- 执行优先级

本文档要求与 `docs/UE_Editor_Agent/specs/开发路线图.md` 保持阶段一致、目标呼应、可直接拆分任务。

---

## 2. 产品定位

### 2.1 目标定义

OpenClaw 是 ArtClaw 面向通用 AI Agent 工作流的标准接入平台之一。

相较于 WorkBuddy：
- WorkBuddy 更偏向 IDE / 工作台内嵌式协作
- OpenClaw 更偏向独立客户端、技能封装、后续生态分发

### 2.2 集成结论

OpenClaw 在本项目中的定位不是“第二个能连上的客户端”，而是：

- **首个优先打通的平台接入样板**
- **标准化方案的第一承载端**
- **后续扩展到其他 AI 平台的基线实现**

### 2.3 与其他平台的关系

| 项 | OpenClaw | 其他平台（如 WorkBuddy） |
|---|---|---|
| 当前优先级 | 第一优先 | 后续扩展 |
| 当前职责 | 先跑通链路并沉淀标准 | 复用 OpenClaw 验证后的标准能力 |
| Skill 来源 | UE 插件统一注册 | UE 插件统一注册 |
| 推荐用途 | 标准交付 / 分发 / 扩展起点 | 平台适配与横向复制 |

**结论**：先直接跑通 OpenClaw，并基于 OpenClaw 做出标准方案，后续再拓展到其他平台。

---

## 3. 集成范围

### 3.1 In Scope

本次 OpenClaw 集成方案覆盖：

- OpenClaw 连接 UE Editor Agent 的配置方式
- OpenClaw 消费 MCP Tools / Resources / Notifications 的方式
- UE / ArtClaw 侧为 OpenClaw 提供的执行、安全、上下文、审计能力
- 与《开发路线图》阶段对应的 features 拆解
- 分阶段验收标准

### 3.2 Out of Scope

当前不在本文档实施范围内：

- 具体某个 UE Skill 的逐个实现细节
- Maya / Max 平台接入细节
- OpenClaw UI 产品设计稿
- 完整企业权限系统实现

---

## 4. 总体链路

```
OpenClaw（独立 AI Agent 客户端）
       │ MCP over stdio / WebSocket
       │
Platform Manager（ArtClaw）
       │ 平台注册 / 路由 / 健康监控
       │
openclaw-mcp-bridge（per DCC instance）
       │
UEEditorAgent Plugin
       │ 命令队列 → 主线程调度 → 风险确认 → 审计日志
       │
UE Editor API（C++ + Python）
```

### 4.1 架构约束

- OpenClaw 只通过 MCP 标准接口接入，不直接耦合 UE 内部实现。
- Skill 注册以 UE 插件侧为唯一事实来源。
- 所有 `unreal` API 调用必须在主线程执行。
- 所有写操作默认纳入安全沙盒与审计体系。

---

## 5. 接入配置要求

### 5.1 Phase 0~1 默认接入方式：stdio

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

**要求**：
- [ ] 本地单机开发优先使用 `stdio`
- [ ] 配置路径明确指向 `openclaw-mcp-bridge`
- [ ] 能稳定执行 `tools/list`

### 5.2 Phase 2+ 可扩展接入方式：WebSocket

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

**要求**：
- [ ] 多实例场景下支持 `WebSocket`
- [ ] Platform Manager 可参与路由
- [ ] 提供基本连接状态与错误诊断

---

## 6. OpenClaw 需消费的能力清单

### 6.1 Tools

必须支持 OpenClaw 调用以下能力：

- `run_ue_python`
- `focus_on_actor`
- `highlight_actors`
- 后续 scene / asset / material / render 等 Skill

**要求**：
- [ ] `tools/list` 能列出工具
- [ ] 参数 Schema 清晰
- [ ] 返回值结构统一
- [ ] 错误信息可读、可回传

### 6.2 Resources

必须支持 OpenClaw 按需读取以下上下文：

- `unreal://level/selection`
- `unreal://level/actors`
- `unreal://editor/mode`
- `unreal://viewport/camera`
- `unreal://asset/current`
- `unreal://project/preferences`

**要求**：
- [ ] 返回结构化 JSON
- [ ] 避免返回原始 `UObject` 全量属性
- [ ] 控制上下文体积，便于模型消费

### 6.3 Notifications

推荐主动推送以下关键事件：

- `notifications/skills/reloaded`
- `notifications/editor/mode_changed`
- `notifications/level/loaded`
- `notifications/transaction/committed`
- `notifications/connection/status_changed`

**要求**：
- [ ] 只推关键事件，避免无意义高频推送
- [ ] 能帮助 OpenClaw 刷新缓存与上下文判断

---

## 7. UE / ArtClaw 侧必备支撑能力

### 7.1 Skill Hub 统一注册

**要求**：
- [ ] OpenClaw 不维护独立 Skill 清单
- [ ] Skill 元数据以 UE 插件侧为唯一事实来源
- [ ] 参数校验、异常格式化、日志记录统一处理

### 7.2 主线程执行保障

执行链路必须满足：

```
OpenClaw → MCP Request → Command Queue → GameThread Execute → Result / Error
```

**要求**：
- [ ] 禁止异步线程直接调用 `unreal` API
- [ ] 所有执行结果可异步回传

### 7.3 风险控制链路

**必须具备**：
- [ ] AST 静态预审
- [ ] 事务保护
- [ ] 主线程调度
- [ ] 高危确认框
- [ ] 审计日志

### 7.4 可观测性

**要求**：
- [ ] OpenClaw 请求进入 UE 后可追踪
- [ ] 关键日志包含请求 ID、执行结果、错误信息
- [ ] 能支持后续性能统计与审计分析

---

## 8. 分阶段 features 目标（对齐《开发路线图》）

---

### Phase 0：接入预设与工程初始化

**路线图对应**：阶段 0：环境预设与工程初始化

**阶段目标**：
让 OpenClaw 能识别 UE Agent、完成最小连接、具备连接可见性和基础日志能力。

**features 清单**：

#### `feature/openclaw-config-bootstrap`
- [ ] 提供 OpenClaw 接入示例配置
- [ ] 区分 `stdio` / `WebSocket` 两种最小配置
- [ ] 输出环境检查清单

#### `feature/openclaw-connection-status`
- [ ] OpenClaw 连接状态接入 `UUEAgentSubsystem`
- [ ] 工具栏图标状态联动
- [ ] 输出连接成功 / 断开日志

#### `feature/openclaw-dependency-bootstrap`
- [ ] 明确 OpenClaw 接入依赖
- [ ] 补充桥接层依赖安装指引

#### `feature/openclaw-log-observability`
- [ ] 打通 OpenClaw 请求到 UE Output Log 的链路
- [ ] 记录请求 ID / 时间 / 结果

**阶段验收标准**：
- [ ] OpenClaw 可发现 UE Agent
- [ ] `tools/list` 可返回基础能力
- [ ] UE 插件 UI 能反映连接状态
- [ ] 日志可追踪一次完整连接过程

---

### Phase 1：执行网关与安全沙盒

**路线图对应**：阶段 1：开放网关与安全沙盒

**阶段目标**：
让 OpenClaw 能安全驱动 UE 执行 Python，具备错误回传、回滚与稳定执行能力。

**features 清单**：

#### `feature/openclaw-run-ue-python`
- [ ] 暴露 `run_ue_python(code: str)`
- [ ] 返回标准化执行结果
- [ ] 返回可读 Traceback

#### `feature/openclaw-static-guard`
- [ ] 执行前做 AST 静态预审
- [ ] 拦截危险调用

#### `feature/openclaw-undo-transaction-guard`
- [ ] 自动包裹 `ScopedEditorTransaction`
- [ ] 支持 Ctrl+Z 撤销

#### `feature/openclaw-main-thread-dispatch`
- [ ] 所有 UE API 调用回到主线程
- [ ] 消除线程错误导致的引擎崩溃风险

#### `feature/openclaw-context-shortcuts`
- [ ] 注入 `S` / `W` / `L` 等快捷上下文
- [ ] 降低代码生成复杂度

**阶段验收标准**：
- [ ] OpenClaw 可执行中等复杂度 UE Python 指令
- [ ] 执行失败能返回错误给 OpenClaw
- [ ] 可撤销场景修改
- [ ] 执行过程不发生线程崩溃

---

### Phase 2：感知增强与原生交互闭环

**路线图对应**：阶段 2：感知增强与原生交互

**阶段目标**：
让 OpenClaw 从“能执行”升级为“有上下文、可确认、有结果反馈”的闭环协作状态。

**features 清单**：

#### `feature/openclaw-in-editor-chat-entry`
- [ ] 预留 UE 内 OpenClaw 对话入口
- [ ] 明确嵌入式或外部唤起方案

#### `feature/openclaw-resource-context-sync`
- [ ] 选中对象映射为 MCP Resource
- [ ] 当前资产映射为 MCP Resource
- [ ] 相机位置映射为 MCP Resource

#### `feature/openclaw-risk-confirmation`
- [ ] 高危指令触发 UE 原生确认框
- [ ] 确认结果反馈给 OpenClaw

#### `feature/openclaw-viewport-feedback`
- [ ] 执行后自动高亮受影响 Actor
- [ ] 支持自动聚焦目标区域

#### `feature/openclaw-editor-mode-filter`
- [ ] 根据当前编辑器模式调整上下文提示

#### `feature/openclaw-error-self-healing-loop`
- [ ] 将 Traceback 自动回传为后续上下文
- [ ] 支持失败后修复重试

**阶段验收标准**：
- [ ] OpenClaw 能主动读取 UE 上下文
- [ ] 高危操作有确认链路
- [ ] 执行结果可在视口中直接感知

---

### Phase 3：知识增强、记忆与版本适配

**路线图对应**：阶段 3：自进化 Skill 与 RAG 知识库

**阶段目标**：
让 OpenClaw 具备项目知识、用户偏好与版本兼容意识，提升一次性成功率。

**features 清单**：

#### `feature/openclaw-skill-hot-reload`
- [ ] Skill 变更后通知 OpenClaw 刷新缓存

#### `feature/openclaw-rag-integration`
- [ ] 接入 UE API 文档索引
- [ ] 接入项目规范索引
- [ ] 接入代码样例索引

#### `feature/openclaw-semantic-prompt-injection`
- [ ] 执行前动态注入检索上下文
- [ ] 降低 API 幻觉

#### `feature/openclaw-tiered-memory-sync`
- [ ] 结构化存储项目事实
- [ ] 结构化存储用户偏好
- [ ] 与 OpenClaw 侧记忆能力建立同步关系

#### `feature/openclaw-version-adapter`
- [ ] 提供 UE 5.3 / 5.4 / 5.5 兼容包装

#### `feature/openclaw-auto-index-pipeline`
- [ ] 支持 Wiki / 规范文档自动向量化

**阶段验收标准**：
- [ ] OpenClaw 生成脚本前能参考项目知识
- [ ] 能记住项目偏好与用户习惯
- [ ] 多 UE 版本下具备基础兼容性

---

### Phase 4：标准封装、分发与生态化

**路线图对应**：阶段 4：分发、优化与生态

**阶段目标**：
把 OpenClaw 集成沉淀为可部署、可共享、可审计、可分发的标准方案。

**features 清单**：

#### `feature/openclaw-skill-package-standard`
- [ ] 定义面向 OpenClaw 的 Skill 包标准
- [ ] 包含 Prompt 增强、MCP 配置、Python 逻辑、说明材料

#### `feature/openclaw-audit-and-performance`
- [ ] 记录完整执行链路
- [ ] 记录性能与审计信息

#### `feature/openclaw-team-sync`
- [ ] 团队共享 Skill
- [ ] 个人记忆与团队资产隔离
- [ ] 兼容 Git 工作流

#### `feature/openclaw-hub-distribution`
- [ ] 对接 ClawHub 或内部制品库
- [ ] 支持浏览 / 下载 / 热更新 Skill 包

#### `feature/openclaw-one-click-deploy`
- [ ] 提供一键部署脚本
- [ ] 自动完成插件安装、配置关联、依赖准备

#### `feature/openclaw-health-check`
- [ ] 提供连通性诊断
- [ ] 提供依赖与索引完整性诊断
- [ ] 提供延迟与环境问题诊断

**阶段验收标准**：
- [ ] OpenClaw 集成可标准化打包
- [ ] 团队可复用部署
- [ ] 具备审计、诊断与远程分发能力

---

## 9. 阶段优先级建议

### 9.1 执行优先级

1. **P0：Phase 0 + Phase 1**
   - 先解决可接入、可执行、可回滚、可追踪
2. **P1：Phase 2**
   - 建立上下文与用户确认闭环
3. **P2：Phase 3**
   - 增加知识增强与记忆能力
4. **P3：Phase 4**
   - 做标准封装、分发和生态能力

### 9.2 策略要求

- [ ] 先以 OpenClaw 作为第一落地平台完成全链路验证
- [ ] 在 Phase 1 完成前，不承诺复杂生态能力
- [ ] 从 Phase 2 起把资源、通知、确认框、反馈做成平台无关能力
- [ ] 后续平台扩展优先复用 OpenClaw 已验证的标准能力
- [ ] 平台差异尽量收敛到配置、分发、交互入口层

---

## 10. 总体验收清单

### 10.1 基础连通
- [ ] OpenClaw 能连接 UE Editor Agent
- [ ] `tools/list` 能返回可用 Skill 列表

### 10.2 执行能力
- [ ] `run_ue_python` 可执行基础与中等复杂度脚本
- [ ] 执行失败时错误信息可回传给 OpenClaw
- [ ] 事务写操作可通过 Ctrl+Z 撤销

### 10.3 交互与安全
- [ ] 高风险操作能触发 UE 原生确认
- [ ] OpenClaw 能读取关键 MCP Resources
- [ ] 执行结果可在 UE 中得到可见反馈

### 10.4 持续演进
- [ ] Skill 热更新后 OpenClaw 能感知变更
- [ ] 审计日志能记录关键执行链路
- [ ] features 拆解与《开发路线图》阶段目标保持一致

---

## 11. 文档结论

OpenClaw 集成不应被视为单纯的平台适配，而应作为 ArtClaw 的首个标准化产品能力推进：

- 前期由 OpenClaw 先打通整条链路
- 中期由 OpenClaw 承接 features 标准化与上下文闭环
- 后期基于 OpenClaw 已验证能力扩展到其他平台

因此，OpenClaw 相关实现应优先围绕“可配置、可执行、可确认、可审计、可分发”五个关键词推进。

---

**版本**：1.2 | **更新**：2026-03-16 | **状态**：PRD / Checklist 版