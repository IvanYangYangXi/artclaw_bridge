"""
Step 3+4 合并: 等轴测逆投影 + 3D 坐标 + 相机 + 俯视布局 + 验证
一次性输出所有结果

修正:
- 相机位置从 image center 的世界坐标推导
- 俯视图紧凑裁剪到物体范围（不画过多空白）
- 左图保持原始宽高比
"""
import json, math, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec
from PIL import Image

# === Paths ===
BASE_DIR = r"D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试"
STEP1_JSON = r"C:\Users\yangjili\lobsterai\project\scene_analysis_output\scene_analysis_result.json"
STEP2_JSON = os.path.join(BASE_DIR, "step2_output", "step2_semantic_groups.json")
ORIGINAL_IMG = os.path.join(BASE_DIR, "clipboard_20260401_104944.png")
OUTPUT_DIR = os.path.join(BASE_DIR, "step3_output")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "step3_3d_coordinates.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(STEP1_JSON, 'r', encoding='utf-8') as f:
    step1 = json.load(f)
with open(STEP2_JSON, 'r', encoding='utf-8') as f:
    step2 = json.load(f)
img = Image.open(ORIGINAL_IMG)
IMG_W, IMG_H = img.size
objects = {o['id']: o for o in step1['objects']}

# ============================================================
# 1. Projection model: Rx(pitch) @ Rz(yaw)
# ============================================================
PITCH_DEG, YAW_DEG = -35.0, 45.0
pitch, yaw = math.radians(PITCH_DEG), math.radians(YAW_DEG)
cos_p, sin_p = math.cos(pitch), math.sin(pitch)
cos_y, sin_y = math.cos(yaw), math.sin(yaw)

Rz = np.array([[cos_y, -sin_y, 0], [sin_y, cos_y, 0], [0, 0, 1]])
Rx = np.array([[1, 0, 0], [0, cos_p, -sin_p], [0, sin_p, cos_p]])
R = Rx @ Rz

proj_x = R[0]        # screen right
proj_y = -R[1]       # screen down (image Y+)
look_dir_world = np.array([R[2][0], R[2][1], R[2][2]])
# Correct: look direction = +R[2] when proj_y = -R[1]
# (verified: lighthouse has negative R[2]·pos, but we use -R[2] as "screen depth")
# Actually for camera placement: camera looks along -R[2] in the flipped system
camera_look_xy = np.array([-R[2][0], -R[2][1]])  # = (+0.406, +0.406) toward +X,+Y
camera_look_xy_n = camera_look_xy / np.linalg.norm(camera_look_xy)

# Ground projection 2x2
A = np.array([[proj_x[0], proj_x[1]], [proj_y[0], proj_y[1]]])
A_inv = np.linalg.inv(A)

# ============================================================
# 2. Scale calibration from anchor
# ============================================================
anchor = objects['umbrella_01']
anchor_h_px = (anchor['bbox_pct']['y_max'] - anchor['bbox_pct']['y_min']) / 100 * IMG_H
z_proj_factor = abs(proj_y[2])
scale = anchor_h_px / (2.2 * z_proj_factor)

# ============================================================
# 3. Origin = platform_01 ground contact
# ============================================================
origin_pct = objects['platform_01']['ground_contact_pct']
origin_px = np.array([origin_pct['x'] / 100 * IMG_W, origin_pct['y'] / 100 * IMG_H])

def screen_to_world(sx_pct, sy_pct, z=0.0):
    s_px = np.array([sx_pct / 100 * IMG_W, sy_pct / 100 * IMG_H])
    d = (s_px - origin_px) / scale
    d[0] -= proj_x[2] * z
    d[1] -= proj_y[2] * z
    xy = A_inv @ d
    return float(xy[0]), float(xy[1])

def world_to_screen(x, y, z=0.0):
    p = np.array([proj_x[0]*x + proj_x[1]*y + proj_x[2]*z,
                   proj_y[0]*x + proj_y[1]*y + proj_y[2]*z])
    s_px = p * scale + origin_px
    return float(s_px[0] / IMG_W * 100), float(s_px[1] / IMG_H * 100)

# ============================================================
# 4. Compute all 3D coordinates
# ============================================================
BACKDROP_IDS = {'backdrop_01', 'sun_01', 'cloud_01', 'cloud_02'}
objects_3d = []

