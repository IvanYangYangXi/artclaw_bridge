---
name: comfyui-model-manager
description: >
  ComfyUI 模型管理：查询、下载、删除、搜索模型。
  支持 Checkpoints, LoRA, VAE, ControlNet 等所有模型类型。
  Use when AI needs to: (1) list available models,
  (2) download models from CivitAI or HuggingFace,
  (3) manage model files.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 96
---

# ComfyUI 模型管理器

> 管理 ComfyUI 的模型文件：查询、下载、删除。

---

## 预注入变量

`run_python` 已注入：`folder_paths`, `client`

---

## 核心功能

### 1. 列出模型

```python
from comfyui_model_manager import list_models

# 列出所有 checkpoints
checkpoints = list_models("checkpoints")
print(f"找到 {len(checkpoints)} 个 checkpoints")
for ckpt in checkpoints[:10]:
    print(f"  - {ckpt}")

# 列出 LoRA
loras = list_models("loras")
print(f"\n找到 {len(loras)} 个 LoRA")
```

### 2. 搜索模型

```python
from comfyui_model_manager import search_models

# 本地搜索
results = search_models("sdxl", model_type="checkpoints")
print(f"本地找到 {len(results)} 个匹配")
```

### 3. 下载模型

```python
from comfyui_model_manager import download_model

# 从 URL 下载
result = download_model(
    url="https://civitai.com/api/download/models/12345",
    model_type="loras",
    filename="my_lora.safetensors"
)

print(result)
# {
#   "success": True,
#   "path": ".../models/loras/my_lora.safetensors",
#   "size": "145.2 MB"
# }
```

### 4. CivitAI 搜索下载

```python
from comfyui_model_manager import search_civitai, download_from_civitai

# 搜索
results = search_civitai(
    query="anime style",
    model_type="LORA",
    sort="Most Downloaded"
)

# 下载第一个
if results:
    model = results[0]
    download_from_civitai(
        model_id=model["id"],
        save_path=f"models/loras/{model['name']}.safetensors"
    )
```

### 5. 删除模型

```python
from comfyui_model_manager import delete_model

delete_model("old_model.safetensors", model_type="checkpoints")
```

---

## 支持的模型类型

| 类型 | folder_paths 参数 | 说明 |
|------|-------------------|------|
| Checkpoints | `checkpoints` | 主模型 |
| LoRA | `loras` | LoRA 模型 |
| VAE | `vae` | VAE 模型 |
| ControlNet | `controlnet` | ControlNet 模型 |
| CLIP | `clip` | CLIP 模型 |
| CLIP Vision | `clip_vision` | CLIP Vision |
| Upscale | `upscale_models` | 超分模型 |
| Embeddings | `embeddings` | Textual Inversion |

---

## 完整示例

### 下载并使用新模型

```python
# 1. 检查模型是否存在
from comfyui_model_manager import model_exists

if not model_exists("sdxl_anime.safetensors", "checkpoints"):
    print("模型不存在，开始下载...")
    
    # 2. 从 CivitAI 搜索
    from comfyui_model_manager import search_civitai
    results = search_civitai("sdxl anime", model_type="Checkpoint")
    
    if results:
        # 3. 下载
        from comfyui_model_manager import download_from_civitai
        download_from_civitai(
            model_id=results[0]["id"],
            model_type="checkpoints"
        )
else:
    print("模型已存在")

# 4. 在 workflow 中使用
ckpts = folder_paths.get_filename_list("checkpoints")
print(f"可用 checkpoints: {ckpts}")
```

---

## API 参考

### `list_models(model_type: str) -> list`

列出指定类型的所有模型。

### `search_models(keyword: str, model_type: str) -> list`

本地搜索模型。

### `download_model(url: str, model_type: str, filename: str) -> dict`

从 URL 下载模型。

### `search_civitai(query: str, model_type: str, sort: str) -> list`

搜索 CivitAI。

### `download_from_civitai(model_id: int, model_type: str) -> dict`

从 CivitAI 下载。

### `delete_model(filename: str, model_type: str) -> bool`

删除模型。

---

*Skill 版本: 0.1.0*
