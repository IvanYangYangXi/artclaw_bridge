"""
memory_store.py - DCCClawBridge 记忆管理 v2 适配层
===================================================

将 memory_core.MemoryManagerV2（平台无关）接入 DCC MCP Server。

职责:
  - 确定 DCC 的存储路径 (~/.artclaw/{maya|max}/memory_v2.json)
  - 注册 MCP Tool (memory)
  - 旧格式自动迁移
  - 适配 Python logging

共享核心:
  - memory_core.py (core/)
  - 开发模式: 通过相对路径回溯导入
  - 部署模式: 安装器已复制到 core/ 目录
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, List, Optional

logger = logging.getLogger("artclaw.memory")

# ---------------------------------------------------------------------------
# 导入 memory_core
# 优先级:
#   1. 自包含部署: memory_core.py 已复制到 core/ 目录（同级）
#   2. 开发模式: 通过相对路径找到 core/
# ---------------------------------------------------------------------------

try:
    from memory_core import MemoryManagerV2, DEFAULT_CONFIG  # noqa: E402
except ImportError:
    _bridge_pkg_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "core")
    )
    if os.path.isdir(_bridge_pkg_dir) and _bridge_pkg_dir not in sys.path:
        sys.path.insert(0, _bridge_pkg_dir)

    from memory_core import MemoryManagerV2, DEFAULT_CONFIG  # noqa: E402


# ============================================================================
# DCC 存储路径
# ============================================================================

def _get_default_storage_dir(dcc_name: str = "maya") -> str:
    """获取 DCC 默认存储目录"""
    return os.path.join(os.path.expanduser("~"), ".artclaw", dcc_name)


# ============================================================================
# DCC 适配封装
# ============================================================================

class DCCMemoryStore:
    """DCC 环境下的记忆管理器封装"""

    def __init__(self, dcc_name: str = "maya", data_dir: str = ""):
        self._dcc_name = dcc_name
        self._data_dir = data_dir or _get_default_storage_dir(dcc_name)
        os.makedirs(self._data_dir, exist_ok=True)

        storage_path = os.path.join(self._data_dir, "memory_v2.json")

        self._manager = MemoryManagerV2(
            storage_path=storage_path,
            dcc_name=dcc_name,
        )

        # 检查并迁移旧格式
        self._try_migrate_v1()

        logger.info(f"MemoryStore v2 初始化完成: {dcc_name}, {storage_path}")
        stats = self._manager.get_stats()
        logger.info(f"  记忆条目: {stats.get('total_entries', 0)}")

        # 启动定时维护
        self._manager.start_maintenance_timer()

    def _try_migrate_v1(self):
        """检测并迁移 v1 格式的记忆文件"""
        old_file = os.path.join(self._data_dir, "memory.json")
        v2_file = os.path.join(self._data_dir, "memory_v2.json")

        if os.path.exists(old_file) and not os.path.exists(v2_file):
            logger.info("检测到 v1 格式记忆文件，开始迁移...")
            try:
                count = MemoryManagerV2.migrate_from_dcc_v1(old_file, v2_file)
                # 迁移成功后重新加载
                self._manager = MemoryManagerV2(
                    storage_path=v2_file,
                    dcc_name=self._dcc_name,
                )
                logger.info(f"v1 迁移完成: {count} 条记录")
            except Exception as e:
                logger.error(f"v1 迁移失败: {e}")

    @property
    def manager(self) -> MemoryManagerV2:
        """获取底层 MemoryManagerV2 实例"""
        return self._manager

    # ------------------------------------------------------------------
    # 向后兼容: 旧版 MemoryStore 接口代理
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any, layer: str = "project", ttl: int = 0):
        """兼容旧版 set(key, value, layer, ttl)"""
        tag_map = {"system": "fact", "project": "fact", "short_term": "context"}
        tag = tag_map.get(layer, "fact")
        self._manager.record(key, value, tag=tag, importance=0.5, source=f"dcc:{layer}")

    def get(self, key: str) -> Optional[Any]:
        """兼容旧版 get(key)"""
        result = self._manager.get(key)
        if result is None:
            return None
        return result.get("value")

    def search(self, query: str, limit: int = 10) -> List[dict]:
        """兼容旧版 search(query, limit)"""
        return self._manager.search(query, limit=limit)

    def list_all(self, layer: str = "") -> List[dict]:
        """兼容旧版 list_all(layer)"""
        return self._manager.list_entries(limit=200)

    def delete(self, key: str) -> bool:
        """兼容旧版 delete(key)"""
        return self._manager.delete(key)

    def flush(self):
        """强制保存（关闭时调用）"""
        self._manager.stop_maintenance_timer()


# 旧名称别名
MemoryStore = DCCMemoryStore


# ============================================================================
# MCP 注册
# ============================================================================

# 旧 layer 名 → v2 tag 映射
_LAYER_TAG_MAP = {
    "system": "fact",
    "project": "fact",
    "short_term": "context",
    "facts": "fact",
    "preferences": "preference",
    "conventions": "convention",
}


def init_memory_store(mcp_server, data_dir: str = "", dcc_name: str = "maya") -> DCCMemoryStore:
    """初始化记忆存储并注册 MCP 工具

    签名与旧版兼容（多一个 dcc_name 可选参数）。
    """
    store = DCCMemoryStore(dcc_name=dcc_name, data_dir=data_dir)

    def _handle_memory(arguments: dict) -> str:
        action = arguments.get("action", "get")
        key = arguments.get("key", "")
        value = arguments.get("value")
        layer = arguments.get("layer", "")
        query = arguments.get("query", "")
        tag = arguments.get("tag", "")
        importance = arguments.get("importance", 0.5)

        mgr = store.manager

        if action == "get":
            if not key:
                return json.dumps({"error": "未指定 key"}, ensure_ascii=False)
            result = mgr.get(key)
            if result is None:
                return json.dumps({"found": False, "key": key}, ensure_ascii=False)
            return json.dumps({"found": True, **result}, ensure_ascii=False, default=str)

        elif action == "set":
            if not key:
                return json.dumps({"error": "未指定 key"}, ensure_ascii=False)
            resolved_tag = tag or _LAYER_TAG_MAP.get(layer, "fact")
            ok = mgr.record(key, value, tag=resolved_tag, importance=importance, source="mcp:set")
            return json.dumps({"success": ok, "key": key, "tag": resolved_tag}, ensure_ascii=False)

        elif action == "search":
            resolved_tag = tag or (_LAYER_TAG_MAP.get(layer) if layer else None)
            v2_layer = layer if layer in ("short_term", "mid_term", "long_term") else None
            results = mgr.search(query or key, tag=resolved_tag, layer=v2_layer)
            return json.dumps({"query": query or key, "count": len(results), "results": results},
                              ensure_ascii=False, default=str)

        elif action == "list":
            resolved_tag = tag or (_LAYER_TAG_MAP.get(layer) if layer else None)
            v2_layer = layer if layer in ("short_term", "mid_term", "long_term") else None
            entries = mgr.list_entries(layer=v2_layer, tag=resolved_tag)
            return json.dumps({"count": len(entries), "entries": entries},
                              ensure_ascii=False, default=str)

        elif action == "delete":
            if not key:
                return json.dumps({"error": "未指定 key"}, ensure_ascii=False)
            ok = mgr.delete(key)
            return json.dumps({"success": ok, "key": key}, ensure_ascii=False)

        elif action == "check_operation":
            tool = arguments.get("tool", "")
            action_hint = arguments.get("action_hint", "")
            if not tool:
                return json.dumps({"error": "未指定 tool"}, ensure_ascii=False)
            result = mgr.check_operation(tool, action_hint)
            return json.dumps(result, ensure_ascii=False, default=str)

        elif action == "maintain":
            result = mgr.maintain(full=True)
            return json.dumps(result, ensure_ascii=False, default=str)

        else:
            return json.dumps({"error": f"未知操作: {action}"}, ensure_ascii=False)

    # v2.6: 默认不注册 MCP 工具，通过 run_python 调用 Python API
    if os.environ.get("ARTCLAW_LEGACY_MCP", "").lower() == "true":
        mcp_server.register_tool(
            name="memory",
            description=(
                "分层记忆管理 v2。action: get(读取)/set(存储)/search(搜索)/list(列出)/"
                "delete(删除)/check_operation(查询操作历史)/maintain(触发维护)。"
                "tag: fact/preference/convention/operation/crash/pattern/context"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get", "set", "search", "list", "delete",
                                 "check_operation", "maintain"],
                    },
                    "key": {"type": "string", "description": "记忆键名"},
                    "value": {"description": "要存储的值 (action=set 时使用)"},
                    "layer": {
                        "type": "string",
                        "enum": ["short_term", "mid_term", "long_term",
                                 "system", "project"],
                        "description": "记忆层级（旧名称自动映射）",
                    },
                    "tag": {
                        "type": "string",
                        "enum": ["fact", "preference", "convention",
                                 "operation", "crash", "pattern", "context"],
                        "description": "语义标签 (v2)",
                    },
                    "importance": {
                        "type": "number",
                        "description": "重要性评分 0-1 (默认 0.5)",
                    },
                    "query": {"type": "string", "description": "搜索关键词"},
                    "tool": {"type": "string", "description": "工具名称 (check_operation)"},
                    "action_hint": {"type": "string", "description": "动作提示 (check_operation)"},
                },
                "required": ["action"],
            },
            handler=_handle_memory,
        )
        logger.info(f"MemoryStore v2: MCP tool registered - legacy mode ({store._manager.get_stats().get('total_entries', 0)} entries)")
    else:
        logger.info(f"MemoryStore v2: MCP tool skipped - v2.6 slim mode ({store._manager.get_stats().get('total_entries', 0)} entries)")
    return store
