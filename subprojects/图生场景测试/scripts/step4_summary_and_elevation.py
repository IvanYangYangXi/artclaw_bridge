"""
Step 4 补充: 3D 参数汇总表 + 侧视标高图
"""
import json, math, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D

BASE_DIR = r"D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试"
STEP3_JSON = os.path.join(BASE_DIR, "step3_output", "step3_3d_coordinates.json")
STEP2_JSON = os.path.join(BASE_DIR, "step2_output", "step2_semantic_groups.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "step3_output")

with open(STEP3_JSON, 'r', encoding='utf-8') as f:
    s3 = json.load(f)
with open(STEP2_JSON, 'r', encoding='utf-8') as f:
    step2 = json.load(f)

objects_3d = s3['objects_3d']
cam = s3['camera']

GROUP_COLORS = {
    'beach_area': '#E8C890', 'ocean_area': '#4A90D9', 'lighthouse_area': '#E63946',
    'sky_backdrop': '#87CEEB', 'foreground_decor': '#808080'
}
OBJ_TO_GROUP = {}
for gid, ginfo in step2['groups'].items():
    for m in ginfo['members']:
        OBJ_TO_GROUP[m['id']] = gid

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# 1. 3D Parameters Summary Table (as image)
# ============================================================
ground_objs = [o for o in objects_3d if not o.get('is_backdrop', False)]
backdrop_objs = [o for o in objects_3d if o.get('is_backdrop', False)]

fig_t, ax_t = plt.subplots(figsize=(16, 10))
ax_t.axis('off')
ax_t.set_title('Step 3+4: 3D Parameters Summary', fontsize=16, fontweight='bold', pad=20)

# Camera info
cam_text = (f"Camera: orthographic | pos=({cam['position_m']['x']}, {cam['position_m']['y']}, {cam['position_m']['z']})m | "
            f"look-at=({cam['look_at_m']['x']}, {cam['look_at_m']['y']})m | "
            f"pitch={cam['rotation_deg']['pitch']}, yaw={cam['rotation_deg']['yaw']} | "
            f"ortho_width={cam['ortho_width_m']}m")
ax_t.text(0.5, 0.97, cam_text, transform=ax_t.transAxes, fontsize=9, ha='center', va='top',
          bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

# Table data
headers = ['ID', 'Category', 'X(m)', 'Y(m)', 'Z(m)', 'W(m)', 'D(m)', 'H(m)', 'Rot', 'Group', 'Conf']
rows = []
for o in sorted(ground_objs, key=lambda x: x['id']):
    p = o['position_m']
    s = o['size_m']
    gid = OBJ_TO_GROUP.get(o['id'], '?')
    rows.append([
        o['id'], o['category'],
        f"{p['x']:+.2f}", f"{p['y']:+.2f}", f"{p['z']:.2f}",
        f"{s.get('w',0):.1f}", f"{s.get('d',0):.1f}", f"{s.get('h',0):.1f}",
        f"{o.get('rotation_deg', 0)}",
        gid.replace('_area','').replace('_decor',''),
        o['confidence']
    ])

# Color cells by group
cell_colors = []
for row_data in rows:
    row_colors = []
    gname = row_data[9]
    for gid, c in GROUP_COLORS.items():
        if gname in gid:
            base_color = c
            break
    else:
        base_color = '#FFFFFF'
    
    from matplotlib.colors import to_rgba
    rgba = to_rgba(base_color, alpha=0.15)
    row_colors = [rgba] * len(headers)
    cell_colors.append(row_colors)

table = ax_t.table(cellText=rows, colLabels=headers, cellLoc='center', loc='center',
                    cellColours=cell_colors)
table.auto_set_font_size(False)
table.set_fontsize(8)
table.scale(1, 1.4)

# Style header
for j, h in enumerate(headers):
    table[0, j].set_facecolor('#2C3E50')
    table[0, j].set_text_props(color='white', fontweight='bold')

table_path = os.path.join(OUTPUT_DIR, 'parameters_summary.png')
fig_t.savefig(table_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig_t)
print(f"[OK] Parameters table -> {table_path}")

# ============================================================
# 2. Side elevation view (XZ plane, looking from Y direction)
# ============================================================
fig_s, ax_s = plt.subplots(figsize=(16, 6))

# Depth sorting: draw far objects first
for o in sorted(ground_objs, key=lambda x: x['position_m']['y'], reverse=True):
    oid = o['id']
    pos = o['position_m']
    size = o['size_m']
    gz = o.get('ground_z_m', 0)
    gid = OBJ_TO_GROUP.get(oid, 'foreground_decor')
    color = GROUP_COLORS.get(gid, '#888')
    
    w = size.get('w', 1)
    h = size.get('h', 0.5)
    
    # Draw as rectangle from ground to top
    rect = patches.Rectangle(
        (pos['x'] - w/2, gz), w, h,
        linewidth=1.5, edgecolor=color, facecolor=color, alpha=0.35
    )
    ax_s.add_patch(rect)
    
    # Label
    ax_s.text(pos['x'], gz + h + 0.08, oid,
              fontsize=5.5, ha='center', va='bottom', color='black', fontweight='bold',
              rotation=45,
              bbox=dict(boxstyle='round,pad=0.06', facecolor='white', alpha=0.7, edgecolor=color))

# Ground line
all_x = [o['position_m']['x'] for o in ground_objs]
ax_s.axhline(y=0, color='#8B4513', linewidth=2, alpha=0.5, label='Ground (Z=0)')
ax_s.axhline(y=0.5, color='#8B4513', linewidth=1, alpha=0.3, linestyle=':', label='Stairs level')

margin_x = 1.0
ax_s.set_xlim(min(all_x) - margin_x, max(all_x) + margin_x)
ax_s.set_ylim(-0.5, 10)
ax_s.set_xlabel('X (m)', fontsize=11)
ax_s.set_ylabel('Z (m) - Height', fontsize=11)
ax_s.set_title('Side Elevation View (XZ plane)', fontsize=14, fontweight='bold')
ax_s.grid(True, alpha=0.15, linestyle='--')
ax_s.set_aspect('equal')
ax_s.legend(loc='upper left', fontsize=8)

# Scale bar
ax_s.plot([min(all_x) - 0.5, min(all_x) - 0.5], [0, 2], 'k-', linewidth=2)
ax_s.text(min(all_x) - 0.7, 1, '2m', fontsize=9, ha='right', va='center', fontweight='bold')

side_path = os.path.join(OUTPUT_DIR, 'side_elevation.png')
fig_s.savefig(side_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig_s)
print(f"[OK] Side elevation -> {side_path}")

print("\nStep 4 outputs complete.")
