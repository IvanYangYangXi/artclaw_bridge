---
name: ue57-viewport-capture
description: >
  Capture UE viewport screenshots (color, depth, normal buffers) and build AI
  analysis context. Use when AI needs to: (1) take a screenshot of the current
  viewport, (2) capture depth/normal maps alongside color, (3) analyze scene
  composition/lighting/performance visually, (4) get viewport image + camera
  transform for scene analysis. NOT for: runtime game screenshots, cinematic
  rendering, Sequencer captures.
metadata:
  artclaw:
    author: ArtClaw
    software: unreal_engine
    version: 1.0.0
---

# UE 视口截图与场景分析

截取 UE 编辑器视口画面（支持颜色/深度/法线等多 Buffer），收集相机变换和场景元数据，构建 AI 视觉分析上下文。

## 调用方式

通过 `run_ue_python` 执行 Python 代码。所有函数在 `__init__.py` 中定义。

---

## 核心概念

### Buffer 类型

| Buffer | 说明 | 格式 | 用途 |
|--------|------|------|------|
| `color` | 最终渲染画面 (LDR) | JPG | 默认，通用分析 |
| `base_color` | 基础颜色（无光照） | JPG | 材质/贴图分析 |
| `depth` | 场景深度 | PNG | 空间关系、遮挡分析 |
| `normal` | 世界法线 | PNG | 几何质量、表面朝向 |
| `hdr` | HDR 颜色 | EXR | 曝光/色调分析 |

### 分析模式

| Mode | 说明 |
|------|------|
| `general` | 综合分析（内容、构图、光照、颜色、优化） |
| `composition` | 构图分析（三分法、视觉焦点、空间层次） |
| `lighting` | 光照分析（光源、阴影、GI、色温） |
| `performance` | 性能分析（过度绘制、LOD、光源数量） |
| `color` | 色彩分析（色调、配色、后处理） |
| `custom` | 自定义分析（需提供 custom_prompt） |

### 分辨率策略

- **截图分辨率** (`quick_capture`): 1920×1080，保证画面质量
- **分析分辨率** (`quick_analyze`): 1024×576，节省 token（颜色 JPG ~49KB，三 buffer 合计 ~233KB base64）
- 颜色类 buffer 用 JPG 压缩（quality=85），深度/法线用 PNG 保持精度

---

## 操作示例

### 模块导入（每次使用前）

```python
import importlib, sys
skill_path = r"C:\Users\yangjili\.openclaw\workspace\skills\ue57_viewport_capture"
if skill_path not in sys.path:
    sys.path.insert(0, skill_path)
if "ue57_viewport_capture" in sys.modules:
    importlib.reload(sys.modules["ue57_viewport_capture"])
from ue57_viewport_capture import quick_capture, quick_analyze, capture_viewport_scenecapture, cleanup_captures
```

### 1. 快速截图（全分辨率）

```python
from ue57_viewport_capture import quick_capture

result = quick_capture()                              # 仅颜色
result = quick_capture(buffers=["color", "depth", "normal"])  # 多 buffer

print(result["images"])   # {"color": "D:/.../capture_xxx_color.jpg"}
print(result["camera"])   # {"location": {...}, "rotation": {...}}
```

### 2. AI 分析截图（小分辨率，省 token）

```python
from ue57_viewport_capture import quick_analyze

# 综合分析
context = quick_analyze(mode="general")

# 光照分析（含深度）
context = quick_analyze(mode="lighting", buffers=["color", "depth"])

# 性能分析（全 buffer）
context = quick_analyze(mode="performance", buffers=["color", "depth", "normal"])

# 自定义分析
context = quick_analyze(
    mode="custom",
    buffers=["color"],
    custom_prompt="请分析这个场景是否适合作为恐怖游戏的关卡。"
)
```

### 3. AI 拿到 context 后的使用方式

`quick_analyze` 返回的 context 包含：

```python
context = {
    "images_base64": {"color": "base64...", "depth": "base64...", ...},
    "camera": {"location": {"x":..., "y":..., "z":...}, "rotation": {...}},
    "scene_stats": {"total_actors": 128, "lights": [...], "by_class": {...}},
    "analysis_prompt": "预构建的分析指引文本",
    "mode": "general",
    "resolution": [1024, 576],
}
```

AI 应将 `images_base64` 中的图片作为视觉输入，结合 `analysis_prompt` 和 `scene_stats` 进行分析。

### 4. 自定义分辨率截图

```python
from ue57_viewport_capture import capture_viewport_scenecapture

result = capture_viewport_scenecapture(
    resolution=(2560, 1440),
    buffers=["color", "normal"],
    filename_prefix="my_scene",
)
```

### 5. 清理旧截图

```python
from ue57_viewport_capture import cleanup_captures
deleted = cleanup_captures(max_age_hours=24)
```

---

## 输出目录

`{ProjectDir}/Saved/ViewportCaptures/`

文件命名: `capture_{timestamp}_{buffer}.jpg|png|exr`

---

## 技术细节

### 实现流程

```
1. 读取当前视口相机位置/旋转
2. 生成临时 SceneCapture2D Actor（与视口相机同位置）
3. 创建 RenderTarget（RGBA8 / RGBA16F）
4. 设置 CaptureSource（Color/Depth/Normal 等）
5. capture_scene() 即时渲染
6. export_to_disk() 导出图片
7. 清理临时 Actor 和 RenderTarget
```

### 注意事项

- SceneCapture2D 渲染结果可能与视口略有差异（后处理、AA 等）
- 深度图和法线图为特殊编码，需要 AI 理解其含义
- 多 Buffer 截图会依次创建/销毁临时 Actor
- HDR buffer 只能导出为 EXR 格式
- UE Python 环境无 PIL/OpenCV，压缩通过小分辨率+JPG 实现
