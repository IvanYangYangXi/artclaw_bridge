---
name: comfyui-txt2img
description: >
  ComfyUI 文生图标准工作流。checkpoint + CLIP + KSampler + VAEDecode + SaveImage。
  Use when AI needs to: (1) generate images from text prompts,
  (2) tune sampling parameters, (3) add LoRA to generation pipeline.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
---

# ComfyUI 文生图 (txt2img)

> ⚠️ **操作前必须先阅读 `comfyui-operation-rules`**

---

## 完整工作流代码

**可直接复制使用，修改 prompt 和参数即可。**

```python
import random

# Step 1: 查询可用模型
ckpts = folder_paths.get_filename_list("checkpoints")
print("Available checkpoints:")
for c in ckpts:
    print(f"  {c}")
ckpt_name = ckpts[0]  # 选择第一个，或按需指定
print(f"\nUsing: {ckpt_name}")
```

```python
import random

# Step 2: 构建 workflow
ckpt_name = "..."  # 上一步选择的模型名
seed = random.randint(0, 2**63)

wf = {}

# 1. 加载 Checkpoint → MODEL(0), CLIP(1), VAE(2)
wf["1"] = {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {"ckpt_name": ckpt_name}
}

# 2. 正向提示词 → CONDITIONING(0)
wf["2"] = {
    "class_type": "CLIPTextEncode",
    "inputs": {
        "text": "a majestic mountain landscape at golden hour, dramatic clouds, photorealistic, 8k",
        "clip": ["1", 1]
    }
}

# 3. 负向提示词 → CONDITIONING(0)
wf["3"] = {
    "class_type": "CLIPTextEncode",
    "inputs": {
        "text": "ugly, blurry, low quality, deformed, watermark, text",
        "clip": ["1", 1]
    }
}

# 4. 空 Latent → LATENT(0)
wf["4"] = {
    "class_type": "EmptyLatentImage",
    "inputs": {"width": 1024, "height": 1024, "batch_size": 1}
}

# 5. 采样 → LATENT(0)
wf["5"] = {
    "class_type": "KSampler",
    "inputs": {
        "model": ["1", 0],
        "positive": ["2", 0],
        "negative": ["3", 0],
        "latent_image": ["4", 0],
        "seed": seed,
        "steps": 20,
        "cfg": 7.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 1.0
    }
}

# 6. VAE 解码 → IMAGE(0)
wf["6"] = {
    "class_type": "VAEDecode",
    "inputs": {"samples": ["5", 0], "vae": ["1", 2]}
}

# 7. 保存图片
wf["7"] = {
    "class_type": "SaveImage",
    "inputs": {"images": ["6", 0], "filename_prefix": "txt2img"}
}

# Step 3: 提交执行
result = submit_workflow(wf)
print(f"Done! Images: {len(result['images'])}")

# Step 4: 展示结果
for img in result["images"]:
    img_bytes = client.get_image(img["filename"], img["subfolder"], img["type"])
    save_preview(img_bytes, f"txt2img_{img['filename']}")
```

---

## 参数调优指南

### KSampler 参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `steps` | 采样步数 | 20-30（更多=更精细，更慢） |
| `cfg` | 提示词引导强度 | 5-10（过高=过饱和/伪影） |
| `sampler_name` | 采样算法 | 见下表 |
| `scheduler` | 噪声调度 | 见下表 |
| `seed` | 随机种子 | 随机，固定=可复现 |
| `denoise` | 去噪强度 | txt2img 固定 1.0 |

### 采样器选择

| sampler_name | 特点 | 推荐场景 |
|-------------|------|---------|
| `euler` | 快速，稳定 | 通用默认 |
| `euler_ancestral` | 有创造性随机 | 更多变化 |
| `dpmpp_2m` | 高质量，快速 | ⭐ SDXL 推荐 |
| `dpmpp_sde` | 高质量，较慢 | 精细细节 |
| `dpmpp_2m_sde` | 平衡质量/速度 | 通用高质量 |
| `uni_pc` | 少步数高质量 | 10-15 步快速出图 |
| `heun` | 高精度 | 精细控制 |
| `dpm_2` | 经典 DPM | 兼容性好 |
| `dpm_2_ancestral` | DPM + 随机 | 更多创意 |
| `lms` | 线性多步 | 稳定输出 |

