# ComfyUI 外部 MCP 项目整合方案

> 分析日期: 2026-04-10
> 来源项目: Comfy-Cozy, comfyui-arbo-mcp-hub, comfyui-mcp
> 目标: 提取有价值的 tools/skills，按重要度分类整合到 ArtClaw Bridge

---

## 1. 外部项目功能分析

### 1.1 ArboRithmDev/comfyui-arbo-mcp-hub (79 tools)

**核心功能模块**:

| 模块 | 工具数量 | 功能描述 |
|------|----------|----------|
| **generation** | ~5 | txt2img/img2img workflow 构建、批量生成、高清修复 |
| **models** | ~8 | 模型下载、删除、列表、搜索、CivitAI/HuggingFace 集成 |
| **packages** | ~10 | 节点包搜索、安装、更新、卸载、依赖管理 |
| **repair** | ~4 | workflow 诊断、缺失节点检测、自动修复、迁移 |
| **introspection** | ~15 | 节点列表、模型扫描、系统状态、队列查询 |
| **instances** | ~6 | 多 ComfyUI 实例管理、切换、状态监控 |
| **combo** | ~20 | 复合操作（一键安装+配置+运行）|
| **canvas** | ~10 | 节点图操作（添加/删除/连接节点）|

**技术特点**:
- 作为 ComfyUI 自定义节点运行（同进程）
- 依赖 ComfyUI-Manager 进行节点/模型管理
- 支持多实例配置
- workflow_repair 模块有智能节点替换逻辑

### 1.2 JosephOIbrahim/Comfy-Cozy (113 tools)

**从 README 提取的核心功能**:

| 功能类别 | 描述 |
|----------|------|
| **Workflow 管理** | 加载、保存、修复、版本控制 |
| **模型供应** | CivitAI + HuggingFace 搜索下载、自动安装 |
| **迭代渲染** | 参数优化、A/B 测试、风格学习 |
| **节点管理** | 缺失节点自动检测安装、包依赖解析 |
| **自然语言交互** | "make it dreamier" → 自动调整参数 |

**技术特点**:
- TypeScript 实现（独立进程 MCP Server）
- 多 provider 支持（Claude, GPT-4o, Gemini, Ollama）
- 有学习用户风格的能力
- Patent Pending（可能有使用限制）

### 1.3 alecc08/comfyui-mcp (3 tools)

**功能**:
- `comfyui_generate_image`: 统一生成工具（txt2img/img2img/post-process）
- `comfyui_get_image`: 获取生成结果
- `comfyui_get_request_history`: 查询历史

**技术特点**:
- Python 实现，简洁
- 模板填参模式（非动态构建）
- 图片缓存机制

---

## 2. 功能重要度评估

### 2.1 使用频率评估

| 功能 | 使用频率 | 用户价值 | 技术复杂度 |
|------|----------|----------|------------|
| **基础生成 (txt2img)** | ⭐⭐⭐⭐⭐ 极高 | 核心功能 | 低 |
| **模型列表查询** | ⭐⭐⭐⭐⭐ 极高 | 必备 | 低 |
| **节点类型查询** | ⭐⭐⭐⭐⭐ 极高 | 必备 | 低 |
| **队列状态查询** | ⭐⭐⭐⭐⭐ 极高 | 必备 | 低 |
| **图生图 (img2img)** | ⭐⭐⭐⭐⭐ 极高 | 核心功能 | 中 |
| **ControlNet 工作流** | ⭐⭐⭐⭐ 高 | 常用 | 中 |
| **模型下载 (CivitAI)** | ⭐⭐⭐⭐ 高 | 高频需求 | 中 |
| **缺失节点自动安装** | ⭐⭐⭐⭐ 高 | 解决痛点 | 高 |
| **Workflow 修复** | ⭐⭐⭐ 中 | 解决痛点 | 高 |
| **高清修复 (Hires Fix)** | ⭐⭐⭐ 中 | 常用 | 中 |
| **批量生成** | ⭐⭐⭐ 中 | 效率工具 | 中 |
| **Inpainting 局部重绘** | ⭐⭐⭐ 中 | 特定场景 | 中 |
| **多实例管理** | ⭐⭐ 低 | 高级用户 | 高 |
| **风格学习** | ⭐⭐ 低 | 长期价值 | 极高 |
| **A/B 测试** | ⭐⭐ 低 | 专业用户 | 高 |

