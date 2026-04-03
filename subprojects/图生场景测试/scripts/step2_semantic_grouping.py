"""
Step 2: 语义分组 + 标注图生成
输入: scene_analysis_result.json (Step 1 输出)
输出:
  - step2_semantic_groups.json (语义分组结构)
  - step2_output/layout_overview.png (2D 布局示意图)
  - step2_output/depth_layers.png (深度层可视化)
  - step2_output/spatial_relations.png (空间关系图)
"""

import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch
import numpy as np

# === 路径配置 ===
INPUT_JSON = r"C:\Users\yangjili\lobsterai\project\scene_analysis_output\scene_analysis_result.json"
OUTPUT_DIR = r"D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\step2_output"
OUTPUT_JSON = r"D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\step2_output\step2_semantic_groups.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === 加载 Step 1 数据 ===
with open(INPUT_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

objects = {obj['id']: obj for obj in data['objects']}
relations = data['spatial_relations']
groups_raw = data['groups']

# === 1. 语义分组 ===
SEMANTIC_GROUPS = {
    "beach_area": {
        "label": "沙滩主区域",
        "color": "#E8C890",
        "members": ["platform_01", "stairs_01", "umbrella_01", "chair_01", "chair_02",
                     "character_01", "character_02", "ball_01", "ball_02"]
    },
    "ocean_area": {
        "label": "海洋区域",
        "color": "#4A90D9",
        "members": ["water_01"]
    },
    "lighthouse_area": {
        "label": "灯塔区域",
        "color": "#E63946",
        "members": ["lighthouse_01", "rock_base_01"]
    },
    "sky_backdrop": {
        "label": "天空背景",
        "color": "#87CEEB",
        "members": ["backdrop_01", "sun_01", "cloud_01", "cloud_02"]
    },
    "foreground_decor": {
        "label": "前景装饰",
        "color": "#808080",
        "members": ["geo_blocks_01", "rock_01"]
    }
}

def compute_group_bbox(group_members):
    """合并子对象 bbox 计算分组包围盒"""
    x_mins, y_mins, x_maxs, y_maxs = [], [], [], []
    for mid in group_members:
        if mid in objects:
            bbox = objects[mid]['bbox_pct']
            x_mins.append(bbox['x_min'])
            y_mins.append(bbox['y_min'])
            x_maxs.append(bbox['x_max'])
            y_maxs.append(bbox['y_max'])
    if not x_mins:
        return None
    return {
        "x_min": min(x_mins), "y_min": min(y_mins),
        "x_max": max(x_maxs), "y_max": max(y_maxs)
    }

# 构建输出 JSON
semantic_output = {
    "source": "step2_semantic_grouping",
    "input_file": "scene_analysis_result.json",
    "total_objects": len(objects),
    "total_groups": len(SEMANTIC_GROUPS),
    "groups": {}
}

for gid, ginfo in SEMANTIC_GROUPS.items():
    bbox = compute_group_bbox(ginfo['members'])
    members_detail = []
    for mid in ginfo['members']:
        if mid in objects:
            obj = objects[mid]
            members_detail.append({
                "id": mid,
                "category": obj['category'],
                "subcategory": obj['subcategory'],
                "center_pct": obj['center_pct'],
                "estimated_size_m": obj['estimated_size_m'],
                "size_confidence": obj['size_confidence'],
                "depth_layer": obj['depth_layer'],
                "notes": obj['notes']
            })
    semantic_output['groups'][gid] = {
        "label": ginfo['label'],
        "color": ginfo['color'],
        "member_count": len(members_detail),
        "bbox_pct": bbox,
        "members": members_detail
    }

# 添加 anchor 推荐（Step 3 用）
semantic_output['anchor_recommendations'] = [
    {
        "id": "umbrella_01",
        "reason": "明确的独立物体，尺寸估算 medium confidence (h=2.2m)，位于场景中心",
        "estimated_height_m": 2.2
    },
    {
        "id": "lighthouse_01",
        "reason": "最高建筑，尺寸估算 medium confidence (h=8.0m)，可作为远景锚点",
        "estimated_height_m": 8.0
    },
    {
        "id": "character_01",
        "reason": "人物高度标准化参考 (~1.0m 坐姿 / ~1.7m 站姿)，普世尺度参考",
        "estimated_height_m": 1.0
    }
]

with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(semantic_output, f, ensure_ascii=False, indent=2)

print(f"[OK] 语义分组 JSON -> {OUTPUT_JSON}")

# === 2. 2D 布局示意图 ===
# 配置中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

GROUP_COLORS = {gid: ginfo['color'] for gid, ginfo in SEMANTIC_GROUPS.items()}
OBJ_TO_GROUP = {}
for gid, ginfo in SEMANTIC_GROUPS.items():
    for mid in ginfo['members']:
        OBJ_TO_GROUP[mid] = gid

fig, ax = plt.subplots(1, 1, figsize=(14, 10))
ax.set_xlim(0, 100)
ax.set_ylim(100, 0)  # Y 翻转，图像坐标系
ax.set_xlabel('X (%)', fontsize=12)
ax.set_ylabel('Y (%)', fontsize=12)
ax.set_title('Step 2: 场景2D布局 — 语义分组标注', fontsize=16, fontweight='bold')
ax.set_aspect('equal')
ax.grid(True, alpha=0.2, linestyle='--')

# 绘制分组包围盒（半透明背景）
for gid, ginfo in SEMANTIC_GROUPS.items():
    bbox = compute_group_bbox(ginfo['members'])
    if bbox:
        rect = patches.Rectangle(
            (bbox['x_min'], bbox['y_min']),
            bbox['x_max'] - bbox['x_min'],
            bbox['y_max'] - bbox['y_min'],
            linewidth=2, edgecolor=ginfo['color'],
            facecolor=ginfo['color'], alpha=0.12,
            linestyle='--', label=f"{ginfo['label']} ({gid})"
        )
        ax.add_patch(rect)
        # 分组标签
        ax.text(bbox['x_min'] + 0.5, bbox['y_min'] + 2,
                ginfo['label'], fontsize=9, fontweight='bold',
                color=ginfo['color'], alpha=0.8)

# 绘制物体 bbox + ID
for oid, obj in objects.items():
    bbox = obj['bbox_pct']
    gid = OBJ_TO_GROUP.get(oid, 'foreground_decor')
    color = GROUP_COLORS.get(gid, '#888888')

    # bbox 矩形
    rect = patches.Rectangle(
        (bbox['x_min'], bbox['y_min']),
        bbox['x_max'] - bbox['x_min'],
        bbox['y_max'] - bbox['y_min'],
        linewidth=1.5, edgecolor=color,
        facecolor='none'
    )
    ax.add_patch(rect)

    # 中心点
    cx, cy = obj['center_pct']['x'], obj['center_pct']['y']
    ax.plot(cx, cy, 'o', color=color, markersize=4)

    # ID 标签
    ax.text(cx, cy - 1.5, oid.replace('_', ' '),
            fontsize=6, ha='center', va='bottom',
            color='black', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.15', facecolor='white', alpha=0.7, edgecolor=color))

    # 地面接触点
    gx, gy = obj['ground_contact_pct']['x'], obj['ground_contact_pct']['y']
    ax.plot(gx, gy, 'v', color=color, markersize=5, alpha=0.6)

# 图例
legend_handles = []
for gid, ginfo in SEMANTIC_GROUPS.items():
    h = patches.Patch(facecolor=ginfo['color'], alpha=0.3, edgecolor=ginfo['color'],
                      label=f"{ginfo['label']}")
    legend_handles.append(h)
ax.legend(handles=legend_handles, loc='upper left', fontsize=9, framealpha=0.8)

layout_path = os.path.join(OUTPUT_DIR, 'layout_overview.png')
fig.savefig(layout_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"[OK] 2D 布局示意图 -> {layout_path}")

# === 3. 深度层可视化 ===
DEPTH_COLORS = {
    'foreground': ('#FF6B6B', '前景'),
    'midground': ('#4ECDC4', '中景'),
    'background': ('#45B7D1', '背景')
}

fig2, ax2 = plt.subplots(1, 1, figsize=(14, 10))
ax2.set_xlim(0, 100)
ax2.set_ylim(100, 0)
ax2.set_xlabel('X (%)', fontsize=12)
ax2.set_ylabel('Y (%)', fontsize=12)
ax2.set_title('Step 2: 深度层分布 (Foreground / Midground / Background)', fontsize=16, fontweight='bold')
ax2.set_aspect('equal')
ax2.grid(True, alpha=0.2, linestyle='--')

# 绘制深度层范围（来自 spatial_layers）
layers = data['spatial_layers']
for layer_name, layer_data in layers.items():
    y_range = layer_data['y_range_pct']
    color, label = DEPTH_COLORS.get(layer_name, ('#999', layer_name))
    rect = patches.Rectangle(
        (0, y_range[0]), 100, y_range[1] - y_range[0],
        facecolor=color, alpha=0.08, edgecolor=color, linewidth=1, linestyle=':'
    )
    ax2.add_patch(rect)
    ax2.text(2, y_range[0] + 2, f"{label} (y:{y_range[0]}-{y_range[1]}%)",
             fontsize=10, color=color, fontweight='bold', alpha=0.7)

# 按深度层绘制物体
for oid, obj in objects.items():
    bbox = obj['bbox_pct']
    depth = obj['depth_layer']
    color, _ = DEPTH_COLORS.get(depth, ('#999', ''))

    rect = patches.Rectangle(
        (bbox['x_min'], bbox['y_min']),
        bbox['x_max'] - bbox['x_min'],
        bbox['y_max'] - bbox['y_min'],
        linewidth=1.5, edgecolor=color, facecolor=color, alpha=0.2
    )
    ax2.add_patch(rect)

    cx, cy = obj['center_pct']['x'], obj['center_pct']['y']
    ax2.text(cx, cy, oid.split('_')[0],
             fontsize=6, ha='center', va='center', color='black',
             bbox=dict(boxstyle='round,pad=0.1', facecolor=color, alpha=0.4))

# 图例
depth_handles = [patches.Patch(facecolor=c, alpha=0.3, label=l) for c, l in DEPTH_COLORS.values()]
ax2.legend(handles=depth_handles, loc='upper left', fontsize=10, framealpha=0.8)

depth_path = os.path.join(OUTPUT_DIR, 'depth_layers.png')
fig2.savefig(depth_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig2)
print(f"[OK] 深度层可视化 -> {depth_path}")

# === 4. 空间关系图 ===
fig3, ax3 = plt.subplots(1, 1, figsize=(14, 10))
ax3.set_xlim(0, 100)
ax3.set_ylim(100, 0)
ax3.set_xlabel('X (%)', fontsize=12)
ax3.set_ylabel('Y (%)', fontsize=12)
ax3.set_title('Step 2: 物体空间关系图', fontsize=16, fontweight='bold')
ax3.set_aspect('equal')
ax3.grid(True, alpha=0.2, linestyle='--')

# 绘制物体节点
for oid, obj in objects.items():
    cx, cy = obj['center_pct']['x'], obj['center_pct']['y']
    gid = OBJ_TO_GROUP.get(oid, 'foreground_decor')
    color = GROUP_COLORS.get(gid, '#888')

    circle = plt.Circle((cx, cy), 2, color=color, alpha=0.6)
    ax3.add_patch(circle)
    ax3.text(cx, cy - 3, oid.replace('_', '\n'),
             fontsize=5.5, ha='center', va='bottom', color='black', fontweight='bold')

# 关系颜色映射
RELATION_COLORS = {
    'left_of': '#2196F3',
    'right_of': '#4CAF50',
    'in_front_of': '#FF9800',
    'behind': '#9C27B0',
    'on_top_of': '#F44336',
    'right_front_of': '#795548',
    'adjacent': '#607D8B',
    'left_front_of': '#00BCD4'
}

# 绘制关系箭头
for rel in relations:
    subj = rel['subject']
    obj_id = rel['object']
    if subj in objects and obj_id in objects:
        sx, sy = objects[subj]['center_pct']['x'], objects[subj]['center_pct']['y']
        ox, oy = objects[obj_id]['center_pct']['x'], objects[obj_id]['center_pct']['y']
        color = RELATION_COLORS.get(rel['relation'], '#999')

        arrow = FancyArrowPatch(
            (sx, sy), (ox, oy),
            arrowstyle='->', mutation_scale=12,
            color=color, linewidth=1.2, alpha=0.7
        )
        ax3.add_patch(arrow)

        # 关系标签（在箭头中点）
        mx, my = (sx + ox) / 2, (sy + oy) / 2
        ax3.text(mx, my, rel['relation'].replace('_', ' '),
                 fontsize=5, ha='center', va='center', color=color, alpha=0.8,
                 bbox=dict(boxstyle='round,pad=0.1', facecolor='white', alpha=0.6))

# 图例
rel_handles = [patches.Patch(facecolor=c, label=r.replace('_', ' '))
               for r, c in RELATION_COLORS.items() if any(rl['relation'] == r for rl in relations)]
if rel_handles:
    ax3.legend(handles=rel_handles, loc='upper left', fontsize=7, framealpha=0.8, ncol=2)

relations_path = os.path.join(OUTPUT_DIR, 'spatial_relations.png')
fig3.savefig(relations_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig3)
print(f"[OK] 空间关系图 -> {relations_path}")

# === 汇总 ===
print("\n========== Step 2 完成 ==========")
print(f"  语义分组: {len(SEMANTIC_GROUPS)} 个分组, {len(objects)} 个物体")
print(f"  输出目录: {OUTPUT_DIR}")
print(f"  - step2_semantic_groups.json")
print(f"  - layout_overview.png")
print(f"  - depth_layers.png")
print(f"  - spatial_relations.png")
