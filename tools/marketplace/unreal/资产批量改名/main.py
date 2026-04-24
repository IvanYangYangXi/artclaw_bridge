"""
UE 资产批量改名工具
为选中的资产添加前缀或后缀。
"""
import unreal


def rename_assets(prefix="", suffix="", separator="_"):
    """批量为选中资产添加前缀/后缀。

    Returns:
        dict: {"renamed_count": int, "renamed_assets": [{"old": str, "new": str}]}
    """
    selected = unreal.EditorUtilityLibrary.get_selected_assets()

    if not selected:
        return {
            "renamed_count": 0,
            "renamed_assets": [],
            "message": "没有选中任何资产，请先在 Content Browser 中选中要改名的资产。"
        }

    if not prefix and not suffix:
        return {
            "renamed_count": 0,
            "renamed_assets": [],
            "message": "前缀和后缀都为空，无需操作。"
        }

    renamed = []
    for asset in selected:
        old_name = asset.get_name()
        new_name = old_name

        if prefix:
            new_name = prefix + separator + new_name
        if suffix:
            new_name = new_name + separator + suffix

        old_path = asset.get_path_name().rsplit(".", 1)[0]
        new_path = old_path.rsplit("/", 1)[0] + "/" + new_name

        success = unreal.EditorAssetLibrary.rename_asset(old_path, new_path)
        if success:
            renamed.append({"old": old_name, "new": new_name})

    return {
        "renamed_count": len(renamed),
        "renamed_assets": renamed,
        "message": f"成功改名 {len(renamed)} 个资产"
    }
