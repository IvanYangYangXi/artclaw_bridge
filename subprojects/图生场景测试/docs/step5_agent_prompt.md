# Step 5 Agent Prompt — UE 场景生成

你的任务是在 UE 编辑器中根据 3D 坐标数据生成一个风格化海滩微缩场景的布局。使用基础几何体作为占位模型。

## 工具

你可以使用 `run_ue_python` 执行 Python 代码操作 UE 编辑器。预注入变量: `L` = unreal 模块。

## 数据文件

3D 坐标 JSON: `D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\step3_output\step3_3d_coordinates.json`
原始参考图: `D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\clipboard_20260401_104944.png`

## 坐标系映射 (数据 → UE)

```
UE_X = data_Y * 100    # 数据的 Y(depth) → UE 的 X(forward)
UE_Y = data_X * 100    # 数据的 X(right) → UE 的 Y(right)  
UE_Z = ground_z_m * 100 + height_cm / 2   # 底面贴地，pivot 在中心
UE_Yaw = -data_rotation_deg
单位: 1m = 100cm (UE units)
```

## 执行步骤

### Phase A: 放置 3 个标志物验证坐标系

先只放这 3 个物体，确认空间关系正确：

1. **platform_01** (Cube, 沙黄色) — 场景原点
   - 位置: UE(0, 0, 75), 尺寸: (1000, 1200, 150)
   
2. **umbrella_01** (Cone, 红色) — 场景中心锚定物  
   - 位置: UE(137, 44, 110), 尺寸: (150, 150, 220)

3. **lighthouse_01** (Cylinder, 红色) — 最远最高物体
   - 位置: UE(-91, 418, 400), 尺寸: (250, 250, 800)

放置后，设置 viewport camera 到等轴测视角：
- 位置: (-1007, -860, 860)
- Rotation: Pitch=-35, Yaw=45, Roll=0

然后截取 viewport 截图，报告这 3 个物体的相对位置是否看起来合理（platform 在近处中下，umbrella 在其上方偏左，lighthouse 在远处右上角高处）。

### Phase B: 批量生成剩余物体

如果 Phase A 正确，读取 JSON 文件，批量生成所有 14 个地面物体。

对每个物体：
1. 读取 position_m, size_m, rotation_deg, ground_z_m
2. 转换坐标: `ue_x = position_m.y * 100`, `ue_y = position_m.x * 100`, `ue_z = ground_z_m * 100 + size_m.h * 100 / 2`
3. 根据 category 选择几何体:
   - prop/building → Cube 或 Cylinder
   - character → Cylinder (细长)
   - ball 类 → Sphere
   - water → Cube (扁平)
4. 设置 Actor Label = 物体 ID
5. 设置简单材质颜色区分不同分组:
   - beach_area: 沙黄 (0.91, 0.78, 0.56)
   - ocean_area: 蓝色 (0.29, 0.56, 0.85)
   - lighthouse_area: 红色 (0.90, 0.22, 0.27)
   - foreground_decor: 灰色 (0.5, 0.5, 0.5)

跳过 4 个 backdrop 物体 (backdrop_01, sun_01, cloud_01, cloud_02)。

### Phase C: 截图验证

完成后：
1. 设置 viewport 到等轴测视角（同 Phase A 的相机参数）
2. 截取 viewport 截图
3. 与原图对比，报告:
   - 物体相对位置是否匹配
   - 是否有穿插/重叠问题
   - 整体比例感觉是否合理

## 注意事项

- 使用 `unreal.EditorLevelLibrary` 的 `spawn_actor_from_class` 或静态网格体来创建几何体
- Cube 在 UE 中是 `/Engine/BasicShapes/Cube.Cube`，Sphere 是 `Sphere.Sphere` 等
- 设置 Actor Scale 而非直接设置 size：基础几何体默认 100cm，scale = desired_size / 100
- 所有操作在一个 undo transaction 内，方便撤销
- `water_01` 和 `platform_01` 的 estimated size 偏大（是整个区域的估算），实际放置时可适当缩小到视觉合理范围
