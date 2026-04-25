# ComfyUI Skill 开发规划

> 基于外部 MCP 项目整合的 Skill 开发路线图
> 版本: 1.0
> 日期: 2026-04-10

---

## 1. 新增 Official Skills

### 1.1 comfyui-img2img

**功能**: 图生图标准流程

**Python API**:
```python
# 通过 run_python 执行
from comfyui_img2img import build_img2img_workflow

wf = build_img2img_workflow(
    image_path="/path/to/input.png",
    prompt="enhanced version",
    denoise=0.75,
    checkpoint="sdxl_base.safetensors"
)
result = submit_workflow(wf)
```

**核心工作流**:
```
LoadImage → CLIPTextEncode(×2) → CheckpointLoader → KSampler 
→ VAEDecode → SaveImage
```

**文件结构**:
```
~/.openclaw/workspace/skills/comfyui-img2img/
├── SKILL.md
└── references/
    └── img2img_patterns.md
```

**开发时间**: 1 天
**优先级**: P1

---

### 1.2 comfyui-model-manager

**功能**: 模型查询、下载、管理

**Python API**:
```python
# 列出模型
from comfyui_model_manager import list_models, search_models

checkpoints = list_models("checkpoints")
results = search_models("sdxl", model_type="checkpoints")

# 下载模型
from comfyui_model_manager import download_model
download_model(
    url="https://civitai.com/...",
    model_type="loras",
    filename="my_lora.safetensors"
)
```

**核心功能**:
| 功能 | 说明 | 来源 |
|------|------|------|
| 模型列表 | folder_paths 扫描 | 自有 |
| 模型搜索 | CivitAI API 集成 | arbo-mcp + Comfy-Cozy |
| 模型下载 | HTTP 下载 + 进度 | arbo-mcp |
| 模型信息 | 元数据读取 | 自有 |

**文件结构**:
```
~/.openclaw/workspace/skills/comfyui-model-manager/
├── SKILL.md
├── references/
│   ├── civitai_api.md
│   └── model_types.md
└── scripts/
    └── (Python 模块通过 run_python 调用)
```

**开发时间**: 2 天
**优先级**: P1

---

### 1.3 comfyui-hires-fix

**功能**: 高清修复工作流（低分辨率生成 → 放大 → 重采样）

**Python API**:
```python
from comfyui_hires_fix import build_hires_workflow

wf = build_hires_workflow(
    prompt="masterpiece, best quality",
    base_width=512,
    base_height=512,
    upscale_by=2.0,
    upscaler="4x-UltraSharp.pth",
    denoise=0.4
)
```

**核心工作流**:
```
EmptyLatent(512) → KSampler → VAEDecode → UpscaleModelLoader 
→ ImageUpscaleWithModel → VAEEncode → KSampler(0.4 denoise) 
→ VAEDecode → SaveImage
```

**开发时间**: 1 天
**优先级**: P1

---

### 1.4 comfyui-controlnet

**功能**: ControlNet 工作流模板

**支持的预处理器**:
- Canny (边缘检测)
- OpenPose (姿态)
- Depth (深度图)
- MLSD (直线)
- Scribble (涂鸦)
- Segmentation (语义分割)

**Python API**:
```python
from comfyui_controlnet import build_controlnet_workflow

wf = build_controlnet_workflow(
    control_type="canny",
    image_path="/path/to/reference.png",
    prompt="a person dancing",
    checkpoint="sdxl_base.safetensors",
    controlnet_model="controlnet-canny-sdxl.safetensors"
)
```

**文件结构**:
```
~/.openclaw/workspace/skills/comfyui-controlnet/
├── SKILL.md
└── references/
    ├── controlnet_types.md
    └── preprocessor_settings.md
```

**开发时间**: 2 天
**优先级**: P1

---

### 1.5 comfyui-workflow-templates

**功能**: Workflow 模板库管理

**Python API**:
```python
# 列出模板
from comfyui_workflow_templates import list_templates, load_template

templates = list_templates(category="official", tags=["portrait"])
wf = load_template("official/txt2img-sdxl", params={
    "prompt": "a beautiful portrait",
    "checkpoint": "sdxl_base.safetensors"
})

# 保存模板
from comfyui_workflow_templates import save_template
save_template(current_wf, name="my-style", category="user", tags=["anime"])
```

**模板库结构**:
```
~/.openclaw/workspace/skills/comfyui-workflow-templates/
├── SKILL.md
├── templates/
│   ├── official/
│   │   ├── txt2img-basic.json
│   │   ├── txt2img-sdxl.json
│   │   ├── img2img-basic.json
│   │   ├── hires-fix-esrgan.json
│   │   ├── controlnet-canny.json
│   │   ├── controlnet-openpose.json
│   │   ├── inpainting-basic.json
│   │   └── lora-workflow.json
│   ├── marketplace/
│   │   └── (社区分享)
│   └── user/
│       └── (用户自定义)
└── references/
    └── template_format.md
```

**开发时间**: 2 天
**优先级**: P1

---

### 1.6 comfyui-inpainting

**功能**: 局部重绘工作流

**Python API**:
```python
from comfyui_inpainting import build_inpaint_workflow

wf = build_inpaint_workflow(
    image_path="/path/to/image.png",
    mask_path="/path/to/mask.png",  # 或自动生成
    prompt="replace with this",
    denoise=1.0
)
```

**开发时间**: 1 天
**优先级**: P2

---

