# Phase 2: Skill 管理

> 版本: 2.1
> 日期: 2026-04-10
> 工期: 1周
> 依赖: Phase 1

---

## 参考文档

- **架构设计**: [architecture-design.md](../specs/architecture-design.md)
- **UI 设计**: [ui-design.md](../ui/ui-design.md)
- **API 设计**: [api-design.md](../api/api-design.md)
- **Skill 管理体系**: [SKILL_DEVELOPMENT_GUIDE.md](../../../../docs/skills/SKILL_DEVELOPMENT_GUIDE.md)
- **OpenClaw Gateway**: [gateway-forwarding-roadmap.md](../../../../docs/features/gateway-forwarding-roadmap.md)

---

## 目标

实现完整的 Skill 生命周期管理，与现有 `skill_hub` 体系兼容。

**交付标准**:
- Skill 可安装/更新/卸载
- Skill 可启用/禁用/钉选/收藏
- 配置同步到 `~/.artclaw/config.json`
- 最近使用记录（仅执行时）
- 批量操作支持（多选安装/卸载/启用/禁用）

---

## 与现有系统的兼容

### 现有配置格式

`~/.artclaw/config.json`:
```json
{
  "disabled_skills": ["skill-id-1"],
  "pinned_skills": ["skill-id-2"],
  "favorites": {
    "skills": ["skill-id-3"]
  },
  "recent": {
    "skills": [
      {"id": "skill-id-1", "used_at": "2026-04-10T10:00:00Z"}
    ]
  }
}
```

### 兼容要求

1. 读取现有配置
2. 修改后保存回原文件
3. 不破坏其他配置项

---

## 状态流转

### 状态流转图

```
                    ┌─────────────┐
         ┌─────────►│  未安装     │◄────────┐
         │          │ not_installed│         │
         │          └──────┬──────┘         │
      卸载│                 │ 安装            │更新失败
         │                 ▼                │
         │          ┌─────────────┐         │
         └──────────┤   已安装    │─────────┘
                    │  installed  │
                    └──────┬──────┘
                           │ 检测到新版本
                           ▼
                    ┌─────────────┐
                    │  有更新     │
                    │update_available│
                    └──────┬──────┘
                           │ 更新
                           └──────────────► (回到已安装)

┌─────────────────────────────────────────────────────────────┐
│                     【禁用状态】正交维度                       │
│                                                              │
│   禁用是独立状态，与安装状态正交：                              │
│   - 任何安装状态（已安装/有更新）都可被禁用                      │
│   - 禁用后 Skill 在列表中显示为灰色，不可运行                    │
│   - 禁用后仍可卸载、更新、取消钉选                              │
│                                                              │
│   状态组合矩阵：                                               │
│   ┌──────────────┬────────────┬──────────────┐               │
│   │              │  未禁用     │    已禁用     │               │
│   ├──────────────┼────────────┼──────────────┤               │
│   │ 未安装       │ 正常显示    │   N/A        │               │
│   │ 已安装       │ 可运行      │ 灰色，不可运行 │               │
│   │ 有更新       │ 可更新运行  │ 灰色，可更新   │               │
│   └──────────────┴────────────┴──────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### 各状态下的可用操作

| 状态组合 | 主按钮 | 次按钮 | 更多菜单 |
|---------|--------|--------|----------|
| 未安装 + 未禁用 | [安装] | [文档] | - |
| 已安装 + 未禁用 | [运行] | [文档] | [禁用] [钉选/取消钉选] [收藏/取消收藏] |
| 有更新 + 未禁用 | [更新] [运行] | [文档] | [禁用] [钉选/取消钉选] [收藏/取消收藏] |
| 已安装 + 已禁用 | [启用] | [文档] | [卸载] [取消钉选] |
| 有更新 + 已禁用 | [启用] [更新] | [文档] | [卸载] [取消钉选] |

---

## 钉选 vs 收藏

### 概念区分

| 维度 | 钉选 (Pin) | 收藏 (Favorite) |
|------|------------|-----------------|
| **功能** | 快捷访问 | 标记喜欢 |
| **影响** | 影响排序，显示在上下文 | 筛选标签 |
| **显示位置** | 对话面板上下文栏、列表顶部 | 收藏标签页 |
| **数量限制** | 最多 5 个 | 无限制 |
| **图标** | 📌 | ⭐ |
| **使用场景** | 高频使用的 Skill | 感兴趣/常用的 Skill |

### 钉选行为

- 钉选的 Skill 自动出现在对话面板的上下文栏
- 钉选 Skill 在列表中置顶显示
- 钉选数量达到上限时，新钉选需先取消旧钉选
- 卸载钉选的 Skill 时自动取消钉选

### 收藏行为

- 收藏的 Skill 可在"我的"标签页筛选查看
- 收藏状态不影响 Skill 的执行和排序
- 收藏是轻量级标记，无数量限制

---

## 最近使用记录

### 记录时机

**仅在实际执行 Skill 时记录**:
- ✅ 用户点击 [运行] 按钮执行 Skill
- ✅ 通过 API 调用执行 Skill
- ✅ 对话中 Agent 执行 Skill

**不记录**:
- ❌ 浏览/打开 Skill 详情页
- ❌ 查看 Skill 文档
- ❌ 安装/更新/卸载操作

### 记录格式

```json
{
  "recent": {
    "skills": [
      {"id": "skill-id-1", "used_at": "2026-04-10T10:00:00Z"},
      {"id": "skill-id-2", "used_at": "2026-04-10T09:30:00Z"}
    ]
  }
}
```

### 存储策略

- 最多保存 20 条记录
- 按时间倒序排列
- 同一 Skill 重复执行时，更新 `used_at` 并移到最前
- 超过 20 条时，删除最旧的记录

---

## 与 skill_hub 集成

### skill_hub 能力

现有 `skill_hub` 提供以下能力：
- `skill_hub.install(skill_id, source)` - 安装 Skill
- `skill_hub.update(skill_id)` - 更新 Skill
- `skill_hub.uninstall(skill_id)` - 卸载 Skill
- `skill_hub.list_installed()` - 列出已安装 Skills
- `skill_hub.get_skill_info(skill_id)` - 获取 Skill 信息

### 集成方式

Tool Manager 后端通过调用 `skill_hub` API 实现安装/更新/卸载：

```python
# 伪代码示例
from artclaw import skill_hub

