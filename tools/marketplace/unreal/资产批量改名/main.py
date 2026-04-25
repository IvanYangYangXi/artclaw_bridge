"""UE 资产批量重命名 — 为选中的资产添加前缀或后缀。"""
# ── SDK 头 ──
import os, json
import artclaw_sdk as sdk

def _load_manifest():
    return json.loads(
        open(os.path.join(os.path.dirname(__file__), "manifest.json"),
             encoding="utf-8").read()
    )
# ── SDK 头结束 ──

import unreal


def rename_assets(**kwargs):
    """入口函数。"""
    manifest = _load_manifest()
    parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)

    prefix = parsed.get("prefix", "")
    suffix = parsed.get("suffix", "")
    separator = parsed.get("separator", "_")

    selected = sdk.context.get_selected_assets()
    if not selected:
        return sdk.result.fail("NO_INPUT", "没有选中任何资产，请在 Content Browser 中选择要重命名的资产。")

    if not prefix and not suffix:
        return sdk.result.fail("NO_PARAMS", "前缀和后缀均为空，无需操作。")

    renamed = []
    for asset_info in selected:
        old_name = asset_info["name"]
        old_path = asset_info["path"]
        new_name = old_name

        if prefix:
            new_name = prefix + separator + new_name
        if suffix:
            new_name = new_name + separator + suffix

        new_path = old_path.rsplit("/", 1)[0] + "/" + new_name
        success = unreal.EditorAssetLibrary.rename_asset(old_path, new_path)
        if success:
            renamed.append({"old": old_name, "new": new_name})

    return sdk.result.success(
        data={"renamed_count": len(renamed), "renamed_assets": renamed},
        message=f"成功重命名 {len(renamed)} 个资产"
    )
