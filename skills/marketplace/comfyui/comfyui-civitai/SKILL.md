---
name: comfyui-civitai
description: >
  ComfyUI CivitAI 集成：搜索、下载 CivitAI 上的模型。
  Use when AI needs to: (1) search models on CivitAI,
  (2) download models from CivitAI,
  (3) browse popular models.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 80
---

# ComfyUI CivitAI 集成

> 搜索和下载 CivitAI 上的模型。

---

## 预注入变量

`run_python` 已注入：`folder_paths`

---

## 核心功能

### 1. 搜索模型

```python
from comfyui_civitai import search_models

results = search_models(
    query="anime style",
    model_type="LORA",  # Checkpoint, LORA, TextualInversion, etc.
    sort="Most Downloaded",  # or "Highest Rated", "Newest"
    limit=10
)

for model in results:
    print(f"{model['name']} by {model['creator']}")
    print(f"  Downloads: {model['downloads']}, Rating: {model['rating']}")
    print(f"  URL: {model['civitai_url']}")
```

### 2. 获取模型详情

```python
from comfyui_civitai import get_model_info

info = get_model_info(model_id=12345)
print(f"Name: {info['name']}")
print(f"Description: {info['description'][:200]}...")
print(f"Versions: {len(info['versions'])}")
```

### 3. 下载模型

```python
from comfyui_civitai import download_model

# 下载最新版本
result = download_model(
    model_id=12345,
    model_type="loras",  # 保存到 models/loras/
    filename="my_lora.safetensors"
)

print(f"Downloaded to: {result['path']}")
```

### 4. 下载特定版本

```python
from comfyui_civitai import download_model_version

result = download_model_version(
    version_id=67890,
    model_type="checkpoints"
)
```

---

## 完整示例

### 搜索并下载 LoRA

```python
from comfyui_civitai import search_models, download_model

# 1. 搜索
results = search_models(
    query="studio ghibli style",
    model_type="LORA",
    sort="Most Downloaded",
    limit=5
)

# 2. 显示结果
for i, model in enumerate(results):
    print(f"{i+1}. {model['name']}")
    print(f"   {model['description'][:100]}...")

# 3. 下载第一个
if results:
    model = results[0]
    print(f"\nDownloading {model['name']}...")
    
    result = download_model(
        model_id=model['id'],
        model_type="loras"
    )
    
    if result['success']:
        print(f"✅ Downloaded to {result['path']}")
    else:
        print(f"❌ Error: {result['error']}")
```

### 批量下载 Checkpoint

```python
from comfyui_civitai import search_models, download_model

# 搜索高质量 checkpoints
results = search_models(
    query="photorealistic",
    model_type="Checkpoint",
    sort="Highest Rated",
    limit=3
)

# 批量下载
for model in results:
    print(f"Downloading {model['name']}...")
    download_model(model['id'], model_type="checkpoints")
```

---

## API 参考

### `search_models(query, model_type, sort, limit) -> list`

搜索 CivitAI 模型。

### `get_model_info(model_id) -> dict`

获取模型详情。

### `download_model(model_id, model_type, filename) -> dict`

下载模型。

### `download_model_version(version_id, model_type) -> dict`

下载特定版本。

---

*Skill 版本: 0.1.0*
