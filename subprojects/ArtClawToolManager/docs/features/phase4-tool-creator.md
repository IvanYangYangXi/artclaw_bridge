# Phase 4.2: Tool Creator Skill 设计

> 对应工作日: Day 5-7

---

## 1. 概述

Tool Creator 是一个特殊的 Skill，用户点击"创建工具"后跳转对话面板，Agent 引导完成工具创建。

**入口**: 工具管理器页面 → [创建工具] 标签 → 自动发送 `/create tool`

## 2. 创建流程

```
/create tool → 选择创建方式 → 引导收集信息 → 生成 manifest.json → 预览 → 保存
```

### 2.1 状态流转

```
start → select_method → collect_info → generate → preview → confirm → save → complete
```

## 3. 三种创建方式

### 3.1 包装 Skill

**适用场景**: 将现有 Skill 包装为固定参数的快捷工具

**对话流程**:
```
Agent: 选择创建方式: [包装 Skill] [编写脚本] [组合工具]
用户: 包装 Skill
Agent: 选择要包装的 Skill（列出可用 Skills）
用户: comfyui-txt2img
Agent: 该 Skill 有以下参数: prompt/width/height/steps，暴露哪些给用户？
用户: 只保留 prompt 和 steps，width/height 固定 1024
Agent: [生成 manifest.json 预览] → [保存] [修改] [取消]
```

**生成的 manifest.json**:
```json
{
  "id": "user/quick-txt2img",
  "name": "快速文生图",
  "implementation": {
    "type": "skill_wrapper",
    "skill": "comfyui-txt2img",
    "fixedParams": { "width": 1024, "height": 1024 }
  },
  "inputs": [
    { "id": "prompt", "name": "提示词", "type": "string", "required": true },
    { "id": "steps", "name": "采样步数", "type": "number", "default": 20 }
  ]
}
```

### 3.2 编写脚本

**适用场景**: 自定义 Python 脚本，使用 artclaw_sdk

**对话流程**:
```
用户: 编写脚本
Agent: 目标 DCC: [UE5] [Maya] [ComfyUI] [通用]
用户: Maya 2024
Agent: 请描述工具功能
用户: 批量导出选中模型为 FBX
Agent: 需要什么参数？（如导出路径、前缀等）
用户: 导出路径，文件名前缀，是否包含动画
Agent: [生成 main.py + manifest.json] → [保存] [修改] [取消]
```

**生成的脚本遵循 artclaw_sdk 范式**（详见 [trigger-mechanism.md#9](../specs/trigger-mechanism.md)）:

```python
"""批量导出 FBX — 由 Tool Creator 生成"""
import artclaw_sdk as sdk

def batch_export_fbx(export_path: str, file_prefix: str = "", include_animation: bool = False):
    selected = sdk.get_selected()
    if not selected:
        return sdk.result.fail("TOOL_INVALID_SELECTION", "请先选择要导出的对象")
    
    sdk.progress.start(total=len(selected))
    exported = []
    for i, obj in enumerate(selected):
        filename = f"{file_prefix}{obj.name}.fbx"
        # ... DCC 专属导出逻辑 ...
        exported.append(filename)
        sdk.progress.update(i + 1, message=f"导出 {obj.name}")
    sdk.progress.finish()
    
    return sdk.result.success(
        data={"exportedCount": len(exported), "files": exported},
        message=f"成功导出 {len(exported)} 个模型"
    )
```

### 3.3 组合工具

**适用场景**: 将多个工具串联

**对话流程**:
```
用户: 组合工具
Agent: 选择要组合的工具（列出已有工具）
用户: 先运行"命名检查"，通过后运行"批量导出 FBX"
Agent: 确认管线: 命名检查 → (通过) → 批量导出 FBX
       参数映射: 命名检查.prefix → 批量导出.file_prefix
       [保存] [修改] [取消]
```

## 4. 界面-Agent 交互协议

### 消息格式

```typescript
// 前端 → Agent（自动发送）
interface CreateToolMessage {
  command: '/create tool';
}

// Agent → 前端（选择创建方式）
interface SelectMethodResponse {
  type: 'tool_creator.select_method';
  methods: ['skill_wrapper', 'script', 'composite'];
}

// Agent → 前端（工具预览）
interface ToolPreviewResponse {
  type: 'tool_creator.preview';
  manifest: object;           // 生成的 manifest.json
  actions: ['save', 'modify', 'cancel'];
}

// 前端 → Agent（用户确认）
interface ConfirmAction {
  type: 'tool_creator.confirm';
  action: 'save' | 'modify' | 'cancel';
}
```

## 5. Tool Creator Skill 文件

```
~/.openclaw/skills/artclaw-tool-creator/
├── SKILL.md                   # Skill 定义（含 artclaw_sdk API 速查）
└── references/
    └── sdk-api-reference.md   # artclaw_sdk 完整 API 参考
```

**SKILL.md 关键内容**:
- 创建流程状态机
- 三种创建方式的对话模板
- artclaw_sdk API 速查表（AI 生成脚本时参考）
- manifest.json Schema
