"""
Step 4: 生成 3D 参数汇总 CSV
"""
import json, csv, os

BASE_DIR = r"D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试"
STEP3_JSON = os.path.join(BASE_DIR, "step3_output", "step3_3d_coordinates.json")
STEP2_JSON = os.path.join(BASE_DIR, "step2_output", "step2_semantic_groups.json")

with open(STEP3_JSON, 'r', encoding='utf-8') as f:
    s3 = json.load(f)
with open(STEP2_JSON, 'r', encoding='utf-8') as f:
    step2 = json.load(f)

OBJ_TO_GROUP = {}
for gid, ginfo in step2['groups'].items():
    for m in ginfo['members']:
        OBJ_TO_GROUP[m['id']] = gid

# Objects CSV
obj_csv = os.path.join(BASE_DIR, "step3_output", "parameters_summary.csv")
with open(obj_csv, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['ID', 'Category', 'X(m)', 'Y(m)', 'Z(m)', 'GroundZ(m)',
                'W(m)', 'D(m)', 'H(m)', 'Rotation', 'Group', 'Backdrop', 'Confidence'])
    for o in sorted(s3['objects_3d'], key=lambda x: x['id']):
        p = o['position_m']
        s = o['size_m']
        gid = OBJ_TO_GROUP.get(o['id'], '')
        w.writerow([
            o['id'], o['category'],
            p['x'], p['y'], p['z'], o.get('ground_z_m', 0),
            s.get('w', 0), s.get('d', 0), s.get('h', 0),
            o.get('rotation_deg', 0),
            gid, o.get('is_backdrop', False), o.get('confidence', '')
        ])

# Camera CSV
cam_csv = os.path.join(BASE_DIR, "step3_output", "camera_parameters.csv")
cam = s3['camera']
proj = s3['projection']
with open(cam_csv, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['Parameter', 'Value'])
    w.writerow(['Type', cam['type']])
    w.writerow(['Position X(m)', cam['position_m']['x']])
    w.writerow(['Position Y(m)', cam['position_m']['y']])
    w.writerow(['Position Z(m)', cam['position_m']['z']])
    w.writerow(['LookAt X(m)', cam['look_at_m']['x']])
    w.writerow(['LookAt Y(m)', cam['look_at_m']['y']])
    w.writerow(['Pitch', cam['rotation_deg']['pitch']])
    w.writerow(['Yaw', cam['rotation_deg']['yaw']])
    w.writerow(['Roll', cam['rotation_deg']['roll']])
    w.writerow(['OrthoWidth(m)', cam['ortho_width_m']])
    w.writerow(['Scale(px/m)', proj['scale_px_per_m']])
    w.writerow(['Projection', proj['rotation_order']])

print(f"[OK] {obj_csv}")
print(f"[OK] {cam_csv}")
