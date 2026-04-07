---
name: sd-material-recipes
description: >
  SD 材质配方系统：常见 PBR 材质的标准节点图搭建指南。
  参考 substance-designer-mcp 的 79 个材质配方。
  Use when AI needs to: (1) create PBR materials, (2) build material graphs,
  (3) follow best practices for material creation.
  Substance Designer only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: substance_designer
---

# SD 材质配方

> 常见 PBR 材质的标准节点图搭建指南。
> ⚠️ **操作前必须先阅读 `sd-operation-rules` 和 `sd-node-ops` Skill。**

---

## 配方设计模式

所有材质配方遵循统一模式：

```
[噪波/纹理源] → [加工处理] → [通道映射] → [PBR 输出]
```

### 通用流程

1. **选择纹理源** — 噪波（Perlin, Cells, Clouds）或基础形状
2. **加工处理** — Levels、Blend、Warp、Blur 等调整
3. **通道映射** — 将处理结果路由到各 PBR 通道
4. **PBR 输出** — BaseColor, Normal, Roughness, Metallic, Height, AO

### 通用工具函数

以下辅助函数用于所有配方：

```python
# ✅ 直接使用预注入变量：sd, app, graph, SDPropertyCategory,
# float2, float4, SDValueFloat, SDValueInt, SDValueString, SDValueFloat4 等
# ❌ 禁止 import sd.api 子模块（会超时死锁）


def create_node(definition_id, x, y, label=None):
    """创建节点并设置位置"""
    node = graph.newNode(definition_id)
    if node is None:
        print(f"错误：无法创建 {definition_id}")
        return None
    node.setPosition(float2(x, y))
    if label:
        print(f"  创建: {label} ({definition_id})")
    return node


def connect(src_node, src_port, dst_node, dst_port):
    """连接两个节点"""
    try:
        conn = src_node.newPropertyConnectionFromId(src_port, dst_node, dst_port)
        return conn is not None
    except Exception as e:
        print(f"连接失败: {e}")
        return False


def set_param(node, param_id, value):
    """安全设置参数"""
    prop = node.getPropertyFromId(param_id, SDPropertyCategory.Input)
    if prop:
        node.setPropertyValue(prop, value)
        return True
    return False


def create_output(usage, label, x, y):
    """创建 PBR 输出节点"""
    node = create_node("sbs::compositing::output", x, y, f"Output: {label}")
    if node:
        id_prop = node.getPropertyFromId("identifier", SDPropertyCategory.Annotation)
        if id_prop:
            node.setPropertyValue(id_prop, SDValueString.sNew(usage))
        lbl_prop = node.getPropertyFromId("label", SDPropertyCategory.Annotation)
        if lbl_prop:
            node.setPropertyValue(lbl_prop, SDValueString.sNew(label))
    return node
```

---

## 配方 1：基础金属 — Steel（钢铁）

### 设计思路

钢铁表面特点：高金属度、低到中等粗糙度、细微划痕纹理、冷色调。

```
Perlin Noise ─┬─→ Levels ──→ Roughness
              │
              ├─→ Gradient Map ──→ BaseColor
              │
              └─→ Normal ──→ Normal

Uniform (1.0) ──→ Metallic
```

### 节点搭建

