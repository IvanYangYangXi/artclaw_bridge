"""
generate_material_documentation - 生成材质使用文档 (参考实现)
=============================================================

这是 ArtClaw Skill 开发模板中的参考实现。
基于 skills/unreal_engine/material/generate_material_documentation/ 样板 Skill。

展示了:
- MaterialEditingLibrary 的使用方式
- 参数提取 (Scalar, Vector, Texture, StaticSwitch)
- 材质图表节点遍历
- Markdown 文档生成
- 标准的错误处理和返回值格式

用法:
    由 AI Agent 通过 MCP 协议调用。
"""

from skill_hub import tool as ue_tool
import json
import os

try:
    import unreal
except ImportError:
    unreal = None  # 允许在 UE 外部测试


# ============================================================================
# 辅助函数
# ============================================================================

def _extract_scalar_params(material) -> list:
    """提取 Scalar 参数"""
    params = []
    try:
        mel = unreal.MaterialEditingLibrary
        names = mel.get_scalar_parameter_names(material)
        for name in names:
            value = mel.get_scalar_parameter_value(material, name)
            params.append({
                "name": str(name),
                "type": "Scalar",
                "default_value": round(float(value), 4),
            })
    except Exception:
        pass
    return params


def _extract_vector_params(material) -> list:
    """提取 Vector 参数"""
    params = []
    try:
        mel = unreal.MaterialEditingLibrary
        names = mel.get_vector_parameter_names(material)
        for name in names:
            value = mel.get_vector_parameter_value(material, name)
            params.append({
                "name": str(name),
                "type": "Vector",
                "default_value": {
                    "r": round(value.r, 4),
                    "g": round(value.g, 4),
                    "b": round(value.b, 4),
                    "a": round(value.a, 4),
                },
            })
    except Exception:
        pass
    return params


def _extract_texture_params(material) -> list:
    """提取 Texture 参数"""
    params = []
    try:
        mel = unreal.MaterialEditingLibrary
        names = mel.get_texture_parameter_names(material)
        for name in names:
            texture = mel.get_texture_parameter_value(material, name)
            tex_path = ""
            if texture:
                try:
                    tex_path = str(texture.get_path_name())
                except Exception:
                    tex_path = str(texture.get_name()) if texture else ""
            params.append({
                "name": str(name),
                "type": "Texture",
                "default_texture": tex_path,
            })
    except Exception:
        pass
    return params


def _extract_switch_params(material) -> list:
    """提取 Static Switch 参数"""
    params = []
    try:
        mel = unreal.MaterialEditingLibrary
        names = mel.get_static_switch_parameter_names(material)
        for name in names:
            value = mel.get_static_switch_parameter_value(material, name)
            params.append({
                "name": str(name),
                "type": "StaticSwitch",
                "default_value": bool(value),
            })
    except Exception:
        pass
    return params


def _extract_material_info(material) -> dict:
    """提取材质基本信息"""
    info = {
        "name": str(material.get_name()),
        "path": str(material.get_path_name()),
        "class": str(material.get_class().get_name()),
    }

    property_map = {
        "blend_mode": "blend_mode",
        "shading_model": "shading_model",
        "two_sided": "two_sided",
        "is_masked": "is_masked",
    }
    for key, prop_name in property_map.items():
        try:
            val = material.get_editor_property(prop_name)
            info[key] = str(val) if not isinstance(val, bool) else val
        except Exception:
            pass

    return info


def _extract_expressions(material) -> list:
    """
    提取材质图表中的关键节点（Material Expressions）。

    注意: MaterialEditingLibrary.get_material_expressions() 在部分 UE 版本中
    可能不可用。如果不可用，此功能会优雅降级为空列表。
    """
    expressions = []
    try:
        mel = unreal.MaterialEditingLibrary
        if hasattr(mel, 'get_material_expressions'):
            exprs = mel.get_material_expressions(material)
            for expr in exprs[:50]:  # 限制数量防止过大
                expr_info = {
                    "class": str(expr.get_class().get_name()),
                    "name": str(expr.get_name()),
                }
                try:
                    desc = expr.get_editor_property("desc")
                    if desc:
                        expr_info["description"] = str(desc)
                except Exception:
                    pass
                expressions.append(expr_info)
    except Exception:
        pass
    return expressions