for oid, obj in objects.items():
    gc = obj['ground_contact_pct']
    est = obj['estimated_size_m']
    is_bd = oid in BACKDROP_IDS
    
    x, y = screen_to_world(gc['x'], gc['y'])
    z_ground = 0.5 if oid == 'stairs_01' else 0.0
    if z_ground > 0:
        x, y = screen_to_world(gc['x'], gc['y'], z_ground)
    
    z_center = z_ground + est.get('h', 0) * 0.5
    
    # Reprojection check
    rx, ry = world_to_screen(x, y, z_ground)
    err = math.sqrt((rx - gc['x'])**2 + (ry - gc['y'])**2)
    
    objects_3d.append({
        "id": oid, "category": obj['category'],
        "position_m": {"x": round(x, 2), "y": round(y, 2), "z": round(z_center, 2)},
        "ground_z_m": round(z_ground, 2),
        "size_m": est,
        "rotation_deg": obj.get('rotation_hint_deg', 0),
        "is_backdrop": is_bd,
        "is_anchor": (oid == 'umbrella_01'),
        "confidence": "low" if is_bd else ("high" if err < 1 else "medium"),
        "reprojection_error_pct": round(err, 4)
    })

# ============================================================
# 5. Camera from image center
# ============================================================
img_cx, img_cy = screen_to_world(50, 50)
cam_dist = 15
cam_x = img_cx - camera_look_xy_n[0] * cam_dist
cam_y = img_cy - camera_look_xy_n[1] * cam_dist
cam_z = cam_dist * abs(math.sin(pitch))

# Visible range (image corners on ground)
corners_w = [screen_to_world(sx, sy) for sx, sy in [(0,0),(100,0),(0,100),(100,100)]]
vis_x = [c[0] for c in corners_w]
vis_y = [c[1] for c in corners_w]

# Ortho width: screen width in meters
ortho_w_m = IMG_W / scale

ground_objs = [o for o in objects_3d if not o['is_backdrop']]
all_x = [o['position_m']['x'] for o in ground_objs]
all_y = [o['position_m']['y'] for o in ground_objs]
errs = [o['reprojection_error_pct'] for o in ground_objs]

print(f"Scale: {scale:.2f} px/m")
print(f"Scene: X[{min(all_x):.2f}, {max(all_x):.2f}] Y[{min(all_y):.2f}, {max(all_y):.2f}]")
print(f"Camera: ({cam_x:.2f}, {cam_y:.2f}, {cam_z:.2f})")
print(f"Look-at: ({img_cx:.2f}, {img_cy:.2f})")
print(f"Visible: X[{min(vis_x):.2f}, {max(vis_x):.2f}] Y[{min(vis_y):.2f}, {max(vis_y):.2f}]")
print(f"Ortho width: {ortho_w_m:.2f}m")
print(f"Reproj err: mean={np.mean(errs):.4f}%, max={max(errs):.4f}%")

# ============================================================
# 6. Output JSON
# ============================================================
output = {
    "step": "step3+4_combined",
    "version": 3,
    "image_size": {"w": IMG_W, "h": IMG_H},
    "coordinate_system": {
        "origin": "platform_01 ground_contact",
        "origin_screen_pct": {"x": origin_pct['x'], "y": origin_pct['y']},
        "units": "meters",
        "axes": {"X": "right", "Y": "depth (screen upper-right = +Y)", "Z": "up"}
    },
    "projection": {
        "type": "isometric_orthographic",
        "rotation_order": "Rx(pitch) @ Rz(yaw)",
        "pitch_deg": PITCH_DEG, "yaw_deg": YAW_DEG,
        "proj_x": proj_x.tolist(),
        "proj_y": proj_y.tolist(),
        "scale_px_per_m": round(scale, 2),
        "anchor": {"id": "umbrella_01", "height_m": 2.2, "bbox_h_px": round(anchor_h_px, 1)}
    },
    "camera": {
        "type": "orthographic",
        "position_m": {"x": round(cam_x, 2), "y": round(cam_y, 2), "z": round(cam_z, 2)},
        "look_at_m": {"x": round(img_cx, 2), "y": round(img_cy, 2), "z": 0},
        "look_direction_xy": {"x": round(camera_look_xy_n[0], 4), "y": round(camera_look_xy_n[1], 4)},
        "rotation_deg": {"pitch": PITCH_DEG, "yaw": YAW_DEG, "roll": 0},
        "ortho_width_m": round(ortho_w_m, 2)
    },
    "visible_area": {
        "corners_world": [{"x": round(c[0],2), "y": round(c[1],2)} for c in corners_w],
        "x_range_m": [round(min(vis_x),2), round(max(vis_x),2)],
        "y_range_m": [round(min(vis_y),2), round(max(vis_y),2)]
    },
    "objects_3d": objects_3d,
    "validation": {
        "mean_reprojection_error_pct": round(float(np.mean(errs)), 4),
        "max_reprojection_error_pct": round(float(max(errs)), 4),
        "total_ground_objects": len(ground_objs),
        "total_backdrop_objects": len(objects_3d) - len(ground_objs)
    }
}

