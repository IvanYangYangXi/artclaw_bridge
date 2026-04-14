---
name: comfyui-context
description: >
  查询 ComfyUI 上下文：系统信息、模型列表、队列状态、节点类型、工作流历史。
  Use when AI needs to: (1) get system info, (2) list available models,
  (3) check queue status, (4) query node types and schemas, (5) get workflow history.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.2.0
    author: ArtClaw
    dcc: comfyui
    priority: 99
---

# ComfyUI 上下文查询

> 查询 ComfyUI 当前状态：系统、模型、队列、节点类型。
> 所有操作为**只读**，不修改任何内容。

---

## 预注入变量

直接使用，无需 import：
`nodes`, `folder_paths`, `client`, `L` (L.model_management)

---

## 1. 系统信息

```python
stats = client.get_system_stats()
print(f"系统信息: {stats}")

# GPU/VRAM 信息
mm = L.model_management
if mm:
    total = mm.get_total_memory() / (1024**3)
    free = mm.get_free_memory() / (1024**3)
    print(f"VRAM: {free:.1f}GB free / {total:.1f}GB total")
```

---

## 2. 列出可用模型

```python
# Checkpoints（主模型）
ckpts = folder_paths.get_filename_list("checkpoints")
print(f"Checkpoints ({len(ckpts)}):")
for c in ckpts:
    print(f"  {c}")

# LoRA
loras = folder_paths.get_filename_list("loras")
print(f"\nLoRAs ({len(loras)}):")
for l in loras:
    print(f"  {l}")

# VAE
vaes = folder_paths.get_filename_list("vae")
print(f"\nVAEs ({len(vaes)}):")
for v in vaes:
    print(f"  {v}")
```

### 可查询的模型类型

| folder_paths 参数 | 说明 |
|-------------------|------|
| `"checkpoints"` | Stable Diffusion 主模型 |
| `"loras"` | LoRA 模型 |
| `"vae"` | VAE 模型 |
| `"controlnet"` | ControlNet 模型 |
| `"clip"` | CLIP 模型 |
| `"clip_vision"` | CLIP Vision 模型 |
| `"upscale_models"` | 超分辨率模型 |
| `"embeddings"` | Textual Inversion embeddings |
| `"hypernetworks"` | Hypernetwork 模型 |

---

## 3. 队列状态

```python
queue = client.get_queue()
running = queue.get("queue_running", [])
pending = queue.get("queue_pending", [])
print(f"运行中: {len(running)}")
print(f"排队中: {len(pending)}")

# 取消当前任务
# client.cancel_current()

# 清空队列
# client.clear_queue()
```

---

## 4. 列出所有可用节点类型

```python
all_nodes = sorted(nodes.NODE_CLASS_MAPPINGS.keys())
print(f"可用节点类型 ({len(all_nodes)}):")
for name in all_nodes:
    print(f"  {name}")
```

### 按关键词搜索节点

```python
keyword = "sampler"  # 修改为需要搜索的关键词
matches = [n for n in nodes.NODE_CLASS_MAPPINGS.keys() if keyword.lower() in n.lower()]
print(f"包含 '{keyword}' 的节点:")
for m in matches:
    print(f"  {m}")
```

---

## 5. 查询节点参数 Schema

```python
# 查询 KSampler 的输入参数定义
class_name = "KSampler"
NodeClass = nodes.NODE_CLASS_MAPPINGS[class_name]
input_types = NodeClass.INPUT_TYPES()

print(f"=== {class_name} ===")
print(f"RETURN_TYPES: {NodeClass.RETURN_TYPES}")
print(f"FUNCTION: {NodeClass.FUNCTION}")
print(f"CATEGORY: {NodeClass.CATEGORY}")

print("\nRequired inputs:")
for name, spec in input_types.get("required", {}).items():
    print(f"  {name}: {spec}")

if "optional" in input_types:
    print("\nOptional inputs:")
    for name, spec in input_types.get("optional", {}).items():
        print(f"  {name}: {spec}")
```

### 查询输出

```python
# INPUT_TYPES() 返回格式：
# {
#   "required": {
#     "param_name": ("TYPE",),                    # 连接输入
#     "param_name": ("TYPE", {"default": ...}),   # 带默认值
#     "param_name": (["opt1", "opt2"],),           # 枚举选项
#     "param_name": ("INT", {"default": 20, "min": 1, "max": 10000}),  # 数值范围
#   },
#   "optional": { ... }
# }
```

---