def _generate_markdown(mat_info: dict, params: dict, expressions: list,
                       include_parameters: bool, include_graph: bool) -> str:
    """生成 Markdown 文档"""
    lines = []

    lines.append(f"# {mat_info['name']} 材质文档")
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- **材质名称**: {mat_info['name']}")
    lines.append(f"- **资产路径**: `{mat_info['path']}`")
    lines.append(f"- **类型**: {mat_info['class']}")

    for key in ["blend_mode", "shading_model", "two_sided", "is_masked"]:
        if key in mat_info:
            display_key = key.replace("_", " ").title()
            lines.append(f"- **{display_key}**: {mat_info[key]}")
    lines.append("")

    if include_parameters:
        scalars = params.get("scalar", [])
        if scalars:
            lines.append("## Scalar 参数")
            lines.append("")
            lines.append("| 参数名 | 默认值 |")
            lines.append("|--------|--------|")
            for p in scalars:
                lines.append(f"| {p['name']} | {p['default_value']} |")
            lines.append("")

        vectors = params.get("vector", [])
        if vectors:
            lines.append("## Vector 参数")
            lines.append("")
            lines.append("| 参数名 | R | G | B | A |")
            lines.append("|--------|---|---|---|---|")
            for p in vectors:
                v = p["default_value"]
                lines.append(f"| {p['name']} | {v['r']} | {v['g']} | {v['b']} | {v['a']} |")
            lines.append("")

        textures = params.get("texture", [])
        if textures:
            lines.append("## Texture 参数")
            lines.append("")
            lines.append("| 参数名 | 默认贴图 |")
            lines.append("|--------|----------|")
            for p in textures:
                tex = p.get("default_texture", "None")
                lines.append(f"| {p['name']} | `{tex}` |")
            lines.append("")

        switches = params.get("static_switch", [])
        if switches:
            lines.append("## Static Switch 参数")
            lines.append("")
            lines.append("| 参数名 | 默认值 |")
            lines.append("|--------|--------|")
            for p in switches:
                lines.append(f"| {p['name']} | {p['default_value']} |")
            lines.append("")

        total = len(scalars) + len(vectors) + len(textures) + len(switches)
        if total == 0:
            lines.append("## 参数")
            lines.append("")
            lines.append("此材质没有暴露的参数。")
            lines.append("")

    if include_graph and expressions:
        lines.append("## 材质图表节点")
        lines.append("")
        lines.append(f"共 {len(expressions)} 个节点：")
        lines.append("")
        lines.append("| 节点类型 | 名称 | 描述 |")
        lines.append("|----------|------|------|")
        for e in expressions:
            desc = e.get("description", "")
            lines.append(f"| {e['class']} | {e['name']} | {desc} |")
        lines.append("")
    elif include_graph and not expressions:
        lines.append("## 材质图表节点")
        lines.append("")
        lines.append("_节点图信息不可用（需要 MaterialEditingLibrary.get_material_expressions() 支持）。_")
        lines.append("")

    lines.append("---")
    lines.append("_此文档由 ArtClaw `generate_material_documentation` Skill 自动生成。_")
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# Skill 实现
# ============================================================================

@ue_tool(
    name="generate_material_documentation",
    description="Read a master material's blueprint and generate comprehensive Markdown "
                "documentation. Extracts all parameter types (scalar, vector, texture, "
                "static switch) and optionally material graph nodes. Saves the document "
                "to Saved/MaterialDocs/. Returns the full documentation text and file path.",
    category="material",
    risk_level="low",
)
def generate_material_documentation(arguments: dict) -> str:
    """读取母材质的材质蓝图，创建材质使用文档"""
    if unreal is None:
        return json.dumps({
            "success": False,
            "error": "Not running in Unreal Engine",
        })

    # --- 参数提取 ---
    material_path = arguments.get("material_path", "")
    if not material_path:
        return json.dumps({
            "success": False,
            "error": "material_path is required",
        })

    output_format = arguments.get("output_format", "markdown")
    include_parameters = arguments.get("include_parameters", True)
    include_graph = arguments.get("include_graph", True)

    try:
        # --- 加载材质 ---
        material = unreal.load_asset(material_path)
        if material is None:
            return json.dumps({
                "success": False,
                "error": f"Material not found: {material_path}",
            })

        class_name = str(material.get_class().get_name())
        if "Material" not in class_name:
            return json.dumps({
                "success": False,
                "error": f"Asset is not a Material (got {class_name}): {material_path}",
            })

        # --- 提取信息 ---
        mat_info = _extract_material_info(material)

        params = {}
        if include_parameters:
            params["scalar"] = _extract_scalar_params(material)
            params["vector"] = _extract_vector_params(material)
            params["texture"] = _extract_texture_params(material)
            params["static_switch"] = _extract_switch_params(material)

        expressions = []
        if include_graph:
            expressions = _extract_expressions(material)

        # --- 生成文档 ---
        doc_text = _generate_markdown(
            mat_info, params, expressions,
            include_parameters, include_graph,
        )

        # --- 保存文件 ---
        output_path = ""
        try:
            project_dir = str(unreal.Paths.project_dir())
            docs_dir = os.path.join(project_dir, "Saved", "MaterialDocs")
            os.makedirs(docs_dir, exist_ok=True)

            mat_name = mat_info["name"]
            output_path = os.path.join(docs_dir, f"{mat_name}.md")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(doc_text)
        except Exception as e:
            output_path = f"(save failed: {e})"

        # --- 统计 ---
        param_count = sum(len(v) for v in params.values()) if params else 0
        texture_count = len(params.get("texture", []))

        return json.dumps({
            "success": True,
            "material_name": mat_info["name"],
            "material_path": mat_info["path"],
            "documentation": doc_text,
            "output_path": output_path,
            "parameter_count": param_count,
            "texture_count": texture_count,
            "expression_count": len(expressions),
        }, default=str)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
        })
