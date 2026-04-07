---
name: houdini-simulation
description: >
  Houdini 仿真工作流指南：Pyro/RBD/FLIP/Vellum 的标准搭建流程。
  Use when AI needs to: (1) set up simulations, (2) configure DOPs,
  (3) build Pyro/RBD/FLIP/Vellum setups.
  Houdini only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: houdini
---

# Houdini 仿真工作流指南

Pyro（烟火）、RBD（刚体）、FLIP（流体）、Vellum（柔体/布料）的标准节点搭建流程。

> ⚠️ **仅适用于 Houdini** — 通过 `run_python` 执行，使用 `hou` 模块
>
> 📌 **前置依赖**: 执行任何修改操作前，请先阅读 `houdini-operation-rules` Skill

---

## 通用仿真注意事项

1. **所有仿真操作必须包裹在 undo group 中**
2. **仿真节点链通常为**: Source → Solver → Post-Process → Cache
3. **务必使用 File Cache** 节点缓存仿真结果，避免反复计算
4. **调试时先用低分辨率**，确认效果后再提高分辨率
5. **Houdini 20+ 推荐使用 SOP-level 仿真节点**（而非 DOP Network），更简洁

---

## 1. Pyro 烟火仿真

### 流程: Source → Pyro Solver → Visualize → Cache

```
[Sphere/Source Geometry]
       ↓
[Pyro Source] — 生成密度/温度/燃料体积
       ↓
[Pyro Solver] — 烟火解算
       ↓
[Pyro Post Process] — 后处理（着色等）
       ↓
[File Cache] — 缓存 VDB 到磁盘
```

### Python 代码模板

```python
import hou

with hou.undos.group("ArtClaw: Pyro 仿真搭建"):
    # 创建 geo 节点
    geo = hou.node("/obj").createNode("geo", "pyro_sim")
    for child in geo.children():
        child.destroy()

    # ① 源几何体 - 球体作为火源
    sphere = geo.createNode("sphere", "fire_source")
    sphere.parm("scale").set(0.5)

    # ② Pyro Source - 从几何体生成体积源
    pyro_source = geo.createNode("pyrosource", "pyro_source")
    pyro_source.setInput(0, sphere)
    # 设置为燃烧模式
    pyro_source.parm("mode").set(0)  # Burn

    # ③ Pyro Solver (SOP-level, Houdini 20+)
    pyro_solver = geo.createNode("pyrosolver", "pyro_solver")
    pyro_solver.setInput(0, pyro_source)  # Source 输入

    # 基本参数调整
    pyro_solver.parm("resscale").set(0.5)     # 分辨率缩放（调试用低值）
    pyro_solver.parm("timescale").set(1.0)    # 时间缩放

    # ④ Pyro Post Process - 着色和可视化
    pyro_post = geo.createNode("pyropostprocess", "pyro_post")
    pyro_post.setInput(0, pyro_solver)

    # ⑤ File Cache - 缓存结果
    cache = geo.createNode("filecache", "pyro_cache")
    cache.setInput(0, pyro_post)
    cache.parm("file").set("$HIP/cache/pyro/pyro.$F4.bgeo.sc")
    cache.parm("trange").set(1)  # Render Frame Range

    cache.setDisplayFlag(True)
    cache.setRenderFlag(True)
    geo.layoutChildren()

print("Pyro 仿真节点搭建完成")
print("提示: 点击 Pyro Solver 的 Play 按钮开始仿真")
```

### 备用方案: DOP Network (传统方式)

```python
import hou

with hou.undos.group("ArtClaw: Pyro DOP 搭建"):
    geo = hou.node("/obj").createNode("geo", "pyro_dop")
    for child in geo.children():
        child.destroy()

    # 源几何体
    sphere = geo.createNode("sphere", "source_geo")
    sphere.parm("scale").set(0.3)

    # Volume Rasterize - 把几何体转为体积
    vol_raster = geo.createNode("volumerasterizeattributes", "vol_raster")
    vol_raster.setInput(0, sphere)

    # DOP Network
    dopnet = geo.createNode("dopnet", "pyro_dopnet")

    # 在 DOP 内部创建节点
    smoke_obj = dopnet.createNode("smokeobject", "smoke_object")
    source = dopnet.createNode("volumesource", "volume_source")
    pyro_solver = dopnet.createNode("pyrosolver", "pyro_solver_dop")
    output_dop = dopnet.createNode("output", "output_dop")

    source.setInput(0, smoke_obj)
    pyro_solver.setInput(0, source)
    output_dop.setInput(0, pyro_solver)

    dopnet.layoutChildren()

    # DOP Import - 把仿真结果导回 SOP
    dop_import = geo.createNode("dopimport", "import_sim")
    dop_import.setInput(0, dopnet)

    dop_import.setDisplayFlag(True)
    dop_import.setRenderFlag(True)
    geo.layoutChildren()

print("Pyro DOP 节点搭建完成")
```

