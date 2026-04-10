# ArtClaw Tool Manager - 开发路线图

> 版本: 4.0
> 日期: 2026-04-10

---

## 开发原则

1. **文档先行**: 每个 Phase 开始前完成详细设计文档
2. **确定性**: 文档明确交付标准和验收条件，不产生歧义
3. **渐进交付**: 每个 Phase 产出可运行的版本
4. **快速验证**: 完成核心功能后立即测试

---

## 文档结构

```
docs/
├── specs/                          # 架构设计文档
│   ├── architecture-design.md      # 整体架构
│   ├── ui-design.md                # UI 设计规范
│   ├── api-design.md               # API 规范
│   └── data-models.md              # 数据模型
├── features/                       # Phase 详细文档
│   ├── phase0-technical-research.md    # 技术预研
│   ├── phase1-foundation.md            # 基础框架 + 对话面板
│   ├── phase2-skill-management.md      # Skill 管理
│   ├── phase3-workflow-library.md      # Workflow 库（AI协助执行）
│   ├── phase4-tool-manager.md          # 工具管理器（AI协助执行）
│   ├── phase5-dcc-integration.md       # DCC 集成
│   └── phase6-marketplace.md           # 市集功能（可选）
└── ROADMAP.md                      # 本文件
```

---

## Phase 0: 技术预研（3-5天）

**目标**: 验证关键技术方案，降低后续风险

**任务**:
1. 验证 DCC 通信方案（WebSocket/HTTP）
2. 验证 OpenClaw Gateway 集成方案
3. 验证对话面板技术方案
4. 确定数据存储方案（JSON/SQLite）

**交付标准**:
- [ ] 技术验证报告
- [ ] 关键技术 POC 代码
- [ ] 风险评估和应对方案

---

## Phase 1: 基础框架 + 对话面板（3周）

**目标**: 搭建可运行的基础框架，实现核心对话功能

**核心设计**: Workflow/Tool 执行都通过对话面板，由 AI 协助完成

**交付标准**:
- [ ] 后端服务可启动，API 文档可访问
- [ ] 前端可运行，基础布局完成
- [ ] **对话面板功能完整**
  - [ ] 会话管理（新建、切换、删除、历史）
  - [ ] DCC 软件切换（UE/Maya/ComfyUI/SD/SP）
  - [ ] Agent 平台切换（OpenClaw/LobsterAI等）
  - [ ] Agent 切换（当前平台下的Agent）
  - [ ] 中英文切换
  - [ ] 连接状态显示
  - [ ] 上下文管理（钉选 Skills）
  - [ ] 附件上传
  - [ ] 快捷输入
  - [ ] 信息流送
  - [ ] 工具调用显示
  - [ ] **右侧面板参数表单**（Workflow/Tool执行时显示）
- [ ] Skills 列表展示（基础）
- [ ] 支持官方/市集/我的标签切换
- [ ] 支持搜索和分页
- [ ] 批量操作支持

**文档**:
- [x] architecture-design.md
- [x] ui-design.md
- [x] api-design.md
- [ ] phase1-foundation.md（需详细化）

---

## Phase 2: Skill 管理完整功能（1周）

**目标**: 完整的 Skill 生命周期管理

**交付标准**:
- [ ] Skill 可安装/更新/卸载
- [ ] Skill 可启用/禁用/钉选
- [ ] 配置同步到 `~/.artclaw/config.json`
- [ ] 收藏和最近使用记录
- [ ] **统一操作按钮命名**（运行/安装/更新/卸载/启用/禁用/钉选/收藏）
- [ ] **状态流转清晰**（未安装→已安装→有更新，禁用独立状态）
- [ ] 批量操作（多选安装/卸载/启用/禁用）

**文档**:
- [ ] phase2-skill-management.md（需详细化）

---

## Phase 3: Workflow 库（ComfyUI）（1周）

**目标**: ComfyUI Workflow 模板管理和 AI 协助执行

**核心设计**: 
- 点击 [运行] 跳转对话面板
- AI 协助填写参数
- 右侧面板显示参数表单
- 执行进度和结果在消息流中显示

**交付标准**:
- [ ] Workflow 浏览/安装/收藏
- [ ] 预览图展示
- [ ] **AI 协助执行流程**
  - [ ] 点击 [运行] 跳转对话面板
  - [ ] 自动发送执行请求给 AI
  - [ ] 右侧面板显示参数表单
  - [ ] 支持手动填写和 AI 协助填写
  - [ ] 执行进度在消息流中显示
  - [ ] 执行结果（图片/错误）在消息流中显示
- [ ] 版本管理（沿用 Skill 逻辑）

**说明**: Workflow 是 ComfyUI 专属功能

**文档**:
- [ ] phase3-workflow-library.md（需详细化）

---

## Phase 4: 工具管理器 + Tool Creator（2周）

