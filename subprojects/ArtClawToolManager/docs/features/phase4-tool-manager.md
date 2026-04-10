# Phase 4: 工具管理器

> 版本: 2.0
> 日期: 2026-04-10
> 工期: 2周
> 依赖: Phase 1-3

---

## 目标

实现用户工具管理和创建功能。

**交付标准**:
- 工具列表管理（官方/市集/我的）
- 工具执行
- Tool Creator Skill（Agent 协助创建）
- 发布到市集功能

---

## Week 1: 工具管理

### Day 1-2: Tool 数据模型 + API

### 后端

**API 规范**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/tools` | GET | 列表 |
| `/api/v1/tools/{id}` | GET | 详情 |
| `/api/v1/tools/{id}/execute` | POST | 执行 |
| `/api/v1/tools` | POST | 创建 |
| `/api/v1/tools/{id}` | PUT | 更新 |
| `/api/v1/tools/{id}` | DELETE | 删除 |
| `/api/v1/tools/{id}/publish` | POST | 发布 |

**Tool 数据模型**:

```json
{
  "id": "user/batch-rename",
  "name": "批量重命名",
  "type": "tool",
  "source": "user",
  "description": "批量重命名选中对象",
  "target_dccs": ["maya2024"],
  "implementation": {
    "type": "skill_wrapper",
    "skill": "maya2024-artclaw-highlight"
  },
  "inputs": [
    {
      "id": "prefix",
      "name": "前缀",
      "type": "string",
      "default": "SM_"
    }
  ],
  "outputs": [
    {
      "id": "renamed_count",
      "name": "重命名数量",
      "type": "number"
    }
  ],
  "stats": {
    "use_count": 12,
    "last_used": "2026-04-10T10:00:00Z"
  }
}
```

**实现类型**:

| 类型 | 说明 |
|------|------|
| skill_wrapper | 包装现有 Skill |
| script | Python/JavaScript 脚本 |
| composite | 组合多个工具 |

**验收标准**:
- [ ] 列表 API 返回正确数据
- [ ] 详情 API 包含 inputs/outputs
- [ ] 创建 API 保存到 user 目录

---

### 前端

**工具卡片统一规范**:

所有工具卡片采用统一布局:
1. 标题行: 图标 + 名称 + 状态标签
2. 分隔线
3. 描述
4. 元信息
5. 操作按钮

**状态标签**:
- `[已安装 ✓]` 绿色
- `[可安装]` 灰色
- `[有更新 ↑]` 橙色

**元信息格式**:
- 官方/市集: `来源 · 版本 · 评分 · 下载量`
- 我的: `目标 · 上次使用 · 使用次数`

**操作按钮**:
- 官方/市集: [安装/打开] [文档/预览] [禁用/详情]
- 我的: [运行] [编辑] [发布] [删除]

**验收标准**:
- [ ] 卡片布局统一
- [ ] 状态标签正确显示
- [ ] 操作按钮根据来源变化

---

### Day 3-4: 工具执行

### 后端

**执行流程**:

1. 接收 inputs 和 context
2. 根据 implementation.type 路由
3. 调用对应 DCC Adapter
4. 返回执行结果

**执行响应**:

```json
{
  "success": true,
  "data": {
    "outputs": {
      "renamed_count": 5
    },
    "execution_id": "exec-123",
    "duration": 1200
  }
}
```

**验收标准**:
- [ ] skill_wrapper 类型可执行
- [ ] 参数正确传递
- [ ] 结果正确返回

---

### 前端

**执行对话框**:

- 标题: 工具名称
- 参数表单（根据 inputs 生成）
- 执行按钮
- 结果展示区域

**验收标准**:
- [ ] 参数表单根据定义生成
- [ ] 执行结果显示
- [ ] 错误信息显示

---

### Day 5-7: 工具创建向导（简化版）

### 设计原则

- 界面仅提供入口和说明
- 创建过程由 Agent 通过对话完成
- 不实现复杂的可视化配置

### 界面设计

**创建工具页面**:

- 标题: "创建新工具"
- 创建方式选择:
  - 📦 包装 Skill
  - 📝 编写脚本
  - 🔗 组合工具
- 创建说明:
  - 点击后唤起 Agent
  - Agent 引导完成创建
- 按钮: [🤖 开始创建 - 唤起 Agent]

### Tool Creator Skill

**Skill 名称**: `artclaw-tool-creator`

**触发方式**:
- 界面点击"开始创建"
- 发送消息给 Agent

**交互流程**:

1. 用户选择创建方式
2. 界面发送消息: "我想创建一个工具，使用 [包装 Skill/编写脚本/组合工具] 方式"
3. Agent 引导用户:
   - 描述功能
   - 定义参数
   - 选择目标 DCC
4. Agent 生成工具定义
5. 用户确认后保存

**验收标准**:
- [ ] 界面可唤起 Agent
- [ ] Agent 可引导创建
- [ ] 创建结果保存正确

---

## Week 2: 发布功能

### Day 1-3: 发布到市集

### 后端

**发布流程**:

1. 验证工具完整性
2. 打包工具文件
3. 上传到市集服务器
4. 返回发布结果

**API**:

```
POST /api/v1/tools/{id}/publish
{
  "version": "1.0.0",
  "changelog": "初始版本"
}
```

**验收标准**:
- [ ] 发布前验证完整
- [ ] 发布后可在市集查看
- [ ] 版本号正确

---

### Day 4-5: 市集审核（可选）

**审核状态**:

- pending: 待审核
- approved: 已通过
- rejected: 已拒绝

**验收标准**:
- [ ] 发布后为 pending 状态
- [ ] 审核通过后显示

---

### Day 6-7: 版本管理

**版本列表**:

- 显示历史版本
- 可回滚到旧版本
- 查看版本变更

**验收标准**:
- [ ] 版本列表可查看
- [ ] 可安装指定版本

---

## 验收标准汇总

### 功能验收
- [ ] 工具列表可展示
- [ ] 工具可执行
- [ ] 工具可创建
- [ ] 工具可发布
- [ ] 卡片布局统一

### 集成验收
- [ ] Tool Creator Skill 可用
- [ ] 与 Agent 集成正常

---

## 下一步

Phase 5: DCC 集成
