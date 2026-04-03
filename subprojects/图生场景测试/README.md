# 图生场景测试 — 2D 概念图 → UE 3D 场景

> 子项目路径: `D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试`
> 开始日期: 2026-04-02

## 目标
从一张 2D 概念原画/截图出发，通过多步 AI 分析管线，自动生成 UE5 3D 场景。

## 管线步骤

| Step | 名称 | 状态 | 说明 |
|------|------|------|------|
| 1 | 场景视觉分析 | ✅ 完成 | AI 视觉分析 → 结构化 JSON (18 物体) |
| 2 | 语义分组 + 标注图 | ✅ 完成 | 5 个功能区域分组 + 4 张可视化 |
| 3+4 | 逆投影 + 布局验证 | ✅ 完成 | 等轴测 Rz(45)·Rx(-35), scale=108 px/m |
| 5 | UE 场景生成 | ⏳ 待执行 | 标志物先行 → 批量生成 → 截图验证 |

## 目录结构
```
图生场景测试/
├── README.md
├── clipboard_20260401_104944.png   # 原始输入图片 (838×456)
├── docs/
│   ├── step2_可行性分析与执行方案.md
│   ├── step2_执行记录.md
│   ├── step3+4_执行记录.md
│   ├── step5_执行文档.md             # Step 5 详细技术规格
│   ├── step5_agent_prompt.md          # 给执行 agent 的提示词
│   ├── Step 3：透视分析 + 坐标系建立.md  # 原始规划
│   ├── Step 4：2D 空间布局图 + 3D 信息标注.md
│   └── Step 5：UE 场景生成.md
├── scripts/
│   ├── step2_semantic_grouping.py
│   ├── step2_annotate_original.py
│   ├── step3_combined_final.py      # Step 3+4 合并脚本
│   └── step4_summary_and_elevation.py
├── step1_output/
│   ├── scene_analysis_result.json   # 18 物体结构化数据
│   └── analysis_summary.txt
├── step2_output/
│   ├── step2_semantic_groups.json
│   ├── annotated_original.png
│   ├── layout_overview.png
│   ├── depth_layers.png
│   └── spatial_relations.png
└── step3_output/
    ├── step3_3d_coordinates.json    # 3D 坐标 + 相机 + 投影
    ├── combined_layout.png          # 原图 + 俯视对比
    ├── reprojection_check.png       # 反投影验证
    ├── parameters_summary.png       # 3D 参数汇总表
    └── side_elevation.png           # 侧视标高图
```

## 测试场景
- 风格化低多边形海滩微缩场景
- 等轴测 45° 视角 (pitch=-35°, yaw=45°)
- 18 个物体: 灯塔、遮阳伞、躺椅、人物、海浪、沙滩平台等
- 场景实际范围: ~5m × 3.6m

## 关键技术参数
- 投影: `Rx(-35°) @ Rz(45°)`, orthographic
- Scale: 108.41 px/m (锚定: umbrella h=2.2m)
- 原点: platform_01 ground_contact
- 相机: (-8.6, -10.1, 8.6)m, 看向 (2.0, 0.5)