class SkillService:
    def install(self, skill_id: str, source: str):
        # 调用 skill_hub 安装
        result = skill_hub.install(skill_id, source)
        # 更新本地状态缓存
        self._update_status(skill_id, 'installed')
        return result
    
    def update(self, skill_id: str):
        # 调用 skill_hub 更新
        result = skill_hub.update(skill_id)
        # 更新本地状态缓存
        self._update_status(skill_id, 'installed')
        return result
    
    def uninstall(self, skill_id: str):
        # 调用 skill_hub 卸载
        result = skill_hub.uninstall(skill_id)
        # 清理相关配置（钉选、禁用等）
        self._cleanup_config(skill_id)
        return result
```

### 避免功能重复

| 功能 | 责任方 | 说明 |
|------|--------|------|
| Skill 安装/更新/卸载 | skill_hub | Tool Manager 仅作为调用方 |
| Skill 启用/禁用 | Tool Manager | 修改 config.json |
| Skill 钉选/收藏 | Tool Manager | 修改 config.json |
| 最近使用记录 | Tool Manager | 修改 config.json |
| Skill 元数据管理 | Tool Manager | 本地缓存和展示 |

---

## 错误处理

### 安装失败处理

| 错误类型 | 错误码 | 用户提示 | 重试策略 |
|----------|--------|----------|----------|
| 网络连接失败 | NETWORK_ERROR | "网络连接失败，请检查网络后重试" | 可重试，最多3次 |
| 下载超时 | TIMEOUT_ERROR | "下载超时，请稍后重试" | 可重试，最多3次 |
| 磁盘空间不足 | DISK_FULL | "磁盘空间不足，请清理后重试" | 不可重试 |
| Skill 已存在 | ALREADY_INSTALLED | "该 Skill 已安装" | 不可重试 |
| 依赖缺失 | DEPENDENCY_MISSING | "缺少依赖: {dep_name}" | 提示用户手动安装 |
| 权限不足 | PERMISSION_DENIED | "权限不足，请检查目录权限" | 不可重试 |

### 配置同步失败处理

```python
# 配置写入失败时的处理策略
def save_config_with_retry(config):
    max_retries = 3
    for i in range(max_retries):
        try:
            atomic_write(CONFIG_PATH, config)
            return True
        except IOError as e:
            if i < max_retries - 1:
                time.sleep(0.1 * (i + 1))  # 指数退避
            else:
                # 最终失败，记录日志并提示用户
                logger.error(f"Config save failed: {e}")
                raise ConfigSyncError("配置保存失败，请检查磁盘权限")
