# ComfyUI Skill 体系重构方案

> 基于用户操作逻辑的完整 Skill 生态设计
> 版本: 2.0
> 日期: 2026-04-10

---

## 1. 重新分类：官方 vs 市集

### 1.1 官方 Skills（核心基础设施）

**定义**: 用户日常使用 ComfyUI 的基础能力，不依赖外部服务，稳定性要求高

| Skill | 功能 | 用户场景 | 优先级 |
|-------|------|----------|--------|
| `comfyui-operation-rules` | 操作规则约束 | 所有操作前的必读 | P0 ✅ |
| `comfyui-context` | 环境查询 | 查模型/查节点/查状态 | P0 ✅ |
| `comfyui-workflow-builder` | Workflow 构建指南 | 学习如何连节点 | P0 ✅ |
| `comfyui-txt2img` | 文生图 | 最常用功能 | P0 ✅ |
| `comfyui-img2img` | 图生图 | 第二常用功能 | P1 |
| `comfyui-node-installer` | 节点安装 | 遇到缺失节点时自动修复 | **P1** |
| `comfyui-workflow-repair` | Workflow 修复 | 打开旧 workflow 时自动修复 | **P1** |
| `comfyui-model-manager` | 模型管理 | 查模型/下模型/删模型 | P1 |
| `comfyui-hires-fix` | 高清修复 | 提升分辨率 | P2 |
| `comfyui-controlnet` | ControlNet | 控制生成 | P2 |
| `comfyui-inpainting` | 局部重绘 | 修改局部 | P2 |

### 1.2 市集 Skills（扩展生态）

**定义**: 高级功能、特定场景、可能依赖外部服务、社区驱动

| Skill | 功能 | 用户场景 | 优先级 |
|-------|------|----------|--------|
| `comfyui-civitai` | CivitAI 深度集成 | 搜索/下载社区模型 | P2 |
| `comfyui-prompt-optimize` | Prompt 优化 | 改进提示词质量 | P2 |
| `comfyui-batch-gen` | 批量生成 | 生成系列图 | P2 |
| `comfyui-video` | 视频生成 | AnimateDiff / SVD | P3 |
| `comfyui-3d` | 3D 生成 | Zero123 / Wonder3D | P3 |
| `comfyui-multi-instance` | 多实例管理 | 管理多个 ComfyUI | P3 |

---

## 2. Workflow 模板库 Skill：从用户操作逻辑设计

### 2.1 用户故事

```
作为 ComfyUI 用户，我想要：

1. 【发现】浏览官方和社区分享的 workflow 模板
   → 按分类筛选：文生图 / 图生图 / ControlNet / 视频 / 3D
   → 按标签筛选：SD1.5 / SDXL / Flux / 动漫 / 写实
   → 查看模板详情：预览图、节点数、所需模型

2. 【使用】一键使用模板生成图片
   → 选择模板 → 填写参数（提示词、模型等）→ 执行
   → 或者：加载模板到 ComfyUI 进行自定义修改

3. 【管理】管理我的 workflow 收藏
   → 收藏常用模板
   → 创建个人 workflow 库
   → 版本历史（保存不同版本）

4. 【分享】发布我的 workflow 到社区
   → 导出当前 workflow 为模板
   → 添加说明和预览图
   → 发布到 marketplace

5. 【同步】多设备同步
   → 我的 workflow 库云端同步
   → 团队共享 workflow
```

### 2.2 Skill 架构：`comfyui-workflow-manager`

**统一 Skill 名称**: `comfyui-workflow-manager`（替代原来的 `comfyui-workflow-templates`）

**核心功能模块**:

```
comfyui-workflow-manager/
├── SKILL.md                          # 主文档
├── references/
│   ├── workflow-format.md            # Workflow JSON 格式规范
│   ├── template-catalog.md           # 模板分类体系
│   └── publishing-guide.md           # 发布指南
└── templates/                        # 本地模板缓存
    ├── official/                     # 官方模板（随 Skill 更新）
    ├── marketplace/                  # 市集模板（用户下载）
    └── user/                         # 用户个人模板
```

### 2.3 Python API 设计（通过 run_python 调用）

