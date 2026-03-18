"""
knowledge_base.py - 本地知识库与语义检索
==========================================

阶段 3.2 + 3.3 + 3.6: Local RAG + Smart Retrieval + Auto-Indexing

宪法约束:
  - 开发路线图 §3.2: 索引 UE Python API 文档、命名规范、代码范例
  - 开发路线图 §3.3: 根据用户指令语义检索相关 API 片段
  - 开发路线图 §3.6: 一键将 Markdown/PDF 转为索引

设计说明:
  - 使用纯 Python 实现的关键词 + TF-IDF 检索（无需 faiss/ChromaDB 重依赖）
  - 索引存储在 Saved/UEAgent/knowledge/ 目录
  - 支持 Markdown 文档自动切分和索引
  - 通过 MCP Tool 暴露检索能力
  - 未来可升级为向量检索（添加 faiss-cpu 依赖）
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import unreal
    _kb_dir = Path(str(unreal.Paths.project_saved_dir())) / "UEAgent" / "knowledge"
except Exception:
    _kb_dir = Path.home() / ".ue_agent" / "knowledge"

from init_unreal import UELogger


# ============================================================================
# 1. 文档切分
# ============================================================================

def split_markdown(content: str, source: str = "", chunk_size: int = 500) -> List[dict]:
    """将 Markdown 文档按标题切分为 chunks"""
    chunks = []
    current_title = ""
    current_lines = []

    for line in content.split("\n"):
        if line.startswith("#"):
            # 保存前一个 chunk
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    chunks.append({
                        "title": current_title,
                        "text": text[:chunk_size],
                        "source": source,
                    })
            current_title = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)
            # 按大小分块
            if len("\n".join(current_lines)) > chunk_size:
                text = "\n".join(current_lines).strip()
                chunks.append({
                    "title": current_title,
                    "text": text[:chunk_size],
                    "source": source,
                })
                current_lines = []

    # 最后一段
    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            chunks.append({
                "title": current_title,
                "text": text[:chunk_size],
                "source": source,
            })

    return chunks


def _tokenize(text: str) -> List[str]:
    """简单的词元化：小写、按非字母数字分割"""
    return re.findall(r"[a-z_][a-z0-9_]*", text.lower())


# ============================================================================
# 2. Knowledge Base 核心
# ============================================================================

class KnowledgeBase:
    """
    本地知识库。支持关键词检索和 TF-IDF 排序。

    宪法约束:
      - 开发路线图 §3.2: 索引 UE Python API 文档
      - 开发路线图 §3.3: 语义检索
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _kb_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

        # 内存索引
        self._documents: List[dict] = []  # [{title, text, source, tokens}]
        self._idf: Dict[str, float] = {}  # token -> IDF score

        # 加载已有索引
        self._load_index()
        UELogger.info(f"KnowledgeBase: {len(self._documents)} documents indexed")

    def add_document(self, title: str, text: str, source: str = "") -> None:
        """添加单个文档"""
        tokens = _tokenize(text)
        self._documents.append({
            "title": title,
            "text": text,
            "source": source,
            "tokens": tokens,
        })

    def index_markdown_file(self, file_path: str) -> int:
        """索引一个 Markdown 文件"""
        path = Path(file_path)
        if not path.exists():
            return 0

        content = path.read_text(encoding="utf-8", errors="ignore")
        chunks = split_markdown(content, source=path.name)

        for chunk in chunks:
            self.add_document(
                title=chunk["title"],
                text=chunk["text"],
                source=chunk["source"],
            )

        return len(chunks)

    def index_directory(self, dir_path: str, patterns: List[str] = None) -> int:
        """
        索引目录下的所有文档。

        宪法约束:
          - 开发路线图 §3.6: 一键将 Markdown 转为索引
        """
        if patterns is None:
            patterns = ["*.md", "*.txt", "*.rst"]

        directory = Path(dir_path)
        if not directory.exists():
            return 0

        total = 0
        for pattern in patterns:
            for file_path in directory.rglob(pattern):
                count = self.index_markdown_file(str(file_path))
                total += count

        # 重建 IDF
        self._rebuild_idf()
        self._save_index()

        UELogger.info(f"KnowledgeBase: indexed {total} chunks from {dir_path}")
        return total

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """
        检索最相关的文档片段。

        宪法约束:
          - 开发路线图 §3.3: 根据用户指令语义检索
        """
        if not self._documents:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # TF-IDF 打分
        scores: List[Tuple[float, int]] = []
        for idx, doc in enumerate(self._documents):
            score = self._compute_tfidf_score(query_tokens, doc["tokens"])
            if score > 0:
                scores.append((score, idx))

        # 排序取 top_k
        scores.sort(key=lambda x: -x[0])
        results = []
        for score, idx in scores[:top_k]:
            doc = self._documents[idx]
            results.append({
                "title": doc["title"],
                "text": doc["text"][:300],  # 截断以节省 Token
                "source": doc["source"],
                "score": round(score, 4),
            })

        return results

    def search_for_prompt(self, query: str, top_k: int = 3) -> str:
        """
        检索并格式化为 Prompt 注入格式。

        宪法约束:
          - 开发路线图 §3.3: 将检索到的代码范例作为 Context 喂给 AI
        """
        results = self.search(query, top_k)
        if not results:
            return ""

        parts = ["## Relevant Knowledge:"]
        for r in results:
            parts.append(f"\n### {r['title']} (from {r['source']})")
            parts.append(r["text"])

        return "\n".join(parts)

    def get_stats(self) -> dict:
        """获取知识库统计"""
        return {
            "total_documents": len(self._documents),
            "unique_tokens": len(self._idf),
            "index_file": str(self._index_path),
            "sources": list(set(d["source"] for d in self._documents)),
        }

    # ------------------------------------------------------------------
    # TF-IDF 计算
    # ------------------------------------------------------------------

    def _rebuild_idf(self) -> None:
        """重建 IDF 索引"""
        n = len(self._documents)
        if n == 0:
            return

        df: Counter = Counter()
        for doc in self._documents:
            unique_tokens = set(doc.get("tokens", []))
            for token in unique_tokens:
                df[token] += 1

        self._idf = {
            token: math.log(n / (count + 1))
            for token, count in df.items()
        }

    def _compute_tfidf_score(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        """计算查询与文档的 TF-IDF 相似度"""
        if not doc_tokens:
            return 0.0

        doc_tf = Counter(doc_tokens)
        doc_len = len(doc_tokens)

        score = 0.0
        for token in query_tokens:
            tf = doc_tf.get(token, 0) / max(doc_len, 1)
            idf = self._idf.get(token, 0)
            score += tf * idf

        return score

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    @property
    def _index_path(self) -> Path:
        return self._base_dir / "knowledge_index.json"

    def _load_index(self) -> None:
        path = self._index_path
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._documents = data.get("documents", [])
            # 重建 tokens（如果缺失）
            for doc in self._documents:
                if "tokens" not in doc:
                    doc["tokens"] = _tokenize(doc.get("text", ""))
            self._rebuild_idf()
        except Exception as e:
            UELogger.mcp_error(f"Failed to load knowledge index: {e}")

    def _save_index(self) -> None:
        path = self._index_path
        try:
            # 保存时不存 tokens（太大）
            save_docs = [
                {k: v for k, v in doc.items() if k != "tokens"}
                for doc in self._documents
            ]
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"documents": save_docs, "updated_at": time.time()},
                         f, ensure_ascii=False, indent=2)
        except Exception as e:
            UELogger.mcp_error(f"Failed to save knowledge index: {e}")