---

## 2. RBD 刚体仿真

### 流程: Geometry → Fracture → RBD Solver → Cache

```
[Source Geometry]
       ↓
[RBD Material Fracture] — 碎裂
       ↓
[RBD Bullet Solver] — 刚体解算
       ↓
[File Cache] — 缓存结果
```

### Python 代码模板

```python
import hou

with hou.undos.group("ArtClaw: RBD 仿真搭建"):
    geo = hou.node("/obj").createNode("geo", "rbd_sim")
    for child in geo.children():
        child.destroy()

    # ① 源几何体
    box = geo.createNode("box", "rbd_source")
    box.parm("sizex").set(2)
    box.parm("sizey").set(2)
    box.parm("sizez").set(2)
    box.parmTuple("t").set((0, 3, 0))  # 抬高

    # ② RBD Material Fracture - 碎裂
    fracture = geo.createNode("rbdmaterialfracture", "fracture")
    fracture.setInput(0, box)
    # 碎片数量
    fracture.parm("scatter1_npts").set(30)  # Scatter points 数量

    # ③ 地面（碰撞体）
    ground = geo.createNode("grid", "ground_plane")
    ground.parm("sizex").set(20)
    ground.parm("sizey").set(20)

    # ④ Merge 碎片和地面
    merge = geo.createNode("merge", "merge_inputs")
    merge.setInput(0, fracture)
    merge.setInput(1, ground)

    # ⑤ RBD Bullet Solver (SOP-level, Houdini 20+)
    rbd_solver = geo.createNode("rbdbulletsolver", "rbd_solver")
    rbd_solver.setInput(0, merge)

    # 设置地面为静态
    # 通常通过 Ground Plane 或属性来设定

    # ⑥ File Cache
    cache = geo.createNode("filecache", "rbd_cache")
    cache.setInput(0, rbd_solver)
    cache.parm("file").set("$HIP/cache/rbd/rbd.$F4.bgeo.sc")
    cache.parm("trange").set(1)

    cache.setDisplayFlag(True)
    cache.setRenderFlag(True)
    geo.layoutChildren()

print("RBD 仿真节点搭建完成")
print("提示: 按 Play 播放时间线开始仿真")
```

### 为碎片设置属性

```python
import hou

# 在 fracture 后添加 Attribute Wrangle 设置自定义属性
with hou.undos.group("ArtClaw: RBD 属性设置"):
    geo = hou.node("/obj/rbd_sim")
    fracture = geo.node("fracture")

    # 给碎片添加初始速度
    wrangle = geo.createNode("attribwrangle", "init_velocity")
    wrangle.setInput(0, fracture)
    wrangle.parm("snippet").set('''
// 随机初始速度
v@v = set(fit01(rand(@primnum), -2, 2),
           fit01(rand(@primnum+1), 5, 10),
           fit01(rand(@primnum+2), -2, 2));
''')

print("RBD 属性设置完成")
```

---

## 3. FLIP 流体仿真

### 流程: Source → FLIP Solver → Surface → Cache

```
[Source Geometry]
       ↓
[FLIP Source] — 生成粒子源
       ↓
[FLIP Solver] — 流体解算
       ↓
[Particle Fluid Surface] — 粒子转网格
       ↓
[File Cache] — 缓存结果
```

### Python 代码模板