```python
# === 前置代码（参考通用工具函数）===

if graph is None:
    print("错误：没有打开的图")
else:
    print("=== 开始创建 Steel 材质 ===")
    
    # --- 纹理源 ---
    # 使用 Uniform + Levels 模拟基础噪波（原子节点方案）
    noise_node = create_node("sbs::compositing::uniform", -400, 0, "噪波源")
    
    # --- 加工 ---
    levels_rough = create_node("sbs::compositing::levels", 0, 0, "Levels (Roughness)")
    levels_color = create_node("sbs::compositing::levels", 0, 200, "Levels (Color)")
    gradient_map = create_node("sbs::compositing::gradient", 200, 200, "Gradient Map")
    normal_node = create_node("sbs::compositing::normal", 200, 400, "Normal")
    
    # 金属度 — 纯白（1.0 = 全金属）
    metallic_uniform = create_node("sbs::compositing::uniform", 400, 600, "Metallic Uniform")
    
    # --- PBR 输出 ---
    out_x = 600
    out_basecolor = create_output("basecolor", "BaseColor", out_x, 200)
    out_normal = create_output("normal", "Normal", out_x, 400)
    out_roughness = create_output("roughness", "Roughness", out_x, 0)
    out_metallic = create_output("metallic", "Metallic", out_x, 600)
    
    # --- 连接 ---
    if noise_node and levels_rough:
        connect(noise_node, "unique_filter_output", levels_rough, "input1")
    if noise_node and levels_color:
        connect(noise_node, "unique_filter_output", levels_color, "input1")
    if levels_color and gradient_map:
        connect(levels_color, "unique_filter_output", gradient_map, "input1")
    if noise_node and normal_node:
        connect(noise_node, "unique_filter_output", normal_node, "input1")
    
    # 连接到输出
    if levels_rough and out_roughness:
        connect(levels_rough, "unique_filter_output", out_roughness, "inputNodeOutput")
    if gradient_map and out_basecolor:
        connect(gradient_map, "unique_filter_output", out_basecolor, "inputNodeOutput")
    if normal_node and out_normal:
        connect(normal_node, "unique_filter_output", out_normal, "inputNodeOutput")
    if metallic_uniform and out_metallic:
        connect(metallic_uniform, "unique_filter_output", out_metallic, "inputNodeOutput")
    
    print("=== Steel 材质创建完成 ===")
```

### 参数调整指南

| 参数 | 效果 | 范围 |
|------|------|------|
| Levels 输出范围 (Roughness) | 控制粗糙度区间 | 低值 = 更光滑的金属 |
| Gradient Map 颜色 | 改变金属色调 | 银→蓝灰=钢，暖灰→铁，金色→铜 |
| Normal 强度 | 表面细节深度 | 0.1-0.5 = 微妙，0.5-1.0 = 明显 |

### 变体

- **拉丝金属**：用 Directional Warp 代替普通噪波，产生方向性纹理
- **锈蚀金属**：添加 Grunge Map blend 到 BaseColor 和 Roughness
- **铜/黄铜**：修改 Gradient Map 为暖色调

---

## 配方 2：石材 — Granite（花岗岩）

### 设计思路

花岗岩特点：多色矿物颗粒、中等粗糙度、无金属度、细粒纹理。

```
Cells ──────┬──→ Blend ──→ Height ──→ Normal
            │      ↑                     ↓
Perlin ─────┘      │               Output: Normal
                   │
                   └──→ Gradient Map ──→ BaseColor
                   
Levels (from Blend) ──→ Roughness
```

### 节点搭建

```python
if graph is None:
    print("错误：没有打开的图")
else:
    print("=== 开始创建 Granite 材质 ===")
    
    # --- 纹理源 ---
    cells = create_node("sbs::compositing::uniform", -600, 0, "Cells 替代")
    perlin = create_node("sbs::compositing::uniform", -600, 200, "Perlin 替代")
    
    # --- 混合加工 ---
    blend = create_node("sbs::compositing::blend", -200, 100, "Blend")
    if blend:
        set_param(blend, "blendingmode", SDValueInt.sNew(3))  # Multiply
        set_param(blend, "opacity", SDValueFloat.sNew(0.6))
    
    # --- 通道处理 ---
    # Height
    levels_height = create_node("sbs::compositing::levels", 100, 0, "Levels (Height)")
    # Normal from Height
    normal_node = create_node("sbs::compositing::normal", 300, 0, "Normal")
    # BaseColor
    gradient_map = create_node("sbs::compositing::gradient", 100, 200, "Gradient Map")
    # Roughness
    levels_rough = create_node("sbs::compositing::levels", 100, 400, "Levels (Roughness)")
    
    # 金属度 — 0（非金属）
    metallic_uniform = create_node("sbs::compositing::uniform", 500, 600, "Metallic (0)")
    
    # --- PBR 输出 ---
    out_x = 600
    out_basecolor = create_output("basecolor", "BaseColor", out_x, 200)
    out_normal = create_output("normal", "Normal", out_x, 0)
    out_roughness = create_output("roughness", "Roughness", out_x, 400)
    out_metallic = create_output("metallic", "Metallic", out_x, 600)
    out_height = create_output("height", "Height", out_x, 800)
    
    # --- 连接 ---
    # 源 → Blend
    if cells and blend:
        connect(cells, "unique_filter_output", blend, "source")
    if perlin and blend:
        connect(perlin, "unique_filter_output", blend, "destination")
    
    # Blend → 通道处理
    if blend and levels_height:
        connect(blend, "unique_filter_output", levels_height, "input1")
    if blend and gradient_map:
        connect(blend, "unique_filter_output", gradient_map, "input1")
    if blend and levels_rough:
        connect(blend, "unique_filter_output", levels_rough, "input1")
    
    # Height → Normal
    if levels_height and normal_node:
        connect(levels_height, "unique_filter_output", normal_node, "input1")
    
    # → 输出
    if gradient_map and out_basecolor:
        connect(gradient_map, "unique_filter_output", out_basecolor, "inputNodeOutput")
    if normal_node and out_normal:
        connect(normal_node, "unique_filter_output", out_normal, "inputNodeOutput")
    if levels_rough and out_roughness:
        connect(levels_rough, "unique_filter_output", out_roughness, "inputNodeOutput")
    if metallic_uniform and out_metallic:
        connect(metallic_uniform, "unique_filter_output", out_metallic, "inputNodeOutput")
    if levels_height and out_height:
        connect(levels_height, "unique_filter_output", out_height, "inputNodeOutput")
    
    print("=== Granite 材质创建完成 ===")
```

