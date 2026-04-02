#!/usr/bin/env python3
"""
scene_analyze.py — 场景原画结构化视觉分析脚本

用法:
    python scene_analyze.py <image_path> [--output <output_dir>] [--rounds 1|2|3]

功能:
    1. 加载原画图片
    2. 读取 output-schema.json 构造分析 prompt
    3. 调用多模态 AI 进行结构化分析
    4. 可选多轮细化和一致性校验
    5. 保存分析结果 JSON + 摘要报告

输出:
    <output_dir>/
        analysis_result.json   — 结构化分析结果
        analysis_summary.txt   — 人类可读摘要
"""

import argparse
import json
import sys
import os
import base64
from pathlib import Path
from datetime import datetime


def load_image_base64(image_path: str) -> tuple[str, str]:
    """加载图片并返回 (base64_data, mime_type)"""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"图片不存在: {image_path}")

    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    mime_type = mime_map.get(suffix, "image/png")

    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    return data, mime_type


def load_schema(skill_dir: str) -> str:
    """加载 output-schema.json"""
    schema_path = Path(skill_dir) / "references" / "output-schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema 不存在: {schema_path}")
    return schema_path.read_text(encoding="utf-8")


def build_system_prompt() -> str:
    return """你是一个专业的游戏场景视觉分析师。你的任务是对游戏场景概念图/原画进行精确的结构化分析，输出严格的 JSON 格式结果。

核心原则：
1. 只描述图片中实际可见的内容，禁止推测或编造不存在的对象
2. 无法确定的项标注为 "uncertain"，不要猜测
3. 每个可识别的对象单独列出（如 3 棵树列为 tree_01, tree_02, tree_03）
4. 坐标系：左上角 (0,0)，右下角 (100,100)，所有坐标用百分比
5. 诚实标注 confidence，低置信度比错误标注更有价值
6. 如果图片中有编辑器 UI/HUD 元素，在 analysis_meta.ui_notes 中说明但不列入 objects"""


def build_analysis_prompt(schema: str) -> str:
    return f"""请对这张游戏场景图片进行详细的结构化视觉分析。

分析步骤（请按顺序执行）：

### 第一步：整体观察
- 确定场景风格、氛围、主色调
- 判断相机视角类型和角度
- 识别光照方向和强度

### 第二步：空间分层
- 将画面分为前景/中景/远景三层
- 确定每层在画面中的 Y 轴范围（百分比）
- 识别地面区域的轮廓

### 第三步：逐物体识别
对每个可见物体：
- 分配语义化 ID（如 house_main, tree_01）
- 标注类别和细分类型
- 标注 bbox 和中心点（百分比坐标）
- 估算接地点位置（物体与地面接触的位置）
- 估算现实尺寸（米），并标注估算置信度
- 描述主要颜色和材质
- 标注深度层级和遮挡关系
- 如果多个同类物体成组排列，标注 group_id

### 第四步：空间参考分析
- 识别主要的透视引导线（道路、河流、围栏、建筑边缘等）
- 估算消失点位置
- 描述近大远小的尺寸梯度
- 检查阴影方向是否一致

### 第五步：空间关系
- 描述关键物体之间的相对位置关系
- 标注距离层级（close/medium/far）

### 第六步：自检
- 统计识别的物体总数和低置信度数量
- 描述分析的局限性（被遮挡区域、模糊区域等）

输出格式严格遵循以下 JSON Schema：

{schema}

直接输出 JSON，不要包含其他文字。"""


def build_refinement_prompt() -> str:
    return """请检查你的分析结果，重点关注：

1. 是否有遗漏的物体？特别注意：
   - 小型道具（灯柱、信箱、长椅等）
   - 地面细节（水坑、石子路、花坛等）
   - 部分被遮挡但仍可识别的物体

2. bbox 精度检查：
   - 重新审视每个物体的 bbox，确保紧贴物体边缘
   - 检查 ground_contact_pct 是否准确标注在物体与地面的接触点

3. 空间关系完整性：
   - 补充遗漏的物体间空间关系
   - 特别关注相邻物体的关系

输出修正后的完整 JSON（不是增量更新，而是完整的修正版）。"""


def build_validation_prompt() -> str:
    return """请对你的分析结果进行一致性校验：

1. 尺寸一致性：同类物体（如多棵同种树）的 estimated_size_m 是否合理一致？
2. 深度一致性：depth_layer 分配是否与 y 坐标和物体大小梯度吻合？
3. 遮挡一致性：标注了 "occluded_by: X" 的物体，X 的 bbox 是否确实在其前方？
4. 光影一致性：所有物体的阴影方向是否与 lighting.shadow_direction_clock 一致？
5. 分组一致性：group 成员的 category/subcategory 是否一致？

列出发现的不一致项，然后输出修正后的完整 JSON。"""


