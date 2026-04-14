"""
ComfyUI Node Installer - 节点安装器实现
======================================

此模块提供检测和安装缺失节点的功能。
通过 run_python 在 ComfyUI 进程中执行。
"""

# 节点到包的映射表（简化版，完整版见 references/node-package-mapping.md）
NODE_TYPE_TO_PACKAGE = {
    # ControlNet
    "CannyEdgePreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "OpenposePreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    "DepthPreprocessor": {"name": "ComfyUI-ControlNet-Aux", "url": "https://github.com/Fannovel16/comfyui_controlnet_aux"},
    
    # 动画
    "ADE_AnimateDiffLoader": {"name": "ComfyUI-AnimateDiff-Evolved", "url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved"},
    
    # 视频
    "VHS_LoadVideo": {"name": "ComfyUI-VideoHelperSuite", "url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    "VHS_VideoCombine": {"name": "ComfyUI-VideoHelperSuite", "url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"},
    
    # 工具节点
    "CR_Image_Panel": {"name": "ComfyUI_Comfyroll_CustomNodes", "url": "https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes"},
    
    # rgthree
    "Context": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    "Display Any": {"name": "rgthree-comfy", "url": "https://github.com/rgthree/rgthree-comfy"},
    
    # 放大
    "UltimateSDUpscale": {"name": "ComfyUI-UltimateSDUpscale", "url": "https://github.com/ssitu/ComfyUI-UltimateSDUpscale"},
}

# 已知迁移映射
NODE_MIGRATION_MAP = {
    "CheckpointLoader": "CheckpointLoaderSimple",
}


def find_missing_nodes(workflow: dict, available_nodes: set = None) -> list:
    """
    检测 workflow 中缺失的节点类型
    
    Args:
        workflow: Workflow JSON dict
        available_nodes: 可选，已提供的可用节点集合
        
    Returns:
        缺失节点列表，每项包含 node_id, node_type, package 信息
    """
    # 获取可用节点
    if available_nodes is None:
        import nodes
        available_nodes = set(nodes.NODE_CLASS_MAPPINGS.keys())
    
    missing = []
    
    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            continue
            
        class_type = node_data.get("class_type")
        if not class_type:
            continue
        
        # 检查是否可用
        if class_type in available_nodes:
            continue
            
        # 检查是否在迁移映射中
        if class_type in NODE_MIGRATION_MAP:
            migrated_type = NODE_MIGRATION_MAP[class_type]
            if migrated_type in available_nodes:
                continue
        
        # 查找包信息
        package_info = NODE_TYPE_TO_PACKAGE.get(class_type)
        
        missing.append({
            "node_id": node_id,
            "node_type": class_type,
            "package": package_info["name"] if package_info else "unknown",
            "install_url": package_info["url"] if package_info else None,
            "suggestion": f"请安装 {package_info['name']}" if package_info else "未知节点，请手动查找"
        })
    
    return missing


def diagnose_workflow(workflow: dict) -> dict:
    """
    诊断 workflow，返回完整的诊断报告
    
    Args:
        workflow: Workflow JSON
        
    Returns:
        诊断报告 dict
    """
    import nodes
    
    available_nodes = set(nodes.NODE_CLASS_MAPPINGS.keys())
    missing = find_missing_nodes(workflow, available_nodes)
    
    # 提取所有使用的节点类型
    used_types = set()
    for node_data in workflow.values():
        if isinstance(node_data, dict):
            class_type = node_data.get("class_type")
            if class_type:
                used_types.add(class_type)
    
    # 按包分组
    packages_needed = {}
    for m in missing:
        pkg = m["package"]
        if pkg not in packages_needed:
            packages_needed[pkg] = {
                "url": m["install_url"],
                "nodes": []
            }
        packages_needed[pkg]["nodes"].append(m["node_type"])
    
    return {
        "status": "missing_found" if missing else "ok",
        "total_nodes": len(used_types),
        "available_count": len(used_types & available_nodes),
        "missing_count": len(missing),
        "missing": missing,
        "packages_needed": packages_needed,
        "can_auto_install": all(m["install_url"] for m in missing) if missing else True
    }


def install_via_manager(package_url: str, package_name: str = None) -> dict:
    """
    通过 ComfyUI-Manager 安装节点包
    
    Args:
        package_url: GitHub URL 或其他安装地址
        package_name: 包名（可选）
        
    Returns:
        安装结果
    """
    try:
        # 尝试导入 Manager 的 API
        import sys
        import os
        
        # 查找 ComfyUI-Manager 的安装脚本
        custom_nodes_dir = os.path.join(os.path.dirname(sys.executable), 
                                        "ComfyUI", "custom_nodes")
        
        manager_dir = None
        if os.path.exists(custom_nodes_dir):
            for d in os.listdir(custom_nodes_dir):
                if "manager" in d.lower():
                    potential = os.path.join(custom_nodes_dir, d)
                    if os.path.isdir(potential):
                        manager_dir = potential
                        break
        
        if not manager_dir:
            return {
                "success": False,
                "error": "ComfyUI-Manager 未安装",
                "suggestion": "请先安装 ComfyUI-Manager: https://github.com/ltdrdata/ComfyUI-Manager"
            }
        
        # 使用 git clone 安装
        import subprocess
        import urllib.parse
        
        # 从 URL 提取仓库名
        repo_name = package_name or package_url.split("/")[-1].replace(".git", "")
        target_dir = os.path.join(custom_nodes_dir, repo_name)
        
        # 检查是否已存在
        if os.path.exists(target_dir):
            return {
                "success": False,
                "error": f"{repo_name} 已存在",
                "suggestion": "如需更新请使用 git pull 或删除后重新安装"
            }
        
        # 执行 git clone
        result = subprocess.run(
            ["git", "clone", package_url, target_dir],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"成功安装 {repo_name}",
                "path": target_dir,
                "reboot_required": True,
                "note": "请重启 ComfyUI 以加载新节点"
            }
        else:
            return {
                "success": False,
                "error": f"git clone 失败: {result.stderr}",
                "suggestion": "请检查网络连接或手动安装"
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "安装超时",
            "suggestion": "网络可能较慢，请手动安装"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "请手动安装或检查错误日志"
        }


def install_missing_nodes(workflow: dict, auto_install: bool = False) -> dict:
    """
    安装 workflow 所需的所有缺失节点
    
    Args:
        workflow: Workflow JSON
        auto_install: 是否自动安装（False 时只返回安装计划）
        
    Returns:
        安装结果或安装计划
    """
    diagnosis = diagnose_workflow(workflow)
    
    if diagnosis["status"] == "ok":
        return {
            "success": True,
            "message": "所有节点已可用，无需安装",
            "installed": [],
            "reboot_required": False
        }
    
    packages = diagnosis["packages_needed"]
    
    # 生成安装计划
    install_plan = []
    for pkg_name, pkg_info in packages.items():
        if pkg_info["url"]:
            install_plan.append({
                "package": pkg_name,
                "url": pkg_info["url"],
                "nodes": pkg_info["nodes"]
            })
    
    if not auto_install:
        return {
            "success": True,
            "action": "plan_only",
            "plan": install_plan,
            "message": f"需要安装 {len(install_plan)} 个包"
        }
    
    # 自动安装
    installed = []
    failed = []
    
    for item in install_plan:
        result = install_via_manager(item["url"], item["package"])
        if result["success"]:
            installed.append(item["package"])
        else:
            failed.append({
                "package": item["package"],
                "error": result.get("error", "未知错误")
            })
    
    return {
        "success": len(failed) == 0,
        "installed": installed,
        "failed": failed,
        "reboot_required": len(installed) > 0,
        "message": f"安装完成: {len(installed)} 成功, {len(failed)} 失败"
    }


def search_packages(query: str, limit: int = 10) -> list:
    """
    搜索节点包（基于本地映射表）
    
    Args:
        query: 搜索关键词
        limit: 最大返回数量
        
    Returns:
        匹配的包列表
    """
    query_lower = query.lower()
    results = []
    
    # 在映射表中搜索
    for node_type, package_info in NODE_TYPE_TO_PACKAGE.items():
        if not package_info:
            continue
            
        if (query_lower in node_type.lower() or 
            query_lower in package_info["name"].lower()):
            
            results.append({
                "node_type": node_type,
                "package_name": package_info["name"],
                "url": package_info["url"]
            })
            
        if len(results) >= limit:
            break
    
    return results


# 便捷函数：一键诊断并显示结果
def quick_diagnose(workflow: dict) -> str:
    """
    快速诊断 workflow 并返回格式化的字符串报告
    
    Args:
        workflow: Workflow JSON
        
    Returns:
        格式化的诊断报告
    """
    result = diagnose_workflow(workflow)
    
    if result["status"] == "ok":
        return "✅ 所有节点已安装，可以正常运行"
    
    lines = [
        f"⚠️ 发现 {result['missing_count']} 个缺失节点",
        f"   总节点数: {result['total_nodes']}",
        f"   可用节点: {result['available_count']}",
        "",
        "缺失节点列表:"
    ]
    
    for m in result["missing"]:
        lines.append(f"  • {m['node_type']} → {m['suggestion']}")
    
    if result["packages_needed"]:
        lines.extend(["", "需要安装的包:"])
        for pkg_name, pkg_info in result["packages_needed"].items():
            if pkg_info["url"]:
                lines.append(f"  • {pkg_name}")
                lines.append(f"    {pkg_info['url']}")
    
    if result["can_auto_install"]:
        lines.extend(["", "💡 提示: 可以使用 install_missing_nodes(workflow, auto_install=True) 自动安装"])
    else:
        lines.extend(["", "⚠️ 注意: 部分节点无法自动识别，请手动查找安装"])
    
    return "\n".join(lines)