### 2.2 整合价值评估

| 功能 | 复用价值 | 整合难度 | 建议 |
|------|----------|----------|------|
| **workflow_repair 逻辑** | ⭐⭐⭐⭐⭐ | 中 | **高优先级** - 解决实际痛点 |
| **CivitAI 客户端** | ⭐⭐⭐⭐⭐ | 低 | **高优先级** - 高频需求 |
| **ComfyUI-Manager 集成** | ⭐⭐⭐⭐ | 中 | **中优先级** - 依赖外部组件 |
| **高清修复 workflow 模板** | ⭐⭐⭐⭐ | 低 | **高优先级** - 常用功能 |
| **ControlNet 模板库** | ⭐⭐⭐⭐ | 低 | **高优先级** - 常用功能 |
| **多实例管理** | ⭐⭐⭐ | 高 | **低优先级** - 非核心需求 |
| **风格学习** | ⭐⭐⭐ | 极高 | **暂缓** - 技术复杂、有专利风险 |

---

## 3. Skill 分类方案

### 3.1 官方分类 (Official)

**标准**: 核心功能、高频使用、稳定可靠、符合 ArtClaw 架构

| Skill 名称 | 功能 | 来源 | 优先级 |
|------------|------|------|--------|
| `comfyui-txt2img` | 文生图标准流程 | 自有 + arbo-mcp | P0 ✅ 已有 |
| `comfyui-context` | 系统/模型/节点查询 | 自有 | P0 ✅ 已有 |
| `comfyui-operation-rules` | 通用操作规则 | 自有 | P0 ✅ 已有 |
| `comfyui-workflow-builder` | Workflow 构建指南 | 自有 | P0 ✅ 已有 |
| `comfyui-img2img` | 图生图流程 | arbo-mcp | **P1 新增** |
| `comfyui-model-manager` | 模型查询/下载/管理 | arbo-mcp + Comfy-Cozy | **P1 新增** |
| `comfyui-hires-fix` | 高清修复工作流 | arbo-mcp | **P1 新增** |
| `comfyui-controlnet` | ControlNet 工作流模板 | arbo-mcp | **P1 新增** |
| `comfyui-inpainting` | 局部重绘工作流 | arbo-mcp | **P2 新增** |

### 3.2 市集分类 (Marketplace)

**标准**: 高级功能、特定场景、可能依赖外部组件、实验性

| Skill 名称 | 功能 | 来源 | 优先级 |
|------------|------|------|--------|
| `comfyui-node-installer` | 缺失节点自动检测安装 | arbo-mcp | P2 |
| `comfyui-workflow-repair` | Workflow 自动诊断修复 | arbo-mcp | P2 |
| `comfyui-batch-gen` | 批量生成/变体 | arbo-mcp | P2 |
| `comfyui-civitai` | CivitAI 深度集成（搜索/下载/收藏）| Comfy-Cozy | P2 |
| `comfyui-multi-instance` | 多实例管理 | arbo-mcp | P3 |
| `comfyui-prompt-optimize` | Prompt 优化建议 | Comfy-Cozy | P3 |

---

## 4. Workflow 模板库 Skill 化方案

### 4.1 模板库结构

```
~/.openclaw/skills/comfyui-workflow-templates/
├── official/                    # 官方维护
│   ├── txt2img-basic.json
│   ├── txt2img-sdxl.json
│   ├── img2img-basic.json
│   ├── hires-fix-esrgan.json
│   ├── controlnet-canny.json
│   ├── controlnet-openpose.json
│   ├── controlnet-depth.json
│   ├── inpainting-basic.json
│   └── lora-workflow.json
├── marketplace/                 # 社区分享
│   ├── anime-style/
│   ├── photorealistic/
│   ├── architectural/
│   └── character-design/
└── user/                        # 用户自定义
    └── (用户保存的 workflow)
```

### 4.2 模板 Skill: `comfyui-workflow-templates`