### 参数调整指南

| 参数 | 效果 |
|------|------|
| Blend 模式/透明度 | 调整两种纹理的混合比例 |
| Gradient Map | 定义矿物颜色（灰白+黑色+粉色 = 花岗岩典型色） |
| Normal 强度 | 颗粒凹凸感 |
| Levels (Roughness) | 整体粗糙度范围（花岗岩通常 0.6-0.9） |

### 变体

- **大理石**：用 Directional Warp 产生流纹，Gradient Map 用白+灰色调
- **砂岩**：更细腻的噪波，暖黄色 Gradient Map
- **板岩**：层状纹理 + 方向性 Warp

---

## 配方 3：布料 — Fabric（织物）

### 设计思路

织物特点：方向性纹理（经纬编织）、高粗糙度、无金属、明显的表面凹凸。

```
Uniform ──→ Directional Warp ──→ Warp ──┬──→ Normal ──→ Output: Normal
                                         │
                                         ├──→ Levels ──→ Roughness
                                         │
                                         └──→ Height

Gradient Map (from Warp) ──→ BaseColor
```

### 节点搭建

```python
if graph is None:
    print("错误：没有打开的图")
else:
    print("=== 开始创建 Fabric 材质 ===")
    
    # --- 纹理源 ---
    base_noise = create_node("sbs::compositing::uniform", -600, 0, "基础噪波")
    warp_noise = create_node("sbs::compositing::uniform", -600, 300, "扭曲噪波")
    
    # --- 方向性扭曲 (模拟编织方向) ---
    dir_warp = create_node("sbs::compositing::directionalwarp", -200, 0, "Directional Warp")
    if dir_warp:
        set_param(dir_warp, "intensity", SDValueFloat.sNew(5.0))
    
    # --- Warp (整体扭曲) ---
    warp = create_node("sbs::compositing::warp", 100, 0, "Warp")
    if warp:
        set_param(warp, "intensity", SDValueFloat.sNew(3.0))
    
    # --- 通道处理 ---
    normal_node = create_node("sbs::compositing::normal", 400, 0, "Normal")
    if normal_node:
        set_param(normal_node, "intensity", SDValueFloat.sNew(8.0))  # 布料需要较强法线
    
    levels_rough = create_node("sbs::compositing::levels", 400, 200, "Levels (Roughness)")
    gradient_map = create_node("sbs::compositing::gradient", 400, 400, "Gradient Map")
    
    # 金属度 — 0
    metallic_uniform = create_node("sbs::compositing::uniform", 600, 600, "Metallic (0)")
    
    # --- PBR 输出 ---
    out_x = 800
    out_basecolor = create_output("basecolor", "BaseColor", out_x, 400)
    out_normal = create_output("normal", "Normal", out_x, 0)
    out_roughness = create_output("roughness", "Roughness", out_x, 200)
    out_metallic = create_output("metallic", "Metallic", out_x, 600)
    out_height = create_output("height", "Height", out_x, 800)
    
    # --- 连接 ---
    # 源 → Directional Warp
    if base_noise and dir_warp:
        connect(base_noise, "unique_filter_output", dir_warp, "input1")
    
    # Directional Warp → Warp
    if dir_warp and warp:
        connect(dir_warp, "unique_filter_output", warp, "input1")
    if warp_noise and warp:
        connect(warp_noise, "unique_filter_output", warp, "input2")
    
    # Warp → 通道处理
    if warp and normal_node:
        connect(warp, "unique_filter_output", normal_node, "input1")
    if warp and levels_rough:
        connect(warp, "unique_filter_output", levels_rough, "input1")
    if warp and gradient_map:
        connect(warp, "unique_filter_output", gradient_map, "input1")
    
    # → 输出
    if gradient_map and out_basecolor:
        connect(gradient_map, "unique_filter_output", out_basecolor, "inputNodeOutput")
    if normal_node and out_normal:
        connect(normal_node, "unique_filter_output", out_normal, "inputNodeOutput")
    if levels_rough and out_roughness:
        connect(levels_rough, "unique_filter_output", out_roughness, "inputNodeOutput")
    if metallic_uniform and out_metallic:
        connect(metallic_uniform, "unique_filter_output", out_metallic, "inputNodeOutput")
    if warp and out_height:
        connect(warp, "unique_filter_output", out_height, "inputNodeOutput")
    
    print("=== Fabric 材质创建完成 ===")
```

