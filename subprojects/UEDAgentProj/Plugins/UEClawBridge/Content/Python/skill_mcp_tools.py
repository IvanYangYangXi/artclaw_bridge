"""
skill_mcp_tools.py - Skill 管理 MCP Tools
=============================================

阶段 B5: MCP Tools for Skill Management

宪法约束:
  - skill-management-system.md 9.1: 新增 Tools
  - 系统架构设计 1.5: Core Tool / Skill 二层体系

提供以下 MCP Tools:
  - skill_create: 从模板创建新 Skill 脚手架
  - skill_generate: 自然语言描述生成 Skill (需 AI)
  - skill_test: 测试 Skill 基础合规性
  - skill_package: 打包 Skill 为可分发格式
  - skill_publish: 发布 Skill 到指定层级
  - skill_list: 列出已注册 Skill
  - skill_info: 查看 Skill 详情
  - skill_enable: 启用 Skill
  - skill_disable: 禁用 Skill
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Optional

from init_unreal import UELogger
from skill_manifest import (
    parse_manifest, validate_manifest, SkillManifest,
    VALID_SOFTWARE, VALID_CATEGORIES, VALID_RISK_LEVELS,
)


# ============================================================================
# 注册入口
# ============================================================================

def register_skill_tools(mcp_server, skill_hub) -> None:
    """将精简后的 Skill 管理 Tool 注册到 MCP Server（v2.6: 默认不注册）"""

    if os.environ.get("ARTCLAW_LEGACY_MCP", "").lower() != "true":
        UELogger.info("Skill management MCP tools: skipped (v2.6 slim mode). "
                      "Use skill_hub.execute_skill() / list_skills() Python API instead.")
        return

    # --- 以下为旧版 MCP 注册（仅 ARTCLAW_LEGACY_MCP=true 时执行）---

    # --- skill_list: 保留，查询用 ---
    mcp_server.register_tool(
        name="skill_list",
        description=(
            "List all registered ArtClaw skills. "
            "Can filter by category, software, source layer, or keyword. "
            "Returns name, version, category, layer, and description."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": f"Filter by category: {sorted(VALID_CATEGORIES)}",
                },
                "software": {
                    "type": "string",
                    "description": f"Filter by software: {sorted(VALID_SOFTWARE)}",
                },
                "layer": {
                    "type": "string",
                    "description": "Filter by source layer: official, team, user, custom",
                },
                "keyword": {
                    "type": "string",
                    "description": "Search keyword (matches name, description, tags)",
                },
            },
        },
        handler=lambda args: _handle_skill_list(skill_hub, args),
    )

    # --- skill_manage: 合并 create/test/package/publish/install/uninstall/enable/disable/update/info ---
    mcp_server.register_tool(
        name="skill_manage",
        description=(
            "Manage ArtClaw skills. Actions: info, create, test, package, publish, "
            "install, uninstall, enable, disable, update. "
            "Pass 'action' and action-specific parameters."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["info", "create", "test", "package", "publish",
                             "install", "uninstall", "enable", "disable", "update"],
                    "description": "Management action to perform",
                },
                "name": {
                    "type": "string",
                    "description": "Skill name (for most actions)",
                },
                "description": {
                    "type": "string",
                    "description": "Skill description (for create)",
                },
                "category": {
                    "type": "string",
                    "description": f"Category (for create): {sorted(VALID_CATEGORIES)}",
                },
                "software": {
                    "type": "string",
                    "description": "Target software (for create, default: unreal_engine)",
                    "default": "unreal_engine",
                },
                "template": {
                    "type": "string",
                    "description": "Template (for create): basic, advanced",
                    "default": "basic",
                },
                "target_layer": {
                    "type": "string",
                    "description": "Target layer: user, team, official, custom",
                    "default": "user",
                },
                "source": {
                    "type": "string",
                    "description": "Source path (for install)",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Output directory (for package)",
                },
                "message": {
                    "type": "string",
                    "description": "Publish message",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Confirm destructive action (for uninstall)",
                    "default": False,
                },
                "path": {
                    "type": "string",
                    "description": "Skill directory path (for test)",
                },
                "risk_level": {
                    "type": "string",
                    "description": "Risk level (for create)",
                    "default": "low",
                },
                "display_name": {
                    "type": "string",
                    "description": "Display name (for create)",
                },
                "author": {
                    "type": "string",
                    "description": "Author (for create)",
                    "default": "User",
                },
            },
            "required": ["action"],
        },
        handler=lambda args: _handle_skill_manage(skill_hub, args),
    )

    # --- skill_generate: 自然语言生成 (v2 对话式) ---
    mcp_server.register_tool(
        name="skill_generate",
        description=(
            "Generate a new skill from a natural language description. "
            "Analyzes the intent, determines category/software, generates "
            "manifest.json + __init__.py + SKILL.md. "
            "Returns generated file contents for review before activation.\n\n"
            "WORKFLOW (AI-driven conversational skill creation):\n"
            "1. User describes what they want → AI calls this tool with description\n"
            "2. Tool auto-detects UE version, software, infers category/risk_level\n"
            "3. AI reviews the result, presents a summary to the user for confirmation\n"
            "4. If user confirms → AI calls skill_manage(action='create') to install\n"
            "5. If user wants changes → AI adjusts parameters and re-generates\n\n"
            "AI can pass pre-inferred fields (name, display_name, category, risk_level) "
            "to override the tool's fallback inference. Fields left empty will be auto-inferred.\n\n"
            "The tool returns needs_confirmation=true — AI MUST show the summary to the "
            "user and wait for confirmation before calling skill_manage(action='create')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of the desired skill",
                },
                "name": {
                    "type": "string",
                    "description": "Skill name in snake_case (AI-inferred, or leave empty for auto)",
                },
                "display_name": {
                    "type": "string",
                    "description": "Human-readable display name (AI-inferred, or leave empty for auto)",
                },
                "category": {
                    "type": "string",
                    "description": f"Hint for category: {sorted(VALID_CATEGORIES)}",
                },
                "risk_level": {
                    "type": "string",
                    "description": f"Risk level: {sorted(VALID_RISK_LEVELS)} (AI-inferred based on read/write/delete)",
                },
                "software": {
                    "type": "string",
                    "description": f"Target software: {sorted(VALID_SOFTWARE)} (auto-detected from environment if empty)",
                },
                "target_layer": {
                    "type": "string",
                    "description": "Target layer: user (default), team, custom",
                    "default": "user",
                },
                "author": {
                    "type": "string",
                    "description": "Author name (optional)",
                },
            },
            "required": ["description"],
        },
        handler=lambda args: _handle_skill_generate(skill_hub, args),
    )

    UELogger.info(f"Registered 3 skill management MCP tools (consolidated from 12)")


# ============================================================================
# Handler 实现
# ============================================================================

def _handle_skill_manage(hub, arguments: dict) -> str:
    """统一 skill 管理操作路由"""
    action = arguments.get("action", "")
    dispatch = {
        "info": _handle_skill_info,
        "create": _handle_skill_create,
        "test": _handle_skill_test,
        "package": _handle_skill_package,
        "publish": _handle_skill_publish,
        "install": _handle_skill_install,
        "uninstall": _handle_skill_uninstall,
        "enable": _handle_skill_enable,
        "disable": _handle_skill_disable,
        "update": _handle_skill_update,
    }
    handler = dispatch.get(action)
    if handler is None:
        return json.dumps({"success": False, "error": f"Unknown action: {action}"})
    return handler(hub, arguments)


def _handle_skill_list(hub, arguments: dict) -> str:
    """列出 Skill"""
    category = arguments.get("category", "")
    software = arguments.get("software", "")
    layer = arguments.get("layer", "")
    keyword = arguments.get("keyword", "").lower()

    skills = hub.get_skill_list()

    # 过滤
    if category:
        skills = [s for s in skills if s.get("category") == category]
    if software:
        skills = [s for s in skills if s.get("software", "universal") == software]
    if layer:
        skills = [s for s in skills if s.get("source_layer") == layer]
    if keyword:
        skills = [
            s for s in skills
            if keyword in s.get("name", "").lower()
            or keyword in s.get("description", "").lower()
            or keyword in str(s.get("tags", [])).lower()
        ]

    return json.dumps({
        "success": True,
        "count": len(skills),
        "skills": skills,
        "disabled": hub.get_disabled_skills(),
    }, default=str)


def _handle_skill_info(hub, arguments: dict) -> str:
    """获取 Skill 详情"""
    name = arguments.get("name", "")
    if not name:
        return json.dumps({"success": False, "error": "name is required"})

    info = hub.get_skill_info(name)
    if info is None:
        return json.dumps({"success": False, "error": f"Skill not found: {name}"})

    # 附加冲突信息
    conflict_report = hub.get_conflict_report()
    conflicts = []
    if conflict_report:
        for c in conflict_report.get("skill_conflicts", []):
            if c["skill_name"] == name:
                conflicts.append(c)
        for c in conflict_report.get("tool_conflicts", []):
            if c.get("winner_skill") == name:
                conflicts.append(c)

    info["conflicts"] = conflicts
    info["success"] = True
    return json.dumps(info, default=str)


def _handle_skill_create(hub, arguments: dict) -> str:
    """创建新 Skill"""
    name = arguments.get("name", "")
    description = arguments.get("description", "")
    display_name = arguments.get("display_name", name)
    category = arguments.get("category", "utils")
    software = arguments.get("software", "unreal_engine")
    risk_level = arguments.get("risk_level", "low")
    template = arguments.get("template", "basic")
    target_layer = arguments.get("target_layer", "user")
    author = arguments.get("author", "User")

    # 验证
    if not name:
        return json.dumps({"success": False, "error": "name is required"})
    if not description:
        return json.dumps({"success": False, "error": "description is required"})
    if category not in VALID_CATEGORIES:
        return json.dumps({"success": False, "error": f"Invalid category: {category}"})
    if software not in VALID_SOFTWARE:
        return json.dumps({"success": False, "error": f"Invalid software: {software}"})
    if risk_level not in VALID_RISK_LEVELS:
        return json.dumps({"success": False, "error": f"Invalid risk_level: {risk_level}"})

    # 确定目标目录
    layer_map = {
        "official": "00_official",
        "team": "01_team",
        "user": "02_user",
        "custom": "99_custom",
    }
    layer_dir = layer_map.get(target_layer, "02_user")
    skill_dir = hub._skills_dir / layer_dir / name

    if skill_dir.exists():
        return json.dumps({
            "success": False,
            "error": f"Skill directory already exists: {skill_dir}"
        })

    try:
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 生成 SKILL.md (OpenClaw 兼容格式)
        skill_md = _generate_skill_md(name, display_name, description, category, risk_level)
        skill_md_path = skill_dir / "SKILL.md"
        skill_md_path.write_text(skill_md, encoding="utf-8")

        # 生成 manifest.json (ArtClaw MCP 注册用)
        manifest = {
            "manifest_version": "1.0",
            "name": name,
            "display_name": display_name,
            "description": description,
            "version": "1.0.0",
            "author": author,
            "license": "MIT",
            "software": software,
            "category": category,
            "risk_level": risk_level,
            "dependencies": [],
            "tags": [category],
            "entry_point": "__init__.py",
            "tools": [
                {
                    "name": name,
                    "description": description
                }
            ]
        }
        manifest_path = skill_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # 生成 __init__.py
        init_code = _generate_init_code(name, description, category, risk_level, template)
        init_path = skill_dir / "__init__.py"
        init_path.write_text(init_code, encoding="utf-8")

        # 触发重新扫描
        hub.scan_and_register()

        return json.dumps({
            "success": True,
            "skill_name": name,
            "skill_dir": str(skill_dir),
            "layer": target_layer,
            "files_created": ["SKILL.md", "manifest.json", "__init__.py"],
            "message": f"Skill '{name}' created in {target_layer} layer. Edit {init_path} to implement your logic."
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _generate_skill_md(name: str, display_name: str, description: str,
                       category: str, risk_level: str) -> str:
    """生成 SKILL.md (OpenClaw 兼容格式)"""
    # name 转 kebab-case 用于 SKILL.md (OpenClaw 惯例)
    kebab_name = name.replace("_", "-")
    return (
        f"---\n"
        f"name: {kebab_name}\n"
        f"description: >\n"
        f"  {description}\n"
        f"---\n"
        f"\n"
        f"# {display_name}\n"
        f"\n"
        f"{description}\n"
        f"\n"
        f"## Tool\n"
        f"\n"
        f"`{name}(arguments)`\n"
        f"\n"
        f"## Notes\n"
        f"\n"
        f"- Category: {category}\n"
        f"- Risk level: {risk_level}\n"
        f"- Auto-loaded by ArtClaw Skill Hub\n"
        f"- Edit `__init__.py` to implement logic\n"
    )


def _generate_init_code(name: str, description: str, category: str,
                         risk_level: str, template: str) -> str:
    """生成 __init__.py 模板代码"""
    if template == "advanced":
        return f'''"""
{name} - {description}
{'=' * (len(name) + 3 + len(description))}