**功能**:
- 列出可用模板（按分类/标签筛选）
- 加载模板并填充参数
- 保存当前 workflow 为模板
- 模板版本管理

**Python API** (通过 `run_python` 调用):

```python
# 列出模板
from comfyui_workflow_templates import list_templates
templates = list_templates(category="official", tag="controlnet")

# 加载模板
from comfyui_workflow_templates import load_template
wf = load_template("official/txt2img-sdxl", params={
    "prompt": "a cat",
    "checkpoint": "sdxl_base.safetensors"
})

# 保存模板
from comfyui_workflow_templates import save_template
save_template(wf, name="my-anime-style", category="user")
```

### 4.3 模板与 Skill 的关系

```
┌─────────────────────────────────────────────────────┐
│              Skill: comfyui-txt2img                 │
│  (指导 AI 如何构建/修改 txt2img workflow)            │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│         Skill: comfyui-workflow-templates           │
│  (提供预置 workflow JSON，快速启动)                  │
│  - 加载模板 → 填充参数 → 返回 workflow dict          │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              run_python (MCP Tool)                  │
│  - submit_workflow(wf) → 执行生成                   │
│  - save_preview() → 展示结果                        │
└─────────────────────────────────────────────────────┘
```

---

## 5. 技术整合规范

### 5.1 代码移植规范

从外部项目移植代码到 ArtClaw Skill 时需遵循：

| 规范项 | 要求 |
|--------|------|
| **架构一致性** | 必须使用 `run_python` 执行，不得新增 MCP tools |
| **预注入变量** | 复用 `S, W, L, client, submit_workflow` 等 |
| **错误处理** | 使用 `try/except` + 详细错误信息 |
| **图片返回** | 使用 `[IMAGE:path]` 标记 |
| **API 查询优先** | 不得硬编码节点类型/参数名，必须动态查询 |
| **文档完整** | SKILL.md 必须包含使用示例和 API 参考 |

### 5.2 Skill 文档规范

每个 Skill 必须包含：

```markdown
---
name: skill-name
description: >
  简短描述（用于 OpenClaw 匹配）
  Use when AI needs to: (1) ..., (2) ..., (3) ...
metadata:
  artclaw:
    version: x.x.x
    author: ArtClaw / 来源项目
    dcc: comfyui
    priority: 100
---

# Skill 名称

## 功能概述
...

## 预注入变量
...

## API 参考
...

## 使用示例
...

## 注意事项
...
```

### 5.3 外部依赖处理

| 外部依赖 | 处理方式 | 说明 |
|----------|----------|------|
| ComfyUI-Manager | 可选依赖 | Skill 检测是否安装，未安装时提示用户 |
| CivitAI API | 直接集成 | 使用 REST API，无额外依赖 |
| HuggingFace | 直接集成 | 使用 huggingface_hub 库 |

---

## 6. 实施路线图

### Phase 1: 核心增强 (本周)
- [ ] 新增 `comfyui-img2img` Skill
- [ ] 新增 `comfyui-model-manager` Skill（基础功能）
- [ ] 验证现有 4 个 Skill 的可用性

### Phase 2: 高级功能 (下周)
- [ ] 新增 `comfyui-hires-fix` Skill
- [ ] 新增 `comfyui-controlnet` Skill
- [ ] 创建 `comfyui-workflow-templates` Skill + 官方模板库

### Phase 3: 生态扩展 (后续)
- [ ] 移植 workflow_repair 逻辑到 `comfyui-workflow-repair` (Marketplace)
- [ ] 移植节点安装功能到 `comfyui-node-installer` (Marketplace)
- [ ] CivitAI 深度集成 (Marketplace)

---

## 7. 参考代码片段

### 7.1 从 arbo-mcp-hub 提取的 workflow_repair 核心逻辑

