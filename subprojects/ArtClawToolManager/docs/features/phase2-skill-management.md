# Phase 2: Skill 管理完整功能

> 版本: 1.0
> 日期: 2026-04-10
> 工期: 1周（5个工作日）

---

## 目录

1. [概述](#1-概述)
2. [开发任务分解](#2-开发任务分解)
3. [状态流转设计](#3-状态流转设计)
4. [与 skill_hub 集成](#4-与-skill_hub-集成)
5. [错误处理方案](#5-错误处理方案)
6. [测试计划](#6-测试计划)
7. [代码示例](#7-代码示例)

---

## 1. 概述

### 1.1 目标

实现完整的 Skill 生命周期管理功能，包括安装、更新、卸载、启用、禁用、钉选、收藏等操作，以及配置同步和最近使用记录。

### 1.2 范围

- Skill 安装/更新/卸载（含事务机制）
- Skill 启用/禁用/钉选/收藏
- 配置同步（config.json）
- 最近使用记录
- 批量操作实现
- 统一操作按钮命名

### 1.3 交付物

| 交付物 | 说明 |
|--------|------|
| Skill 管理后端 API | 完整的 REST API |
| Skill 管理前端页面 | 列表/详情/操作界面 |
| 配置同步模块 | config.json 读写 |
| 最近使用记录模块 | 使用历史追踪 |
| 批量操作组件 | 多选批量处理 |
| 单元测试 | 核心逻辑测试 |
| 集成测试 | API 端到端测试 |

---

## 2. 开发任务分解

### Day 1: 后端基础架构

#### 任务 2.1.1: Skill 服务层设计

**交付物**: `src/server/services/skill_service.py`

**验收标准**:
- [ ] SkillService 类实现
- [ ] 支持 CRUD 操作
- [ ] 支持状态查询
- [ ] 单元测试覆盖 > 80%

**代码结构**:
```python
class SkillService:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.skill_hub = SkillHubClient()
    
    async def list_skills(self, filters: SkillFilter) -> List[Skill]:
        """获取 Skill 列表"""
        pass
    
    async def install_skill(self, skill_id: str, version: str = None) -> OperationResult:
        """安装 Skill"""
        pass
    
    async def update_skill(self, skill_id: str) -> OperationResult:
        """更新 Skill"""
        pass
    
    async def uninstall_skill(self, skill_id: str) -> OperationResult:
        """卸载 Skill"""
        pass
    
    async def toggle_enabled(self, skill_id: str, enabled: bool) -> OperationResult:
        """启用/禁用 Skill"""
        pass
    
    async def toggle_pinned(self, skill_id: str, pinned: bool) -> OperationResult:
        """钉选/取消钉选 Skill"""
        pass
    
    async def toggle_favorite(self, skill_id: str, favorited: bool) -> OperationResult:
        """收藏/取消收藏 Skill"""
        pass
```

**工时**: 4h

---

#### 任务 2.1.2: 配置管理器实现

**交付物**: `src/server/services/config_manager.py`

**验收标准**:
- [ ] ConfigManager 类实现
- [ ] 支持 `~/.artclaw/config.json` 读写
- [ ] 文件锁机制防止并发写入
- [ ] 配置变更事件通知
- [ ] 单元测试覆盖 > 80%

**配置结构**:
```json
{
  "version": "1.0",
  "skills": {
    "pinned": ["official/comfyui-txt2img", "official/ue5-material"],
    "disabled": ["marketplace/some-skill"],
    "favorites": ["official/comfyui-txt2img"],
    "installed": {
      "official/comfyui-txt2img": {
        "version": "1.2.0",
        "installed_at": "2026-04-10T10:00:00Z",
        "updated_at": "2026-04-10T10:00:00Z",
        "source": "official"
      }
    }
  },
  "recent": {
    "skills": [
      {"id": "official/comfyui-txt2img", "used_at": "2026-04-10T10:00:00Z"}
    ]
  }
}
```

**工时**: 4h

---

### Day 2: 事务机制与安装流程

#### 任务 2.2.1: 事务管理器

**交付物**: `src/server/services/transaction_manager.py`

**验收标准**:
- [ ] TransactionManager 类实现
- [ ] 支持事务开始/提交/回滚
- [ ] 支持操作日志记录
- [ ] 失败自动回滚机制
- [ ] 单元测试覆盖 > 80%

**事务流程**:
```
开始事务
  │
  ├── 下载 Skill 文件
  │
  ├── 验证文件完整性
  │
  ├── 备份现有版本（更新时）
  │
  ├── 安装/更新文件
  │
  ├── 更新配置
  │
  └── 提交事务
       │
       └── 成功: 清理备份
       │
       └── 失败: 回滚到备份
```

**工时**: 4h

---

#### 任务 2.2.2: Skill 安装/更新/卸载实现

**交付物**: `src/server/services/skill_operations.py`

**验收标准**:
- [ ] 安装流程实现（含事务）
- [ ] 更新流程实现（含事务）
- [ ] 卸载流程实现（含事务）
- [ ] 版本检测逻辑
- [ ] 依赖检查逻辑
- [ ] 单元测试覆盖 > 80%

**安装流程详细步骤**:
```python
async def install_skill(self, skill_id: str, version: str = None) -> OperationResult:
    tx = self.transaction_manager.begin()
    try:
        # 1. 检查是否已安装
        if self.is_installed(skill_id):
            return OperationResult.fail("Skill already installed")
        
        # 2. 获取 Skill 元数据
        metadata = await self.skill_hub.get_skill_metadata(skill_id, version)
        
        # 3. 检查依赖
        for dep in metadata.dependencies:
            if not self.is_installed(dep):
                return OperationResult.fail(f"Dependency {dep} not installed")
        
        # 4. 下载 Skill
        download_path = await self.skill_hub.download_skill(skill_id, version)
        tx.add_file(download_path)
        
        # 5. 验证文件
        if not self.verify_skill_package(download_path):
            return OperationResult.fail("Invalid skill package")
        
        # 6. 解压安装
        install_path = self.get_install_path(skill_id)
        await self.extract_skill(download_path, install_path)
        tx.add_operation("install", install_path)
        
        # 7. 更新配置
        self.config_manager.add_installed_skill(skill_id, metadata)
        
        # 8. 提交事务
        tx.commit()
        
        return OperationResult.success()
        
    except Exception as e:
        tx.rollback()
        return OperationResult.fail(str(e))
```

**工时**: 4h

---

### Day 3: API 层与前端组件

#### 任务 2.3.1: REST API 实现

**交付物**: `src/server/api/skills.py`

**验收标准**:
- [ ] GET /api/skills - 列表查询
- [ ] POST /api/skills/{id}/install - 安装
- [ ] POST /api/skills/{id}/update - 更新
- [ ] POST /api/skills/{id}/uninstall - 卸载
- [ ] POST /api/skills/{id}/enable - 启用
- [ ] POST /api/skills/{id}/disable - 禁用
- [ ] POST /api/skills/{id}/pin - 钉选
- [ ] POST /api/skills/{id}/unpin - 取消钉选
- [ ] POST /api/skills/{id}/favorite - 收藏
- [ ] POST /api/skills/{id}/unfavorite - 取消收藏
- [ ] POST /api/skills/batch - 批量操作
- [ ] API 文档更新
- [ ] 集成测试覆盖

**API 规范**:
```yaml
/api/skills:
  get:
    parameters:
      - name: source
        in: query
        enum: [all, official, marketplace, user]
      - name: status
        in: query
        enum: [all, installed, not_installed, update_available, disabled]
      - name: search
        in: query
      - name: sort
        in: query
        enum: [name, installed_at, updated_at, use_count]
      - name: pinned_first
        in: query
        type: boolean
    responses:
      200:
        schema:
          type: object
          properties:
            items:
              type: array
              items: Skill
            total: integer
            page: integer
            page_size: integer

/api/skills/{id}/install:
  post:
    requestBody:
      schema:
        type: object
        properties:
          version:
            type: string
    responses:
      200:
        schema: OperationResult
      409:
        description: Already installed
      422:
        description: Dependency missing

/api/skills/batch:
  post:
    requestBody:
      schema:
        type: object
        properties:
          operation:
            enum: [install, uninstall, enable, disable, pin, unpin]
          skill_ids:
            type: array
            items: string
```

**工时**: 4h

---

#### 任务 2.3.2: 前端 Skill 列表组件

**交付物**: `src/web/pages/Skills/SkillList.tsx`

**验收标准**:
- [ ] Skill 列表展示
- [ ] 标签切换（全部/官方/市集/我的）
- [ ] 搜索功能
- [ ] 排序功能
- [ ] 分页功能
- [ ] 钉选项置顶显示
- [ ] 单元测试覆盖 > 70%

**组件结构**:
```typescript
interface SkillListProps {
  source: 'all' | 'official' | 'marketplace' | 'user';
  searchQuery?: string;
  sortBy?: 'name' | 'installed_at' | 'updated_at' | 'use_count';
  pinnedFirst?: boolean;
}

const SkillList: React.FC<SkillListProps> = ({
  source,
  searchQuery,
  sortBy = 'name',
  pinnedFirst = true
}) => {
  // 实现...
};
```

**工时**: 4h

---

### Day 4: 操作按钮与批量操作

#### 任务 2.4.1: 统一操作按钮组件

**交付物**: `src/web/components/SkillActionButtons.tsx`

**验收标准**:
- [ ] 统一按钮命名规范实现
- [ ] 根据状态动态显示按钮
- [ ] 操作确认对话框
- [ ] 操作进度显示
- [ ] 操作结果提示
- [ ] 单元测试覆盖 > 80%

**按钮命名规范**:
```typescript
const ACTION_LABELS = {
  run: '运行',
  install: '安装',
  update: '更新',
  uninstall: '卸载',
  enable: '启用',
  disable: '禁用',
  pin: '钉选',
  unpin: '取消钉选',
  favorite: '收藏',
  unfavorite: '取消收藏',
  detail: '详情',
  docs: '文档'
} as const;
```

**按钮状态映射**:
```typescript
interface SkillActions {
  // 根据状态决定显示哪些按钮
  getVisibleActions(skill: Skill): ActionType[] {
    const actions: ActionType[] = [];
    
    switch (skill.status) {
      case 'not_installed':
        actions.push('install', 'detail');
        break;
      case 'installed':
        actions.push('run', 'update', 'uninstall', 'disable');
        if (!skill.runtimeStatus?.pinned) actions.push('pin');
        if (!skill.runtimeStatus?.favorited) actions.push('favorite');
        break;
      case 'update_available':
        actions.push('run', 'update', 'uninstall', 'disable');
        break;
      case 'disabled':
        actions.push('enable', 'uninstall');
        break;
    }
    
    if (skill.runtimeStatus?.pinned) actions.push('unpin');
    if (skill.runtimeStatus?.favorited) actions.push('unfavorite');
    
    return actions;
  }
}
```

**工时**: 4h

---

#### 任务 2.4.2: 批量操作组件

**交付物**: `src/web/components/BatchOperationBar.tsx`

**验收标准**:
- [ ] 多选复选框实现
- [ ] 批量操作栏显示
- [ ] 批量安装/卸载/启用/禁用/钉选
- [ ] 批量操作进度显示
- [ ] 部分失败处理
- [ ] 单元测试覆盖 > 70%

**批量操作流程**:
```typescript
interface BatchOperation {
  operation: 'install' | 'uninstall' | 'enable' | 'disable' | 'pin' | 'unpin';
  skillIds: string[];
}

async function executeBatchOperation(batch: BatchOperation): Promise<BatchResult> {
  const results: OperationResult[] = [];
  const progress = new BatchProgress(batch.skillIds.length);
  
  for (const skillId of batch.skillIds) {
    try {
      const result = await executeSingleOperation(batch.operation, skillId);
      results.push({ skillId, success: result.success, error: result.error });
    } catch (e) {
      results.push({ skillId, success: false, error: e.message });
    }
    progress.increment();
  }
  
  return {
    total: batch.skillIds.length,
    success: results.filter(r => r.success).length,
    failed: results.filter(r => !r.success).length,
    details: results
  };
}
```

**工时**: 4h

---

### Day 5: 最近使用与集成测试

#### 任务 2.5.1: 最近使用记录模块

**交付物**: `src/server/services/recent_usage_service.py`

**验收标准**:
- [ ] 使用记录写入
- [ ] 最近使用列表查询
- [ ] 自动清理旧记录（保留最近 50 条）
- [ ] 前端最近使用展示
- [ ] 单元测试覆盖 > 80%

**实现**:
```python
class RecentUsageService:
    MAX_RECENT_ITEMS = 50
    
    def record_usage(self, skill_id: str):
        """记录 Skill 使用"""
        recent = self.config_manager.get('recent.skills', [])
        
        # 移除已存在的相同记录
        recent = [r for r in recent if r['id'] != skill_id]
        
        # 添加到开头
        recent.insert(0, {
            'id': skill_id,
            'used_at': datetime.utcnow().isoformat()
        })
        
        # 限制数量
        recent = recent[:self.MAX_RECENT_ITEMS]
        
        self.config_manager.set('recent.skills', recent)
    
    def get_recent_skills(self, limit: int = 10) -> List[RecentSkill]:
        """获取最近使用的 Skills"""
        recent = self.config_manager.get('recent.skills', [])
        skill_ids = [r['id'] for r in recent[:limit]]
        
        # 获取完整 Skill 信息
        skills = self.skill_service.get_skills_by_ids(skill_ids)
        
        # 按最近使用顺序排序
        skill_map = {s.id: s for s in skills}
        return [skill_map[id] for id in skill_ids if id in skill_map]
```

**工时**: 3h

---

#### 任务 2.5.2: 集成测试与文档完善

**交付物**: 
- `tests/integration/test_skills_api.py`
- 本文档完善

**验收标准**:
- [ ] API 端到端测试
- [ ] 事务回滚测试
- [ ] 并发操作测试
- [ ] 性能测试（列表查询 < 200ms）
- [ ] 文档更新完成

**测试用例**:
```python
class TestSkillOperations:
    async def test_install_skill_success(self):
        """测试成功安装 Skill"""
        response = await client.post('/api/skills/official/test-skill/install')
        assert response.status_code == 200
        assert response.json()['success'] is True
        
        # 验证文件已安装
        assert skill_exists('official/test-skill')
        
        # 验证配置已更新
        config = load_config()
        assert 'official/test-skill' in config['skills']['installed']
    
    async def test_install_skill_rollback(self):
        """测试安装失败回滚"""
        # 模拟安装过程中失败
        with mock.patch('extract_skill', side_effect=Exception('Extract failed')):
            response = await client.post('/api/skills/official/test-skill/install')
            assert response.status_code == 500
            
        # 验证文件已清理
        assert not skill_exists('official/test-skill')
        
        # 验证配置未更新
        config = load_config()
        assert 'official/test-skill' not in config['skills']['installed']
    
    async def test_batch_operations(self):
        """测试批量操作"""
        response = await client.post('/api/skills/batch', json={
            'operation': 'install',
            'skill_ids': ['official/skill1', 'official/skill2']
        })
        
        result = response.json()
        assert result['total'] == 2
        assert result['success'] == 2
        assert result['failed'] == 0
```

**工时**: 5h

---

## 3. 状态流转设计

### 3.1 状态流转图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Skill 状态流转图                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐                                                        │
│   │   未安装    │                                                        │
│   │ not_installed│◄─────────────────────────────────────────────┐        │
│   └──────┬──────┘                                              │        │
│          │ 安装                                                 │        │
│          ▼                                                     │        │
│   ┌─────────────┐     检测到新版本      ┌─────────────┐         │        │
│   │   已安装    │──────────────────────►│   有更新    │         │        │
│   │  installed  │◄──────────────────────│update_avail │         │        │
│   └──────┬──────┘     更新              └──────┬──────┘         │        │
│          │                                      │               │        │
│          │ 禁用                                 │ 更新          │        │
│          ▼                                      │               │        │
│   ┌─────────────┐                               │               │        │
│   │   已禁用    │                               │               │        │
│   │  disabled   │◄──────────────────────────────┘               │        │
│   └──────┬──────┘                                              │        │
│          │ 启用                                                 │        │
│          │                                                     │        │
│          │ 卸载                                                 │        │
│          └─────────────────────────────────────────────────────┘        │
│                                                                          │
│   注: 禁用是独立状态，与安装状态正交                                      │
│       已禁用的工具仍可卸载                                               │
│       更新时保留禁用状态                                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 运行时状态

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Skill 运行时状态（正交）                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   安装状态 (status)          运行时状态 (runtimeStatus)                  │
│   ─────────────────          ─────────────────────────                   │
│   • not_installed            • enabled: boolean                          │
│   • installed                • pinned: boolean                           │
│   • update_available         • favorited: boolean                        │
│   • disabled                                                             │
│                                                                          │
│   组合示例:                                                              │
│   • installed + enabled + pinned + favorited                            │
│   • installed + disabled                                                │
│   • update_available + enabled + pinned                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 状态流转代码实现

```python
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, List

class InstallStatus(Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    DISABLED = "disabled"

@dataclass
class RuntimeStatus:
    enabled: bool = True
    pinned: bool = False
    favorited: bool = False

class SkillStateMachine:
    """Skill 状态机"""
    
    # 有效状态流转
    VALID_TRANSITIONS = {
        InstallStatus.NOT_INSTALLED: {
            'install': InstallStatus.INSTALLED
        },
        InstallStatus.INSTALLED: {
            'uninstall': InstallStatus.NOT_INSTALLED,
            'disable': InstallStatus.DISABLED,
            'detect_update': InstallStatus.UPDATE_AVAILABLE
        },
        InstallStatus.UPDATE_AVAILABLE: {
            'update': InstallStatus.INSTALLED,
            'uninstall': InstallStatus.NOT_INSTALLED,
            'disable': InstallStatus.DISABLED
        },
        InstallStatus.DISABLED: {
            'enable': InstallStatus.INSTALLED,
            'uninstall': InstallStatus.NOT_INSTALLED
        }
    }
    
    def __init__(self, status: InstallStatus = InstallStatus.NOT_INSTALLED):
        self._status = status
        self._runtime = RuntimeStatus()
    
    @property
    def status(self) -> InstallStatus:
        return self._status
    
    @property
    def runtime_status(self) -> RuntimeStatus:
        return self._runtime
    
    def can_transition(self, action: str) -> bool:
        """检查是否可以执行状态流转"""
        return action in self.VALID_TRANSITIONS.get(self._status, {})
    
    def transition(self, action: str) -> bool:
        """执行状态流转"""
        if not self.can_transition(action):
            return False
        
        self._status = self.VALID_TRANSITIONS[self._status][action]
        return True
    
    def toggle_enabled(self) -> bool:
        """切换启用状态"""
        if self._status == InstallStatus.DISABLED:
            return self.transition('enable')
        elif self._status == InstallStatus.INSTALLED:
            return self.transition('disable')
        return False
    
    def toggle_pinned(self) -> bool:
        """切换钉选状态"""
        if self._status in (InstallStatus.INSTALLED, InstallStatus.UPDATE_AVAILABLE):
            self._runtime.pinned = not self._runtime.pinned
            return True
        return False
    
    def toggle_favorite(self) -> bool:
        """切换收藏状态"""
        self._runtime.favorited = not self._runtime.favorited
        return True
```

---

## 4. 与 skill_hub 集成

### 4.1 集成架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Skill 管理器与 skill_hub 集成                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────────┐          ┌──────────────────┐                    │
│   │  Skill Manager   │          │    skill_hub     │                    │
│   │   (本系统)        │◄────────►│  (远程服务)       │                    │
│   └────────┬─────────┘   HTTP   └──────────────────┘                    │
│            │                                                            │
│   ┌────────▼─────────┐                                                  │
│   │  SkillHubClient  │                                                  │
│   │  - 元数据获取     │                                                  │
│   │  - 文件下载       │                                                  │
│   │  - 版本检查       │                                                  │
│   │  - 搜索查询       │                                                  │
│   └──────────────────┘                                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 SkillHubClient 实现

```python
import aiohttp
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class SkillMetadata:
    id: str
    name: str
    version: str
    description: str
    source: str
    dependencies: List[str]
    download_url: str
    checksum: str
    size: int

class SkillHubClient:
    """skill_hub 客户端"""
    
    def __init__(self, base_url: str = "https://api.artclaw.io"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_skills(
        self,
        query: str = "",
        source: Optional[str] = None,
        sort: str = "name",
        page: int = 1,
        page_size: int = 20
    ) -> SearchResult:
        """搜索 Skills"""
        params = {
            'q': query,
            'sort': sort,
            'page': page,
            'page_size': page_size
        }
        if source:
            params['source'] = source
        
        async with self.session.get(
            f"{self.base_url}/v1/skills",
            params=params
        ) as response:
            data = await response.json()
            return SearchResult(
                items=[SkillMetadata(**item) for item in data['items']],
                total=data['total'],
                page=data['page'],
                page_size=data['page_size']
            )
    
    async def get_skill_metadata(
        self,
        skill_id: str,
        version: Optional[str] = None
    ) -> SkillMetadata:
        """获取 Skill 元数据"""
        params = {}
        if version:
            params['version'] = version
        
        async with self.session.get(
            f"{self.base_url}/v1/skills/{skill_id}",
            params=params
        ) as response:
            data = await response.json()
            return SkillMetadata(**data)
    
    async def download_skill(
        self,
        skill_id: str,
        version: Optional[str] = None,
        target_path: Optional[str] = None
    ) -> str:
        """下载 Skill 文件"""
        metadata = await self.get_skill_metadata(skill_id, version)
        
        target_path = target_path or f"/tmp/{skill_id.replace('/', '_')}.zip"
        
        async with self.session.get(metadata.download_url) as response:
            with open(target_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
        
        # 验证校验和
        if not self._verify_checksum(target_path, metadata.checksum):
            raise ValueError("Downloaded file checksum mismatch")
        
        return target_path
    
    async def check_updates(
        self,
        installed_skills: List[InstalledSkill]
    ) -> List[UpdateInfo]:
        """检查更新"""
        skill_ids = [s.id for s in installed_skills]
        
        async with self.session.post(
            f"{self.base_url}/v1/skills/check-updates",
            json={'skill_ids': skill_ids}
        ) as response:
            data = await response.json()
            return [
                UpdateInfo(
                    skill_id=item['skill_id'],
                    current_version=item['current_version'],
                    latest_version=item['latest_version']
                )
                for item in data['updates']
            ]
    
    def _verify_checksum(self, file_path: str, expected_checksum: str) -> bool:
        """验证文件校验和"""
        import hashlib
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest() == expected_checksum
```

### 4.3 本地缓存策略

```python
import json
import os
from datetime import datetime, timedelta
from typing import Optional

class SkillMetadataCache:
    """Skill 元数据本地缓存"""
    
    CACHE_TTL = timedelta(hours=1)
    CACHE_DIR = "~/.artclaw/cache/skills"
    
    def __init__(self):
        self.cache_dir = os.path.expanduser(self.CACHE_DIR)
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_cache_path(self, skill_id: str) -> str:
        """获取缓存文件路径"""
        safe_id = skill_id.replace('/', '_')
        return os.path.join(self.cache_dir, f"{safe_id}.json")
    
    def get(self, skill_id: str) -> Optional[SkillMetadata]:
        """从缓存获取"""
        cache_path = self._get_cache_path(skill_id)
        
        if not os.path.exists(cache_path):
            return None
        
        # 检查是否过期
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - mtime > self.CACHE_TTL:
            os.remove(cache_path)
            return None
        
        with open(cache_path, 'r') as f:
            data = json.load(f)
            return SkillMetadata(**data)
    
    def set(self, skill_id: str, metadata: SkillMetadata):
        """写入缓存"""
        cache_path = self._get_cache_path(skill_id)
        
        with open(cache_path, 'w') as f:
            json.dump(metadata.__dict__, f, indent=2)
    
    def invalidate(self, skill_id: str):
        """使缓存失效"""
        cache_path = self._get_cache_path(skill_id)
        if os.path.exists(cache_path):
            os.remove(cache_path)
    
    def clear(self):
        """清空缓存"""
        for f in os.listdir(self.cache_dir):
            os.remove(os.path.join(self.cache_dir, f))
```

---

## 5. 错误处理方案

### 5.1 错误分类

```python
from enum import Enum
from typing import Optional, Dict

class ErrorCategory(Enum):
    """错误分类"""
    NETWORK = "network"           # 网络错误
    FILE_SYSTEM = "file_system"   # 文件系统错误
    VALIDATION = "validation"     # 验证错误
    DEPENDENCY = "dependency"     # 依赖错误
    PERMISSION = "permission"     # 权限错误
    UNKNOWN = "unknown"           # 未知错误

class SkillOperationError(Exception):
    """Skill 操作错误基类"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        skill_id: Optional[str] = None,
        recoverable: bool = False,
        retry_after: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        super().__init__(message)
        self.category = category
        self.skill_id = skill_id
        self.recoverable = recoverable
        self.retry_after = retry_after
        self.details = details or {}
    
    def to_dict(self) -> Dict:
        return {
            'error': True,
            'message': str(self),
            'category': self.category.value,
            'skill_id': self.skill_id,
            'recoverable': self.recoverable,
            'retry_after': self.retry_after,
            'details': self.details
        }

# 具体错误类型
class NetworkError(SkillOperationError):
    """网络错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.NETWORK, recoverable=True, **kwargs)

class FileSystemError(SkillOperationError):
    """文件系统错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.FILE_SYSTEM, recoverable=False, **kwargs)

class ValidationError(SkillOperationError):
    """验证错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.VALIDATION, recoverable=False, **kwargs)

class DependencyError(SkillOperationError):
    """依赖错误"""
    def __init__(self, message: str, missing_deps: list, **kwargs):
        super().__init__(
            message,
            ErrorCategory.DEPENDENCY,
            recoverable=False,
            details={'missing_dependencies': missing_deps},
            **kwargs
        )

class PermissionError(SkillOperationError):
    """权限错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.PERMISSION, recoverable=False, **kwargs)
```

### 5.2 错误处理策略

```python
import asyncio
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar('T')

def with_retry(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    retryable_exceptions: tuple = (NetworkError,)
):
    """重试装饰器"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except SkillOperationError as e:
                    last_error = e
                    
                    if e.category not in retryable_exceptions:
                        raise
                    
                    if attempt < max_retries:
                        delay = retry_delay * (2 ** attempt)  # 指数退避
                        await asyncio.sleep(delay)
                    else:
                        raise
            
            raise last_error
        
        return wrapper
    return decorator

def with_transaction():
    """事务装饰器"""
    def decorator(func: Callable[..., OperationResult]):
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> OperationResult:
            tx = self.transaction_manager.begin()
            try:
                result = await func(self, *args, **kwargs)
                if result.success:
                    tx.commit()
                else:
                    tx.rollback()
                return result
            except Exception as e:
                tx.rollback()
                return OperationResult.fail(str(e))
        
        return wrapper
    return decorator
```

### 5.3 API 错误响应

```python
from fastapi import HTTPException
from fastapi.responses import JSONResponse

async def skill_operation_exception_handler(request, exc: SkillOperationError):
    """全局异常处理"""
    
    status_code = {
        ErrorCategory.NETWORK: 503,
        ErrorCategory.FILE_SYSTEM: 500,
        ErrorCategory.VALIDATION: 422,
        ErrorCategory.DEPENDENCY: 422,
        ErrorCategory.PERMISSION: 403,
        ErrorCategory.UNKNOWN: 500
    }.get(exc.category, 500)
    
    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict()
    )

# 在 FastAPI 应用中注册
app.add_exception_handler(SkillOperationError, skill_operation_exception_handler)
```

### 5.4 前端错误处理

```typescript
// 错误处理 Hook
export function useSkillOperations() {
  const [error, setError] = useState<SkillError | null>(null);
  const [loading, setLoading] = useState(false);

  const handleOperation = async (
    operation: () => Promise<OperationResult>,
    options: {
      onSuccess?: () => void;
      onError?: (error: SkillError) => void;
      retryable?: boolean;
    } = {}
  ) => {
    setLoading(true);
    setError(null);

    try {
      const result = await operation();
      
      if (result.success) {
        options.onSuccess?.();
      } else {
        throw new Error(result.error);
      }
    } catch (err) {
      const skillError = parseSkillError(err);
      setError(skillError);
      options.onError?.(skillError);

      // 自动重试可恢复的错误
      if (options.retryable && skillError.recoverable) {
        setTimeout(() => {
          handleOperation(operation, { ...options, retryable: false });
        }, skillError.retryAfter || 1000);
      }
    } finally {
      setLoading(false);
    }
  };

  return { handleOperation, error, loading, clearError: () => setError(null) };
}

// 错误提示组件
export const ErrorToast: React.FC<{ error: SkillError | null }> = ({ error }) => {
  if (!error) return null;

  const categoryMessages = {
    network: '网络连接失败，请检查网络后重试',
    file_system: '文件操作失败，请检查磁盘空间',
    validation: '验证失败，请检查输入参数',
    dependency: `缺少依赖: ${error.details?.missing_dependencies?.join(', ')}`,
    permission: '权限不足，请以管理员身份运行',
    unknown: '发生未知错误，请查看日志'
  };

  return (
    <Toast type="error">
      <ToastTitle>操作失败</ToastTitle>
      <ToastDescription>{categoryMessages[error.category]}</ToastDescription>
      {error.recoverable && (
        <ToastAction onClick={() => window.location.reload()}>
          重试
        </ToastAction>
      )}
    </Toast>
  );
};
```

---

## 6. 测试计划

### 6.1 单元测试

```python
# tests/unit/test_skill_service.py
import pytest
from unittest.mock import Mock, patch

class TestSkillService:
    @pytest.fixture
    def skill_service(self):
        config_manager = Mock()
        skill_hub = Mock()
        return SkillService(config_manager, skill_hub)

    async def test_install_skill_success(self, skill_service):
        """测试成功安装"""
        skill_hub.get_skill_metadata.return_value = Mock(
            version="1.0.0",
            dependencies=[]
        )
        
        result = await skill_service.install_skill("official/test")
        
        assert result.success is True
        skill_hub.download_skill.assert_called_once()

    async def test_install_skill_already_installed(self, skill_service):
        """测试重复安装"""
        skill_service.config_manager.is_installed.return_value = True
        
        result = await skill_service.install_skill("official/test")
        
        assert result.success is False
        assert "already installed" in result.error

    async def test_install_skill_missing_dependency(self, skill_service):
        """测试缺少依赖"""
        skill_hub.get_skill_metadata.return_value = Mock(
            version="1.0.0",
            dependencies=["official/dep"]
        )
        skill_service.config_manager.is_installed.return_value = False
        
        result = await skill_service.install_skill("official/test")
        
        assert result.success is False
        assert "Dependency" in result.error

    async def test_toggle_enabled(self, skill_service):
        """测试启用/禁用切换"""
        # 禁用已安装的 Skill
        skill_service.config_manager.get_skill_status.return_value = "installed"
        
        result = await skill_service.toggle_enabled("official/test", False)
        
        assert result.success is True
        skill_service.config_manager.add_disabled_skill.assert_called_once()

    async def test_batch_operations(self, skill_service):
        """测试批量操作"""
        skill_ids = ["official/s1", "official/s2"]
        
        result = await skill_service.batch_install(skill_ids)
        
        assert result.total == 2
        assert result.success == 2
```

### 6.2 集成测试

```python
# tests/integration/test_skills_api.py
import pytest
from httpx import AsyncClient

class TestSkillsAPI:
    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    async def test_list_skills(self, client):
        """测试获取 Skill 列表"""
        response = await client.get("/api/skills")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_install_skill_api(self, client):
        """测试安装 API"""
        response = await client.post("/api/skills/official/test-skill/install")
        
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_batch_operations_api(self, client):
        """测试批量操作 API"""
        response = await client.post("/api/skills/batch", json={
            "operation": "install",
            "skill_ids": ["official/s1", "official/s2"]
        })
        
        assert response.status_code == 200
        result = response.json()
        assert result["total"] == 2
        assert "success" in result
        assert "failed" in result

    async def test_error_handling(self, client):
        """测试错误处理"""
        # 安装不存在的 Skill
        response = await client.post("/api/skills/official/nonexistent/install")
        
        assert response.status_code == 404
        assert "error" in response.json()
```

### 6.3 性能测试

```python
# tests/performance/test_skill_performance.py
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

class TestSkillPerformance:
    async def test_list_skills_performance(self, skill_service):
        """测试列表查询性能"""
        start = time.time()
        
        for _ in range(100):
            await skill_service.list_skills()
        
        elapsed = time.time() - start
        avg_time = elapsed / 100
        
        assert avg_time < 0.2  # 平均 < 200ms

    async def test_concurrent_installs(self, skill_service):
        """测试并发安装"""
        import asyncio
        
        skill_ids = [f"official/skill_{i}" for i in range(10)]
        
        start = time.time()
        
        tasks = [
            skill_service.install_skill(sid)
            for sid in skill_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start
        
        # 所有操作应在合理时间内完成
        assert elapsed < 30
        
        # 检查是否有死锁或数据竞争
        success_count = sum(1 for r in results if getattr(r, 'success', False))
        assert success_count == len(skill_ids)
```

### 6.4 测试覆盖率要求

| 模块 | 覆盖率要求 |
|------|-----------|
| skill_service.py | > 85% |
| config_manager.py | > 90% |
| transaction_manager.py | > 90% |
| skill_operations.py | > 85% |
| skill_hub_client.py | > 75% |
| API 路由 | > 80% |
| 前端组件 | > 70% |

---

## 7. 代码示例

### 7.1 完整 Skill 服务实现

```python
# src/server/services/skill_service.py
from typing import List, Optional
from dataclasses import dataclass
import asyncio

@dataclass
class OperationResult:
    success: bool
    error: Optional[str] = None
    data: Optional[dict] = None
    
    @classmethod
    def success(cls, data: Optional[dict] = None):
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str):
        return cls(success=False, error=error)

@dataclass
class BatchResult:
    total: int
    success: int
    failed: int
    details: List[dict]

class SkillService:
    """Skill 管理服务"""
    
    def __init__(
        self,
        config_manager: ConfigManager,
        skill_hub: SkillHubClient,
        transaction_manager: TransactionManager
    ):
        self.config = config_manager
        self.hub = skill_hub
        self.tx = transaction_manager
    
    async def list_skills(
        self,
        source: str = 'all',
        status: str = 'all',
        search: str = '',
        sort_by: str = 'name',
        pinned_first: bool = True
    ) -> List[Skill]:
        """获取 Skill 列表"""
        
        # 获取远程 Skills
        remote_skills = await self._fetch_remote_skills(source, search)
        
        # 合并本地状态
        skills = []
        for remote in remote_skills:
            local_status = self._get_local_status(remote.id)
            skill = self._merge_skill_info(remote, local_status)
            skills.append(skill)
        
        # 过滤
        if status != 'all':
            skills = [s for s in skills if s.status.value == status]
        
        # 排序
        skills = self._sort_skills(skills, sort_by, pinned_first)
        
        return skills
    
    @with_transaction()
    async def install_skill(
        self,
        skill_id: str,
        version: Optional[str] = None
    ) -> OperationResult:
        """安装 Skill"""
        
        # 检查是否已安装
        if self.config.is_skill_installed(skill_id):
            return OperationResult.fail(f"Skill {skill_id} is already installed")
        
        try:
            # 获取元数据
            metadata = await self.hub.get_skill_metadata(skill_id, version)
            
            # 检查依赖
            for dep in metadata.dependencies:
                if not self.config.is_skill_installed(dep):
                    raise DependencyError(
                        f"Missing dependency: {dep}",
                        missing_deps=[dep],
                        skill_id=skill_id
                    )
            
            # 下载
            download_path = await self.hub.download_skill(skill_id, version)
            
            # 验证
            if not self._verify_skill_package(download_path, metadata):
                raise ValidationError("Invalid skill package checksum")
            
            # 安装
            install_path = self._get_install_path(skill_id)
            await self._extract_skill(download_path, install_path)
            
            # 更新配置
            self.config.add_installed_skill(skill_id, {
                'version': metadata.version,
                'installed_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
                'source': metadata.source
            })
            
            return OperationResult.success()
            
        except SkillOperationError:
            raise
        except Exception as e:
            raise SkillOperationError(
                f"Failed to install skill: {str(e)}",
                ErrorCategory.UNKNOWN,
                skill_id=skill_id
            )
    
    @with_transaction()
    async def update_skill(self, skill_id: str) -> OperationResult:
        """更新 Skill"""
        
        if not self.config.is_skill_installed(skill_id):
            return OperationResult.fail(f"Skill {skill_id} is not installed")
        
        # 检查是否有更新
        current = self.config.get_installed_skill(skill_id)
        latest = await self.hub.get_skill_metadata(skill_id)
        
        if current['version'] == latest.version:
            return OperationResult.fail("Already up to date")
        
        # 备份当前版本
        backup_path = self._backup_skill(skill_id)
        
        try:
            # 卸载旧版本
            await self._uninstall_skill_files(skill_id)
            
            # 安装新版本
            download_path = await self.hub.download_skill(skill_id, latest.version)
            install_path = self._get_install_path(skill_id)
            await self._extract_skill(download_path, install_path)
            
            # 更新配置
            self.config.update_installed_skill(skill_id, {
                'version': latest.version,
                'updated_at': datetime.utcnow().isoformat()
            })
            
            # 清理备份
            self._remove_backup(backup_path)
            
            return OperationResult.success()
            
        except Exception as e:
            # 回滚
            self._restore_backup(backup_path, skill_id)
            raise
    
    @with_transaction()
    async def uninstall_skill(self, skill_id: str) -> OperationResult:
        """卸载 Skill"""
        
        if not self.config.is_skill_installed(skill_id):
            return OperationResult.fail(f"Skill {skill_id} is not installed")
        
        # 检查是否有其他 Skill 依赖它
        dependents = self._find_dependents(skill_id)
        if dependents:
            return OperationResult.fail(
                f"Cannot uninstall: required by {', '.join(dependents)}"
            )
        
        # 删除文件
        await self._uninstall_skill_files(skill_id)
        
        # 更新配置
        self.config.remove_installed_skill(skill_id)
        self.config.remove_pinned_skill(skill_id)
        self.config.remove_disabled_skill(skill_id)
        self.config.remove_favorite_skill(skill_id)
        
        return OperationResult.success()
    
    async def toggle_enabled(self, skill_id: str, enabled: bool) -> OperationResult:
        """启用/禁用 Skill"""
        
        if not self.config.is_skill_installed(skill_id):
            return OperationResult.fail(f"Skill {skill_id} is not installed")
        
        if enabled:
            self.config.remove_disabled_skill(skill_id)
        else:
            self.config.add_disabled_skill(skill_id)
        
        return OperationResult.success()
    
    async def toggle_pinned(self, skill_id: str, pinned: bool) -> OperationResult:
        """钉选/取消钉选 Skill"""
        
        if pinned:
            # 限制最大钉选数量
            pinned_skills = self.config.get_pinned_skills()
            if len(pinned_skills) >= 10:
                return OperationResult.fail("Maximum 10 pinned skills allowed")
            self.config.add_pinned_skill(skill_id)
        else:
            self.config.remove_pinned_skill(skill_id)
        
        return OperationResult.success()
    
    async def toggle_favorite(self, skill_id: str, favorited: bool) -> OperationResult:
        """收藏/取消收藏 Skill"""
        
        if favorited:
            self.config.add_favorite_skill(skill_id)
        else:
            self.config.remove_favorite_skill(skill_id)
        
        return OperationResult.success()
    
    async def batch_operation(
        self,
        operation: str,
        skill_ids: List[str]
    ) -> BatchResult:
        """批量操作"""
        
        results = []
        
        for skill_id in skill_ids:
            try:
                if operation == 'install':
                    result = await self.install_skill(skill_id)
                elif operation == 'uninstall':
                    result = await self.uninstall_skill(skill_id)
                elif operation == 'enable':
                    result = await self.toggle_enabled(skill_id, True)
                elif operation == 'disable':
                    result = await self.toggle_enabled(skill_id, False)
                elif operation == 'pin':
                    result = await self.toggle_pinned(skill_id, True)
                elif operation == 'unpin':
                    result = await self.toggle_pinned(skill_id, False)
                else:
                    result = OperationResult.fail(f"Unknown operation: {operation}")
                
                results.append({
                    'skill_id': skill_id,
                    'success': result.success,
                    'error': result.error
                })
                
            except Exception as e:
                results.append({
                    'skill_id': skill_id,
                    'success': False,
                    'error': str(e)
                })
        
        return BatchResult(
            total=len(skill_ids),
            success=sum(1 for r in results if r['success']),
            failed=sum(1 for r in results if not r['success']),
            details=results
        )
```

### 7.2 前端 Skill 卡片组件

```typescript
// src/web/components/SkillCard.tsx
import React, { useState } from 'react';
import { Skill, SkillStatus } from '../types/skill';
import { useSkillOperations } from '../hooks/useSkillOperations';

interface SkillCardProps {
  skill: Skill;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (selected: boolean) => void;
  onStatusChange?: () => void;
}

export const SkillCard: React.FC<SkillCardProps> = ({
  skill,
  selectable = false,
  selected = false,
  onSelect,
  onStatusChange
}) => {
  const { handleOperation, loading, error } = useSkillOperations();
  const [showConfirm, setShowConfirm] = useState<string | null>(null);

  const getVisibleActions = (): ActionType[] => {
    const actions: ActionType[] = [];
    
    switch (skill.status) {
      case SkillStatus.NOT_INSTALLED:
        actions.push('install', 'detail');
        break;
      case SkillStatus.INSTALLED:
        actions.push('run', 'update', 'uninstall', 'disable');
        if (!skill.runtimeStatus?.pinned) actions.push('pin');
        if (!skill.runtimeStatus?.favorited) actions.push('favorite');
        break;
      case SkillStatus.UPDATE_AVAILABLE:
        actions.push('run', 'update', 'uninstall', 'disable');
        break;
      case SkillStatus.DISABLED:
        actions.push('enable', 'uninstall');
        break;
    }
    
    if (skill.runtimeStatus?.pinned) actions.push('unpin');
    if (skill.runtimeStatus?.favorited) actions.push('unfavorite');
    
    return actions;
  };

  const handleAction = async (action: ActionType) => {
    if (['uninstall', 'disable'].includes(action)) {
      setShowConfirm(action);
      return;
    }

    await executeAction(action);
  };

  const executeAction = async (action: ActionType) => {
    const operations: Record<ActionType, () => Promise<any>> = {
      install: () => skillApi.install(skill.id),
      update: () => skillApi.update(skill.id),
      uninstall: () => skillApi.uninstall(skill.id),
      enable: () => skillApi.toggleEnabled(skill.id, true),
      disable: () => skillApi.toggleEnabled(skill.id, false),
      pin: () => skillApi.togglePinned(skill.id, true),
      unpin: () => skillApi.togglePinned(skill.id, false),
      favorite: () => skillApi.toggleFavorite(skill.id, true),
      unfavorite: () => skillApi.toggleFavorite(skill.id, false),
      run: () => skillApi.run(skill.id),
      detail: () => { /* 打开详情 */ },
      docs: () => { /* 打开文档 */ }
    };

    await handleOperation(operations[action], {
      onSuccess: () => {
        onStatusChange?.();
        setShowConfirm(null);
      }
    });
  };

  const actionLabels: Record<ActionType, string> = {
    run: '运行',
    install: '安装',
    update: '更新',
    uninstall: '卸载',
    enable: '启用',
    disable: '禁用',
    pin: '钉选',
    unpin: '取消钉选',
    favorite: '收藏',
    unfavorite: '取消收藏',
    detail: '详情',
    docs: '文档'
  };

  const statusLabels: Record<SkillStatus, string> = {
    [SkillStatus.NOT_INSTALLED]: '可安装',
    [SkillStatus.INSTALLED]: '已安装',
    [SkillStatus.UPDATE_AVAILABLE]: '有更新',
    [SkillStatus.DISABLED]: '已禁用'
  };

  return (
    <Card className={skill.runtimeStatus?.pinned ? 'border-primary' : ''}>
      <CardHeader>
        {selectable && (
          <Checkbox
            checked={selected}
            onCheckedChange={onSelect}
          />
        )}
        <div className="flex items-center gap-2">
          <span className="text-2xl">{skill.icon || '🎯'}</span>
          <div>
            <CardTitle>{skill.name}</CardTitle>
            <Badge variant={getStatusVariant(skill.status)}>
              {statusLabels[skill.status]}
            </Badge>
          </div>
        </div>
        {skill.runtimeStatus?.pinned && (
          <PinIcon className="text-primary" />
        )}
        {skill.runtimeStatus?.favorited && (
          <StarIcon className="text-yellow-500" />
        )}
      </CardHeader>
      
      <CardContent>
        <p className="text-sm text-muted-foreground">{skill.description}</p>
        <div className="flex items-center gap-4 text-xs text-muted-foreground mt-2">
          <span>{skill.source}</span>
          <span>v{skill.data.version}</span>
          <span>⭐ {skill.stats.rating}</span>
          <span>📥 {skill.stats.downloads}</span>
        </div>
      </CardContent>
      
      <CardFooter className="flex flex-wrap gap-2">
        {getVisibleActions().map(action => (
          <Button
            key={action}
            size="sm"
            variant={getActionVariant(action)}
            onClick={() => handleAction(action)}
            disabled={loading}
          >
            {actionLabels[action]}
          </Button>
        ))}
      </CardFooter>

      {/* 确认对话框 */}
      <ConfirmDialog
        open={!!showConfirm}
        onClose={() => setShowConfirm(null)}
        onConfirm={() => executeAction(showConfirm as ActionType)}
        title={`确认${actionLabels[showConfirm as ActionType]}?`}
        description={`确定要${actionLabels[showConfirm as ActionType]} ${skill.name} 吗？`}
      />

      {/* 错误提示 */}
      <ErrorToast error={error} />
    </Card>
  );
};
```

### 7.3 批量操作栏组件

```typescript
// src/web/components/BatchOperationBar.tsx
import React, { useState } from 'react';
import { useSkillOperations } from '../hooks/useSkillOperations';

interface BatchOperationBarProps {
  selectedSkills: string[];
  onClearSelection: () => void;
  onOperationComplete: () => void;
}

export const BatchOperationBar: React.FC<BatchOperationBarProps> = ({
  selectedSkills,
  onClearSelection,
  onOperationComplete
}) => {
  const { handleOperation } = useSkillOperations();
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);

  if (selectedSkills.length === 0) return null;

  const batchOperations = [
    { key: 'install', label: '批量安装', icon: '⬇️' },
    { key: 'uninstall', label: '批量卸载', icon: '🗑️' },
    { key: 'enable', label: '批量启用', icon: '✅' },
    { key: 'disable', label: '批量禁用', icon: '🚫' },
    { key: 'pin', label: '批量钉选', icon: '📌' },
    { key: 'unpin', label: '批量取消钉选', icon: '📍' }
  ];

  const handleBatchOperation = async (operation: string) => {
    await handleOperation(
      async () => {
        const result = await skillApi.batchOperation({
          operation,
          skill_ids: selectedSkills
        });
        
        // 显示进度
        setProgress({ current: 0, total: selectedSkills.length });
        
        // 模拟进度更新（实际应从 WebSocket 获取）
        for (let i = 0; i < selectedSkills.length; i++) {
          await new Promise(r => setTimeout(r, 100));
          setProgress({ current: i + 1, total: selectedSkills.length });
        }
        
        return result;
      },
      {
        onSuccess: () => {
          onOperationComplete();
          onClearSelection();
          setProgress(null);
        }
      }
    );
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-background border rounded-lg shadow-lg p-4 z-50">
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium">
          已选择 {selectedSkills.length} 项
        </span>
        
        <Separator orientation="vertical" className="h-6" />
        
        <div className="flex gap-2">
          {batchOperations.map(op => (
            <Button
              key={op.key}
              size="sm"
              variant="outline"
              onClick={() => handleBatchOperation(op.key)}
            >
              <span className="mr-1">{op.icon}</span>
              {op.label}
            </Button>
          ))}
        </div>
        
        <Separator orientation="vertical" className="h-6" />
        
        <Button size="sm" variant="ghost" onClick={onClearSelection}>
          清除选择
        </Button>
      </div>
      
      {/* 进度条 */}
      {progress && (
        <div className="mt-3">
          <Progress value={(progress.current / progress.total) * 100} />
          <p className="text-xs text-muted-foreground text-center mt-1">
            处理中... {progress.current}/{progress.total}
          </p>
        </div>
      )}
    </div>
  );
};
```

---

## 附录

### A. 配置 Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ArtClaw Config",
  "type": "object",
  "properties": {
    "version": {
      "type": "string",
      "description": "配置版本"
    },
    "skills": {
      "type": "object",
      "properties": {
        "pinned": {
          "type": "array",
          "items": { "type": "string" },
          "maxItems": 10
        },
        "disabled": {
          "type": "array",
          "items": { "type": "string" }
        },
        "favorites": {
          "type": "array",
          "items": { "type": "string" }
        },
        "installed": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "properties": {
              "version": { "type": "string" },
              "installed_at": { "type": "string", "format": "date-time" },
              "updated_at": { "type": "string", "format": "date-time" },
              "source": { "type": "string" }
            },
            "required": ["version", "installed_at", "source"]
          }
        }
      }
    },
    "recent": {
      "type": "object",
      "properties": {
        "skills": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": { "type": "string" },
              "used_at": { "type": "string", "format": "date-time" }
            }
          },
          "maxItems": 50
        }
      }
    }
  }
}
```

### B. API 端点汇总

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | /api/skills | 获取 Skill 列表 |
| GET | /api/skills/{id} | 获取 Skill 详情 |
| POST | /api/skills/{id}/install | 安装 Skill |
| POST | /api/skills/{id}/update | 更新 Skill |
| POST | /api/skills/{id}/uninstall | 卸载 Skill |
| POST | /api/skills/{id}/enable | 启用 Skill |
| POST | /api/skills/{id}/disable | 禁用 Skill |
| POST | /api/skills/{id}/pin | 钉选 Skill |
| POST | /api/skills/{id}/unpin | 取消钉选 Skill |
| POST | /api/skills/{id}/favorite | 收藏 Skill |
| POST | /api/skills/{id}/unfavorite | 取消收藏 Skill |
| POST | /api/skills/{id}/run | 运行 Skill |
| POST | /api/skills/batch | 批量操作 |
| GET | /api/skills/recent | 获取最近使用 |

### C. 文件结构

```
src/
├── server/
│   ├── api/
│   │   └── skills.py              # API 路由
│   ├── services/
│   │   ├── skill_service.py       # Skill 服务
│   │   ├── config_manager.py      # 配置管理
│   │   ├── transaction_manager.py # 事务管理
│   │   ├── skill_operations.py    # 操作实现
│   │   ├── skill_hub_client.py    # skill_hub 客户端
│   │   └── recent_usage_service.py # 最近使用
│   └── models/
│       └── skill.py               # 数据模型
└── web/
    ├── components/
    │   ├── SkillCard.tsx          # Skill 卡片
    │   ├── SkillActionButtons.tsx # 操作按钮
    │   ├── BatchOperationBar.tsx  # 批量操作栏
    │   └── ErrorToast.tsx         # 错误提示
    ├── pages/
    │   └── Skills/
    │       ├── index.tsx          # Skill 页面
    │       └── SkillList.tsx      # Skill 列表
    └── hooks/
        └── useSkillOperations.ts  # 操作 Hook
```

---

*文档版本: 1.0*
*最后更新: 2026-04-10*