```python
# ============================================================
# 发现与浏览
# ============================================================

# 列出模板（支持多种筛选）
from comfyui_workflow_manager import list_templates

# 列出官方模板
templates = list_templates(source="official", category="txt2img", model_type="sdxl")

# 列出市集模板（热门）
templates = list_templates(source="marketplace", sort="downloads", limit=20)

# 搜索模板
templates = list_templates(query="portrait photography", tags=["realistic", "sdxl"])

# 获取模板详情
from comfyui_workflow_manager import get_template_info
info = get_template_info(template_id="official/txt2img-sdxl-v1")
print(info)
# {
#   "id": "official/txt2img-sdxl-v1",
#   "name": "SDXL 文生图标准版",
#   "description": "...",
#   "preview_image": "...",
#   "node_count": 7,
#   "required_models": ["sdxl_base.safetensors"],
#   "required_custom_nodes": [],
#   "parameters": ["prompt", "negative_prompt", "seed", ...],
#   "source": "official",
#   "version": "1.0.0",
#   "author": "ArtClaw"
# }


# ============================================================
# 使用模板
# ============================================================

# 方式1: 直接执行（快速模式）
from comfyui_workflow_manager import run_template

result = run_template(
    template_id="official/txt2img-sdxl-v1",
    parameters={
        "prompt": "a beautiful sunset over mountains",
        "negative_prompt": "low quality",
        "checkpoint": "sdxl_base.safetensors",  # 可覆盖默认模型
        "seed": 42
    }
)
# 返回: {"success": True, "images": [...], "prompt_id": "..."}

# 方式2: 加载为 workflow 后自定义（高级模式）
from comfyui_workflow_manager import load_template

wf = load_template("official/txt2img-sdxl-v1")
# 返回 workflow dict，可以修改后再 submit

# 修改参数
wf["2"]["inputs"]["text"] = "my custom prompt"

# 提交执行
result = submit_workflow(wf)


# ============================================================
# 管理我的库
# ============================================================

# 收藏模板
from comfyui_workflow_manager import favorite_template
favorite_template("marketplace/awesome-portrait-v2")

# 列出我的收藏
favorites = list_templates(source="favorites")

# 保存当前 workflow 到我的库
from comfyui_workflow_manager import save_to_my_library
save_to_my_library(
    workflow=current_wf,
    name="我的动漫风格",
    description="调整后的参数",
    tags=["anime", "personal"],
    category="user"
)

# 列出我的库
my_workflows = list_templates(source="user")

# 删除我的 workflow
from comfyui_workflow_manager import delete_user_workflow
delete_user_workflow("user/我的动漫风格")


# ============================================================
# 发布与分享
# ============================================================

# 导出当前 ComfyUI 中的 workflow 为模板
from comfyui_workflow_manager import export_workflow

# 获取当前 workflow（从 ComfyUI 前端或文件）
export_workflow(
    name="超写实肖像工作流",
    description="适合生成高质量人像",
    workflow_data=current_wf,  # 或从文件加载
    preview_image="/path/to/preview.png",
    tags=["portrait", "realistic", "sdxl"],
    target="marketplace"  # 或 "team" 发布到团队
)

# 更新已发布的模板
from comfyui_workflow_manager import update_template
update_template(
    template_id="marketplace/awesome-portrait-v2",
    new_version={...}
)


# ============================================================
# 版本管理
# ============================================================

# 保存 workflow 版本（自动或手动）
from comfyui_workflow_manager import save_version
save_version(
    workflow_id="user/我的动漫风格",
    comment="调整了 CFG 值"
)

# 列出版本历史
from comfyui_workflow_manager import list_versions
versions = list_versions("user/我的动漫风格")

# 回滚到某个版本
from comfyui_workflow_manager import rollback_version
wf = rollback_version("user/我的动漫风格", version_id="v3")
```

### 2.4 模板分类体系

```yaml
# 分类维度1: 功能类型
categories:
  - id: txt2img
    name: 文生图
    description: 从文本生成图像
  - id: img2img
    name: 图生图
    description: 基于参考图生成
  - id: controlnet
    name: ControlNet
    description: 可控生成
  - id: inpainting
    name: 局部重绘
    description: 修改图像局部
  - id: upscale
    name: 高清放大
    description: 提升分辨率
  - id: video
    name: 视频生成
    description: 生成视频
  - id: 3d
    name: 3D生成
    description: 生成3D内容
  - id: workflow-utils
    name: 工作流工具
    description: 辅助工具

# 分类维度2: 模型类型
model_types:
  - sd1.5
  - sdxl
  - flux
  - svd
  - animate-diff

# 分类维度3: 风格
tags:
  - realistic
  - anime
  - painting
  - photography
  - architectural
  - character
  - landscape
  - abstract
```

### 2.5 模板存储后端

**本地存储**:
```
~/.openclaw/workspace/skills/comfyui-workflow-manager/
├── templates/
│   ├── official/          # 随 Skill 更新
│   ├── marketplace/       # 从远程下载缓存
│   └── user/              # 用户个人创建
├── favorites.json         # 收藏列表
└── versions/              # 版本历史
    └── user/
        └── 我的动漫风格/
            ├── v1.json
            ├── v2.json
            └── metadata.json
```

