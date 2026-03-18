"""
asset_ops.py - 资产操作 Skill
===============================

P0 核心 Skill：资产加载、查询、路径检索、重命名等操作。
Skill Hub 自动发现并注册。保存后热重载生效。
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None  # 允许在 UE 外部测试


# ============================================================================
# 辅助函数
# ============================================================================

def _prune_asset_data(asset_data) -> dict:
    """将 AssetData 转为精简字典"""
    return {
        "asset_name": str(asset_data.asset_name),
        "asset_class": str(asset_data.asset_class_path.asset_name) if hasattr(asset_data, 'asset_class_path') else str(getattr(asset_data, 'asset_class', '')),
        "package_path": str(asset_data.package_path) if hasattr(asset_data, 'package_path') else "",
        "object_path": str(asset_data.get_full_name()) if hasattr(asset_data, 'get_full_name') else str(asset_data.object_path) if hasattr(asset_data, 'object_path') else "",
    }


# ============================================================================
# Asset Skills - 查询
# ============================================================================

@ue_tool(
    name="get_selected_assets",
    description="Get the list of currently selected assets in the Content Browser. "
                "Returns each asset's name, class, path, and package info. "
                "Use this to understand what assets the user has selected for editing.",
    category="asset",
    risk_level="low",
)
def get_selected_assets(arguments: dict) -> str:
    """获取资源管理器（Content Browser）中当前选中的资产列表"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    limit = arguments.get("limit", 100)

    try:
        # get_selected_asset_data 返回 AssetData（更丰富），优先使用
        selected_data = unreal.EditorUtilityLibrary.get_selected_asset_data()
        total = len(selected_data)

        assets = []
        for ad in selected_data[:limit]:
            assets.append(_prune_asset_data(ad))

        # 同时获取选中的文件夹路径（如果有）
        selected_folders = []
        try:
            folders = unreal.EditorUtilityLibrary.get_selected_folder_paths()
            selected_folders = [str(f) for f in folders]
        except Exception:
            pass

        result = {
            "success": True,
            "count": len(assets),
            "assets": assets,
        }
        if selected_folders:
            result["selected_folders"] = selected_folders
        if total > limit:
            result["truncated"] = True
            result["total"] = total

        return json.dumps(result, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="load_asset",
    description="Load an asset by its content browser path and return its basic info. "
                "Path format: '/Game/MyFolder/MyAsset' or '/Engine/BasicShapes/Cube'. "
                "Returns asset name, class, and whether it loaded successfully.",
    category="asset",
    risk_level="low",
)
def load_asset(arguments: dict) -> str:
    """按路径加载资产并返回基本信息"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    asset_path = arguments.get("asset_path", "")
    if not asset_path:
        return json.dumps({"success": False, "error": "需要提供 asset_path 参数"})

    try:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if asset is None:
            return json.dumps({
                "success": False,
                "error": f"未找到资产或加载失败: {asset_path}"
            })

        return json.dumps({
            "success": True,
            "asset": {
                "name": str(asset.get_name()),
                "class": str(asset.get_class().get_name()),
                "path": asset_path,
                "full_name": str(asset.get_full_name()),
            },
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="get_asset_path",
    description="Get the content browser path(s) for asset(s) matching a search query. "
                "Searches by name substring in the given directory (default: /Game/). "
                "Returns matching asset paths, classes, and names.",
    category="asset",
    risk_level="low",
)
def get_asset_path(arguments: dict) -> str:
    """按名称搜索资产路径"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    query = arguments.get("query", "")
    if not query:
        return json.dumps({"success": False, "error": "需要提供 query 参数"})

    search_dir = arguments.get("search_dir", "/Game/")
    class_filter = arguments.get("class_filter", "")
    recursive = arguments.get("recursive", True)
    limit = arguments.get("limit", 50)

    try:
        # 获取目录下所有资产
        asset_paths = unreal.EditorAssetLibrary.list_assets(
            search_dir,
            recursive=recursive,
            include_folder=False,
        )

        results = []
        query_lower = query.lower()

        for path in asset_paths:
            path_str = str(path)
            # 名称匹配
            asset_name = path_str.rsplit("/", 1)[-1].split(".")[0]
            if query_lower not in asset_name.lower():
                continue

            # 可选的类过滤
            if class_filter:
                asset_data = unreal.EditorAssetLibrary.find_asset_data(path_str)
                if asset_data and asset_data.is_valid():
                    cls_name = str(asset_data.asset_class_path.asset_name) if hasattr(asset_data, 'asset_class_path') else ""
                    if class_filter.lower() not in cls_name.lower():
                        continue

            results.append({
                "path": path_str,
                "name": asset_name,
            })

            if len(results) >= limit:
                break

        return json.dumps({
            "success": True,
            "query": query,
            "count": len(results),
            "assets": results,
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="list_assets_in_directory",
    description="List all assets in a content browser directory. "
                "Returns asset names, classes, and paths. "
                "Default directory is '/Game/'.",
    category="asset",
    risk_level="low",
)
def list_assets_in_directory(arguments: dict) -> str:
    """列出目录下的所有资产"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    directory = arguments.get("directory", "/Game/")
    recursive = arguments.get("recursive", False)
    limit = arguments.get("limit", 100)

    try:
        asset_paths = unreal.EditorAssetLibrary.list_assets(
            directory,
            recursive=recursive,
            include_folder=False,
        )

        total = len(asset_paths)
        results = []
        for path in asset_paths[:limit]:
            path_str = str(path)
            name = path_str.rsplit("/", 1)[-1].split(".")[0]
            results.append({
                "path": path_str,
                "name": name,
            })

        result = {
            "success": True,
            "directory": directory,
            "count": len(results),
            "assets": results,
        }
        if total > limit:
            result["truncated"] = True
            result["total"] = total

        return json.dumps(result, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Asset Skills - 修改
# ============================================================================

@ue_tool(
    name="rename_asset",
    description="Rename an asset in the content browser. "
                "Provide the full asset path and the new name (without path). "
                "Automatically updates all references. "
                "WARNING: This modifies the project on disk.",
    category="asset",
    risk_level="high",
)
def rename_asset(arguments: dict) -> str:
    """重命名资产"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    asset_path = arguments.get("asset_path", "")
    new_name = arguments.get("new_name", "")
    if not asset_path:
        return json.dumps({"success": False, "error": "需要提供 asset_path 参数"})
    if not new_name:
        return json.dumps({"success": False, "error": "需要提供 new_name 参数"})

    try:
        # 确认资产存在
        if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
            return json.dumps({
                "success": False,
                "error": f"未找到资产: {asset_path}"
            })

        # 计算新路径
        directory = asset_path.rsplit("/", 1)[0]
        new_path = f"{directory}/{new_name}"

        # 执行重命名
        success = unreal.EditorAssetLibrary.rename_asset(asset_path, new_path)

        if success:
            return json.dumps({
                "success": True,
                "old_path": asset_path,
                "new_path": new_path,
            }, default=str)
        else:
            return json.dumps({
                "success": False,
                "error": f"重命名失败，目标可能已存在: {new_path}"
            })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="does_asset_exist",
    description="Check if an asset exists at the given content browser path. "
                "Returns true/false. Useful for validation before operations.",
    category="asset",
    risk_level="low",
)
def does_asset_exist(arguments: dict) -> str:
    """检查资产是否存在"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    asset_path = arguments.get("asset_path", "")
    if not asset_path:
        return json.dumps({"success": False, "error": "需要提供 asset_path 参数"})

    try:
        exists = unreal.EditorAssetLibrary.does_asset_exist(asset_path)
        return json.dumps({
            "success": True,
            "asset_path": asset_path,
            "exists": exists,
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