### 调度器选择

| scheduler | 特点 |
|-----------|------|
| `normal` | 标准线性调度 |
| `karras` | ⭐ 推荐，噪声过渡更自然 |
| `exponential` | 指数衰减 |
| `sgm_uniform` | SGM 均匀调度 |

---

## 分辨率指南

| 模型 | 推荐分辨率 | 常用宽高比 |
|------|-----------|-----------|
| SD 1.5 | 512×512 | 512×768, 768×512 |
| SDXL | 1024×1024 | 1024×1024, 1216×832, 832×1216 |
| SD 3 | 1024×1024 | 同 SDXL |

**SDXL 常用宽高比**:

| 比例 | 尺寸 | 用途 |
|------|------|------|
| 1:1 | 1024×1024 | 头像、图标 |
| 3:2 | 1216×832 | 横向风景 |
| 2:3 | 832×1216 | 竖向人像 |
| 16:9 | 1344×768 | 宽屏场景 |
| 9:16 | 768×1344 | 手机壁纸 |

---

## 添加 LoRA

在 Checkpoint 和 CLIP 编码之间插入 LoraLoader：

```python
# 查可用 LoRA
loras = folder_paths.get_filename_list("loras")
print("LoRAs:", loras)
```

```python
wf = {}
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt_name}}

# LoRA: 接收 Checkpoint 的 MODEL 和 CLIP，输出增强后的 MODEL(0) 和 CLIP(1)
wf["1.5"] = {"class_type": "LoraLoader", "inputs": {
    "model": ["1", 0], "clip": ["1", 1],
    "lora_name": "my_style.safetensors",
    "strength_model": 0.8,    # 模型影响强度 (0~1)
    "strength_clip": 0.8      # 文本编码影响强度 (0~1)
}}

# 后续节点引用 LoRA 输出（注意改 ID）
wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "...", "clip": ["1.5", 1]}}
wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "...", "clip": ["1.5", 1]}}
# ... EmptyLatentImage 不变
wf["5"] = {"class_type": "KSampler", "inputs": {
    "model": ["1.5", 0],  # ⚠️ 用 LoRA 的 MODEL 输出
    "positive": ["2", 0], "negative": ["3", 0],
    # ...其余不变
}}
```

**多个 LoRA**: 链式连接，每个 LoraLoader 接上一个的 MODEL/CLIP 输出。

---

## Prompt 技巧

### 正向提示词结构

```
[主体描述], [风格], [质量词], [细节]
```

示例：
```
a cyberpunk city at night, neon lights reflecting on wet streets,
cinematic lighting, photorealistic, highly detailed, 8k uhd
```

### 常用质量词

| 类别 | 关键词 |
|------|--------|
| 高质量 | `masterpiece, best quality, highly detailed, 8k uhd` |
| 写实 | `photorealistic, hyperrealistic, raw photo, DSLR` |
| 插画 | `illustration, anime style, digital art` |
| 光照 | `cinematic lighting, dramatic lighting, volumetric lighting, golden hour` |
| 构图 | `wide angle, close-up, bird's eye view, low angle` |

### 负向提示词模板

```
ugly, blurry, low quality, worst quality, deformed, disfigured,
watermark, text, signature, extra limbs, bad anatomy, bad hands
```

---

## 质量调优速查

| 目标 | 调整方法 |
|------|---------|
| 更高质量 | steps 25-40, cfg 7-8, `dpmpp_2m` + `karras` |
| 更快速度 | steps 10-15, `uni_pc` + `normal` |
| 更多细节 | 提高 steps, 加质量词, cfg 适当提高 |
| 减少伪影 | 降低 cfg (5-7), 换 `euler` 采样器 |
| 更有创意 | 用 `_ancestral` 采样器, 不同 seed |
| 复现结果 | 固定 seed + 相同参数 |
