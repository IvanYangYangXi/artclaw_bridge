# Step 2：语义分组 + 标注图生成 — 可行性分析与执行方案

> 日期: 2026-04-02
> 状态: 分析中
> 输入: Step 1 场景分析 JSON (`scene_analysis_result.json`)
> 输出: 语义分组 JSON + 标注叠加图 + 分组关系图

---

## 1. Step 1 输出质量评估

### 1.1 数据完整性 ✅
- **物体数量**: 18 个，覆盖 5 大类（building/character/prop/terrain_feature/water）
- **置信度**: high=13, medium=4, low=1 — 整体可靠
- **坐标系**: 百分比坐标 (bbox_pct, center_pct, ground_contact_pct)，与图像无关
- **尺寸估算**: 每个物体有 estimated_size_m (w/d/h)，但置信度参差
- **空间关系**: 10 条 spatial_relations + 4 个 group + 3 条透视线

### 1.2 存在的问题
1. **无原始图片**: lobsterai 项目目录里没有找到原始输入图片，后续标注图生成需要图片
2. **尺寸置信度低**: sun_01/cloud/backdrop 等装饰元素尺寸估算不可靠（low confidence）
3. **3D 坐标缺失**: Step 1 只有 2D 百分比坐标，没有 3D 世界坐标 — 这是 Step 3 的工作
4. **相机参数不精确**: pitch=-35°, yaw=45°, FOV=uncertain — 需要 Step 3 精化

### 1.3 结论
Step 1 的数据**足够支撑 Step 2**（语义分组 + 2D 标注），3D 坐标是 Step 3 的事。

---

## 2. Step 2 目标定义

Step 2 的核心任务是**在 Step 1 的 2D 分析基础上，做进一步的语义组织和可视化**，为 Step 3 的 3D 坐标估算提供结构化输入。

### 2.1 输出清单

| # | 输出物 | 格式 | 用途 |
|---|--------|------|------|
| 1 | 语义分组 JSON | `.json` | 按功能区域重新组织物体，定义层级关系 |
| 2 | 2D 标注叠加图 | `.png` | 在原图上叠加 bbox + ID + 分组颜色 |
| 3 | 深度层可视化 | `.png` | 前景/中景/背景 三层分色标注 |
| 4 | 物体关系图 | `.png` | 空间关系的有向图可视化 |

### 2.2 语义分组策略

基于 Step 1 数据，将 18 个物体按**功能区域**重新分组：

```
scene_root
├── beach_area (沙滩主区域)
│   ├── platform_01 (沙滩平台)
│   ├── stairs_01 (台阶)
│   ├── umbrella_01 (遮阳伞)
│   ├── chair_01 (躺椅左)
│   ├── chair_02 (躺椅右)
│   ├── character_01 (坐姿人物)
│   ├── character_02 (行走人物)
│   ├── ball_01 (沙滩球)
│   └── ball_02 (小蓝球)
├── ocean_area (海洋区域)
│   └── water_01 (风格化海浪)
├── lighthouse_area (灯塔区域)
│   ├── lighthouse_01 (灯塔)
│   └── rock_base_01 (岩石基座)
├── sky_backdrop (天空背景)
│   ├── backdrop_01 (背景墙)
│   ├── sun_01 (装饰太阳)
│   ├── cloud_01 (云朵1)
│   └── cloud_02 (云朵2)
└── foreground_decor (前景装饰)
    ├── geo_blocks_01 (几何体块)
    └── rock_01 (装饰岩石)
```

### 2.3 分组依据
- **beach_area**: 以 platform_01 为基座，其上所有交互物体
- **ocean_area**: 独立水体区域
- **lighthouse_area**: lighthouse_01 + rock_base_01 有明确 "on_top_of" 关系
- **sky_backdrop**: 背景墙面及其附着装饰（太阳、云朵）
- **foreground_decor**: 前景装饰性元素，不参与场景交互

---

## 3. 技术方案

### 3.1 语义分组 JSON 生成
- **方法**: 基于 Step 1 的 spatial_relations + depth_layer + 位置邻近度
- **工具**: Python 脚本，纯数据处理
- **依赖**: 仅需 scene_analysis_result.json
- **可行性**: ✅ 完全可行，数据充分

### 3.2 2D 标注图生成
- **方法**: Python + Pillow/matplotlib 在原图上绘制
- **问题**: ⚠️ **需要原始输入图片**
- **备选方案**:
  - A) 找到原始图片路径（询问 Ivan）
  - B) 不依赖原图，生成纯示意图（仅用百分比坐标画 bbox）
  - C) 跳过标注叠加图，只生成布局示意图
- **建议**: 先走方案 B（生成示意图），同时询问原图位置

### 3.3 深度层可视化
- **方法**: 根据 depth_layer (foreground/midground/background) 用不同颜色区域
- **工具**: matplotlib
- **可行性**: ✅ 完全可行

### 3.4 物体关系图
- **方法**: 基于 spatial_relations 构建有向图
- **工具**: Python + graphviz 或 matplotlib
- **可行性**: ✅ 完全可行

---

## 4. 前置条件检查

| 条件 | 状态 | 备注 |
|------|------|------|
| scene_analysis_result.json | ✅ 可用 | 18 个物体完整数据 |
| Python 环境 | 待检查 | 需要 matplotlib, Pillow |
| 原始输入图片 | ⚠️ 缺失 | lobsterai 目录未找到图片文件 |
| 输出目录 | ✅ 已创建 | `subprojects/图生场景测试/` |

---

## 5. 执行计划

### Phase 1: 语义分组 JSON (无依赖，立即可做)
1. 读取 scene_analysis_result.json
2. 按 2.2 策略生成分组结构
3. 为每个分组计算包围盒（合并子对象 bbox）
4. 输出 `step2_semantic_groups.json`

### Phase 2: 可视化图表 (依赖 Phase 1)
1. 生成 2D 布局示意图（百分比坐标空间，不需要原图）
2. 生成深度层分色图
3. 生成物体空间关系图
4. 所有图表输出到 `step2_output/` 目录

### Phase 3: 原图标注 (依赖原始图片)
- 待确认原图路径后，在原图上叠加标注

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 无原始图片 | 无法生成叠加标注图 | 先做示意图，后补原图标注 |
| 百分比坐标精度 | 分组包围盒可能不准 | Step 3 会用透视分析修正 |
| 装饰元素尺寸不可靠 | 影响后续 3D 场景比例 | 在分组中标记 confidence，Step 3 用锚定物校准 |

---

## 7. Step 3 的前瞻评估

Step 2 完成后，Step 3（透视分析 + 坐标系建立）的关键挑战：

1. **等轴测视角特殊性**: pitch=-35°, yaw=45° 的等轴测视角，消失点在无穷远处（平行投影），传统透视分析方法需要适配
2. **缺少明确消失点**: low-poly 风格化场景，边缘线不多，Hough 变换可能检测困难
3. **建议的锚定物**: 选 umbrella_01（尺寸估算 medium confidence, h=2.2m）或 lighthouse_01（h=8.0m）作为尺度参考
4. **等轴测投影矩阵**: 相比透视投影，等轴测的逆投影更简单（无需 FOV），这是利好

> Step 3 技术可行，但需要针对等轴测视角调整传统透视分析流程。
