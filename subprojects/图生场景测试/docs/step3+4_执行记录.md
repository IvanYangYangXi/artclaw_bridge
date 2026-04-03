# Step 3+4：等轴测逆投影 + 3D 坐标 + 布局验证 — 执行记录

> 状态: ✅ 已完成
> 日期: 2026-04-02
> 脚本: `scripts/step3_combined_final.py` + `scripts/step4_summary_and_elevation.py`

## 输入
- Step 1: `scene_analysis_result.json` (18 物体百分比坐标)
- Step 2: `step2_semantic_groups.json` (5 分组)
- 原图: `clipboard_20260401_104944.png` (838×456)

## 输出
- `step3_output/step3_3d_coordinates.json` — 完整 3D 坐标 + 相机 + 投影矩阵
- `step3_output/combined_layout.png` — 原图 + 俯视布局双图对比
- `step3_output/reprojection_check.png` — 反投影验证叠加原图
- `step3_output/parameters_summary.png` — 3D 参数汇总表
- `step3_output/side_elevation.png` — 侧视标高图 (XZ 平面)

## 关键参数

| 参数 | 值 |
|------|----|
| 投影类型 | 等轴测 orthographic |
| 旋转 | Rx(pitch=-35°) @ **Rz**(yaw=45°) |
| scale | 108.41 px/m |
| 原点 | platform_01 ground_contact (36.5%, 85%) |
| 场景范围 | X[-1.1, 4.2] Y[-1.9, 1.8]，约 5.0m × 3.6m |
| 可视范围 | X[-2.5, 6.6] Y[-4.0, 5.1]，9.1m × 9.1m |
| 相机位置 | (-8.6, -10.1, 8.6) 看向 (2.0, 0.5) |
| 正交宽度 | 7.73m |
| 反投影误差 | 0% (解析解) |

## 开发过程中的 Bug 及修复

### Bug 1: yaw 绕错轴 (Ry → Rz)
- proj_x = [0.707, **0**, 0.707] → Y 不影响 screen X → 俯视图 Y 拉伸
- 修正: Rz(yaw) → proj_x = [0.707, **-0.707**, 0]

### Bug 2: 相机位置方向反
- depth direction 符号混淆，相机算到了场景右上方
- 修正: camera = look_at - look_dir * distance

### Bug 3: 俯视图空白过多
- 相机 dist 过大 + 没画 image frame → 看不出物体和画面边界关系
- 修正: 添加 image frame 四边形 + 紧凑裁剪
