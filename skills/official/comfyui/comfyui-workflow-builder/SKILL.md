---
name: comfyui-workflow-builder
description: >
  ComfyUI Workflow 动态构建指南。节点类型、连接语法、常用管线模板。
  Use when AI needs to: (1) build workflow JSON dynamically,
  (2) understand node connections, (3) use txt2img/img2img templates.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 90
---

# ComfyUI Workflow 构建指南

> ⚠️ **操作前必须先阅读 `comfyui-operation-rules`**

---

## Workflow JSON 结构

```python
workflow = {
    "node_id": {                          # 字符串 ID（"1", "2", ...）
        "class_type": "NodeClassName",     # 节点类型名
        "inputs": {
            "param": value,                # 直接值
            "input": ["other_id", idx]     # 连接: [源节点ID, 输出索引(0-based)]
        }
    }
}
```

**核心规则**:
- Node ID 是**字符串**（`"1"` 不是 `1`）
- 连接语法: `["source_node_id", output_index]`
- 输出索引对应 `RETURN_TYPES` 的顺序（0-based）

---

## 构建步骤

### Step 1: 查询环境

```python
# 查可用模型
ckpts = folder_paths.get_filename_list("checkpoints")
print("Checkpoints:", ckpts)

# 查节点参数（第一次用某节点前必查）
info = nodes.NODE_CLASS_MAPPINGS["KSampler"].INPUT_TYPES()
print(info)
```

### Step 2: 逐步构建 Workflow

```python
import random

ckpt_name = ckpts[0]  # 选第一个模型
seed = random.randint(0, 2**63)

wf = {}
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt_name}}
wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "a beautiful sunset", "clip": ["1", 1]}}
wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "ugly, blurry", "clip": ["1", 1]}}
wf["4"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}}
wf["5"] = {"class_type": "KSampler", "inputs": {
    "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
    "latent_image": ["4", 0], "seed": seed, "steps": 20,
    "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0
}}
wf["6"] = {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}
wf["7"] = {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "ComfyUI"}}
```

### Step 3: 提交并获取结果

```python
result = submit_workflow(wf)
print(f"Prompt ID: {result['prompt_id']}")
print(f"Images: {len(result['images'])}")

# 展示输出
for img in result["images"]:
    img_bytes = client.get_image(img["filename"], img["subfolder"], img["type"])
    save_preview(img_bytes, f"output_{img['node_id']}")
```

---

## 完整模板: txt2img

```
CheckpointLoaderSimple ──MODEL──► KSampler ──LATENT──► VAEDecode ──IMAGE──► SaveImage
        ├──CLIP──► CLIPTextEncode(+) ──CONDITIONING──►   ↑
        ├──CLIP──► CLIPTextEncode(-) ──CONDITIONING──►   ↑
        └──VAE─────────────────────────────────────────► ↑
EmptyLatentImage ──LATENT──────────────────────────────► ↑
```

### 输出索引参考

| 节点 | 输出 0 | 输出 1 | 输出 2 |
|------|--------|--------|--------|
| CheckpointLoaderSimple | MODEL | CLIP | VAE |
| CLIPTextEncode | CONDITIONING | — | — |
| EmptyLatentImage | LATENT | — | — |
| KSampler | LATENT | — | — |
| VAEDecode | IMAGE | — | — |
| VAEEncode | LATENT | — | — |
| LoraLoader | MODEL | CLIP | — |
| LoadImage | IMAGE | MASK | — |

---

## 完整模板: img2img

```python
import random

wf = {}
# 加载模型
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt_name}}
# 加载输入图片（文件名需在 ComfyUI input 目录中）
wf["2"] = {"class_type": "LoadImage", "inputs": {"image": "input_image.png"}}
# 图片 → Latent
wf["3"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}}
# 提示词
wf["4"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "oil painting style", "clip": ["1", 1]}}
wf["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "ugly, blurry", "clip": ["1", 1]}}
# 采样（denoise < 1.0 保留原图结构）
wf["6"] = {"class_type": "KSampler", "inputs": {
    "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
    "latent_image": ["3", 0], "seed": random.randint(0, 2**63),
    "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal",
    "denoise": 0.6  # ⚠️ img2img 关键: 0.3~0.8, 越低越保留原图
}}
wf["7"] = {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}}
wf["8"] = {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "img2img"}}
```

**上传图片到 ComfyUI input 目录**:
```python
with open(r"D:\my_image.png", "rb") as f:
    uploaded_name = client.upload_image(f.read(), "input_image.png")
print(f"Uploaded as: {uploaded_name}")
# 然后在 LoadImage 中使用 uploaded_name
```

---

## 添加 LoRA

LoRA 插入在 Checkpoint 和 CLIPTextEncode 之间：

```python
# 在 Checkpoint 之后、CLIP 编码之前插入 LoRA
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt_name}}
wf["1.5"] = {"class_type": "LoraLoader", "inputs": {
    "model": ["1", 0], "clip": ["1", 1],
    "lora_name": "my_lora.safetensors",
    "strength_model": 0.8, "strength_clip": 0.8
}}
# 后续节点用 LoRA 的输出
wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "...", "clip": ["1.5", 1]}}
# KSampler 也用 LoRA 的 MODEL
wf["5"] = {"class_type": "KSampler", "inputs": {"model": ["1.5", 0], ...}}
```

---

## 常用节点速查

| 类别 | class_type | 说明 |
|------|-----------|------|
| **加载** | `CheckpointLoaderSimple` | 加载 SD 模型 |
| | `LoraLoader` | 加载 LoRA |
| | `LoadImage` | 加载图片 |
| | `VAELoader` | 加载独立 VAE |
| **编码** | `CLIPTextEncode` | 文本→条件 |
| | `VAEEncode` | 图片→Latent |
| | `VAEDecode` | Latent→图片 |
| **采样** | `KSampler` | 标准采样器 |
| | `KSamplerAdvanced` | 高级采样（start/end step） |
| **Latent** | `EmptyLatentImage` | 空 Latent（txt2img） |
| | `LatentUpscale` | Latent 放大 |
| | `LatentComposite` | Latent 合成 |
| **条件** | `ConditioningCombine` | 合并条件 |
| | `ConditioningSetArea` | 区域条件 |
| **输出** | `SaveImage` | 保存图片到 output |
| | `PreviewImage` | 临时预览 |

---

## 结果处理

```python
result = submit_workflow(wf)

# 方式1: 通过 client 下载图片字节
for img in result["images"]:
    img_bytes = client.get_image(img["filename"], img["subfolder"], img["type"])
    save_preview(img_bytes, img["filename"])

# 方式2: 直接用文件路径（如果在同一机器）
import os
output_dir = folder_paths.get_output_directory()
for img in result["images"]:
    path = os.path.join(output_dir, img.get("subfolder", ""), img["filename"])
    if os.path.isfile(path):
        save_preview(path, img["filename"])
```
