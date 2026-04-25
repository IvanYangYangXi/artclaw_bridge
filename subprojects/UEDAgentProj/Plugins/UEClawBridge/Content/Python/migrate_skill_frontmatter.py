"""
migrate_skill_frontmatter.py — 批量迁移 SKILL.md frontmatter 到 OpenClaw 兼容格式

将 ArtClaw 专属字段（author/software/category/risk_level/display_name/version/tags）
从 YAML 顶层迁移到 metadata.artclaw.* 命名空间。

用法:
    python migrate_skill_frontmatter.py [--dry-run] [--dir <skills_dir>]
    python migrate_skill_frontmatter.py --dry-run   # 只预览，不修改
    python migrate_skill_frontmatter.py              # 执行迁移
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path


# OpenClaw 允许的顶层 frontmatter 字段
OPENCLAW_ALLOWED = {"name", "description", "license", "allowed-tools", "metadata"}

# 需要迁移到 metadata.artclaw.* 的 ArtClaw 字段
ARTCLAW_FIELDS = {
    "author", "software", "category", "risk_level", "risk-level",
    "display_name", "display-name", "version", "tags",
}

# 不应该迁移的字段（manifest.json 专属，不属于 SKILL.md）
SKIP_FIELDS = {
    "manifest_version", "manifest-version", "entry_point", "entry-point",
    "dependencies", "icon", "config", "tools",
    "software_version", "software-version",
}


def parse_frontmatter_raw(content: str) -> tuple:
    """解析 SKILL.md，返回 (frontmatter_lines, body_lines, start_idx, end_idx)"""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, lines, -1, -1

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx < 0:
        return None, lines, -1, -1

    fm_lines = lines[1:end_idx]
    body_lines = lines[end_idx + 1:]
    return fm_lines, body_lines, 1, end_idx


def extract_flat_fields(fm_lines: list) -> dict:
    """从 frontmatter 行中提取 flat key-value 对。"""
    fields = {}
    current_key = None
    current_value_lines = []
    is_multiline = False

    for line in fm_lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if not stripped or stripped.startswith("#"):
            if is_multiline:
                current_value_lines.append("")
            continue

        # 顶层 key（缩进为 0）
        if indent == 0 and ":" in stripped:
            # 保存上一个多行值
            if current_key and is_multiline:
                fields[current_key] = " ".join(l for l in current_value_lines if l).strip()

            colon_idx = stripped.index(":")
            key = stripped[:colon_idx].strip()
            value = stripped[colon_idx + 1:].strip()

            if value in (">", "|", ">-", "|-"):
                current_key = key
                is_multiline = True
                current_value_lines = []
            elif value.startswith("{") or value.startswith("["):
                # inline JSON — 保持原样
                fields[key] = value
                current_key = key
                is_multiline = False
            elif value:
                # 去引号
                if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or
                                         (value[0] == "'" and value[-1] == "'")):
                    value = value[1:-1]
                fields[key] = value
                current_key = key
                is_multiline = False
            else:
                # 空值（可能有嵌套子块）
                current_key = key
                is_multiline = True
                current_value_lines = []
        elif is_multiline and current_key:
            current_value_lines.append(stripped)

    if current_key and is_multiline:
        joined = " ".join(l for l in current_value_lines if l).strip()
        if joined:
            fields[current_key] = joined

    return fields


def has_metadata_artclaw(fm_lines: list) -> bool:
    """检查 frontmatter 中是否已有 metadata.artclaw 块。"""
    in_metadata = False
    for line in fm_lines:
        stripped = line.strip()
        if stripped == "metadata:" or stripped.startswith("metadata:"):
            in_metadata = True
            continue
        if in_metadata and "artclaw:" in stripped:
            return True
        # 如果碰到另一个顶层 key，重置
        indent = len(line) - len(line.lstrip())
        if indent == 0 and ":" in stripped and stripped != "metadata:":
            in_metadata = False
    return False


def build_new_frontmatter(fields: dict, original_fm_lines: list) -> str:
    """根据提取的字段构建新格式 frontmatter。"""
    lines = []

    # name (必需，转 kebab-case)
    name = fields.get("name", "")
    if name:
        # snake_case → kebab-case
        kebab_name = name.replace("_", "-")
        lines.append(f"name: {kebab_name}")

    # description (保持原格式)
    desc = fields.get("description", "")
    if desc:
        # 检查原 frontmatter 中 description 是否是多行的
        desc_is_multiline = False
        for fl in original_fm_lines:
            if fl.strip().startswith("description:"):
                if fl.strip().endswith(">") or fl.strip().endswith("|"):
                    desc_is_multiline = True
                break

        if desc_is_multiline or len(desc) > 80:
            lines.append("description: >")
            # 按句子分行
            words = desc.split()
            current_line = ""
            for w in words:
                if len(current_line) + len(w) + 1 > 78:
                    lines.append(f"  {current_line}")
                    current_line = w
                else:
                    current_line = f"{current_line} {w}" if current_line else w
            if current_line:
                lines.append(f"  {current_line}")
        else:
            lines.append(f"description: \"{desc}\"")

    # license
    lic = fields.get("license", "")
    if lic:
        lines.append(f"license: {lic}")

    # allowed-tools (保持原值)
    at = fields.get("allowed-tools", "")
    if at:
        lines.append(f"allowed-tools: {at}")

    # metadata 块
    # 检查是否已有 metadata 块（inline JSON）
    existing_metadata = fields.get("metadata", "")
    if existing_metadata and existing_metadata.startswith("{"):
        # 解析已有 inline JSON metadata，合并 artclaw 字段
        try:
            meta_obj = json.loads(existing_metadata)
        except json.JSONDecodeError:
            meta_obj = {}
    else:
        meta_obj = {}

    # 收集需要迁移的 artclaw 字段
    artclaw_data = {}
    for f in ARTCLAW_FIELDS:
        val = fields.get(f, "")
        if val:
            # 统一 key 为 snake_case
            key = f.replace("-", "_")
            artclaw_data[key] = val

    if artclaw_data:
        # 写入 metadata 块
        lines.append("metadata:")

        # openclaw 子块（如有）
        oc = meta_obj.get("openclaw")
        if oc:
            lines.append("  openclaw:")
            for k, v in oc.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"    {k}: {json.dumps(v)}")
                else:
                    lines.append(f"    {k}: \"{v}\"")

        # artclaw 子块
        lines.append("  artclaw:")
        # 按固定顺序输出
        ordered_keys = ["display_name", "author", "software", "category",
                        "risk_level", "version", "tags"]
        for key in ordered_keys:
            if key in artclaw_data:
                val = artclaw_data[key]
                if key == "tags" and isinstance(val, str):
                    # tags 可能是字符串列表
                    lines.append(f"    {key}: {val}")
                else:
                    lines.append(f"    {key}: {val}")

        # 其他非标准的 artclaw 字段
        for key, val in artclaw_data.items():
            if key not in ordered_keys:
                lines.append(f"    {key}: {val}")

    elif "openclaw" in meta_obj:
        # 只有 openclaw 没有 artclaw
        lines.append("metadata:")
        lines.append("  openclaw:")
        for k, v in meta_obj["openclaw"].items():
            if isinstance(v, (dict, list)):
                lines.append(f"    {k}: {json.dumps(v)}")
            else:
                lines.append(f"    {k}: \"{v}\"")

    return "\n".join(lines)


def migrate_skill_md(skill_md_path: Path, dry_run: bool = True) -> dict:
    """
    迁移单个 SKILL.md 文件。

    Returns: {"path": str, "status": "migrated"|"skipped"|"error", "message": str}
    """
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"path": str(skill_md_path), "status": "error", "message": str(e)}

    fm_lines, body_lines, start, end = parse_frontmatter_raw(content)
    if fm_lines is None:
        return {"path": str(skill_md_path), "status": "skipped",
                "message": "No frontmatter found"}

    # 已有 metadata.artclaw → 已迁移
    if has_metadata_artclaw(fm_lines):
        return {"path": str(skill_md_path), "status": "skipped",
                "message": "Already has metadata.artclaw"}

    # 提取字段
    fields = extract_flat_fields(fm_lines)

    # 检查是否有需要迁移的字段
    fields_to_migrate = [f for f in ARTCLAW_FIELDS if fields.get(f)]
    if not fields_to_migrate:
        return {"path": str(skill_md_path), "status": "skipped",
                "message": "No ArtClaw fields to migrate"}

    # 构建新 frontmatter
    new_fm = build_new_frontmatter(fields, fm_lines)

    # 组装新文件
    new_content = "---\n" + new_fm + "\n---\n" + "\n".join(body_lines)

    if dry_run:
        return {"path": str(skill_md_path), "status": "would_migrate",
                "message": f"Fields to move: {fields_to_migrate}",
                "preview": new_fm}

    # 写入
    try:
        skill_md_path.write_text(new_content, encoding="utf-8")
        return {"path": str(skill_md_path), "status": "migrated",
                "message": f"Migrated {len(fields_to_migrate)} fields"}
    except Exception as e:
        return {"path": str(skill_md_path), "status": "error", "message": str(e)}


def migrate_all(skills_dir: Path, dry_run: bool = True) -> list:
    """迁移目录下所有 SKILL.md 文件。"""
    results = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if skill_md.exists():
            result = migrate_skill_md(skill_md, dry_run)
            results.append(result)

        # 也检查子目录（分层结构）
        for sub in sorted(entry.iterdir()):
            if sub.is_dir():
                sub_md = sub / "SKILL.md"
                if sub_md.exists():
                    result = migrate_skill_md(sub_md, dry_run)
                    results.append(result)

                # 再深一层（layer/dcc/skill/）
                for subsub in sorted(sub.iterdir()):
                    if subsub.is_dir():
                        subsub_md = subsub / "SKILL.md"
                        if subsub_md.exists():
                            result = migrate_skill_md(subsub_md, dry_run)
                            results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="迁移 SKILL.md frontmatter 到 OpenClaw 兼容格式")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="只预览不修改")
    parser.add_argument("--dir", default=None,
                        help="Skills 目录（默认: ~/.openclaw/workspace/skills/ 和项目源码 skills/）")
    args = parser.parse_args()

    dirs_to_scan = []
    if args.dir:
        dirs_to_scan.append(Path(args.dir))
    else:
        # 默认扫描两个目录
        oc_skills = Path.home() / ".openclaw" / "workspace" / "skills"
        if oc_skills.exists():
            dirs_to_scan.append(oc_skills)

        # 项目源码
        project_skills = Path(r"D:\MyProject_D\artclaw_bridge\skills")
        if project_skills.exists():
            dirs_to_scan.append(project_skills)

    all_results = []
    for d in dirs_to_scan:
        print(f"\n{'='*60}")
        print(f"Scanning: {d}")
        print(f"{'='*60}")
        results = migrate_all(d, dry_run=args.dry_run)
        all_results.extend(results)

        for r in results:
            status = r["status"]
            path = r["path"]
            msg = r["message"]
            if status == "migrated":
                print(f"  [MIGRATED] {path}")
                print(f"             {msg}")
            elif status == "would_migrate":
                print(f"  [WOULD MIGRATE] {path}")
                print(f"                  {msg}")
                if "preview" in r:
                    for line in r["preview"].split("\n"):
                        print(f"                  | {line}")
            elif status == "error":
                print(f"  [ERROR] {path}: {msg}")
            # skipped → 不打印

    # 汇总
    migrated = sum(1 for r in all_results if r["status"] in ("migrated", "would_migrate"))
    skipped = sum(1 for r in all_results if r["status"] == "skipped")
    errors = sum(1 for r in all_results if r["status"] == "error")
    print(f"\n{'='*60}")
    print(f"Total: {len(all_results)} files scanned")
    print(f"  Migrated/Would migrate: {migrated}")
    print(f"  Skipped (already OK): {skipped}")
    print(f"  Errors: {errors}")
    if args.dry_run and migrated > 0:
        print(f"\n  Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