def generate_summary(result: dict) -> str:
    """生成人类可读摘要"""
    lines = []
    lines.append("=" * 60)
    lines.append("场景视觉分析摘要")
    lines.append("=" * 60)

    # 场景概览
    overview = result.get("scene_overview", {})
    lines.append(f"\n【场景】{overview.get('scene_type', '?')} / {overview.get('style', '?')}")
    lines.append(f"【氛围】{overview.get('mood', '?')}")
    lines.append(f"【主色】{', '.join(overview.get('dominant_colors', []))}")

    lighting = overview.get("lighting", {})
    lines.append(f"【光照】{lighting.get('type', '?')} / {lighting.get('direction_clock', '?')} / {lighting.get('intensity', '?')}")

    # 相机
    cam = result.get("camera", {})
    lines.append(f"\n【相机】{cam.get('view_type', '?')} / pitch={cam.get('pitch_angle_deg', '?')}° / yaw={cam.get('yaw_angle_deg', '?')}°")

    # 物体统计
    objects = result.get("objects", [])
    lines.append(f"\n【物体数量】{len(objects)}")

    cat_count: dict[str, int] = {}
    confidence_count = {"high": 0, "medium": 0, "low": 0}
    for obj in objects:
        cat = obj.get("category", "unknown")
        cat_count[cat] = cat_count.get(cat, 0) + 1
        conf = obj.get("confidence", "medium")
        if conf in confidence_count:
            confidence_count[conf] += 1

    for cat, count in sorted(cat_count.items()):
        lines.append(f"  - {cat}: {count}")

    lines.append(f"\n【置信度分布】high={confidence_count['high']} / medium={confidence_count['medium']} / low={confidence_count['low']}")

    # 分组
    groups = result.get("groups", [])
    if groups:
        lines.append(f"\n【分组】{len(groups)} 个")
        for g in groups:
            lines.append(f"  - {g.get('group_id', '?')}: {len(g.get('members', []))} 个成员, {g.get('pattern', '?')}")

    # 空间参考
    refs = result.get("spatial_references", {})
    persp = refs.get("perspective_lines", [])
    vps = refs.get("vanishing_points_pct", [])
    lines.append(f"\n【透视线】{len(persp)} 条")
    lines.append(f"【消失点】{len(vps)} 个")

    # 分析元信息
    meta = result.get("analysis_meta", {})
    if meta.get("analysis_limitations"):
        lines.append(f"\n【分析限制】{meta['analysis_limitations']}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def extract_json_from_response(text: str) -> dict:
    """从 AI 回复中提取 JSON（处理 markdown code block 包裹的情况）"""
    text = text.strip()
    # 去掉 markdown code block
    if text.startswith("```"):
        # 找到第一个换行后的内容
        first_newline = text.index("\n")
        last_backtick = text.rfind("```")
        if last_backtick > first_newline:
            text = text[first_newline + 1:last_backtick].strip()

    return json.loads(text)


def main():
    parser = argparse.ArgumentParser(description="场景原画结构化视觉分析")
    parser.add_argument("image", help="原画图片路径")
    parser.add_argument("--output", "-o", default=None, help="输出目录（默认: 图片同目录/scene_analysis_<timestamp>）")
    parser.add_argument("--rounds", "-r", type=int, default=1, choices=[1, 2, 3], help="分析轮数: 1=基础, 2=+细化, 3=+一致性校验")
    parser.add_argument("--skill-dir", default=None, help="Skill 目录（默认: 脚本所在的上级目录）")
    parser.add_argument("--dry-run", action="store_true", help="只输出 prompt 不调用 AI")
    args = parser.parse_args()

    # 定位 skill 目录
    if args.skill_dir:
        skill_dir = args.skill_dir
    else:
        skill_dir = str(Path(__file__).parent.parent)

    # 加载 schema
    schema = load_schema(skill_dir)

    # 加载图片
    img_b64, mime_type = load_image_base64(args.image)
    print(f"[OK] 已加载图片: {args.image} ({mime_type})")

    # 构造 prompt
    system_prompt = build_system_prompt()
    analysis_prompt = build_analysis_prompt(schema)

    if args.dry_run:
        print("\n=== System Prompt ===")
        print(system_prompt)
        print("\n=== Analysis Prompt ===")
        print(analysis_prompt)
        print(f"\n[DRY RUN] 图片已加载 ({len(img_b64)} bytes base64)")
        print(f"[DRY RUN] 共 {args.rounds} 轮分析")
        return

    # ---- AI 调用部分 ----
    # 此脚本输出 prompt 和结构供外部调用
    # 实际 AI 调用由 OpenClaw Agent 在 SKILL.md 流程中完成
    # 这里提供 prompt 构造和结果解析功能

    print("\n[INFO] 此脚本提供 prompt 构造和结果解析功能。")
    print("[INFO] 实际 AI 视觉分析由 Agent 通过多模态 API 完成。")
    print("[INFO] 使用 --dry-run 查看生成的完整 prompt。")

    # 输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(args.image).parent / f"scene_analysis_{timestamp}"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存 prompt 供 Agent 使用
    prompt_data = {
        "system_prompt": system_prompt,
        "rounds": [
            {"round": 1, "prompt": analysis_prompt},
        ],
        "image_path": str(Path(args.image).resolve()),
        "image_mime": mime_type,
        "output_dir": str(output_dir),
    }

    if args.rounds >= 2:
        prompt_data["rounds"].append({"round": 2, "prompt": build_refinement_prompt()})
    if args.rounds >= 3:
        prompt_data["rounds"].append({"round": 3, "prompt": build_validation_prompt()})

    prompt_file = output_dir / "prompts.json"
    with open(prompt_file, "w", encoding="utf-8") as f:
        json.dump(prompt_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Prompt 已保存: {prompt_file}")


def save_result(output_dir: str, result_json: str) -> None:
    """供外部调用: 解析 AI 返回的 JSON 并保存结果 + 摘要"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result = extract_json_from_response(result_json)

    # 保存 JSON
    result_file = output_path / "analysis_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 分析结果已保存: {result_file}")

    # 生成并保存摘要
    summary = generate_summary(result)
    summary_file = output_path / "analysis_summary.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"[OK] 分析摘要已保存: {summary_file}")

    return result


if __name__ == "__main__":
    main()