### 参数调整指南

| 参数 | 效果 |
|------|------|
| Directional Warp 方向/强度 | 编织方向和密度 |
| Warp 强度 | 织物不规则程度 |
| Normal 强度 | 织物凹凸深度（布料通常 5-15） |
| Gradient Map | 织物颜色 |
| Roughness Levels | 布料通常 0.7-1.0 |

### 变体

- **丝绸**：降低 Roughness (0.3-0.5)，减小 Normal 强度，使用 Anisotropic 着色
- **粗麻布**：增大 Warp 和 Normal 强度，更粗的噪波
- **牛仔布**：添加编织图案叠加（Tile Generator + Blend）

---

## 配方扩展指南

### 如何创建新配方

1. **分析参考材质的物理特性**：
   - 是否金属？ → Metallic 值
   - 粗糙/光滑？ → Roughness 范围
   - 表面细节？ → Normal 强度
   - 颜色特征？ → Gradient Map 设计

2. **选择纹理源**：
   - 有机纹理 → Perlin Noise, Clouds
   - 规则图案 → Cells, Tile Generator
   - 不规则/脏旧 → Grunge Map, BnW Spots
   - 划痕/磨损 → Scratches, Directional Noise

3. **设计处理链**：
   - 单源线性处理 → Source → Process → Output
   - 多源混合 → Sources → Blend → Process → Output
   - 分层细节 → Macro + Meso + Micro 三层叠加

4. **通道映射**：
   - Height 通常来自主纹理源的灰度
   - Normal 从 Height 生成
   - Roughness 和 Height 通常相关但需要 Levels 调整
   - BaseColor 通过 Gradient Map 从灰度映射

### 常见材质 Roughness 参考值

| 材质 | Roughness 范围 | Metallic |
|------|----------------|----------|
| 抛光金属 | 0.05 - 0.15 | 1.0 |
| 拉丝金属 | 0.3 - 0.5 | 1.0 |
| 锈蚀金属 | 0.6 - 0.9 | 0.0 - 1.0 (混合) |
| 光滑塑料 | 0.1 - 0.3 | 0.0 |
| 粗糙塑料 | 0.5 - 0.8 | 0.0 |
| 木材 | 0.4 - 0.7 | 0.0 |
| 石材 | 0.5 - 0.9 | 0.0 |
| 布料 | 0.7 - 1.0 | 0.0 |
| 皮革 | 0.3 - 0.6 | 0.0 |
| 玻璃 | 0.0 - 0.05 | 0.0 |
| 水面 | 0.0 - 0.02 | 0.0 |

---

## ⚠️ 重要提醒

1. **端口名称验证**：配方中使用的端口名（如 `"unique_filter_output"`, `"input1"`）是参考值。实际端口名可能不同，创建后务必用 `node.getProperties(SDPropertyCategory.Output)` 确认。

2. **库节点替代**：配方中部分使用 `uniform` 作为噪波源占位。实际使用时应替换为对应的库节点（Cells, Perlin Noise 等），库节点的端口名需要单独确认。

3. **单线程约束**：所有配方代码必须串行执行，不得并发。

4. **无 Undo**：配方创建后无法一键撤销，建议在空图中测试。
