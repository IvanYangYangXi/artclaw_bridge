"""
memory-promote-to-team
将个人记忆中的高价值踩坑记录晋升到团队记忆。
"""
import json
import os
import sys


def _ensure_core_path():
    """确保 core/ 目录在 sys.path 中"""
    candidates = [
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "core")),
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "subprojects", "DCCClawBridge", "core")),
    ]
    for candidate in candidates:
        mc = os.path.join(candidate, "memory_core.py")
        if os.path.exists(mc) and candidate not in sys.path:
            sys.path.insert(0, candidate)
            return True
    return False


UNIFIED_MEMORY_PATH = os.path.join(os.path.expanduser("~"), ".artclaw", "memory.json")


def promote_to_team(**kwargs):
    """
    入口函数。kwargs 由 Tool Manager 传入。

    参数:
        min_importance (float): 最低重要性阈值 (0-1), 默认 0.7
        dry_run (bool): True=预览, False=实际写入, 默认 True
    """
    min_importance = float(kwargs.get("min_importance", 0.7))
    dry_run = bool(kwargs.get("dry_run", True))

    if not _ensure_core_path():
        return {"success": False, "error": "无法找到 memory_core 模块。"}

    try:
        from memory_core import MemoryManagerV2
    except ImportError:
        return {"success": False, "error": "无法导入 memory_core 模块。"}

    if not os.path.exists(UNIFIED_MEMORY_PATH):
        return {
            "success": True,
            "report": "记忆文件不存在: ~/.artclaw/memory.json\n尚未产生任何记忆数据。",
            "candidates_count": 0,
        }

    mgr = MemoryManagerV2(storage_path=UNIFIED_MEMORY_PATH, dcc_name="artclaw")
    stats = mgr.get_stats()
    total = stats.get("total_entries", 0)

    candidates = mgr.promote_to_team(
        min_importance=min_importance,
        tags=("crash", "pattern", "convention"),
        dry_run=dry_run,
    )

    lines = []
    lines.append("# 记忆晋升报告")
    lines.append("")
    lines.append(f"- 记忆文件: `{UNIFIED_MEMORY_PATH}`")
    lines.append(f"- 记忆条目总数: {total}")
    lines.append(f"- 最低重要性阈值: {min_importance}")
    lines.append(f"- 模式: {'预览（dry_run）' if dry_run else '✅ 实际写入'}")
    lines.append(f"- 候选数: {len(candidates)}")
    lines.append("")

    if not candidates:
        lines.append("没有发现符合条件的候选记录。")
        lines.append("")
        lines.append("可能原因:")
        lines.append(f"- 个人记忆中没有 importance >= {min_importance:.1f} 的 crash/pattern/convention 条目")
        lines.append("- 记忆数据尚在 short_term 层，未晋升到 mid_term/long_term")
        lines.append(f"- 尝试降低 min_importance 阈值（如 0.5）")
    else:
        for i, c in enumerate(candidates, 1):
            status = ""
            if not dry_run:
                r = c.get("result", {})
                if r.get("accepted"):
                    status = f" ✅ → {r.get('file', '')}"
                else:
                    status = f" ⚠️ {r.get('reason', '')}"

            lines.append(f"{i}. **[{c['category']}]** {c.get('dcc_tag', '')} "
                         f"importance={c['importance']:.2f}{status}")
            lines.append(f"   {c['rule']}")
            lines.append("")

    if dry_run and candidates:
        lines.append("---")
        lines.append("💡 确认后请将 dry_run 设为 false 重新运行以实际写入。")

    report = "\n".join(lines)
    return {"success": True, "report": report, "candidates_count": len(candidates)}
