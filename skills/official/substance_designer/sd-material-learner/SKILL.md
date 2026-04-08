---
name: sd-material-learner
description: >
  从现成 SD 材质 (.sbs) 中学习节点图结构，提取连接关系和参数，
  生成结构化的材质配方文档。用于逆向学习优质材质的制作方法。
  Use when AI needs to: (1) analyze an existing SD material graph,
  (2) extract node connections and parameters from .sbs files,
  (3) learn material recipes from professional examples,
  (4) understand how specific materials are built in SD.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    software: substance_designer
---

# SD 材质学习

> 从现成材质中逆向学习节点图结构，提取可复用的配方。
> ⚠️ **操作前必须先阅读 `sd-operation-rules`**

---

## 工作流程

1. **选择学习目标** — SD 内置材质或用户提供的 .sbs 文件
2. **加载并分析图结构** — 遍历节点、连接、参数
3. **生成配方文档** — 结构化的节点管线 + 参数 + 通道格式
4. **（可选）验证配方** — 在空图中按配方重建，对比效果

---

## SD 内置材质库路径

```
C:\Program Files\Adobe\Adobe Substance 3D Designer\resources\packages\
├── materials\pbr\          # 完整 PBR 材质（最佳学习素材）
│   ├── wood_american_cherry.sbs
│   ├── metal_002.sbs
│   ├── fabric_002.sbs
│   ├── concrete_002.sbs
│   ├── bricks_001.sbs
│   └── ...
├── noise_perlin_noise.sbs  # 噪波库节点
├── wood_fibers_1.sbs       # 木纹纤维节点
└── ...                     # 其他库节点
```

---

## 分析步骤

### Step 1: 加载 .sbs 包

```python
import os
pm = app.getPackageMgr()

sbs_path = r"C:\Program Files\Adobe\Adobe Substance 3D Designer\resources\packages\materials\pbr\wood_american_cherry.sbs"
pkg = pm.getUserPackageFromFilePath(sbs_path)
if not pkg:
    pkg = pm.loadUserPackage(sbs_path)

# 列出包内所有图
resources = pkg.getChildrenResources(False)
for r in resources:
    print(f"  {r.getIdentifier()} ({r.getClassName()})")
```

### Step 2: 遍历节点

```python
# 选择目标图（通常第一个，或名字匹配的）
target_graph = resources[0]

nodes = list(target_graph.getNodes())
for n in nodes:
    defn = n.getDefinition()
    did = defn.getId() if defn else "?"
    pos = n.getPosition()
    name = did.split("::")[-1] if "::" in did else did
    
    # 库节点实例
    is_instance = (name == "sbscompgraph_instance")
    
    print(f"[{n.getIdentifier()}] {did} @ ({pos.x:.0f},{pos.y:.0f})")
```

### Step 3: 提取连接关系

```python
# 对每个节点，提取输入连接（谁连到了我的哪个端口）
for n in nodes:
    in_props = n.getProperties(SDPropertyCategory.Input)
    if not in_props:
        continue
    for p in in_props:
        pid = p.getId()
        if pid.startswith("$"):
            continue
        conns = n.getPropertyConnections(p)
        if conns and conns.getSize() > 0:
            print(f"  {n.getIdentifier()}.{pid} ← connected")
```

### Step 4: 提取非默认参数

```python
# 对每个节点，提取修改过的参数值
for n in nodes:
    in_props = n.getProperties(SDPropertyCategory.Input)
    if not in_props:
        continue
    for p in in_props:
        pid = p.getId()
        if pid.startswith("$"):
            continue
        # 跳过有连接的端口（值被连接覆盖）
        conns = n.getPropertyConnections(p)
        if conns and conns.getSize() > 0:
            continue
        v = n.getPropertyValue(p)
        if v:
            try:
                val = v.get()
                print(f"  {n.getIdentifier()}.{pid} = {val}")
            except:
                pass
```

### Step 5: 识别输出通道

```python
# 查找 output 节点及其 usage identifier
for n in nodes:
    defn = n.getDefinition()
    did = defn.getId() if defn else ""
    if "output" not in did:
        continue
    ip = n.getPropertyFromId("identifier", SDPropertyCategory.Annotation)
    if ip:
        v = n.getPropertyValue(ip)
        usage = v.get() if v else "?"
        print(f"  Output: {usage}")
```

---

## 输出格式：材质配方文档

分析完成后，生成以下格式的配方文档：

```markdown
# 材质名称

## 来源
- 文件: xxx.sbs
- 图: xxx

## 节点列表
| # | 节点类型 | 位置 | 说明 |
|---|----------|------|------|
| 1 | sbs::compositing::xxx | (x,y) | 功能描述 |

## 连接关系
| 源节点.端口 → 目标节点.端口 | 说明 |
|---------------------------|------|
| perlin.output → levels.input1 | 噪波→色阶调整 |

## 关键参数
| 节点 | 参数 | 值 | 说明 |
|------|------|-----|------|
| levels | levelinlow | 0.1 | 提升暗部 |

## 管线图
(文字描述节点图的整体流向)

## PBR 输出通道
| 通道 | 来源节点 | 格式 |
|------|----------|------|
| BaseColor | blend | 彩色 |
| Normal | normal | 彩色 |
```

---

## 注意事项

1. **大型材质图节点很多**（50-200+），分多次调用分析，每次处理一部分
2. **库节点实例**的 definition_id 是 `sbs::compositing::sbscompgraph_instance`，需要额外查询其内部引用的图名称
3. **FxMap 节点** (`sbs::compositing::fxmaps`) 内部有子图，结构复杂，先跳过
4. **参数值类型多样**：float/int/bool/float4/ColorRGBA，用 `v.get()` 统一获取
5. **连接方向**：通过查询目标节点的输入端口连接来确定，不要从源端口查（方向会翻转）
6. **分析结果保存**：建议保存到 `~/.openclaw/skills/sd-learned-recipes/` 目录下，按材质名命名