```

### 网络错误处理

| 场景 | 处理方式 |
|------|----------|
| 请求超时 | 显示重试按钮，自动重试3次 |
| 连接断开 | 显示离线状态，自动重连 |
| API 返回 5xx | 提示服务暂时不可用，建议稍后重试 |
| API 返回 4xx | 根据具体错误码提示用户 |

### 错误提示规范

- **Toast 提示**: 操作成功/失败的即时反馈
- **对话框**: 需要用户决策的错误（如卸载确认）
- **状态标签**: 卡片上显示当前状态（如"安装失败"）
- **日志**: 详细错误信息记录到日志文件

---

## Day 1-2: 安装/更新/卸载

### 后端

**新增 API**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/skills/{id}/install` | POST | 安装 |
| `/api/v1/skills/{id}/update` | POST | 更新 |
| `/api/v1/skills/{id}/uninstall` | POST | 卸载 |

**行为定义**:

- **安装**:
  - 检查是否已安装，已安装返回 409 (ALREADY_INSTALLED)
  - 调用 `skill_hub.install(skill_id, source)`
  - 返回安装路径和版本
  - 错误时返回具体错误码

- **更新**:
  - 检查是否已安装，未安装返回 400 (NOT_INSTALLED)
  - 调用 `skill_hub.update(skill_id)`
  - 保留原有钉选/禁用状态
  - 返回新版本号

- **卸载**:
  - 检查是否已安装，未安装返回 400 (NOT_INSTALLED)
  - 调用 `skill_hub.uninstall(skill_id)`
  - 自动从钉选列表移除
  - 保留最近使用记录（仅作历史参考）
  - 返回成功消息

**验收标准**:
- [ ] 安装后目录存在
- [ ] 安装后状态变为 installed
- [ ] 更新后版本号变更
- [ ] 卸载后目录删除
- [ ] 卸载后状态变为 not_installed
- [ ] 安装失败时返回具体错误码

---

### 前端

**统一操作按钮命名**:

| 功能 | 按钮文本 |
|------|----------|
| 执行 | **运行** |
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

**卡片操作按钮**（根据状态显示）:

- `not_installed`: [安装] [文档]
- `installed` + 未禁用: [运行] [文档] [更多▼]
- `update_available` + 未禁用: [更新] [运行] [文档] [更多▼]
- `installed`/`update_available` + 已禁用: [启用] [文档] [更多▼]

**更多菜单内容**:
- 未钉选: [钉选] [收藏] [禁用] [卸载]
- 已钉选: [取消钉选] [收藏] [禁用] [卸载]
- 已收藏: [钉选/取消钉选] [取消收藏] [禁用] [卸载]

**交互**:
- 点击安装/更新/卸载后显示 loading
- 操作成功后刷新列表
- 卸载前确认对话框
- 错误时显示 Toast 提示

**验收标准**:
- [ ] 按钮根据状态正确显示
- [ ] 操作后列表刷新
- [ ] loading 状态正常
- [ ] 确认对话框正常
- [ ] 错误提示清晰

---

## Day 3: 启用/禁用/钉选/收藏

### 后端