# ============================================================================
# 3. MCP 注册
# ============================================================================

_kb_instance: Optional[KnowledgeBase] = None


def init_knowledge_base(mcp_server, base_dir: Optional[Path] = None) -> KnowledgeBase:
    """初始化知识库并注册 MCP 接口"""
    global _kb_instance
    _kb_instance = KnowledgeBase(base_dir)

    # 自动索引项目文档目录
    _auto_index_project_docs()

    # --- MCP Tools ---

    mcp_server.register_tool(
        name="knowledge_search",
        description=(
            "Search the local knowledge base for UE API documentation, project conventions, "
            "and code examples. Use this before writing complex UE Python code to find correct API usage."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'set material color', 'spawn actor')"},
                "top_k": {"type": "integer", "default": 5, "description": "Number of results"},
            },
            "required": ["query"],
        },
        handler=_handle_kb_search,
    )

    # knowledge_index / knowledge_stats 已移除为 MCP Tool（低频，可通过 run_ue_python 调用）
    # 函数仍保留供内部使用

    UELogger.info("KnowledgeBase: registered 1 MCP tool (search only)")
    return _kb_instance


def get_knowledge_base() -> Optional[KnowledgeBase]:
    return _kb_instance


def _auto_index_project_docs():
    """自动索引项目内的文档目录"""
    if _kb_instance is None:
        return

    # 如果已有索引，跳过
    if _kb_instance._documents:
        return

    try:
        project_dir = Path(str(unreal.Paths.project_dir()))

        # 尝试常见文档目录
        doc_dirs = [
            project_dir / "Docs",
            project_dir / "docs",
            project_dir / "Documentation",
        ]

        for doc_dir in doc_dirs:
            if doc_dir.exists():
                _kb_instance.index_directory(str(doc_dir))
                break

    except Exception:
        pass  # 静默失败


# --- Handlers ---

def _handle_kb_search(arguments: dict) -> str:
    kb = get_knowledge_base()
    if not kb:
        return json.dumps({"error": "KnowledgeBase not initialized"})

    query = arguments.get("query", "")
    top_k = arguments.get("top_k", 5)
    results = kb.search(query, top_k)
    return json.dumps({"query": query, "count": len(results), "results": results})


def _handle_kb_index(arguments: dict) -> str:
    kb = get_knowledge_base()
    if not kb:
        return json.dumps({"error": "KnowledgeBase not initialized"})

    directory = arguments.get("directory", "")
    patterns = arguments.get("patterns")
    count = kb.index_directory(directory, patterns)
    return json.dumps({"indexed": count, "directory": directory, "total": len(kb._documents)})


def _handle_kb_stats(arguments: dict) -> str:
    kb = get_knowledge_base()
    if not kb:
        return json.dumps({"error": "KnowledgeBase not initialized"})
    return json.dumps(kb.get_stats())