## 6. 通过 HTTP API 查询节点信息

```python
# 查询单个节点类型的完整信息（包括输入输出描述）
info = client.get_object_info("KSampler")
print(info)

# 查询所有节点类型（大量数据，谨慎使用）
# all_info = client.get_object_info()
```

---

## 7. 综合环境摘要

一次性获取关键环境信息：

```python
# 系统
mm = L.model_management
if mm:
    print(f"VRAM: {mm.get_free_memory()/(1024**3):.1f}GB / {mm.get_total_memory()/(1024**3):.1f}GB")

# 模型
ckpts = folder_paths.get_filename_list("checkpoints")
loras = folder_paths.get_filename_list("loras")
print(f"\nCheckpoints: {len(ckpts)}")
for c in ckpts[:5]:
    print(f"  {c}")
if len(ckpts) > 5:
    print(f"  ... +{len(ckpts)-5} more")

print(f"\nLoRAs: {len(loras)}")
for l in loras[:5]:
    print(f"  {l}")
if len(loras) > 5:
    print(f"  ... +{len(loras)-5} more")

# 队列
queue = client.get_queue()
print(f"\nQueue: {len(queue.get('queue_running',[]))} running, {len(queue.get('queue_pending',[]))} pending")

# 节点
print(f"Available nodes: {len(nodes.NODE_CLASS_MAPPINGS)}")
```

---

## 8. 查询历史记录

```python
# 获取最近的生成历史
history = client.get_history(limit=10)

for item in history:
    prompt_id = item.get("prompt_id")
    outputs = item.get("outputs", {})
    
    print(f"\nPrompt ID: {prompt_id}")
    print(f"  Status: {item.get('status', 'unknown')}")
    
    # 查找输出图片
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for img in node_output["images"]:
                filename = img.get("filename")
                subfolder = img.get("subfolder", "")
                print(f"  Output: {subfolder}/{filename}")
```

### 获取特定任务的输出

```python
# 通过 prompt_id 查询结果
prompt_id = "your-prompt-id"
history = client.get_history(prompt_id)

if history:
    item = history[0]
    outputs = item.get("outputs", {})
    
    # 提取所有图片路径
    images = []
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for img in node_output["images"]:
                images.append(img)
    
    print(f"找到 {len(images)} 张输出图片")
```

---

## 9. 实用工具函数

### 检查模型是否存在

```python
def check_model_exists(model_name: str, model_type: str = "checkpoints") -> bool:
    """检查模型是否存在"""
    models = folder_paths.get_filename_list(model_type)
    return model_name in models

# 使用
if check_model_exists("sd_xl_base_1.0.safetensors"):
    print("模型存在")
else:
    print("模型不存在，请先下载")
```

### 查找相似节点

```python
def find_similar_nodes(keyword: str, limit: int = 10) -> list:
    """查找与关键词相似的节点"""
    matches = []
    keyword_lower = keyword.lower()
    
    for name in nodes.NODE_CLASS_MAPPINGS.keys():
        if keyword_lower in name.lower():
            matches.append(name)
        if len(matches) >= limit:
            break
    
    return matches

# 使用
sampler_nodes = find_similar_nodes("sampler", limit=5)
print(f"找到采样器节点: {sampler_nodes}")
```

### 获取节点分类列表

```python
def get_node_categories() -> dict:
    """获取节点分类统计"""
    categories = {}
    
    for name, node_class in nodes.NODE_CLASS_MAPPINGS.items():
        category = getattr(node_class, "CATEGORY", "uncategorized")
        if category not in categories:
            categories[category] = []
        categories[category].append(name)
    
    return categories

# 使用
categories = get_node_categories()
for cat, node_list in sorted(categories.items()):
    print(f"{cat}: {len(node_list)} 个节点")
```

---

## 快速参考：client API

| 方法 | 说明 |
|------|------|
| `client.get_system_stats()` | 系统信息（GPU/设备） |
| `client.get_queue()` | 队列状态 |
| `client.get_object_info(class_type?)` | 节点类型信息 |
| `client.list_models(type)` | 列出模型（HTTP API） |
| `client.get_history(limit?, prompt_id?)` | 获取历史记录 |
| `client.cancel_current()` | 取消当前任务 |
| `client.clear_queue()` | 清空队列 |
| `client.check_connection()` | 检查连接状态 |
| `client.upload_image(bytes, name)` | 上传图片 |
| `client.get_image(filename, subfolder, type)` | 下载输出图片 |