**目标**: 用户工具管理和创建

**核心设计**:
- 工具执行同样采用 AI 协助模式
- Tool Creator 由 Agent 协助完成

**交付标准**:
- [ ] 工具列表管理（全部/官方/市集/我的）
- [ ] **AI 协助执行流程**（同 Workflow）
- [ ] **Tool Creator Skill 完整交互流程**
  - [ ] 创建方式选择（包装 Skill/编写脚本/组合工具）
  - [ ] Agent 引导对话流程
  - [ ] 工具定义生成和保存
- [ ] 发布到市集功能
- [ ] 版本管理（沿用 Skill 逻辑）
- [ ] 批量操作（多选删除/发布）

**文档**:
- [ ] phase4-tool-manager.md（需详细化）

---

## Phase 5: DCC 集成（2-3周）

**目标**: DCC 内嵌快捷面板，与 Web 管理器联动

**交付标准**:
- [ ] UE Slate 面板
- [ ] Maya Qt 面板
- [ ] ComfyUI 按钮扩展
- [ ] 快捷操作面板
- [ ] **与 Web 对话面板功能不重叠**
  - DCC 面板：快捷入口、最近使用
  - Web 面板：完整对话、工具管理
- [ ] DCC 插件分发机制
- [ ] 上下文传递与联动

**说明**: 工期增加（原1周→2-3周），3个DCC面板工作量较大

**文档**:
- [ ] phase5-dcc-integration.md（需详细化）

---

## Phase 6: 市集功能（可选，1-2周）

**目标**: 市集基础设施

**说明**: 当前为本地文件存储，本 Phase 实现远程市集 API

**交付标准**:
- [ ] 远程市集 API 对接
- [ ] 评分/评论系统
- [ ] 版本管理（远程）
- [ ] 创作者收益统计

**文档**:
- [ ] phase6-marketplace.md

---

## 当前状态

**准备开始 Phase 0**

需先完成技术预研，验证关键方案可行性。

---

## 优先级调整说明

### 调整原因

1. **对话面板是大需求**: 需要会话管理、平台切换、Agent切换等完整功能
2. **Workflow/Tool 执行模式变更**: 改为 AI 协助模式，通过对话面板执行
3. **概念模型需明确**: Skill/Workflow/Tool 关系需清晰定义
4. **Phase 5 工期不足**: 3个DCC面板1周无法完成

### 调整内容

| 原顺序 | 新顺序 | 调整原因 |
|--------|--------|----------|
| Phase 1: 2周 | Phase 1: 3周 | 增加对话面板 |
| Phase 3: 工具管理器 | Phase 4: 工具管理器 | 后置 |
| Phase 4: Workflow | Phase 3: Workflow | 前置，与工具管理器并行开发执行逻辑 |
| Phase 5: 1周 | Phase 5: 2-3周 | 增加工期 |
| - | Phase 0: 3-5天 | 新增技术预研 |
| - | Phase 6: 1-2周 | 新增市集功能（可选） |

---

## 关键问题修复清单

### P0（已解决）

- [x] **概念模型混乱**: Skill/Workflow/Tool 定义已明确
- [x] **操作按钮命名不一致**: 统一为"运行/安装/更新/卸载/启用/禁用/钉选/收藏/详情/文档"
- [x] **状态流转不清晰**: Phase 2 文档已细化
- [x] **Tool Creator 设计不完整**: Phase 4 文档已细化交互流程
- [x] **Phase 5 工期不足**: 已调整为 2-3 周
- [x] **批量操作缺失**: Phase 1/2/4 已添加批量操作设计
- [x] **Workflow 进度更新机制**: Phase 3 已细化 WebSocket + 轮询降级方案
- [x] **Workflow/Tool 执行逻辑**: 已改为 AI 协助模式

### P1（待解决）

- [ ] **市集基础设施**: 当前为本地文件存储，Phase 6 实现远程市集

---

## 参考文档

- **架构设计**: [architecture-design.md](./specs/architecture-design.md)
- **UI 设计**: [ui-design.md](./ui/ui-design.md)
- **API 设计**: [api-design.md](./api/api-design.md)

---

## 更新记录

### v4.0 (2026-04-10)
- Workflow/Tool 执行逻辑改为 AI 协助模式
- Phase 3 和 Phase 4 顺序调整（Workflow 前置）
- 新增 Phase 6 市集功能
- 更新关键问题修复清单

### v3.0 (2026-04-10)
- 新增 Phase 0 技术预研
- Phase 1 增加对话面板（工期 2周→3周）
- Phase 3 和 Phase 4 交换顺序
- Phase 5 工期调整（1周→2-3周）

### v2.0 (2026-04-10)
- 增加文档结构说明
- 明确各 Phase 交付标准

### v1.0 (2026-04-10)
- 初始版本
