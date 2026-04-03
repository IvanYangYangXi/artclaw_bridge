# Step 2：语义分组 + 标注图生成

> 状态: ✅ 已完成
> 日期: 2026-04-02
> 脚本: `scripts/step2_semantic_grouping.py`

## 输入
- `scene_analysis_result.json` (Step 1 输出, 18 个物体)

## 输出
- `step2_output/step2_semantic_groups.json` — 语义分组结构 (5 个功能区域)
- `step2_output/layout_overview.png` — 2D 布局示意图 + 分组标注
- `step2_output/depth_layers.png` — 深度层可视化 (前景/中景/背景)
- `step2_output/spatial_relations.png` — 物体空间关系有向图

## 语义分组

| 分组 | 标签 | 物体数 | 说明 |
|------|------|--------|------|
| beach_area | 沙滩主区域 | 9 | 平台+伞+椅+人物+球 |
| ocean_area | 海洋区域 | 1 | 风格化海浪 |
| lighthouse_area | 灯塔区域 | 2 | 灯塔+岩石基座 |
| sky_backdrop | 天空背景 | 4 | 背景墙+太阳+云朵 |
| foreground_decor | 前景装饰 | 2 | 几何体块+岩石 |

## Step 3 锚定物推荐
1. **umbrella_01** (h=2.2m) — 场景中心，medium confidence
2. **lighthouse_01** (h=8.0m) — 远景锚点，medium confidence
3. **character_01** (h=1.0m 坐姿) — 人体标准参考

## 待补充
- 原始输入图片未找到，标注叠加图待原图到位后补做
