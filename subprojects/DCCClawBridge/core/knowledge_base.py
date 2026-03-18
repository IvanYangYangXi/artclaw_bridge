"""
knowledge_base.py - DCCClawBridge 知识库
=========================================

分级索引: 系统级(API文档) → 项目级(规范) → 用户级(笔记)

当前为骨架实现，后续移植 UE 的完整 RAG 知识库。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger("artclaw.kb")


class KnowledgeBase:
    """本地知识库"""

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir
        self._documents: List[dict] = []
        self._index_built = False

    def add_document(self, title: str, content: str, category: str = "system", tags: list = None):
        self._documents.append({
            "title": title,
            "content": content,
            "category": category,
            "tags": tags or [],
        })

    def search(self, query: str, limit: int = 5) -> List[dict]:
        """简单关键词搜索（后续替换为向量检索）"""
        query_lower = query.lower()
        results = []
        for doc in self._documents:
            score = 0
            if query_lower in doc["title"].lower():
                score += 10
            if query_lower in doc["content"].lower():
                score += 5
            for word in query_lower.split():
                if word in doc["content"].lower():
                    score += 1
            if score > 0:
                results.append({**doc, "score": score})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_stats(self) -> dict:
        return {
            "total_documents": len(self._documents),
            "categories": list(set(d["category"] for d in self._documents)),
        }


def init_knowledge_base(mcp_server, data_dir: str = "") -> KnowledgeBase:
    """初始化知识库并注册 MCP 工具"""
    kb = KnowledgeBase(data_dir=data_dir)

    def _handle_search(arguments: dict) -> str:
        query = arguments.get("query", "")
        limit = arguments.get("limit", 5)
        results = kb.search(query, limit)
        if not results:
            return f"未找到与 '{query}' 相关的文档"
        return json.dumps(results, ensure_ascii=False, indent=2)

    mcp_server.register_tool(
        name="knowledge_search",
        description="在本地知识库中搜索相关文档（API 文档、项目规范、代码示例等）",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回结果数量", "default": 5},
            },
            "required": ["query"],
        },
        handler=_handle_search,
    )

    logger.info(f"Knowledge base initialized ({kb.get_stats()['total_documents']} docs)")
    return kb