```python
import hou

with hou.undos.group("ArtClaw: FLIP 仿真搭建"):
    geo = hou.node("/obj").createNode("geo", "flip_sim")
    for child in geo.children():
        child.destroy()

    # ① 流体源几何体
    sphere = geo.createNode("sphere", "fluid_source")
    sphere.parm("scale").set(1.0)
    sphere.parmTuple("t").set((0, 3, 0))  # 抬高让流体下落

    # ② FLIP Source - 将几何体转为 FLIP 粒子源
    flip_source = geo.createNode("flipsource", "flip_source")
    flip_source.setInput(0, sphere)
    flip_source.parm("particlesep").set(0.1)  # 粒子间距（越小越精细）

    # ③ FLIP Solver (SOP-level, Houdini 20+)
    flip_solver = geo.createNode("flipsolver", "flip_solver")
    flip_solver.setInput(0, flip_source)

    # 基本参数
    flip_solver.parm("resscale").set(0.5)     # 分辨率缩放（调试用低值）
    flip_solver.parm("timescale").set(1.0)

    # ④ Particle Fluid Surface - 粒子转网格
    surface = geo.createNode("particlefluidsurface", "fluid_surface")
    surface.setInput(0, flip_solver)
    surface.parm("particlesep").set(0.1)
    surface.parm("voxelscale").set(2.0)       # 体素缩放

    # ⑤ File Cache - 缓存网格
    cache = geo.createNode("filecache", "flip_cache")
    cache.setInput(0, surface)
    cache.parm("file").set("$HIP/cache/flip/flip.$F4.bgeo.sc")
    cache.parm("trange").set(1)

    cache.setDisplayFlag(True)
    cache.setRenderFlag(True)
    geo.layoutChildren()

print("FLIP 仿真节点搭建完成")
print("提示: 先在低分辨率下测试，确认效果后再提高 particlesep")
```

### 添加碰撞体

```python
import hou

with hou.undos.group("ArtClaw: FLIP 碰撞体"):
    geo = hou.node("/obj/flip_sim")
    flip_solver = geo.node("flip_solver")

    # 创建碰撞容器（碗形）
    tube = geo.createNode("tube", "container")
    tube.parm("radscale").set(0)          # 内半径为 0（实心管）
    tube.parm("rad1").set(2)
    tube.parm("rad2").set(2.5)
    tube.parm("height").set(2)
    tube.parm("cap").set(1)               # 封底

    # 连接到 FLIP Solver 的碰撞输入
    # FLIP Solver 的 input 2 通常是碰撞体
    flip_solver.setInput(2, tube)

    geo.layoutChildren()

print("FLIP 碰撞体添加完成")
```

---

## 4. Vellum 柔体/布料仿真

### 流程: Geometry → Vellum Configure → Vellum Solver → Cache

```
[Source Geometry]
       ↓
[Vellum Configure] — 设置约束（布料/柔体/头发）
       ↓
[Vellum Solver] — 柔体解算
       ↓
[Vellum Post Process] — 后处理（可选）
       ↓
[File Cache] — 缓存结果
```

### 布料仿真代码模板

```python
import hou

with hou.undos.group("ArtClaw: Vellum 布料仿真"):
    geo = hou.node("/obj").createNode("geo", "vellum_sim")
    for child in geo.children():
        child.destroy()

    # ① 布料几何体 - 高分辨率网格
    grid = geo.createNode("grid", "cloth_sheet")
    grid.parm("sizex").set(5)
    grid.parm("sizey").set(5)
    grid.parm("rows").set(50)
    grid.parm("cols").set(50)
    grid.parmTuple("t").set((0, 5, 0))  # 抬高

    # ② Vellum Configure Cloth - 设置布料约束
    vellum_cloth = geo.createNode("vellumconstraints", "cloth_config")
    vellum_cloth.setInput(0, grid)
    vellum_cloth.parm("constrainttype").set(0)  # Cloth

    # 布料参数
    # vellum_cloth.parm("stretchstiffness").set(1e+10)   # 拉伸刚度
    # vellum_cloth.parm("bendstiffness").set(1e+5)       # 弯曲刚度

    # ③ 碰撞体 - 球体
    collision_sphere = geo.createNode("sphere", "collision_obj")
    collision_sphere.parm("scale").set(1.5)
    collision_sphere.parmTuple("t").set((0, 2, 0))

    # ④ Vellum Solver
    vellum_solver = geo.createNode("vellumsolver", "vellum_solver")
    # 输入 0: 几何体 + 约束 (从 vellum configure 出来)
    vellum_solver.setInput(0, vellum_cloth, 0)  # Geometry
    vellum_solver.setInput(1, vellum_cloth, 1)  # Constraints
    vellum_solver.setInput(2, collision_sphere)   # Collision geometry

    # Solver 参数
    vellum_solver.parm("substeps").set(5)         # 子步数（越多越稳定）

    # ⑤ Vellum Post Process（可选 - 平滑法线等）
    vellum_post = geo.createNode("vellumpostprocess", "vellum_post")
    vellum_post.setInput(0, vellum_solver)

    # ⑥ File Cache
    cache = geo.createNode("filecache", "vellum_cache")
    cache.setInput(0, vellum_post)
    cache.parm("file").set("$HIP/cache/vellum/cloth.$F4.bgeo.sc")
    cache.parm("trange").set(1)

    cache.setDisplayFlag(True)
    cache.setRenderFlag(True)
    geo.layoutChildren()

print("Vellum 布料仿真节点搭建完成")
```