```python
# workflow_repair.py 核心算法

def find_missing_nodes(workflow: dict, available: dict) -> list:
    """检测 workflow 中缺失的节点类型"""
    missing = []
    for node_id, node_data in workflow.items():
        class_type = node_data.get("class_type")
        if class_type and class_type not in available:
            missing.append({"id": node_id, "type": class_type})
    return missing

def find_alternatives(missing_type: str, node_data: dict, available: dict) -> list:
    """为缺失节点寻找替代方案"""
    alternatives = []
    
    # 1. 检查已知迁移映射
    migration_map = {
        "CheckpointLoader": "CheckpointLoaderSimple",
        "CLIPTextEncode": "CLIPTextEncode",
        # ... 更多映射
    }
    if missing_type in migration_map:
        alt = migration_map[missing_type]
        if alt in available:
            alternatives.append({"type": alt, "reason": "known_migration"})
    
    # 2. 基于输入输出签名匹配
    node_inputs = set(node_data.get("inputs", {}).keys())
    node_outputs = set(node_data.get("outputs", []))
    
    for alt_type, alt_info in available.items():
        alt_inputs = set(alt_info.get("input", {}).get("required", {}).keys())
        alt_outputs = set(alt_info.get("output", []))
        
        # 计算匹配度
        input_match = len(node_inputs & alt_inputs) / max(len(node_inputs), 1)
        output_match = len(node_outputs & alt_outputs) / max(len(node_outputs), 1)
        
        if input_match > 0.5 or output_match > 0.5:
            alternatives.append({
                "type": alt_type,
                "reason": "signature_match",
                "input_match": input_match,
                "output_match": output_match
            })
    
    return sorted(alternatives, key=lambda x: x.get("input_match", 0), reverse=True)
```

### 7.2 从 arbo-mcp-hub 提取的 CivitAI 客户端

```python
# civitai_client.py 核心逻辑

import requests
from typing import List, Dict, Optional

class CivitAIClient:
    BASE_URL = "https://civitai.com/api/v1"
    
    def search_models(
        self,
        query: str,
        model_type: str = "Checkpoint",  # Checkpoint, LORA, etc.
        sort: str = "Highest Rated",
        limit: int = 10
    ) -> List[Dict]:
        """搜索 CivitAI 模型"""
        params = {
            "query": query,
            "types": model_type,
            "sort": sort,
            "limit": limit
        }
        resp = requests.get(f"{self.BASE_URL}/models", params=params)
        resp.raise_for_status()
        return resp.json().get("items", [])
    
    def get_download_url(self, model_id: int, version_id: Optional[int] = None) -> str:
        """获取模型下载链接"""
        model = self.get_model(model_id)
        if version_id:
            version = next((v for v in model.get("modelVersions", []) if v["id"] == version_id), None)
        else:
            version = model.get("modelVersions", [{}])[0]  # 最新版本
        
        files = version.get("files", [])
        if files:
            return files[0].get("downloadUrl")
        return None
```

---

## 8. 总结

### 推荐整合的 Skill（按优先级）

| 优先级 | Skill 名称 | 分类 | 来源 | 预期工作量 |
|--------|------------|------|------|------------|
| P1 | comfyui-img2img | Official | arbo-mcp | 1 天 |
| P1 | comfyui-model-manager | Official | arbo-mcp + Comfy-Cozy | 2 天 |
| P1 | comfyui-hires-fix | Official | arbo-mcp | 1 天 |
| P1 | comfyui-controlnet | Official | arbo-mcp | 2 天 |
| P1 | comfyui-workflow-templates | Official | 自研 | 2 天 |
| P2 | comfyui-inpainting | Official | arbo-mcp | 1 天 |
| P2 | comfyui-node-installer | Marketplace | arbo-mcp | 2 天 |
| P2 | comfyui-workflow-repair | Marketplace | arbo-mcp | 3 天 |
| P2 | comfyui-civitai | Marketplace | Comfy-Cozy | 2 天 |
| P3 | (其他高级功能) | Marketplace | - | - |

### 关键决策

1. **不增加 MCP Tools**: 保持 v2.6 架构，所有功能通过 `run_python` + Skill 实现
2. **官方 vs 市集**: 核心生成功能进 Official，依赖外部组件/高级功能进 Marketplace
3. **Workflow 模板库**: 作为独立 Skill 实现，支持分类管理和参数填充
4. **代码复用**: 优先移植 Python 逻辑（arbo-mcp-hub），TypeScript 项目（Comfy-Cozy）提取算法思路

---

*文档结束*
