---
name: comfyui-img2img
description: >
  ComfyUI 图生图工作流构建与执行。
  Use when AI needs to: (1) generate image from another image,
  (2) perform image-to-image transformation,
  (3) apply style transfer or enhancement to existing image.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 95
---

# ComfyUI 图生图 (img2img)

> 基于参考图像生成新图像，支持风格迁移、图像增强、局部重绘等。

---

## 预注入变量

`run_python` 已注入以下变量，**直接使用，无需 import**：

| 变量 | 类型 | 说明 |
|------|------|------|
| `S` | `[]` | 无选中概念 |
| `W` | `None` | 无当前文件概念 |
| `L` | ComfyUI Lib | `L.nodes`, `L.folder_paths`, `L.model_management` |
| `nodes` | module | 节点注册表 |
| `folder_paths` | module | 模型/输出路径管理 |
| `client` | ComfyUIClient | HTTP API 客户端 |
| `submit_workflow` | func | 提交 workflow 并等待完成 |
| `save_preview` | func | 保存图片并输出 `[IMAGE:]` 标记 |

---

## 核心工作流

标准的 img2img 流程：

```
LoadImage → CLIPTextEncode(×2) → CheckpointLoader → KSampler 
→ VAEDecode → SaveImage
         ↑
    VAEEncode (将输入图编码为 latent)
```

---

## 使用方法

### 方法 1: 使用便捷函数 (推荐)

```python
# 查询可用模型
ckpts = folder_paths.get_filename_list("checkpoints")
print(f"可用模型: {ckpts[:5]}")

# 构建 img2img workflow
wf = {}

# 1. 加载输入图像
wf["1"] = {
    "class_type": "LoadImage",
    "inputs": {"image": "input_image.png"}  # 图片需在 input 目录
}

# 2. 加载模型
wf["2"] = {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}
}

# 3. 编码提示词
wf["3"] = {
    "class_type": "CLIPTextEncode",
    "inputs": {"text": "masterpiece, best quality, a beautiful landscape", "clip": ["2", 1]}
}
wf["4"] = {
    "class_type": "CLIPTextEncode",
    "inputs": {"text": "low quality, blurry, ugly", "clip": ["2", 1]}
}

# 4. 将输入图编码为 latent
wf["5"] = {
    "class_type": "VAEEncode",
    "inputs": {"pixels": ["1", 0], "vae": ["2", 2]}
}

# 5. KSampler (关键：denoise < 1.0)
wf["6"] = {
    "class_type": "KSampler",
    "inputs": {
        "model": ["2", 0],
        "positive": ["3", 0],
        "negative": ["4", 0],
        "latent_image": ["5", 0],
        "seed": 42,
        "steps": 20,
        "cfg": 7.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 0.75  # 关键参数：0.0=原图, 1.0=完全重绘
    }
}

# 6. 解码
wf["7"] = {
    "class_type": "VAEDecode",
    "inputs": {"samples": ["6", 0], "vae": ["2", 2]}
}

# 7. 保存
wf["8"] = {
    "class_type": "SaveImage",
    "inputs": {"images": ["7", 0], "filename_prefix": "img2img_result"}
}

# 提交执行
result = submit_workflow(wf)
print(f"生成完成: {result}")

# 展示结果
if result.get("images"):
    save_preview(result["images"][0])
```

### 方法 2: 动态构建 (更灵活)

```python
import random

def build_img2img_workflow(
    image_name: str,
    prompt: str,
    negative_prompt: str = "",
    checkpoint: str = "",
    denoise: float = 0.75,
    steps: int = 20,
    cfg: float = 7.0,
    seed: int = -1
) -> dict:
    """构建 img2img workflow"""
    
    # 验证参数
    if not checkpoint:
        ckpts = folder_paths.get_filename_list("checkpoints")
        if not ckpts:
            raise ValueError("没有可用的 checkpoint 模型")
        checkpoint = ckpts[0]
    
    if seed < 0:
        seed = random.randint(0, 2**32 - 1)
    
    wf = {}
    node_id = 1
    
    # Load Image
    wf[str(node_id)] = {
        "class_type": "LoadImage",
        "inputs": {"image": image_name}
    }
    load_image_id = node_id
    node_id += 1
    
    # Checkpoint
    wf[str(node_id)] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint}
    }
    checkpoint_id = node_id
    node_id += 1
    
    # CLIP Encode Positive
    wf[str(node_id)] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": [str(checkpoint_id), 1]}
    }
    positive_id = node_id
    node_id += 1
    
    # CLIP Encode Negative
    wf[str(node_id)] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative_prompt, "clip": [str(checkpoint_id), 1]}
    }
    negative_id = node_id
    node_id += 1
    
    # VAE Encode
    wf[str(node_id)] = {
        "class_type": "VAEEncode",
        "inputs": {
            "pixels": [str(load_image_id), 0],
            "vae": [str(checkpoint_id), 2]
        }
    }
    latent_id = node_id
    node_id += 1
    
    # KSampler
    wf[str(node_id)] = {
        "class_type": "KSampler",
        "inputs": {
            "model": [str(checkpoint_id), 0],
            "positive": [str(positive_id), 0],
            "negative": [str(negative_id), 0],
            "latent_image": [str(latent_id), 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": denoise
        }
    }
    sampler_id = node_id
    node_id += 1
    
    # VAE Decode
    wf[str(node_id)] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [str(sampler_id), 0],
            "vae": [str(checkpoint_id), 2]
        }
    }
    decode_id = node_id
    node_id += 1
    
    # Save Image
    wf[str(node_id)] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": [str(decode_id), 0],
            "filename_prefix": "img2img"
        }
    }
    
    return wf

# 使用
wf = build_img2img_workflow(
    image_name="my_photo.png",
    prompt="oil painting style, masterpiece",
    negative_prompt="photorealistic, 3d render",
    denoise=0.6
)

result = submit_workflow(wf)
if result.get("images"):
    save_preview(result["images"][0])
```

