---
name: comfyui-hires-fix
description: >
  ComfyUI 高清修复工作流：低分辨率生成 → 放大 → 重采样。
  支持多种放大算法和重采样策略。
  Use when AI needs to: (1) upscale generated images,
  (2) perform high-resolution fix,
  (3) enhance image details.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 95
---

# ComfyUI 高清修复 (Hires Fix)

> 先生成低分辨率图，放大后再重采样，获得高质量大图。

---

## 预注入变量

`run_python` 已注入：`submit_workflow`, `folder_paths`, `save_preview`

---

## 核心概念

高清修复流程：
```
低分辨率生成 → 放大模型 → 高分辨率重采样 → 最终输出
     512²            2x            1024²              1024²
```

**为什么需要 Hires Fix？**
- 直接生成 1024² 容易出畸形
- 先生成 512² 再放大，质量更好
- 可以控制重采样强度（denoise）

---

## 使用方法

### 方法 1: 使用便捷函数

```python
from comfyui_hires_fix import build_hires_workflow

wf = build_hires_workflow(
    prompt="masterpiece, best quality, a beautiful landscape",
    negative_prompt="low quality, blurry",
    checkpoint="sdxl_base.safetensors",
    
    # 基础生成参数
    base_width=512,
    base_height=512,
    base_steps=20,
    
    # 放大参数
    upscale_by=2.0,  # 512x512 → 1024x1024
    upscaler="4x-UltraSharp.pth",  # 放大模型
    
    # 重采样参数
    hires_steps=15,
    hires_denoise=0.4,  # 0.3-0.5 较好
    
    seed=42
)

# 执行
result = submit_workflow(wf)
if result.get("images"):
    save_preview(result["images"][0])
```

### 方法 2: 分步构建（更灵活）

```python
import random

# 1. 基础生成（低分辨率）
wf = {}
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}}
wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}}
wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}}
wf["4"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}}
wf["5"] = {
    "class_type": "KSampler",
    "inputs": {
        "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
        "seed": random.randint(0, 2**32), "steps": 20, "cfg": 7.0,
        "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0
    }
}

# 2. 解码为像素
wf["6"] = {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}

# 3. 放大模型
wf["7"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": "4x-UltraSharp.pth"}}
wf["8"] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["7", 0], "image": ["6", 0]}}

# 4. 重新编码为 latent
wf["9"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["1", 2]}}

# 5. 高分辨率重采样（关键：denoise < 1.0）
wf["10"] = {
    "class_type": "KSampler",
    "inputs": {
        "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["9", 0],
        "seed": random.randint(0, 2**32), "steps": 15, "cfg": 7.0,
        "sampler_name": "euler", "scheduler": "normal", "denoise": 0.4  # 关键参数
    }
}

# 6. 最终解码和保存
wf["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["1", 2]}}
wf["12"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": "hires"}}

result = submit_workflow(wf)
```

---

## 参数调优指南

### upscale_by（放大倍数）

| 倍数 | 用途 | 显存需求 |
|------|------|----------|
| 1.5x | 轻微放大 | 低 |
| 2.0x | 标准高清修复 | 中 |
| 3.0x | 超高清 | 高 |
| 4.0x | 极高分辨率 | 极高 |

### hires_denoise（重采样强度）

| 值 | 效果 | 使用场景 |
|----|------|----------|
| 0.3 | 轻微细化 | 基础图质量已很好 |
| 0.4 | 平衡 | 推荐默认值 |
| 0.5 | 较强重绘 | 需要更多细节 |
| 0.6+ | 强重绘 | 接近重新生成 |

### 放大模型选择

```python
# 列出可用放大模型
upscalers = folder_paths.get_filename_list("upscale_models")
print(upscalers)

# 推荐：
# - 4x-UltraSharp.pth: 通用，锐利
# - 4x-AnimeSharp.pth: 动漫风格
# - 4x_NMKD-Superscale-SP_178000_G.pth: 写实照片
```

---

## 完整示例

### 动漫风格高清修复

```python
from comfyui_hires_fix import build_hires_workflow

wf = build_hires_workflow(
    prompt="masterpiece, best quality, 1girl, anime style, detailed face",
    negative_prompt="lowres, bad anatomy, bad hands, text, error",
    checkpoint="anime_model.safetensors",
    base_width=512,
    base_height=768,  # 竖图
    upscale_by=2.0,
    upscaler="4x-AnimeSharp.pth",  # 动漫专用放大器
    hires_steps=20,
    hires_denoise=0.45,
    seed=42
)

result = submit_workflow(wf)
```

### 写实照片高清修复

```python
wf = build_hires_workflow(
    prompt="professional photo, portrait, 8k uhd, dslr",
    checkpoint="realistic_model.safetensors",
    base_width=640,
    base_height=384,  # 横图
    upscale_by=2.0,
    upscaler="4x_NMKD-Superscale-SP_178000_G.pth",
    hires_denoise=0.35,  # 写实照片用较低 denoise
)

result = submit_workflow(wf)
```

---

## 注意事项

### ⛔ 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| 显存不足 | 分辨率太高 | 降低 base 分辨率或放大倍数 |
| 放大模型未找到 | 模型不在正确目录 | 放入 `models/upscale_models/` |
| 输出模糊 | denoise 太低 | 提高到 0.4-0.5 |
| 输出变形 | denoise 太高 | 降低到 0.3-0.4 |

### 💡 优化建议

1. **显存优化**: 如果显存不足，先用更小的 base 尺寸
2. **质量优化**: 提高 `hires_steps` 到 20-30
3. **速度优化**: 使用更快的 sampler（如 `dpmpp_2m`）

---

*Skill 版本: 0.1.0*
