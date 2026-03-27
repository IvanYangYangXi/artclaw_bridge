# UE 插件 UI 交互功能清单

## ~~1. Agent 切换器（已移除）~~

**状态**: 已移除

> OpenClaw Gateway 的 connect protocol 不支持 `agentId` 字段，且 cli client 的 binding 规则总是路由到默认 agent。无法在插件内实现 agent 切换。

---

## ~~2. MCP 工具时序自修复（已移除）~~

**状态**: 已移除

> 依赖 agent 切换的 reconnect 机制，随 agent 切换功能一起移除。

---

## 3. 管理面板 Agent 选择器（管理面板内）

**状态**: 已完成基础框架

### 需求
- 管理面板顶部显示当前 Agent + 可用 Agent 列表
- 切换后同功能 1 的行为

---

## 4. Skill/MCP 管理面板

**状态**: Phase 2-5 已完成

### 已实现
- Skill Tab: 列表/启用禁用/钉选/层级筛选/详情弹窗
- MCP Tab: 服务器状态/工具列表
- 管理面板入口: Dashboard 底部工具栏 [管理] 按钮

---

## 变更记录

| 日期 | 功能 | 状态 |
|------|------|------|
| 2026-03-27 | Skill/MCP 管理面板 Phase 2-5 | 已完成 |
| 2026-03-27 | Agent 切换器 | 已移除（Gateway 不支持） |
| 2026-03-27 | MCP 时序自修复 | 已移除 |
