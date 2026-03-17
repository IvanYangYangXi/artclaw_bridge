"""
TODO_skill_name - TODO: 技能描述
==================================

高级模板示例，包含：
- 多 Tool 暴露
- 辅助函数
- ScopedEditorTransaction（撤销支持）
- 全面的错误处理
- 进度反馈

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
# 配置常量
# ============================================================================

MAX_BATCH_SIZE = 100
DEFAULT_TIMEOUT = 60


# ============================================================================
# 辅助函数
# ============================================================================

def _validate_asset_path(asset_path: str) -> bool:
    """验证资产路径是否合法"""
    if not asset_path:
        return False
    if not asset_path.startswith("/Game/"):
        return False
    return True


def _load_asset_safe(asset_path: str):
    """安全加载资产，返回 (asset, error_msg)"""
    if unreal is None:
        return None, "Not running in Unreal Engine"

    if not _validate_asset_path(asset_path):
        return None, f"Invalid asset path: {asset_path}"

    try:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if asset is None:
            return None, f"Asset not found: {asset_path}"
        return asset, None
    except Exception as e:
        return None, f"Failed to load asset: {e}"


def _log(message: str, level: str = "info"):
    """统一日志输出"""
    if unreal is not None:
        log_func = {
            "info": unreal.log,
            "warning": unreal.log_warning,
            "error": unreal.log_error,
        }.get(level, unreal.log)
        log_func(f"[ArtClaw] {message}")


# ============================================================================
# Tool 1: 主工具
# ============================================================================

@ue_tool(
    name="TODO_primary_tool",
    description="TODO: 主工具的详细描述，说明输入输出和用途。"
                "支持批量操作和撤销。",
    category="TODO",
    risk_level="medium",
)
def TODO_primary_tool(arguments: dict) -> str:
    """TODO: 主工具文档字符串"""
    if unreal is None:
        return json.dumps({
            "success": False,
            "error": "Not running in Unreal Engine",
        })

    # --- 参数提取与验证 ---
    target_path = arguments.get("target_path", "")
    batch_items = arguments.get("items", [])
    dry_run = arguments.get("dry_run", False)

    if not target_path and not batch_items:
        return json.dumps({
            "success": False,
            "error": "Either 'target_path' or 'items' is required",
        })

    if len(batch_items) > MAX_BATCH_SIZE:
        return json.dumps({
            "success": False,
            "error": f"Batch size {len(batch_items)} exceeds limit {MAX_BATCH_SIZE}",
        })

    try:
        results = []
        errors = []

        # --- 使用 ScopedEditorTransaction 支持撤销 ---
        with unreal.ScopedEditorTransaction("TODO_primary_tool") as transaction:
            items_to_process = batch_items if batch_items else [target_path]

            for i, item in enumerate(items_to_process):
                try:
                    _log(f"Processing {i + 1}/{len(items_to_process)}: {item}")

                    if dry_run:
                        results.append({
                            "item": item,
                            "status": "dry_run",
                            "message": "Would be processed",
                        })
                        continue

                    # TODO: 实现单个项目的处理逻辑
                    # asset, err = _load_asset_safe(item)
                    # if err:
                    #     errors.append({"item": item, "error": err})
                    #     continue

                    results.append({
                        "item": item,
                        "status": "success",
                    })

                except Exception as e:
                    errors.append({
                        "item": item,
                        "error": str(e),
                    })

        return json.dumps({
            "success": len(errors) == 0,
            "processed": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
            "dry_run": dry_run,
        }, default=str)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
        })


# ============================================================================
# Tool 2: 辅助/查询工具
# ============================================================================

@ue_tool(
    name="TODO_secondary_tool",
    description="TODO: 辅助工具描述。通常是只读查询操作。",
    category="TODO",
    risk_level="low",
)
def TODO_secondary_tool(arguments: dict) -> str:
    """TODO: 辅助工具文档字符串"""
    if unreal is None:
        return json.dumps({
            "success": False,
            "error": "Not running in Unreal Engine",
        })

    # --- 参数提取 ---
    query = arguments.get("query", "")
    filter_type = arguments.get("filter_type", "all")
    limit = min(arguments.get("limit", 50), 500)

    try:
        # TODO: 实现查询逻辑
        items = []

        return json.dumps({
            "success": True,
            "query": query,
            "filter_type": filter_type,
            "total": len(items),
            "items": items[:limit],
        }, default=str)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
        })