## 2. 新增 Marketplace Skills

### 2.1 comfyui-node-installer

**功能**: 缺失节点自动检测和安装

**依赖**: ComfyUI-Manager

**Python API**:
```python
from comfyui_node_installer import diagnose_missing_nodes, install_node_package

# 诊断 workflow
missing = diagnose_missing_nodes(workflow_json)
print(f"缺失节点: {missing}")

# 安装节点包
install_node_package("ComfyUI-Manager", "https://github.com/...")
```

**核心逻辑** (从 arbo-mcp-hub 移植):
```python
def find_missing_nodes(workflow, available_nodes):
    """检测 workflow 中缺失的节点类型"""
    missing = []
    for node_id, node_data in workflow.items():
        class_type = node_data.get("class_type")
        if class_type and class_type not in available_nodes:
            missing.append({"id": node_id, "type": class_type})
    return missing
```

**开发时间**: 2 天
**优先级**: P2

---

### 2.2 comfyui-workflow-repair

**功能**: Workflow 自动诊断和修复

**Python API**:
```python
from comfyui_workflow_repair import diagnose_workflow, repair_workflow

# 诊断
report = diagnose_workflow(workflow_json)
print(f"问题: {report['issues']}")

# 自动修复
repaired = repair_workflow(workflow_json, auto_migrate=True)
```

**核心功能**:
| 功能 | 说明 |
|------|------|
| 缺失节点检测 | 对比可用节点列表 |
| 替代方案推荐 | 基于输入输出签名匹配 |
| 已知迁移映射 | 处理节点重命名/废弃 |
| 自动修复 | 替换为推荐的替代节点 |

**开发时间**: 3 天
**优先级**: P2

---

### 2.3 comfyui-civitai

**功能**: CivitAI 深度集成

**Python API**:
```python
from comfyui_civitai import search_models, get_model_info, download_from_civitai

# 搜索
results = search_models(
    query="anime style",
    model_type="LORA",
    sort="Most Downloaded"
)

# 获取详情
info = get_model_info(model_id=12345)

# 下载
download_from_civitai(
    model_id=12345,
    version_id=67890,
    save_path="models/loras/"
)
```

**开发时间**: 2 天
**优先级**: P2

---

## 3. Skill 优先级总表

| 优先级 | Skill 名称 | 分类 | 开发时间 | 依赖 |
|--------|------------|------|----------|------|
| P1 | comfyui-img2img | Official | 1 天 | 无 |
| P1 | comfyui-model-manager | Official | 2 天 | 无 |
| P1 | comfyui-hires-fix | Official | 1 天 | 无 |
| P1 | comfyui-controlnet | Official | 2 天 | 无 |
| P1 | comfyui-workflow-templates | Official | 2 天 | 无 |
| P2 | comfyui-inpainting | Official | 1 天 | 无 |
| P2 | comfyui-node-installer | Marketplace | 2 天 | ComfyUI-Manager |
| P2 | comfyui-workflow-repair | Marketplace | 3 天 | 无 |
| P2 | comfyui-civitai | Marketplace | 2 天 | 无 |

**总计**: 9 个新 Skill，约 16 天开发时间

---

## 4. 开发顺序建议

### Week 1: 核心生成功能
1. `comfyui-img2img` (1 天)
2. `comfyui-hires-fix` (1 天)
3. `comfyui-controlnet` (2 天)

### Week 2: 模型管理 + 模板库
4. `comfyui-model-manager` (2 天)
5. `comfyui-workflow-templates` (2 天)

### Week 3: 高级功能
6. `comfyui-inpainting` (1 天)
7. `comfyui-node-installer` (2 天)

### Week 4: 生态工具
8. `comfyui-workflow-repair` (3 天)
9. `comfyui-civitai` (2 天)

---

## 5. 技术规范检查清单

每个 Skill 开发完成后需检查：

- [ ] SKILL.md 符合 frontmatter 规范
- [ ] 使用预注入变量（S, W, L, client 等）
- [ ] 所有节点类型/参数名动态查询，无硬编码
- [ ] 错误处理完善（try/except + 详细错误信息）
- [ ] 图片返回使用 `[IMAGE:path]` 标记
- [ ] 提供至少 3 个使用示例
- [ ] 文档包含 API 参考和参数说明
- [ ] 代码符合 ArtClaw Python 规范

---

## 6. 与现有 Skill 的关系

```
comfyui-operation-rules (P0, 已有)
         │
         ├── comfyui-context (P0, 已有) ──→ 查询环境信息
         │
         ├── comfyui-workflow-builder (P0, 已有) ──→ 构建 workflow
         │
         ├── comfyui-txt2img (P0, 已有) ──→ 文生图
         │
         ├── comfyui-img2img (P1, 新增) ──→ 图生图
         │
         ├── comfyui-hires-fix (P1, 新增) ──→ 高清修复
         │
         ├── comfyui-controlnet (P1, 新增) ──→ ControlNet
         │
         ├── comfyui-inpainting (P2, 新增) ──→ 局部重绘
         │
         └── comfyui-workflow-templates (P1, 新增) ──→ 模板库

comfyui-model-manager (P1, 新增)
         ├── 模型列表查询
         ├── CivitAI 搜索
         └── 模型下载

comfyui-node-installer (P2, Marketplace)
         └── 依赖 ComfyUI-Manager

comfyui-workflow-repair (P2, Marketplace)
         └── 高级诊断修复
```

---

*文档结束*