**远程存储**:
- **Official**: 随 ArtClaw Bridge 代码仓库更新
- **Marketplace**: 独立的模板仓库或 CDN
- **Team**: 企业/团队内部 Git 仓库

### 2.6 与现有 Skill 的关系

```
comfyui-workflow-manager (新)
    │
    ├── 发现/浏览 → 调用 comfyui-context 查询环境兼容性
    │
    ├── 使用模板 → 调用 submit_workflow 执行
    │
    ├── 依赖检查 → 调用 comfyui-node-installer 安装缺失节点
    │           → 调用 comfyui-model-manager 下载缺失模型
    │
    ├── workflow 修复 → 调用 comfyui-workflow-repair 自动修复
    │
    └── 发布模板 → 推送到 marketplace 仓库
```

---

## 3. 更多可整合的 Skills

基于 GitHub 搜索，发现以下有价值的项目：

### 3.1 高价值项目

| 项目 | Stars | 功能 | 可整合为 Skill |
|------|-------|------|----------------|
| **ComfyUI-Manager** | 14,175 | 节点管理、模型安装 | 核心依赖，不单独做 Skill |
| **rgthree-comfy** | 2,973 | 快速调整节点、显示优化 | `comfyui-fast-adjust` |
| **ComfyUI-VideoHelperSuite** | 1,579 | 视频加载/保存/处理 | `comfyui-video` |
| **ComfyUI-Crystools** | 1,826 | 系统资源监控、进度显示 | `comfyui-system-monitor` |
| **comfyui-mixlab-nodes** | 1,828 | Workflow-to-APP、GPT集成 | `comfyui-app-builder` |
| **AIGODLIKE-ComfyUI-Studio** | 404 | 模型缩略图、可视化 | `comfyui-model-browser` |

### 3.2 建议新增的 Skills

#### Official（核心）

| Skill | 功能 | 来源 | 优先级 |
|-------|------|------|--------|
| `comfyui-system-monitor` | 系统资源监控、生成进度 | Crystools | P2 |
| `comfyui-fast-adjust` | 快速参数调整、批量修改 | rgthree | P2 |

#### Marketplace（扩展）

| Skill | 功能 | 来源 | 优先级 |
|-------|------|------|--------|
| `comfyui-video` | 视频生成工作流 | VideoHelperSuite | P2 |
| `comfyui-app-builder` | Workflow 转 APP | mixlab | P3 |
| `comfyui-model-browser` | 模型可视化浏览 | AIGODLIKE | P3 |

---

## 4. 完整的 ComfyUI Skill 生态

### 4.1 官方 Skills（12个）

```
comfyui-operation-rules      # 操作规则 ✅
comfyui-context               # 环境查询 ✅
comfyui-workflow-builder      # 构建指南 ✅
comfyui-txt2img               # 文生图 ✅
comfyui-img2img               # 图生图
comfyui-node-installer        # 节点安装 ⭐
comfyui-workflow-repair       # Workflow修复 ⭐
comfyui-model-manager         # 模型管理
comfyui-hires-fix             # 高清修复
comfyui-controlnet            # ControlNet
comfyui-inpainting            # 局部重绘
comfyui-workflow-manager      # Workflow库管理 ⭐
```

### 4.2 市集 Skills（8+个）

```
comfyui-civitai               # CivitAI集成
comfyui-prompt-optimize       # Prompt优化
comfyui-batch-gen             # 批量生成
comfyui-video                 # 视频生成
comfyui-3d                    # 3D生成
comfyui-system-monitor        # 系统监控
comfyui-fast-adjust           # 快速调整
comfyui-app-builder           # APP构建
...
```

---

## 5. 实施优先级（更新）

### Week 1-2: 核心基础设施
1. `comfyui-node-installer` (2天) ⭐
2. `comfyui-workflow-repair` (3天) ⭐
3. `comfyui-workflow-manager` (3天) ⭐

### Week 3-4: 生成功能
4. `comfyui-img2img` (1天)
5. `comfyui-hires-fix` (1天)
6. `comfyui-controlnet` (2天)
7. `comfyui-model-manager` (2天)

### Week 5+: 扩展功能
8. `comfyui-inpainting` (1天)
9. `comfyui-civitai` (2天)
10. 其他 Marketplace Skills

---

## 6. 关键决策

1. **node-installer 和 workflow-repair 作为 Official**
   - 理由：它们是用户使用 ComfyUI 的基础设施，解决"缺失节点"和"workflow 损坏"的核心痛点

2. **workflow-manager 统一模板管理**
   - 发现 → 使用 → 管理 → 发布 → 版本控制，完整生命周期
   - 支持三级存储：official / marketplace / user

3. **新增 system-monitor 和 fast-adjust**
   - 提升用户体验的高价值功能

---

*文档结束*
