---
name: comfyui-workflow-manager
description: >
  ComfyUI Workflow 模板库管理：发现、使用、管理、发布 Workflow 模板。
  支持官方模板、社区模板、个人模板三级体系。
  Use when AI needs to: (1) find and use workflow templates,
  (2) manage personal workflow library,
  (3) publish workflows to community.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 92
---

# ComfyUI Workflow 管理器

> 发现、使用、管理、发布 Workflow 模板。

---

## 预注入变量

`run_python` 已注入：`submit_workflow`, `save_preview`, `client`

---

## 核心功能

### 1. 发现模板

```python
from comfyui_workflow_manager import list_templates

# 列出官方模板
templates = list_templates(source="official", category="txt2img")

# 列出热门社区模板
templates = list_templates(source="marketplace", sort="downloads", limit=10)

# 搜索
templates = list_templates(query="portrait", tags=["sdxl", "realistic"])

for t in templates:
    print(f"{t['name']} - {t['description'][:50]}...")
```

### 2. 使用模板

```python
from comfyui_workflow_manager import run_template

# 一键执行
result = run_template(
    template_id="official/txt2img-sdxl-v1",
    parameters={
        "prompt": "a beautiful sunset",
        "checkpoint": "sdxl_base.safetensors",
        "seed": 42
    }
)

if result.get("images"):
    save_preview(result["images"][0])
```

### 3. 加载并自定义

```python
from comfyui_workflow_manager import load_template

# 加载模板
wf = load_template("official/txt2img-sdxl-v1")

# 自定义修改
wf["2"]["inputs"]["text"] = "my custom prompt"

# 执行
result = submit_workflow(wf)
```

### 4. 管理我的库

```python
from comfyui_workflow_manager import save_to_my_library, list_my_workflows

# 保存当前 workflow
save_to_my_library(
    workflow=current_wf,
    name="我的动漫风格",
    description="调整后的参数",
    tags=["anime", "personal"]
)

# 列出我的 workflows
my_workflows = list_my_workflows()
```

### 5. 收藏模板

```python
from comfyui_workflow_manager import favorite_template, list_favorites

# 收藏
favorite_template("marketplace/awesome-portrait-v2")

# 查看收藏
favorites = list_favorites()
```

---

## 模板分类

```
official/                    # 官方维护
├── txt2img/
│   ├── txt2img-sd15-v1.json
│   ├── txt2img-sdxl-v1.json
│   └── txt2img-flux-v1.json
├── img2img/
├── controlnet/
│   ├── canny-sdxl.json
│   ├── openpose-sdxl.json
│   └── depth-sdxl.json
├── hires-fix/
└── inpainting/

marketplace/                 # 社区分享
├── anime-style/
├── photorealistic/
└── architectural/

user/                        # 个人创建
└── (用户自定义)
```

---

## 完整示例

### 快速开始：使用官方模板

```python
# 1. 浏览可用模板
from comfyui_workflow_manager import list_templates
templates = list_templates(source="official", category="txt2img")

# 2. 选择模板并执行
from comfyui_workflow_manager import run_template
result = run_template(
    template_id="official/txt2img-sdxl-v1",
    parameters={
        "prompt": "masterpiece, best quality, a cat",
        "negative_prompt": "low quality",
        "width": 1024,
        "height": 1024
    }
)

# 3. 查看结果
if result.get("images"):
    save_preview(result["images"][0])
```

### 保存和复用

```python
# 1. 创建一个 workflow
wf = build_custom_workflow(...)

# 2. 保存到个人库
from comfyui_workflow_manager import save_to_my_library
save_to_my_library(
    workflow=wf,
    name="我的专属风格",
    tags=["custom", "favorite"]
)

# 3. 以后快速使用
from comfyui_workflow_manager import load_template
my_wf = load_template("user/我的专属风格")
result = submit_workflow(my_wf)
```

---

## API 参考

### `list_templates(source, category, tags, sort, limit) -> list`

列出模板。

### `get_template_info(template_id) -> dict`

获取模板详情。

### `run_template(template_id, parameters) -> dict`

执行模板。

### `load_template(template_id) -> dict`

加载模板为 workflow dict。

### `save_to_my_library(workflow, name, description, tags) -> str`

保存到个人库。

### `favorite_template(template_id)`

收藏模板。

---

## 模板格式

```json
{
  "id": "official/txt2img-sdxl-v1",
  "name": "SDXL 文生图标准版",
  "version": "1.0.0",
  "description": "标准的 SDXL 文生图 workflow",
  "category": "txt2img",
  "tags": ["sdxl", "official"],
  "author": "ArtClaw",
  "source": "official",
  
  "workflow": {
    "1": {"class_type": "CheckpointLoaderSimple", ...},
    ...
  },
  
  "parameters": [
    {
      "name": "prompt",
      "type": "string",
      "default": "",
      "description": "正向提示词"
    },
    {
      "name": "width",
      "type": "int",
      "default": 1024,
      "min": 512,
      "max": 2048
    }
  ],
  
  "required_models": ["sdxl_base.safetensors"],
  "required_nodes": [],
  
  "preview_image": "preview.png",
  "stats": {
    "downloads": 1000,
    "rating": 4.8
  }
}
```

---

*Skill 版本: 0.1.0*