**新增 API**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/skills/{id}/enable` | POST | 启用 |
| `/api/v1/skills/{id}/disable` | POST | 禁用 |
| `/api/v1/skills/{id}/pin` | POST | 钉选 |
| `/api/v1/skills/{id}/unpin` | POST | 取消钉选 |
| `/api/v1/skills/{id}/favorite` | POST | 收藏 |
| `/api/v1/skills/{id}/unfavorite` | POST | 取消收藏 |

**配置变更**:

- 启用/禁用: 修改 `disabled_skills` 列表
- 钉选/取消: 修改 `pinned_skills` 列表
- 收藏/取消: 修改 `favorites.skills` 列表
- 保存回原配置文件（带重试机制）

**Skill 列表响应增加字段**:
```json
{
  "status": "installed",
  "disabled": false,
  "pinned": true,
  "favorited": false
}
```

**验收标准**:
- [ ] 禁用后 `disabled` 变为 true
- [ ] 钉选后 `pinned` 变为 true
- [ ] 收藏后 `favorited` 变为 true
- [ ] 配置文件中列表更新
- [ ] 不破坏其他配置项
- [ ] 配置写入失败时有重试和提示

---

### 前端

**操作菜单**:

卡片右上角更多按钮，点击展开菜单:
- 已钉选: [取消钉选]
- 未钉选: [钉选]
- 已收藏: [取消收藏]
- 未收藏: [收藏]
- 已禁用: [启用]
- 未禁用: [禁用]
- [卸载] (已安装时)

**钉选标识**:

钉选的 Skill 在卡片上显示 📌 图标

**收藏按钮**:

卡片上显示 ⭐ 图标，已收藏为实心黄色，未收藏为空心灰色

**收藏筛选**:

Skills 页面新增 "收藏" 标签，点击显示收藏的 Skills

**验收标准**:
- [ ] 菜单可展开/收起
- [ ] 操作后状态更新
- [ ] 钉选图标正确显示
- [ ] 收藏图标状态正确
- [ ] 收藏标签可筛选

---

## Day 4-5: 最近使用

### 后端

**新增 API**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/skills/recent` | GET | 获取最近使用列表 |
| `/api/v1/skills/{id}/record-usage` | POST | 记录使用（内部调用） |

**记录时机**:

仅在实际执行 Skill 时记录:
- 用户点击 [运行] 按钮
- 通过 `/api/v1/skills/{id}/run` API 调用
- 对话中 Agent 执行 Skill（通过同一 API）

**不记录**:
- 浏览/打开 Skill 详情页
- 查看 Skill 文档
- 安装/更新/卸载操作

**存储格式**:
```json
{
  "recent": {
    "skills": [
      {"id": "skill-id-1", "used_at": "2026-04-10T10:00:00Z"}
    ]
  }
}
```

**验收标准**:
- [ ] 运行后记录到 recent
- [ ] 最近使用按时间倒序
- [ ] 最近使用最多 20 条
- [ ] 打开详情不记录

---

### 前端

**最近使用展示**:

总览页面显示最近使用的 Skills（最多 5 个）

```
┌────────────────────────────────────────────────────────────────┐
│  最近使用                                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 🎯 txt2img│ │ 🎨 img2img│ │ 🔧 节点安装│ │ ...      │          │
│  │ 2分钟前   │ │ 1小时前   │ │ 昨天      │ │          │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└────────────────────────────────────────────────────────────────┘
```

**验收标准**:
- [ ] 总览显示最近使用
- [ ] 显示相对时间（2分钟前、1小时前、昨天）

---

## Day 6-7: 搜索和筛选优化

### 新增筛选条件

**API 参数扩展**:

| 参数 | 类型 | 说明 |
|------|------|------|
| target_dcc | string | 筛选目标 DCC |
| status | string | 筛选状态 |
| favorited | boolean | 筛选收藏 |

**前端筛选组件**:

- DCC 筛选下拉框: 全部 | ComfyUI | Maya | UE | SD | SP
- 状态筛选下拉框: 全部 | 已安装 | 未安装 | 有更新 | 已禁用
- 收藏筛选: 复选框 "仅显示收藏"

**验收标准**:
- [ ] DCC 筛选有效
- [ ] 状态筛选有效
- [ ] 收藏筛选有效
- [ ] 多个筛选条件可组合

---

## 验收标准汇总

### 功能验收
- [ ] Skill 可安装/更新/卸载
- [ ] 安装后状态正确更新
- [ ] 启用/禁用功能正常
- [ ] 钉选/取消钉选功能正常
- [ ] 收藏/取消收藏功能正常
- [ ] 钉选和收藏概念区分清晰
- [ ] 最近使用记录正确（仅执行时）
- [ ] 配置同步到 `~/.artclaw/config.json`

### 状态流转验收
- [ ] 状态流转图正确实现
- [ ] 各状态下的可用操作正确
- [ ] 禁用状态与安装状态正交

### 错误处理验收
- [ ] 安装失败有明确错误提示
- [ ] 配置同步失败有重试机制
- [ ] 网络错误有恢复策略

### 兼容性验收
- [ ] 与现有 `skill_hub` 兼容
- [ ] 配置格式与现有系统一致
- [ ] 不破坏其他配置项
- [ ] 调用 skill_hub 安装/更新能力，无功能重复

---

## 下一步

Phase 3: 工具管理器 + Tool Creator
