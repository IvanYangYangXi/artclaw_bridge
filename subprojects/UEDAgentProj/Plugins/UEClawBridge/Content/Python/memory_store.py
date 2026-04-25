"""
memory_store.py - UE 记忆管理 v2 适配层
========================================

将 memory_core.MemoryManagerV2（平台无关）接入 UE MCP Server。

职责:
  - 确定 UE 项目的存储路径
  - 注册 MCP Tool (memory)
  - 旧格式自动迁移
  - 适配 UE 日志系统

共享核心:
  - memory_core.py (core/)
  - 开发模式: 通过相对路径回溯导入
  - 部署模式: setup.bat 已复制到 Content/Python/

旧版兼容:
  - 原 MemoryStore 类保留为 LegacyMemoryStore 别名
  - init_memory_store() 签名不变，C++/Python 调用方无需改动
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import unreal
    _project_dir = Path(str(unreal.Paths.project_saved_dir())) / "ClawBridge"
except Exception:
    _project_dir = Path.home() / ".ue_agent"

from claw_bridge_logger import UELogger

# ---------------------------------------------------------------------------
# 导入 memory_core
# 优先级:
#   1. 自包含部署: memory_core.py 与本文件在同一目录
#   2. 开发模式: 通过相对路径找到 core/
# ---------------------------------------------------------------------------

try:
    from memory_core import MemoryManagerV2, DEFAULT_CONFIG  # noqa: E402
except ImportError:
    _bridge_pkg_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..",
                     "core")
    )
    if os.path.isdir(_bridge_pkg_dir) and _bridge_pkg_dir not in sys.path:
        sys.path.insert(0, _bridge_pkg_dir)

    from memory_core import MemoryManagerV2, DEFAULT_CONFIG  # noqa: E402


# ============================================================================
# 1. UE 适配层
# ============================================================================

class UEMemoryStore:
    """UE 环境下的记忆管理器封装"""

    def __init__(self, base_dir: Optional[Path] = None):
        # 统一存储: ~/.artclaw/memory.json
        self._base_dir = base_dir or (Path.home() / ".artclaw")
        self._base_dir.mkdir(parents=True, exist_ok=True)

        storage_path = str(self._base_dir / "memory.json")

        self._manager = MemoryManagerV2(
            storage_path=storage_path,
            dcc_name="unreal_engine",
        )

        # 检查并迁移旧格式
        self._try_migrate_v1()

        UELogger.info(f"MemoryStore 初始化完成: {storage_path}")
        stats = self._manager.get_stats()
        UELogger.info(f"  记忆条目: {stats.get('total_entries', 0)}")

        # 启动定时维护
        self._manager.start_maintenance_timer()

    def _try_migrate_v1(self):
        """检测并迁移 v1 格式的记忆文件"""
        v1_files = ["memory_facts.json", "memory_preferences.json", "memory_conventions.json"]
        has_v1 = any((self._base_dir / f).exists() for f in v1_files)

        if has_v1 and not (self._base_dir / "memory.json").exists():
            UELogger.info("检测到 v1 格式记忆文件，开始迁移...")
            try:
                count = MemoryManagerV2.migrate_from_ue_v1(
                    str(_project_dir),  # v1 文件在旧位置
                    str(self._base_dir / "memory.json")
                )
                # 迁移成功后重新加载
                self._manager = MemoryManagerV2(
                    storage_path=str(self._base_dir / "memory.json"),
                    dcc_name="unreal_engine",
                )
                UELogger.info(f"v1 迁移完成: {count} 条记录")
            except Exception as e:
                UELogger.mcp_error(f"v1 迁移失败: {e}")

    @property
    def manager(self) -> MemoryManagerV2:
        """获取底层 MemoryManagerV2 实例"""
        return self._manager

    # ------------------------------------------------------------------
    # 向后兼容: 旧版 MemoryStore 接口代理
    # ------------------------------------------------------------------

    # 旧 layer 名到新 tag 的映射
    _LAYER_TO_TAG = {
        "facts": "fact",
        "preferences": "preference",
        "conventions": "convention",
    }

    def get(self, layer: str, key: str, default: Any = None) -> Any:
        """兼容旧版 get(layer, key)"""
        result = self._manager.get(key)
        if result is None:
            return default
        return result.get("value", default)

    def set(self, layer: str, key: str, value: Any, metadata: Optional[dict] = None) -> bool:
        """兼容旧版 set(layer, key, value)"""
        tag = self._LAYER_TO_TAG.get(layer, "fact")
        return self._manager.record(key, value, tag=tag, importance=0.5, source=f"mcp:{layer}")

    def delete(self, layer: str, key: str) -> bool:
        """兼容旧版 delete(layer, key)"""
        return self._manager.delete(key)

    def list_keys(self, layer: str) -> list:
        """兼容旧版 list_keys(layer)"""
        tag = self._LAYER_TO_TAG.get(layer)
        entries = self._manager.list_entries(tag=tag, limit=500)
        return [e["key"] for e in entries]

    def search(self, query: str, layer: Optional[str] = None) -> list:
        """兼容旧版 search(query, layer)"""
        tag = self._LAYER_TO_TAG.get(layer) if layer else None
        return self._manager.search(query, tag=tag)

    def export_for_prompt(self) -> str:
        """兼容旧版 export_for_prompt()"""
        return self._manager.export_briefing()

    def get_all_summary(self) -> dict:
        """兼容旧版 get_all_summary()"""
        return self._manager.get_stats()

    def flush(self):
        """强制保存（关闭时调用）"""
        self._manager.stop_maintenance_timer()


# 旧名称别名
MemoryStore = UEMemoryStore
TieredMemoryStore = UEMemoryStore


# ============================================================================
# 2. MCP Tool 注册
# ============================================================================

_memory_store_instance: Optional[UEMemoryStore] = None


def init_memory_store(mcp_server, base_dir: Optional[Path] = None) -> UEMemoryStore:
    """初始化 Memory Store 并注册 MCP 接口

    签名与旧版完全兼容，C++/Python 调用方无需改动。
    """
    global _memory_store_instance
    _memory_store_instance = UEMemoryStore(base_dir)

    # v2.6: memory 不再注册为 MCP 工具，通过 run_ue_python 调用 Python API
    if os.environ.get("ARTCLAW_LEGACY_MCP", "").lower() == "true":
        mcp_server.register_tool(
            name="memory",
            description=(
                "Project memory store. Use action='get' to retrieve, 'set' to store, "
                "'search' to find by keyword, 'list' to enumerate keys. "
                "Layers: facts (project knowledge), preferences (user aesthetics), "
                "conventions (naming rules). "
                "New v2 actions: 'check_operation' (query operation history), "
                "'maintain' (trigger memory maintenance)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get", "set", "search", "list", "delete",
                                 "check_operation", "maintain"],
                        "description": "Action to perform",
                    },
                    "layer": {
                        "type": "string",
                        "enum": ["facts", "preferences", "conventions",
                                 "short_term", "mid_term", "long_term"],
                        "description": "Memory layer (v1 names auto-mapped to v2 tags)",
                    },
                    "key": {
                        "type": "string",
                        "description": "Memory key (for get/set/delete)",
                    },
                    "value": {
                        "description": "Value to store (for set action)",
                    },
                    "tag": {
                        "type": "string",
                        "enum": ["fact", "preference", "convention",
                                 "operation", "crash", "pattern", "context"],
                        "description": "Semantic tag (v2)",
                    },
                    "importance": {
                        "type": "number",
                        "description": "Importance score 0-1 (v2, default 0.5)",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search keyword (for search action)",
                    },
                    "tool": {
                        "type": "string",
                        "description": "Tool name (for check_operation)",
                    },
                    "action_hint": {
                        "type": "string",
                        "description": "Action hint (for check_operation)",
                    },
                },
                "required": ["action"],
            },
            handler=_handle_memory,
        )
        UELogger.info("Memory MCP tool registered (legacy mode)")
    else:
        UELogger.info("Memory: MCP tool skipped (v2.6 slim mode), Python API available via get_memory_store()")

    return _memory_store_instance


def get_memory_store() -> Optional[UEMemoryStore]:
    return _memory_store_instance


# ============================================================================
# 3. MCP Handlers
# ============================================================================

# 旧 layer 名 → v2 tag 映射
_LAYER_TAG_MAP = {
    "facts": "fact",
    "preferences": "preference",
    "conventions": "convention",
}


def _handle_memory(arguments: dict) -> str:
    """统一 memory 操作入口"""
    action = arguments.get("action", "")

    handlers = {
        "get": _handle_get,
        "set": _handle_set,
        "search": _handle_search,
        "list": _handle_list,
        "delete": _handle_delete,
        "check_operation": _handle_check_operation,
        "maintain": _handle_maintain,
    }

    handler = handlers.get(action)
    if handler:
        return handler(arguments)
    return json.dumps({"error": f"未知操作: {action}，支持: {', '.join(handlers.keys())}"})


def _handle_get(args: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore 未初始化"})

    key = args.get("key", "")
    if not key:
        return json.dumps({"error": "未指定 key"})

    result = store.manager.get(key)
    if result is None:
        return json.dumps({"found": False, "key": key})
    return json.dumps({"found": True, **result}, default=str)


def _handle_set(args: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore 未初始化"})

    key = args.get("key", "")
    value = args.get("value")
    if not key:
        return json.dumps({"error": "未指定 key"})

    # 兼容旧版 layer 参数
    layer = args.get("layer", "")
    tag = args.get("tag") or _LAYER_TAG_MAP.get(layer, "fact")
    importance = args.get("importance", 0.5)

    ok = store.manager.record(key, value, tag=tag, importance=importance, source="mcp:set")
    return json.dumps({"success": ok, "key": key, "tag": tag})


def _handle_search(args: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore 未初始化"})

    query = args.get("query", "")
    layer = args.get("layer")
    tag = args.get("tag") or _LAYER_TAG_MAP.get(layer) if layer else None

    # v2 layer 名直接传
    v2_layer = layer if layer in ("short_term", "mid_term", "long_term") else None

    results = store.manager.search(query, tag=tag, layer=v2_layer)
    return json.dumps({"query": query, "count": len(results), "results": results}, default=str)


def _handle_list(args: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore 未初始化"})

    layer = args.get("layer")
    tag = args.get("tag") or _LAYER_TAG_MAP.get(layer) if layer else None
    v2_layer = layer if layer in ("short_term", "mid_term", "long_term") else None

    entries = store.manager.list_entries(layer=v2_layer, tag=tag)
    return json.dumps({"count": len(entries), "entries": entries}, default=str)


def _handle_delete(args: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore 未初始化"})

    key = args.get("key", "")
    if not key:
        return json.dumps({"error": "未指定 key"})

    ok = store.manager.delete(key)
    return json.dumps({"success": ok, "key": key})


def _handle_check_operation(args: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore 未初始化"})

    tool = args.get("tool", "")
    action_hint = args.get("action_hint", "")
    if not tool:
        return json.dumps({"error": "未指定 tool"})

    result = store.manager.check_operation(tool, action_hint)
    return json.dumps(result, default=str)


def _handle_maintain(args: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore 未初始化"})

    result = store.manager.maintain(full=True)
    return json.dumps(result, default=str)
