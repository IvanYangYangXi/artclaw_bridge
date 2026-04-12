# Phase 4: 工具管理器 — 总览

> 版本: 2.0
> 日期: 2026-04-10
> 状态: 待开发

---

## 目标

实现完整的工具管理器功能，包括工具列表管理、AI 协助运行、Tool Creator、版本管理、发布。

## 工期

10 个工作日（2 周）

```
Week 1:
├── Day 1-2: 工具列表管理界面
├── Day 3-4: AI 协助运行流程 + artclaw_sdk 基础模块
└── Day 5: Tool Creator Skill 框架

Week 2:
├── Day 6-7: Tool Creator 完整交互
├── Day 8: 版本管理 + 触发规则管理（Web 端 UI + API）
├── Day 9: 发布到市集（功能入口，评分/评论预留）
└── Day 10: 批量操作 + 错误处理 + 测试
```

## 子文档

| 文档 | 内容 | 对应工作日 |
|------|------|-----------|
| [phase4-tool-list.md](./phase4-tool-list.md) | 工具列表管理 + AI 协助运行 + 批量操作 | Day 1-4, 10 |
| [phase4-tool-creator.md](./phase4-tool-creator.md) | Tool Creator Skill 设计 + 交互协议 | Day 5-7 |
| [phase4-tool-version.md](./phase4-tool-version.md) | 版本管理 + 发布到市集 | Day 8-9 |
| [phase4-tool-api.md](./phase4-tool-api.md) | API 设计 + 数据模型 + 错误处理 | 贯穿全程 |

## 触发机制开发计划

详见 [trigger-mechanism.md](../specs/trigger-mechanism.md)

| 内容 | 开发阶段 | 说明 |
|------|----------|------|
| 触发规则数据模型 | **Phase 4 Day 8** | TriggerRule / FilterConfig / ParameterPreset |
| 触发规则 CRUD API | **Phase 4 Day 8** | REST API + 前端管理界面 |
| 条件筛选配置 UI | **Phase 4 Day 8** | 路径/命名/类型/属性 筛选器 |
| 参数预设管理 | **Phase 4 Day 8** | 预设 CRUD + 快速切换 |
| 筛选预设管理 | **Phase 4 Day 8** | 全局筛选预设 CRUD |
| artclaw_sdk 核心 | **Phase 4 Day 3-4** | context/filters/params/result/progress |
| manifest.json 规范 | **Phase 4 Day 5** | 含 triggers/presets 字段 |
| DCCEventManager | **Phase 5 Week 2** | DCC 端事件注册和回调 |
| FilterEvaluator | **Phase 5 Week 2** | DCC 端条件筛选评估 |
| ScheduleManager | **Phase 5 Week 2** | 定时/周期调度器 |
| pre 事件拦截 | **Phase 5 Week 2** | 事件前拦截+阻止机制 |
| FileWatcher | **Phase 5 Week 3** | 文件/目录监听 |

## 核心概念

**Tool（工具）**: 用户创建的可复用功能单元。

**三种创建方式**:
1. **包装 Skill**: 将现有 Skill 包装为带参数的工具
2. **编写脚本**: 用 Python + artclaw_sdk 编写自定义逻辑
3. **组合工具**: 将多个工具串联成工作流

**运行方式**: 点击[运行] → 跳转对话面板 → AI 协助填参 → 运行（详见 [phase3-workflow-library.md](./phase3-workflow-library.md)）

**触发机制**: 手动/事件/定时/文件监听（详见 [trigger-mechanism.md](../specs/trigger-mechanism.md)）

**manifest.json**: 一个文件包含全部元信息（详见 [trigger-mechanism.md#8](../specs/trigger-mechanism.md)）

## 与 Workflow 的关系

| 特性 | Workflow | Tool |
|------|----------|------|
| 适用范围 | ComfyUI 专用 | 所有 DCC 通用 |
| 运行方式 | AI 协助 | AI 协助（同 Workflow） |
| 创建方式 | 导入/编辑 | Agent 协助创建 |
| 存储格式 | ComfyUI JSON | manifest.json + 脚本 |

## 参考文档

- **架构**: [architecture-design.md](../specs/architecture-design.md)
- **UI 设计**: [ui-design.md](../ui/ui-design.md)
- **触发机制**: [trigger-mechanism.md](../specs/trigger-mechanism.md)
- **AI 协助运行**: [phase3-workflow-library.md](./phase3-workflow-library.md)（共用流程）
- **artclaw_sdk**: [trigger-mechanism.md#9](../specs/trigger-mechanism.md)
