"""
Step 2 补充: 在原图上叠加语义分组标注
输入: 原始图片 + step2_semantic_groups.json
输出: step2_output/annotated_original.png
"""

import json
import os
from PIL import Image, ImageDraw, ImageFont

# === 路径 ===
ORIGINAL_IMG = r"D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\clipboard_20260401_104944.png"
INPUT_JSON = r"C:\Users\yangjili\lobsterai\project\scene_analysis_output\scene_analysis_result.json"
GROUPS_JSON = r"D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\step2_output\step2_semantic_groups.json"
OUTPUT_DIR = r"D:\MyProject_D\artclaw_bridge\subprojects\图生场景测试\step2_output"
OUTPUT_IMG = os.path.join(OUTPUT_DIR, "annotated_original.png")

# === 加载数据 ===
with open(INPUT_JSON, 'r', encoding='utf-8') as f:
    data = json.load(f)

with open(GROUPS_JSON, 'r', encoding='utf-8') as f:
    groups_data = json.load(f)

objects = {obj['id']: obj for obj in data['objects']}

# 物体→分组映射
OBJ_TO_GROUP = {}
GROUP_COLORS_HEX = {}
GROUP_LABELS = {}
for gid, ginfo in groups_data['groups'].items():
    GROUP_COLORS_HEX[gid] = ginfo['color']
    GROUP_LABELS[gid] = ginfo['label']
    for m in ginfo['members']:
        OBJ_TO_GROUP[m['id']] = gid

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# === 加载图片 ===
img = Image.open(ORIGINAL_IMG).convert('RGBA')
W, H = img.size
print(f"原图尺寸: {W}x{H}")

# 创建透明叠加层
overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)

# 尝试加载字体
try:
    font = ImageFont.truetype("msyh.ttc", max(14, H // 60))
    font_small = ImageFont.truetype("msyh.ttc", max(11, H // 80))
    font_title = ImageFont.truetype("msyh.ttc", max(20, H // 40))
except:
    font = ImageFont.load_default()
    font_small = font
    font_title = font

# === 绘制分组包围盒 ===
for gid, ginfo in groups_data['groups'].items():
    bbox = ginfo['bbox_pct']
    if not bbox:
        continue
    rgb = hex_to_rgb(ginfo['color'])
    
    x1 = int(bbox['x_min'] / 100 * W)
    y1 = int(bbox['y_min'] / 100 * H)
    x2 = int(bbox['x_max'] / 100 * W)
    y2 = int(bbox['y_max'] / 100 * H)
    
    # 半透明填充
    draw.rectangle([x1, y1, x2, y2], fill=(*rgb, 25), outline=(*rgb, 120), width=2)
    
    # 分组标签（带背景）
    label = ginfo['label']
    text_bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    draw.rectangle([x1, y1 - th - 6, x1 + tw + 10, y1], fill=(*rgb, 180))
    draw.text((x1 + 5, y1 - th - 3), label, fill=(255, 255, 255, 255), font=font)

# === 绘制物体 bbox + ID ===
for oid, obj in objects.items():
    bbox = obj['bbox_pct']
    gid = OBJ_TO_GROUP.get(oid, 'foreground_decor')
    rgb = hex_to_rgb(GROUP_COLORS_HEX.get(gid, '#888888'))
    
    x1 = int(bbox['x_min'] / 100 * W)
    y1 = int(bbox['y_min'] / 100 * H)
    x2 = int(bbox['x_max'] / 100 * W)
    y2 = int(bbox['y_max'] / 100 * H)
    
    # bbox 边框
    draw.rectangle([x1, y1, x2, y2], outline=(*rgb, 200), width=2)
    
    # ID 标签
    id_label = oid
    text_bbox = draw.textbbox((0, 0), id_label, font=font_small)
    tw, th = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    label_x = x1 + 2
    label_y = y2 + 1
    draw.rectangle([label_x, label_y, label_x + tw + 6, label_y + th + 4],
                    fill=(0, 0, 0, 160))
    draw.text((label_x + 3, label_y + 2), id_label, fill=(*rgb, 255), font=font_small)
    
    # 地面接触点标记
    gx = int(obj['ground_contact_pct']['x'] / 100 * W)
    gy = int(obj['ground_contact_pct']['y'] / 100 * H)
    s = 4
    draw.polygon([(gx, gy - s), (gx - s, gy + s), (gx + s, gy + s)],
                  fill=(*rgb, 180))

# === 合成 ===
result = Image.alpha_composite(img, overlay).convert('RGB')

# 添加标题
draw_final = ImageDraw.Draw(result)
title = "Step 2: 语义分组标注 (5 groups / 18 objects)"
text_bbox = draw_final.textbbox((0, 0), title, font=font_title)
tw = text_bbox[2] - text_bbox[0]
draw_final.rectangle([W//2 - tw//2 - 10, 5, W//2 + tw//2 + 10, 5 + text_bbox[3] - text_bbox[1] + 10],
                      fill=(0, 0, 0, 180))
draw_final.text((W//2 - tw//2, 8), title, fill=(255, 255, 255), font=font_title)

result.save(OUTPUT_IMG, quality=95)
print(f"[OK] 标注图 -> {OUTPUT_IMG}")
print(f"     尺寸: {result.size[0]}x{result.size[1]}")