with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n[OK] JSON -> {OUTPUT_JSON}")

# ============================================================
# 7. Combined visualization: original + top-down + reprojection
# ============================================================
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

GROUP_COLORS = {
    'beach_area': '#E8C890', 'ocean_area': '#4A90D9', 'lighthouse_area': '#E63946',
    'sky_backdrop': '#87CEEB', 'foreground_decor': '#808080'
}
OBJ_TO_GROUP = {}
for gid, ginfo in step2['groups'].items():
    for m in ginfo['members']:
        OBJ_TO_GROUP[m['id']] = gid

img_array = np.array(img)

# --- Figure 1: Side-by-side original + top-down ---
fig1 = plt.figure(figsize=(22, 10))
gs = GridSpec(1, 2, figure=fig1, width_ratios=[1.2, 1.0], wspace=0.12)
ax_img = fig1.add_subplot(gs[0])
ax_top = fig1.add_subplot(gs[1])

# Left: original image (pixel coords, true aspect)
ax_img.imshow(img_array)
ax_img.set_xlim(0, IMG_W); ax_img.set_ylim(IMG_H, 0)
ax_img.set_aspect('equal')
ax_img.set_title('Original + Ground Contact Points', fontsize=13, fontweight='bold')

for o3d in objects_3d:
    if o3d['is_backdrop']:
        continue
    oid = o3d['id']
    gc = objects[oid]['ground_contact_pct']
    gx = gc['x'] / 100 * IMG_W
    gy = gc['y'] / 100 * IMG_H
    gid = OBJ_TO_GROUP.get(oid, 'foreground_decor')
    color = GROUP_COLORS.get(gid, '#888')
    ax_img.plot(gx, gy, 'o', color=color, markersize=7, markeredgecolor='white', markeredgewidth=1, zorder=5)
    ax_img.text(gx + 6, gy - 4, oid, fontsize=5, color='white', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.08', facecolor=color, alpha=0.85), zorder=6)

# Right: top-down (tight crop to objects + camera)
# Include camera but crop tightly
plot_margin = 1.2
plot_x_min = min(min(all_x), cam_x) - plot_margin
plot_x_max = max(all_x) + plot_margin
plot_y_min = min(min(all_y), cam_y) - plot_margin
plot_y_max = max(all_y) + plot_margin

ax_top.set_xlim(plot_x_min, plot_x_max)
ax_top.set_ylim(plot_y_min, plot_y_max)
ax_top.set_aspect('equal')
ax_top.grid(True, alpha=0.15, linestyle='--')
ax_top.set_title('Top-Down (XY ground plane, meters)', fontsize=13, fontweight='bold')
ax_top.set_xlabel('X (m)'); ax_top.set_ylabel('Y (m)')

# Draw visible area boundary (image frame on ground)
vis_polygon_x = [corners_w[0][0], corners_w[1][0], corners_w[3][0], corners_w[2][0], corners_w[0][0]]
vis_polygon_y = [corners_w[0][1], corners_w[1][1], corners_w[3][1], corners_w[2][1], corners_w[0][1]]
ax_top.plot(vis_polygon_x, vis_polygon_y, '-', color='gray', linewidth=1.5, alpha=0.4, label='Image frame')
ax_top.fill(vis_polygon_x, vis_polygon_y, color='lightyellow', alpha=0.15)

# Objects
for o3d in objects_3d:
    if o3d['is_backdrop']:
        continue
    oid = o3d['id']
    pos = o3d['position_m']
    size = o3d['size_m']
    gid = OBJ_TO_GROUP.get(oid, 'foreground_decor')
    color = GROUP_COLORS.get(gid, '#888')
    w, d = size.get('w', 1), size.get('d', 1)
    
    rect = patches.Rectangle(
        (pos['x'] - w/2, pos['y'] - d/2), w, d,
        linewidth=1.5, edgecolor=color, facecolor=color, alpha=0.25
    )
    ax_top.add_patch(rect)
    ax_top.plot(pos['x'], pos['y'], 'o', color=color, markersize=5, markeredgecolor='white', markeredgewidth=0.8)
    ax_top.text(pos['x'], pos['y'] - d/2 - 0.1, oid,
                fontsize=5, ha='center', va='top', color='black', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.06', facecolor='white', alpha=0.7, edgecolor=color))

# Origin
ax_top.plot(0, 0, '+', color='black', markersize=15, markeredgewidth=2, zorder=10)
ax_top.text(0.1, -0.1, 'O', fontsize=8, color='black', fontweight='bold')

# Camera
ax_top.plot(cam_x, cam_y, 's', color='red', markersize=10, markeredgecolor='darkred', markeredgewidth=2, zorder=15)
# Look direction arrow toward look-at point
ax_top.annotate('',
    xy=(img_cx, img_cy), xytext=(cam_x, cam_y),
    arrowprops=dict(arrowstyle='->', color='red', lw=2, mutation_scale=12))
# Label
ax_top.text(cam_x, cam_y - 0.5,
            f'Cam ({cam_x:.1f}, {cam_y:.1f})\nz={cam_z:.1f}m',
            fontsize=6.5, ha='center', color='red', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.15', facecolor='lightyellow', alpha=0.9, edgecolor='red'))
# Look-at cross
ax_top.plot(img_cx, img_cy, 'x', color='red', markersize=8, markeredgewidth=1.5, alpha=0.6)
ax_top.text(img_cx + 0.2, img_cy + 0.2, 'look-at', fontsize=6, color='red', alpha=0.6)

# Scale bar
bar_y = plot_y_min + 0.4
ax_top.plot([plot_x_min + 0.3, plot_x_min + 2.3], [bar_y, bar_y], 'k-', linewidth=3)
ax_top.text(plot_x_min + 1.3, bar_y + 0.2, '2m', fontsize=9, ha='center', fontweight='bold')

# Legend
handles = [patches.Patch(facecolor=c, alpha=0.4, label=gid.replace('_', ' '))
           for gid, c in GROUP_COLORS.items() if gid != 'sky_backdrop']
handles.append(Line2D([0], [0], marker='s', color='red', markeredgecolor='darkred', markersize=8, linestyle='', label='Camera'))
handles.append(Line2D([0], [0], color='gray', alpha=0.5, label='Image frame'))
ax_top.legend(handles=handles, loc='upper right', fontsize=6.5)

fig1.suptitle(f'Step 3+4: Isometric pitch={PITCH_DEG}, yaw={YAW_DEG} | scale={scale:.1f} px/m | ortho={ortho_w_m:.1f}m',
              fontsize=12, y=0.98)

path1 = os.path.join(OUTPUT_DIR, 'combined_layout.png')
fig1.savefig(path1, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig1)
print(f"[OK] Layout -> {path1}")

# --- Figure 2: Reprojection check ---
fig2, ax2 = plt.subplots(1, 1, figsize=(14, 8))
ax2.imshow(img_array, extent=[0, 100, 100, 0], aspect='auto', alpha=0.5)
ax2.set_xlim(0, 100); ax2.set_ylim(100, 0)
ax2.set_title('Reprojection Check: original (circle) vs reprojected (cross)', fontsize=13, fontweight='bold')

for o3d in objects_3d:
    if o3d['is_backdrop']:
        continue
    oid = o3d['id']
    pos = o3d['position_m']
    gc = objects[oid]['ground_contact_pct']
    gz = o3d['ground_z_m']
    gid = OBJ_TO_GROUP.get(oid, 'foreground_decor')
    color = GROUP_COLORS.get(gid, '#888')
    
    rx, ry = world_to_screen(pos['x'], pos['y'], gz)
    
    ax2.plot(gc['x'], gc['y'], 'o', color=color, markersize=9, markerfacecolor='none', linewidth=2)
    ax2.plot(rx, ry, 'x', color=color, markersize=9, linewidth=2)
    ax2.plot([gc['x'], rx], [gc['y'], ry], '-', color=color, linewidth=1, alpha=0.4)
    ax2.text(gc['x'] + 1, gc['y'] - 1.5, oid, fontsize=5.5, color='black',
             bbox=dict(boxstyle='round,pad=0.08', facecolor='white', alpha=0.6))

ax2.plot([], [], 'o', color='gray', markersize=8, markerfacecolor='none', linewidth=2, label='Step 1 position')
ax2.plot([], [], 'x', color='gray', markersize=8, linewidth=2, label='Reprojected from 3D')
ax2.legend(loc='upper left', fontsize=10)

path2 = os.path.join(OUTPUT_DIR, 'reprojection_check.png')
fig2.savefig(path2, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig2)
print(f"[OK] Reprojection -> {path2}")

print(f"\nDone. Output: {OUTPUT_DIR}")
