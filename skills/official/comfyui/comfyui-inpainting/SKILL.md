---
name: comfyui-inpainting
description: >
  ComfyUI 局部重绘（Inpainting）：修改图像的特定区域。
  Use when AI needs to: (1) modify part of an image,
  (2) remove or add objects, (3) change clothing or background.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 93
---

# ComfyUI 局部重绘 (Inpainting)

> 修改图像的特定区域，保持其他部分不变。

---

## 预注入变量

`run_python` 已注入：`submit_workflow`, `save_preview`

---

## 核心概念

局部重绘需要：
1. **原图** - 要修改的图像
2. **遮罩 (Mask)** - 标记要修改的区域（白色=修改，黑色=保持）
3. **提示词** - 描述修改后的内容

---

## 使用方法

### 方法 1: 使用便捷函数

```python
from comfyui_inpainting import build_inpaint_workflow

wf = build_inpaint_workflow(
    image_path="original.png",
    mask_path="mask.png",  # 白色区域会被重绘
    prompt="beautiful red dress",  # 修改后的内容
    negative_prompt="low quality",
    checkpoint="sdxl_base.safetensors",
    denoise=1.0,  # 1.0 = 完全重绘遮罩区域
    seed=42
)

result = submit_workflow(wf)
if result.get("images"):
    save_preview(result["images"][0])
```

### 方法 2: 分步构建

```python
import random

wf = {}

# 1. 加载模型
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}}

# 2. 加载原图和遮罩
wf["2"] = {"class_type": "LoadImage", "inputs": {"image": "original.png"}}
wf["3"] = {"class_type": "LoadImageMask", "inputs": {"image": "mask.png", "channel": "alpha"}}

# 3. 编码提示词
wf["4"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "beautiful red dress", "clip": ["1", 1]}}
wf["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "low quality", "clip": ["1", 1]}}

# 4. VAE 编码原图
wf["6"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}}

# 5. 设置潜空间噪波（只在遮罩区域）
wf["7"] = {
    "class_type": "SetLatentNoiseMask",
    "inputs": {
        "samples": ["6", 0],
        "mask": ["3", 0]
    }
}

# 6. 采样（只在遮罩区域重绘）
wf["8"] = {
    "class_type": "KSampler",
    "inputs": {
        "model": ["1", 0],
        "positive": ["4", 0],
        "negative": ["5", 0],
        "latent_image": ["7", 0],
        "seed": random.randint(0, 2**32),
        "steps": 25,
        "cfg": 7.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 1.0  # 只在遮罩区域生效
    }
}

# 7. 解码保存
wf["9"] = {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}}
wf["10"] = {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "inpaint"}}

result = submit_workflow(wf)
```

---

## 遮罩制作

### 使用外部工具
- Photoshop / GIMP
- 在线工具: remove.bg, Photopea

### 自动生成遮罩（简单场景）

```python
from comfyui_inpainting import create_mask_from_color

# 根据颜色范围创建遮罩
mask = create_mask_from_color(
    image_path="original.png",
    target_color="#FF0000",  # 红色区域
    tolerance=30
)
```

---

## 参数调优

### denoise（重绘强度）

| 值 | 效果 | 使用场景 |
|----|------|----------|
| 0.5 | 轻微修改 | 颜色调整 |
| 0.75 | 中等修改 | 纹理变化 |
| 1.0 | 完全重绘 | 替换物体 |

### 边缘羽化

```python
# 使用模糊让过渡更自然
wf["blur_mask"] = {
    "class_type": "ImageBlur",
    "inputs": {
        "image": ["mask", 0],
        "blur_radius": 5
    }
}
```

---

## 完整示例

### 人物换装

```python
wf = build_inpaint_workflow(
    image_path="person.jpg",
    mask_path="clothes_mask.png",  # 只选中衣服区域
    prompt="elegant blue dress, silk texture",
    denoise=0.9
)
```

### 去除物体

```python
wf = build_inpaint_workflow(
    image_path="scene.jpg",
    mask_path="object_mask.png",  # 选中要去除的物体
    prompt="clean background",  # 描述去除后的样子
    denoise=1.0
)
```

### 添加物体

```python
wf = build_inpaint_workflow(
    image_path="room.jpg",
    mask_path="empty_space_mask.png",
    prompt="vintage leather sofa",
    denoise=0.95
)
```

### 面部修复

```python
wf = build_inpaint_workflow(
    image_path="portrait.jpg",
    mask_path="face_mask.png",
    prompt="beautiful detailed face, perfect eyes",
    denoise=0.6,  # 面部用较低 denoise
    checkpoint="face_restoration_model.safetensors"
)
```

---

## 高级技巧

### 渐进式重绘

```python
# 多次轻微重绘，比一次重度重绘更自然
for i in range(3):
    wf = build_inpaint_workflow(
        image_path=current_image,
        mask_path="mask.png",
        prompt="refine details",
        denoise=0.4  # 每次轻度修改
    )
    result = submit_workflow(wf)
    current_image = result["images"][0]
```

### 结合 ControlNet

```python
from comfyui_inpainting import build_inpaint_with_controlnet

wf = build_inpaint_with_controlnet(
    image_path="person.jpg",
    mask_path="clothes_mask.png",
    prompt="red dress",
    control_type="openpose",  # 保持姿态
    control_image="pose_reference.png"
)
```

---

## 注意事项

### ⛔ 遮罩格式

- PNG 格式，带透明通道
- 白色 = 重绘区域
- 黑色 = 保持区域
- 灰色 = 过渡区域

### 💡 提示词技巧

- 描述**修改后的完整内容**，不是仅描述变化
- 包含原图的风格描述
- 使用 `in the style of original` 保持风格一致

---

*Skill 版本: 0.1.0*
