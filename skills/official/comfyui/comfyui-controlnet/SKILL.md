---
name: comfyui-controlnet
description: >
  ComfyUI ControlNet 工作流：Canny、OpenPose、Depth、Lineart 等控制生成。
  Use when AI needs to: (1) control image generation with reference image,
  (2) use ControlNet preprocessors and models,
  (3) build ControlNet workflows.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 94
---

# ComfyUI ControlNet

> 使用 ControlNet 控制图像生成：姿态、边缘、深度等。

---

## 预注入变量

`run_python` 已注入：`submit_workflow`, `folder_paths`, `save_preview`

---

## ControlNet 类型

| 类型 | 预处理器 | 用途 | 适用场景 |
|------|----------|------|----------|
| **Canny** | CannyEdgePreprocessor | 边缘检测 | 保持轮廓结构 |
| **OpenPose** | OpenposePreprocessor | 人体姿态 | 人物动作控制 |
| **Depth** | DepthPreprocessor | 深度图 | 空间关系控制 |
| **Lineart** | LineartPreprocessor | 线稿提取 | 动漫线稿上色 |
| **MLSD** | M-LSDPreprocessor | 直线检测 | 建筑/室内设计 |
| **Scribble** | ScribblePreprocessor | 涂鸦识别 | 草图生成 |
| **Seg** | SemanticSegmentor | 语义分割 | 场景布局控制 |
| **Normal** | NormalMapPreprocessor | 法线贴图 | 3D 表面细节 |

---

## 使用方法

### 方法 1: 使用便捷函数

```python
from comfyui_controlnet import build_controlnet_workflow

wf = build_controlnet_workflow(
    control_type="canny",  # 或 "openpose", "depth", "lineart"
    image_path="reference.png",
    prompt="masterpiece, best quality, a girl standing",
    negative_prompt="low quality",
    checkpoint="sdxl_base.safetensors",
    controlnet_model="controlnet-canny-sdxl.safetensors",
    control_strength=0.8,  # ControlNet 强度
    width=1024,
    height=1024,
    seed=42
)

result = submit_workflow(wf)
if result.get("images"):
    save_preview(result["images"][0])
```

### 方法 2: 分步构建 Canny

```python
import random

wf = {}

# 1. 加载模型
wf["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl.safetensors"}}

# 2. 加载 ControlNet 模型
wf["2"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": "control_v11p_sd15_canny.pth"}}

# 3. 加载参考图
wf["3"] = {"class_type": "LoadImage", "inputs": {"image": "pose_reference.png"}}

# 4. Canny 预处理
wf["4"] = {
    "class_type": "CannyEdgePreprocessor",
    "inputs": {
        "image": ["3", 0],
        "low_threshold": 100,
        "high_threshold": 200
    }
}

# 5. 编码提示词
wf["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "masterpiece, best quality", "clip": ["1", 1]}}
wf["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "low quality", "clip": ["1", 1]}}

# 6. 应用 ControlNet
wf["7"] = {
    "class_type": "ControlNetApply",
    "inputs": {
        "conditioning": ["5", 0],  # 正面提示词
        "control_net": ["2", 0],   # ControlNet 模型
        "image": ["4", 0],         # 预处理后的图像
        "strength": 0.8            # ControlNet 强度
    }
}

# 7. 生成
wf["8"] = {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}}
wf["9"] = {
    "class_type": "KSampler",
    "inputs": {
        "model": ["1", 0],
        "positive": ["7", 0],  # 使用 ControlNet 后的 conditioning
        "negative": ["6", 0],
        "latent_image": ["8", 0],
        "seed": random.randint(0, 2**32),
        "steps": 20,
        "cfg": 7.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 1.0
    }
}

# 8. 解码保存
wf["10"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}}
wf["11"] = {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "controlnet"}}

result = submit_workflow(wf)
```

---

## 不同 ControlNet 详解

### OpenPose（姿态控制）

```python
wf = build_controlnet_workflow(
    control_type="openpose",
    image_path="person_pose.jpg",
    prompt="1girl, standing, casual clothes",
    controlnet_model="control_v11p_sd15_openpose.pth",
    control_strength=1.0  # 姿态通常用较高强度
)
```

**预处理器选项**:
- `OpenposePreprocessor`: 完整姿态（身体+手+脸）
- `OpenposePreprocessorFaceOnly`: 仅面部
- `OpenposePreprocessorHandOnly`: 仅手部

### Depth（深度控制）

```python
wf = build_controlnet_workflow(
    control_type="depth",
    image_path="scene.jpg",
    prompt="landscape, mountains, lake",
    controlnet_model="control_v11f1p_sd15_depth.pth",
    control_strength=0.7
)
```

### Lineart（线稿）

```python
wf = build_controlnet_workflow(
    control_type="lineart",
    image_path="sketch.png",
    prompt="beautiful anime girl, colored",
    controlnet_model="control_v11p_sd15_lineart.pth",
    control_strength=0.9
)
```

---

## 参数调优

### control_strength（控制强度）

| 值 | 效果 |
|----|------|
| 0.5 | 轻微控制，更多自由度 |
| 0.8 | 平衡控制 |
| 1.0 | 强控制，严格遵循参考 |
| 1.2+ | 超强控制，可能过度约束 |

### 预处理器参数

**Canny 阈值**:
```python
# 低阈值 = 更多边缘
"low_threshold": 50,
"high_threshold": 150

# 高阈值 = 仅主要边缘
"low_threshold": 150,
"high_threshold": 250
```

---

## 完整示例

### 人物换装

```python
# 1. 提取人物姿态
# 2. 生成不同服装
wf = build_controlnet_workflow(
    control_type="openpose",
    image_path="original_pose.jpg",
    prompt="1girl, wearing red dress, elegant",
    control_strength=1.0
)
```

### 建筑渲染

```python
wf = build_controlnet_workflow(
    control_type="mlsd",  # 直线检测，适合建筑
    image_path="building_sketch.jpg",
    prompt="modern architecture, glass building, blue sky",
    control_strength=0.9
)
```

### 多 ControlNet 组合

```python
# 同时使用 OpenPose + Canny
from comfyui_controlnet import build_multi_controlnet_workflow

wf = build_multi_controlnet_workflow(
    controls=[
        {"type": "openpose", "image": "pose.jpg", "strength": 1.0},
        {"type": "canny", "image": "outline.jpg", "strength": 0.6}
    ],
    prompt="character in scene",
    checkpoint="model.safetensors"
)
```

---

## 注意事项

### ⛔ 依赖安装

ControlNet 需要安装 `ComfyUI-ControlNet-Aux`:
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Fannovel16/comfyui_controlnet_aux
```

### ⛔ 模型下载

ControlNet 模型需要单独下载：
- 放入 `models/controlnet/`
- 推荐: control_v11p_sd15_*.pth 系列

---

*Skill 版本: 0.1.0*
