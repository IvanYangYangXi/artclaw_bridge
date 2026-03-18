"""
memory_store.py - DCCClawBridge 分层记忆存储
=============================================

分层: 系统事实(不变) → 项目事实(按项目) → 短期记忆(自动过期)

从 UEClawBridge 移植简化版。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("artclaw.memory")

# 短期记忆默认过期时间（秒）
SHORT_TERM_TTL = 3600 * 24  # 24 小时


class MemoryStore:
    """分层记忆存储"""

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir or os.path.expanduser("~/.artclaw/memory")
        os.makedirs(self._data_dir, exist_ok=True)
        self._cache: Dict[str, dict] = {}
        self._load()

    def _file_path(self) -> str:
        return os.path.join(self._data_dir, "memory.json")

    def _load(self):
        path = self._file_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}
        # 清理过期短期记忆
        self._cleanup_expired()

    def _save(self):
        path = self._file_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2, ensure_ascii=False)

    def _cleanup_expired(self):
        now = time.time()
        to_delete = []
        for key, entry in self._cache.items():
            if entry.get("layer") == "short_term":
                if now - entry.get("timestamp", 0) > entry.get("ttl", SHORT_TERM_TTL):
                    to_delete.append(key)
        for key in to_delete:
            del self._cache[key]

    def set(self, key: str, value: Any, layer: str = "project", ttl: int = 0):
        """存储记忆"""
        entry = {
            "value": value,
            "layer": layer,
            "timestamp": time.time(),
        }
        if layer == "short_term" or ttl > 0:
            entry["ttl"] = ttl or SHORT_TERM_TTL
        self._cache[key] = entry
        self._save()

    def get(self, key: str) -> Optional[Any]:
        """读取记忆"""
        entry = self._cache.get(key)
        if entry is None:
            return None
        # 检查过期
        if entry.get("layer") == "short_term":
            if time.time() - entry.get("timestamp", 0) > entry.get("ttl", SHORT_TERM_TTL):
                del self._cache[key]
                self._save()
                return None
        return entry.get("value")

    def search(self, query: str, limit: int = 10) -> List[dict]:
        """简单关键词搜索"""
        query_lower = query.lower()
        results = []
        for key, entry in self._cache.items():
            val_str = json.dumps(entry.get("value", ""), ensure_ascii=False)
            if query_lower in key.lower() or query_lower in val_str.lower():
                results.append({
                    "key": key,
                    "value": entry["value"],
                    "layer": entry.get("layer", "?"),
                })
        return results[:limit]

    def list_all(self, layer: str = "") -> List[dict]:
        """列出所有记忆"""
        results = []
        for key, entry in self._cache.items():
            if layer and entry.get("layer") != layer:
                continue
            results.append({
                "key": key,
                "layer": entry.get("layer", "?"),
                "timestamp": entry.get("timestamp", 0),
            })
        return results

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            self._save()
            return True
        return False


def init_memory_store(mcp_server, data_dir: str = "") -> MemoryStore:
    """初始化记忆存储并注册 MCP 工具"""
    store = MemoryStore(data_dir=data_dir)

    def _handle_memory(arguments: dict) -> str:
        action = arguments.get("action", "get")
        key = arguments.get("key", "")
        value = arguments.get("value")
        layer = arguments.get("layer", "project")
        query = arguments.get("query", "")

        if action == "get":
            if not key:
                return "错误: 未指定 key"
            result = store.get(key)
            if result is None:
                return f"未找到记忆: {key}"
            return json.dumps({"key": key, "value": result}, ensure_ascii=False)

        elif action == "set":
            if not key:
                return "错误: 未指定 key"
            store.set(key, value, layer=layer)
            return f"已保存: {key}"

        elif action == "search":
            results = store.search(query or key)
            return json.dumps(results, ensure_ascii=False, indent=2)

        elif action == "list":
            results = store.list_all(layer=layer if layer != "project" else "")
            return json.dumps(results, ensure_ascii=False, indent=2)

        elif action == "delete":
            if store.delete(key):
                return f"已删除: {key}"
            return f"未找到: {key}"

        else:
            return f"未知操作: {action}"

    mcp_server.register_tool(
        name="memory",
        description="分层记忆管理。action: get(读取)/set(存储)/search(搜索)/list(列出)/delete(删除)。layer: system(系统)/project(项目)/short_term(短期)",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["get", "set", "search", "list", "delete"]},
                "key": {"type": "string", "description": "记忆键名"},
                "value": {"description": "要存储的值 (action=set 时使用)"},
                "layer": {"type": "string", "enum": ["system", "project", "short_term"], "default": "project"},
                "query": {"type": "string", "description": "搜索关键词 (action=search 时使用)"},
            },
            "required": ["action"],
        },
        handler=_handle_memory,
    )

    logger.info(f"Memory store initialized ({len(store._cache)} entries)")
    return store
