"""UE SM 命名检查 — 静态网格体命名前缀检查（保存拦截 + 放置检查）。"""
import os
import json
import artclaw_sdk as sdk

_log = sdk.logger.get_tool_logger("SM命名检查")


def _load_manifest() -> dict:
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_config(manifest: dict):
    """从 manifest 提取运行时配置：路径前缀列表、目标类型集合、命名前缀。"""
    df = manifest.get("defaultFilters", {})

    # 路径前缀：取 defaultFilters.path 每条 pattern 的 /** 之前部分
    watch_prefixes = []
    for pf in df.get("path", []):
        prefix = pf.get("pattern", "").split("/**")[0]
        if prefix:
            watch_prefixes.append(prefix)

    # 目标类型：defaultFilters.typeFilter.types
    target_classes = set(df.get("typeFilter", {}).get("types", []))

    # 命名前缀：inputs["required_prefix"].default，回退 "SM_"
    inputs_map = {inp["id"]: inp for inp in manifest.get("inputs", [])}
    required_prefix = inputs_map.get("required_prefix", {}).get("default", "SM_")

    return watch_prefixes, target_classes, required_prefix


def _get_asset_name_from_event(evt) -> str:
    """从事件数据中提取真实资产名（不是 Actor 实例名）。

    asset.place.post 事件的 asset_name 是 Actor 实例名（如 StaticMeshActor_5），
    真实资产名在 asset_path 里（如 /Game/_ToolManager/pCylinder.pCylinder → pCylinder）。
    """
    if (evt.asset_class or "") == "StaticMeshActor":
        segment = (evt.asset_path or "").rsplit("/", 1)[-1]
        name = segment.split(".")[0]
        return name if name else evt.asset_name
    return evt.asset_name


def check_sm_naming(**kwargs):
    """入口函数。由 asset.save.pre / asset.place.post 事件触发，返回 allow 或 reject。"""
    manifest = _load_manifest()
    watch_prefixes, target_classes, required_prefix = _get_config(manifest)

    evt = sdk.event.parse(kwargs)
    asset_path = evt.asset_path
    asset_class = evt.asset_class
    asset_name = _get_asset_name_from_event(evt)

    if not asset_path:
        _log.info("无法确定资产信息，放行")
        return sdk.result.allow("无法确定资产信息，放行")

    # ── 1. 路径范围过滤（来自 manifest defaultFilters.path）──
    if watch_prefixes and not any(asset_path.startswith(p) for p in watch_prefixes):
        _log.debug("路径不在监控范围：%s", asset_path)
        return sdk.result.allow(f"路径不在监控范围：{asset_path}")

    # ── 2. 类型过滤（来自 manifest defaultFilters.typeFilter.types）──
    if target_classes and asset_class and asset_class not in target_classes:
        _log.debug("非目标类型（%s），跳过检查", asset_class)
        return sdk.result.allow(f"非目标类型（{asset_class}），跳过检查")

    # ── 3. 命名规则检查 ──
    if asset_name.startswith(required_prefix):
        _log.info("命名合规：%s", asset_name)
        return sdk.result.allow(f"命名合规：{asset_name}")

    # ── 4. 不合规 ──
    reason = (
        f"命名不合规：\"{asset_name}\" 缺少前缀 \"{required_prefix}\"。\n"
        f"请将资产重命名为 \"{required_prefix}{asset_name}\" 后再操作。"
    )
    _log.warning(reason)
    return sdk.result.reject(
        reason=reason,
        data={
            "asset_name": asset_name,
            "asset_path": asset_path,
            "required_prefix": required_prefix,
        },
    )