---

## 关键参数说明

### denoise (去噪强度)

| 值 | 效果 | 使用场景 |
|----|------|----------|
| 0.0 | 完全保留原图 | 无变化 |
| 0.25-0.4 | 轻微变化 | 图像增强、轻微风格化 |
| 0.5-0.65 | 中等变化 | 风格迁移、较大的修改 |
| 0.7-0.85 | 较大变化 | 重绘、创意生成 |
| 1.0 | 完全重绘 | 几乎等于 txt2img |

### 常用参数组合

| 场景 | denoise | steps | cfg | 说明 |
|------|---------|-------|-----|------|
| 图像增强 | 0.3 | 15 | 5 | 轻微提升细节 |
| 风格迁移 | 0.6 | 25 | 7 | 保持构图，改变风格 |
| 面部修复 | 0.4 | 20 | 6 | 修复面部瑕疵 |
| 创意重绘 | 0.75 | 30 | 8 | 较大创意空间 |
| 线稿上色 | 0.85 | 25 | 7 | 基于线稿生成彩色图 |

---

## 高级用法

### 1. 结合 LoRA

```python
wf = {}

# Checkpoint
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}}

# LoRA Loader
wf["2"] = {
    "class_type": "LoraLoader",
    "inputs": {
        "model": ["1", 0],
        "clip": ["1", 1],
        "lora_name": "anime_style.safetensors",
        "strength_model": 0.8,
        "strength_clip": 0.8
    }
}

# 后续使用 ["2", 0] 作为 model，["2", 1] 作为 clip
# ... (img2img 流程)
```

### 2. 结合 ControlNet

```python
# 先加载 ControlNet 模型
wf["cn"] = {
    "class_type": "ControlNetLoader",
    "inputs": {"control_net_name": "control_v11p_sd15_canny.pth"}
}

# 预处理图像（如 Canny 边缘检测）
wf["preprocess"] = {
    "class_type": "CannyEdgePreprocessor",
    "inputs": {"image": ["load_image", 0], "low_threshold": 100, "high_threshold": 200}
}

# 应用 ControlNet
wf["apply_cn"] = {
    "class_type": "ControlNetApply",
    "inputs": {
        "conditioning": ["positive_encode", 0],
        "control_net": ["cn", 0],
        "image": ["preprocess", 0],
        "strength": 0.8
    }
}

# 使用 ["apply_cn", 0] 作为 positive conditioning
```

### 3. 批量处理

```python
import os

input_dir = folder_paths.get_input_directory()
input_images = [f for f in os.listdir(input_dir) if f.endswith((".png", ".jpg"))]

for img_name in input_images[:5]:  # 处理前5张
    wf = build_img2img_workflow(
        image_name=img_name,
        prompt="oil painting style",
        denoise=0.5
    )
    result = submit_workflow(wf)
    print(f"处理完成: {img_name}")
```

---

## 注意事项

### ⛔ 绝对禁止

| 规则 | 说明 |
|------|------|
| NEVER 硬编码模型名 | 必须先 `folder_paths.get_filename_list("checkpoints")` |
| NEVER 假设图片存在 | 先确认图片在 input 目录 |
| NEVER denoise > 1.0 或 < 0.0 | 有效范围是 0.0-1.0 |
| NEVER 忘记 VAEEncode | img2img 必须将图片编码为 latent |

### ⚠️ 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 输出图和输入图一样 | denoise=0 | 提高 denoise 到 0.3+ |
| 输出图完全不像原图 | denoise=1.0 | 降低 denoise 到 0.6-0.8 |
| 图片加载失败 | 图片不在 input 目录 | 将图片放入 ComfyUI/input/ |
| 模型加载失败 | 模型名错误 | 使用 `folder_paths` 查询 |

---

## 参考

- [comfyui-workflow-builder](comfyui-workflow-builder) - Workflow 构建通用指南
- [comfyui-controlnet](comfyui-controlnet) - ControlNet 工作流
- [comfyui-hires-fix](comfyui-hires-fix) - 高清修复

---

*Skill 版本: 0.1.0*
