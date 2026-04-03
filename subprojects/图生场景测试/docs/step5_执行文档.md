# Step 5：UE 场景生成 — 执行文档

> 日期: 2026-04-02
> 执行者: 其他 Agent (通过 UE Editor Python API)
> 工具: `run_ue_python` (unreal module)

## 1. 目标

根据 Step 3+4 的 3D 坐标数据，在 UE 编辑器中生成对应的场景。使用基础几何体（Cube/Sphere/Cylinder 等）作为占位模型，验证空间布局的正确性。

## 2. 输入文件

- **3D 坐标数据**: `D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\step3_output\step3_3d_coordinates.json`
- **原始参考图**: `D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\clipboard_20260401_104944.png`
- **参数汇总**: `D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\step3_output\parameters_summary.csv`

## 3. 坐标系映射 (关键!)

数据坐标系 → UE 坐标系的映射：

| 数据 | UE | 说明 |
|------|----|------|
| X (right) | **Y** | UE 的 Y 轴向右 |
| Y (depth/forward) | **X** | UE 的 X 轴向前 |
| Z (up) | **Z** | 一致 |
| 1 meter | **100 units** | UE 单位是厘米 |

**转换公式:**
```
UE_X = data_Y * 100  (cm)
UE_Y = data_X * 100  (cm)
UE_Z = data_ground_z * 100  (cm)  # 用 ground_z_m，不是 position_m.z
```

> **注意**: `position_m.z` 是物体重心高度（= ground_z + height/2），不是底面高度。
> UE 中 Actor 的位置通常是中心点或 pivot point，需要根据几何体类型调整。

**旋转映射:**
```
UE_Yaw = -data_rotation_deg  (数据中的 rotation 是俯视顺时针，UE Yaw 是逆时针)
```

## 4. 执行策略：两阶段

### Phase A：标志物验证（3-4 个物体 + 相机）

先放置以下标志物，确认坐标系和空间关系正确：

1. **platform_01** — 原点参考，沙滩平台
   - UE pos: (0, 0, 0), size: (1000, 1200, 150)cm
   - 用 Cube, 沙黄色

2. **umbrella_01** — 锚定物，场景中心
   - UE pos: (137, 44, 0), size: (150, 150, 220)cm
   - 用 Cone/Cylinder, 红色

3. **lighthouse_01** — 最远最高物体
   - UE pos: (-91, 418, 0), size: (250, 250, 800)cm
   - 用 Cylinder, 红白色

4. **Camera** — 设置编辑器视口到等轴测视角
   - UE pos: (-1007, -860, 860)cm
   - Rotation: pitch=-35, yaw=45

放置后，将编辑器视口调整到等轴测视角，**截图与原图对比**。如果物体的相对位置关系基本匹配，则进入 Phase B。

### Phase B：批量生成

逐个生成其余 14 个地面物体（跳过 4 个 backdrop 物体）。

每个物体用匹配其形状的基础几何体：
- **umbrella**: Cone
- **chair**: Cube (扁平)
- **character**: Cylinder (细长)
- **ball**: Sphere
- **lighthouse**: Cylinder (高)
- **rock/platform/stairs/geo_blocks**: Cube
- **water**: Cube (扁平, 半透明蓝色)

### 命名规范

Actor Label = 数据中的 ID（如 `umbrella_01`, `chair_01`）

## 5. 物体数据速查

### 地面物体 (14 个)

| ID | UE_X(cm) | UE_Y(cm) | UE_Z(cm) | W(cm) | D(cm) | H(cm) | Yaw | Shape |
|----|----------|----------|----------|-------|-------|-------|-----|-------|
| platform_01 | 0 | 0 | 0 | 1200 | 1000 | 150 | 0 | Cube |
| stairs_01 | 135 | -111 | 50 | 150 | 200 | 100 | 0 | Cube |
| umbrella_01 | 137 | 44 | 0 | 150 | 150 | 220 | 0 | Cone |
| chair_01 | 177 | -25 | 0 | 120 | 60 | 80 | -15 | Cube |
| chair_02 | 93 | 110 | 0 | 120 | 60 | 80 | 10 | Cube |
| character_01 | 19 | 90 | 0 | 50 | 50 | 100 | -90 | Cylinder |
| character_02 | -78 | 179 | 0 | 40 | 50 | 110 | -45 | Cylinder |
| ball_01 | 89 | 13 | 0 | 30 | 30 | 30 | 0 | Sphere |
| ball_02 | -4 | 149 | 0 | 15 | 15 | 15 | 0 | Sphere |
| lighthouse_01 | -91 | 418 | 0 | 250 | 250 | 800 | 0 | Cylinder |
| rock_base_01 | -120 | 367 | 0 | 500 | 600 | 300 | 0 | Cube |
| water_01 | -183 | 183 | 0 | 1200 | 1500 | 200 | 0 | Cube |
| geo_blocks_01 | -75 | 46 | 0 | 100 | 100 | 100 | 0 | Cube |
| rock_01 | -186 | 99 | 0 | 100 | 150 | 100 | 0 | Cube |

### 背景物体 (4 个, Phase B 可选)

| ID | 说明 | 处理 |
|----|------|------|
| backdrop_01 | 天空背景墙 | 大 Plane, 竖直放置 |
| sun_01 | 装饰太阳 | Sphere, 黄色 |
| cloud_01/02 | 装饰云朵 | Cube, 白色 |

### 相机参数

| 参数 | UE 值 |
|------|-------|
| 类型 | Orthographic |
| 位置 | (-1007, -860, 860) cm |
| LookAt | (53, 201, 0) cm |
| Pitch | -35° |
| Yaw | 45° |
| OrthoWidth | 773 cm |

## 6. 验证方法

Phase A 完成后：
1. 设置编辑器 viewport camera 到等轴测参数
2. 截取 viewport 截图
3. 与原图对比物体相对位置关系
4. 如有偏差，报告具体哪些物体位置不对

Phase B 完成后：
1. 重复上述截图对比
2. 检查物体之间是否有穿插/重叠
3. 检查整体场景比例是否合理

## 7. 注意事项

- UE 中 Cube 的 pivot 在中心，所以位置是中心点。Z 坐标用 `ground_z * 100 + height/2` 来让底面贴地
- 颜色只是辅助识别，不需要精确匹配原图
- `water_01` 的 size (15m×12m) 远超场景范围，这是整个海面区域，可以适当缩小到合理范围
- `platform_01` 的 size (12m×10m) 也偏大，是沙滩整体平台，包含了台阶区域
- rotation_deg 对于基础几何体意义有限，主要用于后续替换真实模型时




根据我们的调试过程，正确的坐标系映射是：

```
UE_X = data_Y * 100        # 数据的 Y(depth) → UE 的 X(forward)
UE_Y = data_X * 50         # 数据的 X(right) → UE 的 Y(right)，但要减半
UE_Z = ground_z_m * 100 + size_m.h * 100 / 2  # 底面贴地，pivot 在中心
UE_Yaw = -data_rotation_deg # 旋转方向取反
```

**关键发现：Y 方向需要 *50 而不是 *100**

---