Skill Hub auto-discovers and registers. Save to hot-reload.
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None


# ============================================================================
# Helpers
# ============================================================================

def _validate_input(arguments: dict, required_fields: list) -> str:
    """Validate required fields, return error message or empty string"""
    for field in required_fields:
        if not arguments.get(field):
            return f"{{field}} is required"
    return ""


# ============================================================================
# Tools
# ============================================================================

@ue_tool(
    name="{name}",
    description="{description}",
    category="{category}",
    risk_level="{risk_level}",
)
def {name}(arguments: dict) -> str:
    """TODO: implement"""
    if unreal is None:
        return json.dumps({{"success": False, "error": "Not running in Unreal Engine"}})

    try:
        # TODO: implement your logic
        return json.dumps({{"success": True, "data": {{}}}}, default=str)
    except Exception as e:
        return json.dumps({{"success": False, "error": str(e)}})
'''
    else:  # basic
        return f'''"""
{name} - {description}
{'=' * (len(name) + 3 + len(description))}

Skill Hub auto-discovers and registers. Save to hot-reload.
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None


@ue_tool(
    name="{name}",
    description="{description}",
    category="{category}",
    risk_level="{risk_level}",
)
def {name}(arguments: dict) -> str:
    """TODO: implement"""
    if unreal is None:
        return json.dumps({{"success": False, "error": "Not running in Unreal Engine"}})

    try:
        # TODO: implement your logic
        return json.dumps({{"success": True, "data": {{}}}}, default=str)
    except Exception as e:
        return json.dumps({{"success": False, "error": str(e)}})
'''


def _handle_skill_test(hub, arguments: dict) -> str:
    """测试 Skill 合规性"""
    name = arguments.get("name", "")
    path = arguments.get("path", "")

    if not name and not path:
        return json.dumps({"success": False, "error": "name or path is required"})

    # 找到 Skill 目录
    skill_dir = None
    if path:
        skill_dir = path
    elif name:
        # 搜索所有层级
        for layer_dir_name in ["00_official", "01_team", "02_user", "99_custom"]:
            candidate = hub._skills_dir / layer_dir_name / name
            if candidate.exists():
                skill_dir = str(candidate)
                break
            # 检查 category 子目录
            layer_path = hub._skills_dir / layer_dir_name
            if layer_path.exists():
                for cat_dir in layer_path.iterdir():
                    if cat_dir.is_dir():
                        candidate = cat_dir / name
                        if candidate.exists():
                            skill_dir = str(candidate)
                            break
            if skill_dir:
                break

    if not skill_dir or not os.path.isdir(skill_dir):
        return json.dumps({"success": False, "error": f"Skill directory not found: {name or path}"})

    # 验证 manifest
    manifest_path = os.path.join(skill_dir, "manifest.json")
    is_valid, errors = validate_manifest(manifest_path)

    # 检查入口文件
    entry_exists = os.path.exists(os.path.join(skill_dir, "__init__.py"))

    result = {
        "success": is_valid and entry_exists,
        "skill_dir": skill_dir,
        "manifest_valid": is_valid,
        "entry_point_exists": entry_exists,
        "errors": [e.to_dict() for e in errors if e.severity == "error"],
        "warnings": [e.to_dict() for e in errors if e.severity == "warning"],
    }

    if is_valid and entry_exists:
        result["message"] = "Skill validation passed"
    else:
        result["message"] = "Skill validation failed"

    return json.dumps(result, default=str)


def _handle_skill_package(hub, arguments: dict) -> str:
    """打包 Skill"""
    name = arguments.get("name", "")
    output_dir = arguments.get("output_dir", "")

    if not name:
        return json.dumps({"success": False, "error": "name is required"})

    manifest = hub._manifests.get(name)
    if manifest is None:
        return json.dumps({"success": False, "error": f"Skill not found: {name}"})

    skill_dir = manifest.source_dir
    if not skill_dir or not os.path.isdir(skill_dir):
        return json.dumps({"success": False, "error": f"Skill directory not found: {skill_dir}"})

    # 确定输出目录
    if not output_dir:
        try:
            import unreal as ue
            project_dir = str(ue.Paths.project_dir())
            output_dir = os.path.join(project_dir, "Saved", "SkillPackages")
        except Exception:
            output_dir = os.path.join(str(hub._skills_dir), "_packages")

    os.makedirs(output_dir, exist_ok=True)

    try:
        archive_name = f"{name}-{manifest.version}"
        archive_path = os.path.join(output_dir, archive_name)
        result_path = shutil.make_archive(archive_path, "zip", skill_dir)

        return json.dumps({
            "success": True,
            "package_path": result_path,
            "skill_name": name,
            "version": manifest.version,
            "size_bytes": os.path.getsize(result_path),
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_skill_publish(hub, arguments: dict) -> str:
    """发布 Skill 到目标层级"""
    name = arguments.get("name", "")
    target_layer = arguments.get("target_layer", "")
    message = arguments.get("message", "")

    if not name:
        return json.dumps({"success": False, "error": "name is required"})
    if not target_layer:
        return json.dumps({"success": False, "error": "target_layer is required"})

    manifest = hub._manifests.get(name)
    if manifest is None:
        return json.dumps({"success": False, "error": f"Skill not found: {name}"})

    layer_map = {
        "official": "00_official",
        "team": "01_team",
        "user": "02_user",
        "custom": "99_custom",
    }

    if target_layer not in layer_map:
        return json.dumps({"success": False, "error": f"Invalid layer: {target_layer}"})

    src_dir = manifest.source_dir
    dst_dir = str(hub._skills_dir / layer_map[target_layer] / name)

    if src_dir == dst_dir:
        return json.dumps({"success": False, "error": "Source and target are the same"})

    try:
        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)

        # 重新扫描
        hub.scan_and_register()

        return json.dumps({
            "success": True,
            "skill_name": name,
            "from_layer": manifest.source_layer,
            "to_layer": target_layer,
            "target_dir": dst_dir,
            "message": message or f"Published {name} to {target_layer}",
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_skill_enable(hub, arguments: dict) -> str:
    """启用 Skill"""
    name = arguments.get("name", "")
    if not name:
        return json.dumps({"success": False, "error": "name is required"})

    result = hub.enable_skill(name)
    return json.dumps({
        "success": result,
        "skill_name": name,
        "message": f"Skill '{name}' enabled" if result else f"Skill '{name}' was not disabled",
    })


def _handle_skill_disable(hub, arguments: dict) -> str:
    """禁用 Skill"""
    name = arguments.get("name", "")
    if not name:
        return json.dumps({"success": False, "error": "name is required"})

    result = hub.disable_skill(name)
    return json.dumps({
        "success": result,
        "skill_name": name,
        "message": f"Skill '{name}' disabled" if result else f"Skill '{name}' not found",
    })


# ============================================================================
# Phase B5 新增 Handlers
# ============================================================================

def _collect_environment_context() -> dict:
    """自动收集当前 UE 环境上下文 (B1: 3.7 Skill 创建交互优化)"""
    ctx = {"software": "unreal_engine"}
    try:
        import unreal
        # UE 版本
        ctx["ue_version"] = str(unreal.SystemLibrary.get_engine_version())
        # 项目名
        project_path = str(unreal.Paths.get_project_file_path())
        if project_path:
            ctx["project_name"] = project_path.split("/")[-1].split("\\")[-1].replace(".uproject", "")
        # 当前关卡
        world = unreal.EditorLevelLibrary.get_editor_world()
        if world:
            ctx["current_level"] = world.get_name()
    except Exception as e:
        ctx["_env_error"] = str(e)
    return ctx


def _infer_risk_level(description: str) -> str:
    """从描述推断风险级别 (B4: 3.7 优化)"""
    desc_lower = description.lower()

    # 高危操作关键词
    high_keywords = ["delete", "remove", "drop", "删除", "移除", "清除", "清空"]
    for kw in high_keywords:
        if kw in desc_lower:
            return "high"

    # 中危操作关键词（可撤销的修改）
    medium_keywords = [
        "rename", "set", "modify", "change", "move", "batch", "replace",
        "重命名", "设置", "修改", "移动", "批量", "替换", "编辑",
    ]
    for kw in medium_keywords:
        if kw in desc_lower:
            return "medium"

    return "low"


def _handle_skill_generate(hub, arguments: dict) -> str:
    """
    自然语言生成 Skill — v2 对话式 (3.7 Skill 创建交互优化)

    由上层 AI Agent (OpenClaw/Claude) 驱动:
      1. Agent 调用此 Tool，传入自然语言描述
      2. 此 Tool 自动收集 UE 环境上下文 + 推断元数据
      3. 返回推断结果 + scaffold 供 Agent 展示给用户确认
      4. 用户确认后 Agent 调用 skill_manage(action=create) 安装

    AI Agent 负责: name 精细推断、display_name、多轮追问
    此 Tool 负责: 环境收集、fallback 推断、scaffold 生成
    """
    description = arguments.get("description", "")
    category = arguments.get("category", "")
    software = arguments.get("software", "")
    target_layer = arguments.get("target_layer", "user")
    # v2 新增: AI 可直接传入推断好的字段
    name = arguments.get("name", "")
    display_name = arguments.get("display_name", "")
    risk_level = arguments.get("risk_level", "")
    author = arguments.get("author", "")

    if not description:
        return json.dumps({"success": False, "error": "description is required"})

    # B1: 自动收集环境上下文
    env_context = _collect_environment_context()

    # software: 优先用传入值，其次环境检测值
    if not software:
        software = env_context.get("software", "unreal_engine")

    # name: 优先用 AI 传入值，其次 fallback 推断
    if not name:
        name = _infer_skill_name(description)

    # display_name: 优先用 AI 传入值
    if not display_name:
        display_name = description[:60]

    # category: 优先用传入值，其次推断
    if not category:
        category = _infer_category(description)

    # risk_level: 优先用传入值，其次推断
    if not risk_level:
        risk_level = _infer_risk_level(description)

    # author
    if not author:
        author = "AI Generated"

    # 生成 manifest
    manifest_data = {
        "manifest_version": "1.0",
        "name": name,
        "display_name": display_name,
        "description": description,
        "version": "1.0.0",
        "author": author,
        "license": "MIT",
        "software": software,
        "category": category,
        "risk_level": risk_level,
        "dependencies": [],
        "tags": [category, "ai-generated"],
        "entry_point": "__init__.py",
        "tools": [
            {
                "name": name,
                "description": description
            }
        ]
    }

    # 添加 software_version（如果有 UE 版本信息）
    ue_ver = env_context.get("ue_version", "")
    if ue_ver and software == "unreal_engine":
        # 提取主版本号 e.g. "5.5.1-0+++UE5" -> "5.5"
        parts = ue_ver.split(".")
        if len(parts) >= 2:
            min_ver = f"{parts[0]}.{parts[1]}"
            manifest_data["software_version"] = {"min": min_ver}

    # 生成 SKILL.md (OpenClaw 兼容格式)
    skill_md = _generate_skill_md(name, display_name, description, category, risk_level)

    # 生成 __init__.py scaffold
    init_code = _generate_init_code(name, description, category, risk_level, "advanced")

    return json.dumps({
        "success": True,
        "skill_name": name,
        "display_name": display_name,
        "inferred_category": category,
        "inferred_risk_level": risk_level,
        "environment": env_context,
        "target_layer": target_layer,
        "needs_confirmation": True,
        "generated_files": {
            "SKILL.md": skill_md,
            "manifest.json": manifest_data,
            "__init__.py": init_code,
        },
        "next_steps": [
            f"Review the generated code above",
            f"Call skill_manage with action='create' and name='{name}' to install, or",
            f"Modify the __init__.py code and save to Skills/{_layer_dir(target_layer)}/{name}/",
        ],
        "message": (
            f"Skill scaffold generated for '{name}' ({category}). "
            f"Review the generated files and modify __init__.py to add your implementation."
        ),
    }, default=str, ensure_ascii=False)


def _infer_skill_name(description: str) -> str:
    """从自然语言描述推断 snake_case Skill 名称"""
    import re
    # 提取英文单词或中文关键词
    words = re.findall(r"[a-zA-Z]+", description.lower())
    if not words:
        # 中文描述 → 简单映射
        keyword_map = {
            "材质": "material",
            "灯光": "lighting",
            "场景": "scene",
            "资产": "asset",
            "重命名": "rename",
            "批量": "batch",
            "文档": "documentation",
            "导出": "export",
            "导入": "import",
            "创建": "create",
            "生成": "generate",
            "读取": "read",
            "删除": "delete",
        }
        parts = []
        for cn, en in keyword_map.items():
            if cn in description:
                parts.append(en)
        if not parts:
            parts = ["custom_skill"]
        words = parts

    # 取前 5 个单词组成名称
    name = "_".join(words[:5])
    # 确保符合命名规范
    name = re.sub(r"[^a-z0-9_]", "", name)
    if not name or not name[0].isalpha():
        name = "skill_" + name
    return name[:64]


def _infer_category(description: str) -> str:
    """从描述推断 Skill 分类"""
    desc_lower = description.lower()
    category_keywords = {
        "material": ["material", "shader", "texture", "材质", "贴图", "着色"],
        "lighting": ["light", "shadow", "灯光", "阴影", "照明"],
        "scene": ["scene", "actor", "level", "场景", "关卡", "Actor"],
        "asset": ["asset", "import", "export", "资产", "导入", "导出"],
        "render": ["render", "渲染", "后处理", "post process"],
        "blueprint": ["blueprint", "蓝图", "节点"],
        "animation": ["animation", "anim", "动画", "骨骼"],
        "ui": ["ui", "widget", "umg", "界面"],
        "workflow": ["workflow", "batch", "pipeline", "工作流", "批量"],
        "integration": ["integration", "third-party", "集成", "第三方"],
    }

    for cat, keywords in category_keywords.items():
        for kw in keywords:
            if kw in desc_lower:
                return cat

    return "utils"


def _layer_dir(layer: str) -> str:
    """层级名 → 目录名"""
    return {
        "official": "00_official",
        "team": "01_team",
        "user": "02_user",
        "custom": "99_custom",
    }.get(layer, "02_user")


def _handle_skill_install(hub, arguments: dict) -> str:
    """从本地目录或 zip 安装 Skill"""
    source = arguments.get("source", "")
    target_layer = arguments.get("target_layer", "user")

    if not source:
        return json.dumps({"success": False, "error": "source is required"})

    source_path = Path(source)
    if not source_path.exists():
        return json.dumps({"success": False, "error": f"Source not found: {source}"})

    try:
        # 如果是 zip 文件，先解压到临时目录
        if source_path.suffix == ".zip":
            import tempfile
            import zipfile
            tmp_dir = tempfile.mkdtemp(prefix="artclaw_skill_")
            with zipfile.ZipFile(str(source_path), "r") as zf:
                zf.extractall(tmp_dir)
            # 查找 manifest.json
            tmp_path = Path(tmp_dir)
            manifest_files = list(tmp_path.rglob("manifest.json"))
            if not manifest_files:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return json.dumps({
                    "success": False,
                    "error": "No manifest.json found in archive"
                })
            skill_src_dir = manifest_files[0].parent
        elif source_path.is_dir():
            skill_src_dir = source_path
            tmp_dir = None
        else:
            return json.dumps({
                "success": False,
                "error": "Source must be a directory or .zip file"
            })

        # 验证 manifest
        manifest_path = str(skill_src_dir / "manifest.json")
        is_valid, errors = validate_manifest(manifest_path)
        if not is_valid:
            error_msgs = [e.to_dict() for e in errors if e.severity == "error"]
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return json.dumps({
                "success": False,
                "error": "Manifest validation failed",
                "details": error_msgs,
            })

        # 读取名称
        manifest, _ = parse_manifest(manifest_path)
        if manifest is None:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return json.dumps({"success": False, "error": "Failed to parse manifest"})

        skill_name = manifest.name

        # 确定目标目录
        layer_dir_name = _layer_dir(target_layer)
        dest_dir = hub._skills_dir / layer_dir_name / skill_name

        if dest_dir.exists():
            shutil.rmtree(str(dest_dir))

        shutil.copytree(str(skill_src_dir), str(dest_dir))

        # 清理临时目录
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # 重新扫描
        hub.scan_and_register()

        return json.dumps({
            "success": True,
            "skill_name": skill_name,
            "version": manifest.version,
            "installed_to": str(dest_dir),
            "layer": target_layer,
            "message": f"Skill '{skill_name}' v{manifest.version} installed to {target_layer} layer",
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_skill_uninstall(hub, arguments: dict) -> str:
    """卸载 Skill"""
    name = arguments.get("name", "")
    confirm = arguments.get("confirm", False)

    if not name:
        return json.dumps({"success": False, "error": "name is required"})

    manifest = hub._manifests.get(name)
    if manifest is None:
        return json.dumps({"success": False, "error": f"Skill not found: {name}"})

    if not confirm:
        return json.dumps({
            "success": False,
            "error": "Confirmation required",
            "skill_name": name,
            "source_dir": manifest.source_dir,
            "layer": manifest.source_layer,
            "message": (
                f"This will permanently delete the skill directory "
                f"'{manifest.source_dir}'. Set confirm=true to proceed."
            ),
        })

    try:
        skill_dir = manifest.source_dir
        if not skill_dir or not os.path.isdir(skill_dir):
            return json.dumps({"success": False, "error": "Skill directory not found"})

        # 先禁用（注销 MCP tools）
        hub.disable_skill(name)

        # 删除目录
        shutil.rmtree(skill_dir)

        # 重新扫描
        hub.scan_and_register()

        return json.dumps({
            "success": True,
            "skill_name": name,
            "removed_dir": skill_dir,
            "message": f"Skill '{name}' has been uninstalled",
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_skill_update(hub, arguments: dict) -> str:
    """更新/重新加载 Skill"""
    name = arguments.get("name", "")

    if not name:
        return json.dumps({"success": False, "error": "name is required"})

    manifest = hub._manifests.get(name)
    if manifest is None:
        return json.dumps({"success": False, "error": f"Skill not found: {name}"})

    try:
        old_version = manifest.version

        # 重新扫描并注册
        hub.scan_and_register()

        # 检查更新后的状态
        new_manifest = hub._manifests.get(name)
        if new_manifest is None:
            return json.dumps({
                "success": False,
                "error": f"Skill '{name}' disappeared after rescan (possible manifest error)",
            })

        return json.dumps({
            "success": True,
            "skill_name": name,
            "old_version": old_version,
            "new_version": new_manifest.version,
            "tools": [t.name for t in new_manifest.tools],
            "message": f"Skill '{name}' reloaded (v{old_version} → v{new_manifest.version})",
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})