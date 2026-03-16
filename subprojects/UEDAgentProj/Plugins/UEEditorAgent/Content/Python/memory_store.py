"""
memory_store.py - 分层记忆与偏好存储
======================================

阶段 3.4: Tiered Memory Management

宪法约束:
  - 开发路线图 §3.4: 事实记忆、用户偏好、跨端同步
  - 系统架构设计 §1.3: Resource Manager 提供按需拉取

设计说明:
  - 持久化到 Saved/UEAgent/ 目录下的 JSON 文件
  - 分三层: facts (项目事实), preferences (用户偏好), conventions (项目规范)
  - 通过 MCP Resource 暴露给 AI
  - 通过 MCP Tool 允许 AI 读写
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import unreal
    _project_dir = Path(str(unreal.Paths.project_saved_dir())) / "UEAgent"
except Exception:
    _project_dir = Path.home() / ".ue_agent"

from init_unreal import UELogger


# ============================================================================
# 1. Memory Store 核心
# ============================================================================

class MemoryStore:
    """
    分层记忆存储。

    三个存储层:
      - facts: 项目事实 (常用资产路径、命名规则等)
      - preferences: 用户偏好 (灯光强度、间距等审美偏好)
      - conventions: 项目规范 (编码规范、文件结构约定)

    每层都是 key-value 存储，自动持久化到 JSON 文件。
    """

    LAYERS = ("facts", "preferences", "conventions")

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _project_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

        # 内存缓存
        self._data: Dict[str, Dict[str, Any]] = {}

        # 加载所有层
        for layer in self.LAYERS:
            self._data[layer] = self._load_layer(layer)

        UELogger.info(f"MemoryStore initialized: {self._base_dir}")
        for layer in self.LAYERS:
            count = len(self._data[layer])
            if count > 0:
                UELogger.info(f"  {layer}: {count} entries")

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get(self, layer: str, key: str, default: Any = None) -> Any:
        """获取指定层的值"""
        if layer not in self.LAYERS:
            return default
        entry = self._data[layer].get(key)
        if entry is None:
            return default
        return entry.get("value", default)

    def set(self, layer: str, key: str, value: Any, metadata: Optional[dict] = None) -> bool:
        """设置指定层的值"""
        if layer not in self.LAYERS:
            return False

        self._data[layer][key] = {
            "value": value,
            "updated_at": time.time(),
            "metadata": metadata or {},
        }
        self._save_layer(layer)
        return True

    def delete(self, layer: str, key: str) -> bool:
        """删除指定层的键"""
        if layer not in self.LAYERS:
            return False
        if key in self._data[layer]:
            del self._data[layer][key]
            self._save_layer(layer)
            return True
        return False

    def list_keys(self, layer: str) -> List[str]:
        """列出指定层的所有键"""
        if layer not in self.LAYERS:
            return []
        return list(self._data[layer].keys())

    def search(self, query: str, layer: Optional[str] = None) -> List[dict]:
        """按关键词搜索记忆（简单子串匹配）"""
        results = []
        layers = [layer] if layer else self.LAYERS

        query_lower = query.lower()
        for l in layers:
            if l not in self._data:
                continue
            for key, entry in self._data[l].items():
                val_str = json.dumps(entry.get("value", ""), default=str).lower()
                if query_lower in key.lower() or query_lower in val_str:
                    results.append({
                        "layer": l,
                        "key": key,
                        "value": entry.get("value"),
                        "updated_at": entry.get("updated_at"),
                    })

        return results

    def get_layer_summary(self, layer: str) -> dict:
        """获取指定层的摘要"""
        if layer not in self.LAYERS:
            return {"error": f"Unknown layer: {layer}"}

        data = self._data[layer]
        return {
            "layer": layer,
            "count": len(data),
            "keys": list(data.keys())[:50],
            "file": str(self._layer_path(layer)),
        }

    def get_all_summary(self) -> dict:
        """获取所有层的摘要"""
        return {
            layer: self.get_layer_summary(layer)
            for layer in self.LAYERS
        }

    def export_for_prompt(self) -> str:
        """
        导出记忆为 Prompt 可用的文本格式。

        宪法约束:
          - 开发路线图 §3.4: 跨端同步，AI "入乡随俗"
        """
        parts = []

        # 项目规范
        conventions = self._data.get("conventions", {})
        if conventions:
            parts.append("## Project Conventions")
            for key, entry in list(conventions.items())[:20]:
                parts.append(f"- **{key}**: {entry.get('value', '')}")

        # 项目事实
        facts = self._data.get("facts", {})
        if facts:
            parts.append("\n## Project Facts")
            for key, entry in list(facts.items())[:20]:
                parts.append(f"- **{key}**: {entry.get('value', '')}")

        # 用户偏好
        prefs = self._data.get("preferences", {})
        if prefs:
            parts.append("\n## User Preferences")
            for key, entry in list(prefs.items())[:20]:
                parts.append(f"- **{key}**: {entry.get('value', '')}")

        return "\n".join(parts) if parts else "(No memories stored yet)"

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _layer_path(self, layer: str) -> Path:
        return self._base_dir / f"memory_{layer}.json"

    def _load_layer(self, layer: str) -> Dict[str, Any]:
        path = self._layer_path(layer)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            UELogger.mcp_error(f"Failed to load memory layer {layer}: {e}")
            return {}

    def _save_layer(self, layer: str) -> None:
        path = self._layer_path(layer)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data[layer], f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            UELogger.mcp_error(f"Failed to save memory layer {layer}: {e}")


# ============================================================================
# 2. MCP Tool / Resource 注册
# ============================================================================

_memory_store_instance: Optional[MemoryStore] = None


def init_memory_store(mcp_server, base_dir: Optional[Path] = None) -> MemoryStore:
    """初始化 Memory Store 并注册 MCP 接口"""
    global _memory_store_instance
    _memory_store_instance = MemoryStore(base_dir)

    # --- MCP Tools ---

    mcp_server.register_tool(
        name="memory_get",
        description=(
            "Retrieve a value from the project memory store. "
            "Layers: facts (project knowledge), preferences (user aesthetics), conventions (naming rules)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "layer": {"type": "string", "enum": ["facts", "preferences", "conventions"]},
                "key": {"type": "string", "description": "Memory key to retrieve"},
            },
            "required": ["layer", "key"],
        },
        handler=_handle_memory_get,
    )

    mcp_server.register_tool(
        name="memory_set",
        description=(
            "Store a value in the project memory store. AI can remember project-specific facts, "
            "user preferences, and naming conventions for future sessions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "layer": {"type": "string", "enum": ["facts", "preferences", "conventions"]},
                "key": {"type": "string", "description": "Memory key"},
                "value": {"description": "Value to store (string, number, object, array)"},
            },
            "required": ["layer", "key", "value"],
        },
        handler=_handle_memory_set,
    )

    mcp_server.register_tool(
        name="memory_search",
        description=(
            "Search the project memory store by keyword. "
            "Finds matching keys and values across all layers."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword"},
                "layer": {"type": "string", "description": "Optional: limit to specific layer"},
            },
            "required": ["query"],
        },
        handler=_handle_memory_search,
    )

    mcp_server.register_tool(
        name="memory_list",
        description="List all memory keys, optionally filtered by layer.",
        input_schema={
            "type": "object",
            "properties": {
                "layer": {"type": "string", "description": "Optional: specific layer"},
            },
        },
        handler=_handle_memory_list,
    )

    UELogger.info("MemoryStore: registered 4 MCP tools")
    return _memory_store_instance


def get_memory_store() -> Optional[MemoryStore]:
    return _memory_store_instance


# --- Handlers ---

def _handle_memory_get(arguments: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore not initialized"})

    layer = arguments.get("layer", "facts")
    key = arguments.get("key", "")
    value = store.get(layer, key)

    if value is None:
        return json.dumps({"found": False, "layer": layer, "key": key})
    return json.dumps({"found": True, "layer": layer, "key": key, "value": value}, default=str)


def _handle_memory_set(arguments: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore not initialized"})

    layer = arguments.get("layer", "facts")
    key = arguments.get("key", "")
    value = arguments.get("value")

    ok = store.set(layer, key, value)
    return json.dumps({"success": ok, "layer": layer, "key": key})


def _handle_memory_search(arguments: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore not initialized"})

    query = arguments.get("query", "")
    layer = arguments.get("layer")
    results = store.search(query, layer)
    return json.dumps({"query": query, "count": len(results), "results": results}, default=str)


def _handle_memory_list(arguments: dict) -> str:
    store = get_memory_store()
    if not store:
        return json.dumps({"error": "MemoryStore not initialized"})

    layer = arguments.get("layer")
    if layer:
        return json.dumps(store.get_layer_summary(layer))
    return json.dumps(store.get_all_summary())