### Vellum 柔体（Soft Body）

```python
import hou

with hou.undos.group("ArtClaw: Vellum 柔体"):
    geo = hou.node("/obj").createNode("geo", "vellum_soft")
    for child in geo.children():
        child.destroy()

    # 柔体几何体（用四面体化 Tetrahedral）
    sphere = geo.createNode("sphere", "soft_body")
    sphere.parm("scale").set(1.0)
    sphere.parmTuple("t").set((0, 4, 0))

    # 四面体化 - 柔体需要体积网格
    tet = geo.createNode("solidconform", "tetrahedralize")
    tet.setInput(0, sphere)

    # Vellum Configure - Strut Softbody
    vellum_soft = geo.createNode("vellumconstraints", "soft_config")
    vellum_soft.setInput(0, tet)
    vellum_soft.parm("constrainttype").set(1)  # Strut Softbody

    # 地面
    ground = geo.createNode("grid", "ground")
    ground.parm("sizex").set(20)
    ground.parm("sizey").set(20)

    # Vellum Solver
    vellum_solver = geo.createNode("vellumsolver", "solver")
    vellum_solver.setInput(0, vellum_soft, 0)
    vellum_solver.setInput(1, vellum_soft, 1)
    vellum_solver.setInput(2, ground)
    vellum_solver.parm("substeps").set(5)

    # Cache
    cache = geo.createNode("filecache", "soft_cache")
    cache.setInput(0, vellum_solver)
    cache.parm("file").set("$HIP/cache/vellum_soft/soft.$F4.bgeo.sc")
    cache.parm("trange").set(1)

    cache.setDisplayFlag(True)
    cache.setRenderFlag(True)
    geo.layoutChildren()

print("Vellum 柔体仿真节点搭建完成")
```

---

## 仿真调试技巧

| 技巧 | 说明 |
|---|---|
| **低分辨率先行** | `resscale=0.25` 或减少粒子数，确认效果后再提高 |
| **缓存中间结果** | 在仿真链中间插入 File Cache，避免反复计算上游 |
| **查看帧数据** | 暂停播放，逐帧检查仿真状态 |
| **时间缩放** | `timescale` 控制仿真速度，小于 1 减慢，大于 1 加速 |
| **子步数** | 增加 `substeps` 可提高稳定性，但会变慢 |
| **碰撞厚度** | 如果穿模，增加碰撞体的 thickness 参数 |

---

## 仿真类型选择指南

| 效果 | 推荐仿真类型 | 关键节点 |
|---|---|---|
| 烟雾、火焰、爆炸 | **Pyro** | pyrosolver |
| 破碎、碰撞、倒塌 | **RBD** | rbdbulletsolver |
| 水、液体、倾倒 | **FLIP** | flipsolver |
| 布料、旗帜、窗帘 | **Vellum Cloth** | vellumsolver + vellumconstraints |
| 果冻、橡胶、软物体 | **Vellum Soft** | vellumsolver + solidconform |
| 头发、绳索、线缆 | **Vellum Hair** | vellumsolver + vellumconstraints(hair) |
| 沙粒、雪、颗粒 | **Vellum Grains** | vellumsolver + vellumconstraints(grains) |
