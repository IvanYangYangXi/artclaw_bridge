# Phase 4.1: 工具列表管理 + AI 协助运行 + 批量操作

> 对应工作日: Day 1-4, Day 10

---

## 1. 工具列表管理（Day 1-2）

### Day 1: 列表基础界面

**任务**:
- [ ] 创建 Tools 页面路由和布局
- [ ] 标签切换（全部/官方/市集/我的/创建）
- [ ] 工具卡片组件
- [ ] 搜索功能

```typescript
const handleRunTool = async (tool: ToolItem) => {
  navigate('/chat');
  setExecutionContext({ type: 'tool', id: tool.id, name: tool.name });
  sendMessage(`/run tool:${tool.id}`);
};
```

### Day 2: 卡片和状态管理

**任务**:
- [ ] 工具卡片 UI（状态标签、操作按钮）
- [ ] Zustand Store 状态管理
- [ ] 后端 API 集成
- [ ] 收藏/钉选功能

---

## 2. AI 协助运行流程（Day 3-4）

**与 Workflow 共用同一套流程**，详见 [phase3-workflow-library.md](./phase3-workflow-library.md) 第 3-4 章。

**Tool 特有差异**:

| 项目 | Workflow | Tool |
|------|----------|------|
| 命令格式 | `/run workflow:{id}` | `/run tool:{id}` |
| 执行引擎 | ComfyUI HTTP API | DCC Adapter（run_python） |
| 参数来源 | workflow.json | manifest.json inputs |
| 进度来源 | ComfyUI WebSocket | artclaw_sdk.progress |

### Day 3: 前端

- [ ] [运行] 按钮跳转到对话面板
- [ ] 自动发送 `/run tool:{id}`
- [ ] 右侧面板参数表单（复用 Phase 3 组件）

### Day 4: 后端

```python
class ToolExecutionService:
    async def execute_tool(self, tool_id: str, params: dict) -> ExecutionResult:
        tool = await self.tool_repo.get(tool_id)
        manifest = tool.manifest
        
        if manifest['implementation']['type'] == 'skill_wrapper':
            return await self._execute_skill_wrapper(manifest, params)
        elif manifest['implementation']['type'] == 'script':
            return await self._execute_script(manifest, params)
        elif manifest['implementation']['type'] == 'composite':
            return await self._execute_composite(manifest, params)
    
    async def _execute_script(self, manifest, params):
        """通过 DCC Adapter 运行脚本"""
        entry = manifest['implementation']['entry']
        function = manifest['implementation']['function']
        
        # 生成调用代码
        code = f"import artclaw_sdk as sdk; from {entry} import {function}; {function}(**{params})"
        
        # 发送到 DCC 执行
        return await self.dcc_adapter.run_python(code)
```

---

## 3. 批量操作（Day 10）

### API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/tools/batch/delete` | POST | 批量删除 |
| `/api/v1/tools/batch/publish` | POST | 批量发布 |

注意: Tool 不支持禁用/启用批量操作（工具是用户主动运行的，不需要禁用功能）

### 请求/响应

```json
// 请求
{ "ids": ["id1", "id2", "id3"] }

// 响应
{
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    { "id": "id1", "success": true },
    { "id": "id2", "success": true },
    { "id": "id3", "success": false, "error": "TOOL_NOT_FOUND" }
  ]
}
```

### 前端交互

- 卡片悬停显示复选框
- 选中后底部浮动操作栏: `已选 3 个  [删除] [发布] [取消]`
- 批量操作前显示确认对话框
