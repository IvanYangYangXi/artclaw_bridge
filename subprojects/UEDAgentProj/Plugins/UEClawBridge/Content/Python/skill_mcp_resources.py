"""
skill_mcp_resources.py - Skill 管理 MCP Resources
====================================================

阶段 B6: MCP Resources for Skill Discovery

宪法约束:
  - skill-management-system.md 9.2: 新增 Resources

提供以下 MCP Resources:
  - unreal://skills/official     — 官方库 Skill 列表
  - unreal://skills/team         — 团队库 Skill 列表
  - unreal://skills/user         — 用户库 Skill 列表
  - unreal://skills/custom       — 临时/实验 Skill 列表
  - unreal://skills/disabled     — 已禁用 Skill 列表
  - unreal://skills/categories   — 分类枚举与统计
  - unreal://skills/templates    — 可用模板列表
  - unreal://skills/conflicts    — 冲突检测报告
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from init_unreal import UELogger
from skill_manifest import VALID_CATEGORIES, VALID_SOFTWARE, VALID_RISK_LEVELS


# ============================================================================
# 注册入口
# ============================================================================

def register_skill_resources(mcp_server, skill_hub) -> None:
    """将所有 Skill 管理 Resource 注册到 MCP Server"""

    if not hasattr(mcp_server, 'register_resource'):
        UELogger.info("MCP server does not support resource registration")
        return

    # --- unreal://skills/official ---
    mcp_server.register_resource(
        uri="unreal://skills/official",
        name="Official Skills",
        description="List of ArtClaw official skills (00_official layer)",
        handler=lambda: json.dumps(
            skill_hub.get_skills_by_layer("official"), default=str, indent=2
        ),
    )

    # --- unreal://skills/team ---
    mcp_server.register_resource(
        uri="unreal://skills/team",
        name="Team Skills",
        description="List of team-shared skills (01_team layer)",
        handler=lambda: json.dumps(
            skill_hub.get_skills_by_layer("team"), default=str, indent=2
        ),
    )

    # --- unreal://skills/user ---
    mcp_server.register_resource(
        uri="unreal://skills/user",
        name="User Skills",
        description="List of user's personal skills (02_user layer)",
        handler=lambda: json.dumps(
            skill_hub.get_skills_by_layer("user"), default=str, indent=2
        ),
    )

    # --- unreal://skills/custom ---
    mcp_server.register_resource(
        uri="unreal://skills/custom",
        name="Custom Skills",
        description="List of temporary/experimental skills (99_custom layer)",
        handler=lambda: json.dumps(
            skill_hub.get_skills_by_layer("custom"), default=str, indent=2
        ),
    )

    # --- unreal://skills/disabled ---
    mcp_server.register_resource(
        uri="unreal://skills/disabled",
        name="Disabled Skills",
        description="List of explicitly disabled skills",
        handler=lambda: json.dumps({
            "disabled_skills": skill_hub.get_disabled_skills(),
            "count": len(skill_hub.get_disabled_skills()),
        }, indent=2),
    )

    # --- unreal://skills/categories ---
    mcp_server.register_resource(
        uri="unreal://skills/categories",
        name="Skill Categories",
        description="Available skill categories with counts",
        handler=lambda: _get_categories_data(skill_hub),
    )

    # --- unreal://skills/templates ---
    mcp_server.register_resource(
        uri="unreal://skills/templates",
        name="Skill Templates",
        description="Available templates for creating new skills",
        handler=lambda: _get_templates_data(skill_hub),
    )

    # --- unreal://skills/conflicts ---
    mcp_server.register_resource(
        uri="unreal://skills/conflicts",
        name="Skill Conflicts",
        description="Current skill conflict detection report",
        handler=lambda: json.dumps(
            skill_hub.get_conflict_report() or {"has_conflicts": False},
            default=str, indent=2
        ),
    )

    UELogger.info(f"Registered 8 skill management MCP resources")


# ============================================================================
# Helper 函数
# ============================================================================

def _get_categories_data(skill_hub) -> str:
    """获取分类枚举与统计"""
    from skill_manifest import VALID_CATEGORIES

    # Category display names — inline fallback to avoid path-dependent import
    _CATEGORY_DISPLAY = {
        "scene": "场景操作",
        "asset": "资产管理",
        "material": "材质编辑",
        "lighting": "灯光设置",
        "render": "渲染设置",
        "blueprint": "蓝图操作",
        "animation": "动画相关",
        "ui": "UI/UMG",
        "utils": "工具类",
        "integration": "第三方集成",
        "workflow": "工作流自动化",
    }

    all_skills = skill_hub.get_skill_list()

    # 统计每个分类的 Skill 数量
    counts = {}
    for cat in VALID_CATEGORIES:
        counts[cat] = 0
    for s in all_skills:
        cat = s.get("category", "utils")
        counts[cat] = counts.get(cat, 0) + 1

    categories = []
    for cat in sorted(VALID_CATEGORIES):
        display = _CATEGORY_DISPLAY.get(cat, cat)
        categories.append({
            "name": cat,
            "display_name": display,
            "count": counts.get(cat, 0),
        })

    return json.dumps({
        "categories": categories,
        "total_skills": len(all_skills),
    }, ensure_ascii=False, indent=2)


def _get_templates_data(skill_hub) -> str:
    """获取可用模板列表"""
    templates = [
        {
            "name": "basic",
            "display_name": "Basic Template",
            "description": "Simple single-tool skill with standard error handling",
            "features": ["single tool", "UE guard", "JSON response"],
        },
        {
            "name": "advanced",
            "display_name": "Advanced Template",
            "description": "Multi-tool skill with batch operations, undo support, and helpers",
            "features": [
                "multiple tools",
                "ScopedEditorTransaction",
                "batch operations",
                "helper functions",
                "input validation",
            ],
        },
    ]

    # 检查 artclaw/skills/templates/ 目录是否有自定义模板
    # (模板目录在项目根目录，不在 UE 插件中)
    # 这里只返回内置模板信息

    return json.dumps({
        "templates": templates,
        "count": len(templates),
    }, indent=2)