"""本地知识库——用于 RAG 检索的固定程序实现。

存储：
- 内置规则备注（D&D 5e / D&D 4e / COC / 自定义）
- 玩家上传的剧本/规则/备注（PDF/DOCX/TXT 等）
- 剧本切分后的设定细节

检索：
- 基于字符 n-gram 的 TF-IDF 风格本地检索，不调用 LLM，零 token 消耗。

实现：文档 CRUD → knowledge_docs，检索 → knowledge_retrieval，
文本辅助 → knowledge_text；本模块只做类装配、单例与兼容再导出。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from backend.knowledge_docs import KnowledgeDocsMixin
from backend.knowledge_retrieval import KnowledgeRetrievalMixin
from backend.knowledge_text import (
    _TOKEN_CACHE,
    _TOKEN_CACHE_MAX,
    _classify_query,
    _clean_content,
    _is_garbled,
    _safe_source,
    _safe_title,
    _tokenize,
    _tokenize_uncached,
)

# 兼容既有导入路径：调用方与测试仍可从本模块取这些符号
__all__ = [
    "DEFAULT_KB_PATH",
    "KnowledgeBase",
    "_TOKEN_CACHE",
    "_TOKEN_CACHE_MAX",
    "_classify_query",
    "_clean_content",
    "_is_garbled",
    "_safe_source",
    "_safe_title",
    "_tokenize",
    "_tokenize_uncached",
    "get_knowledge_base",
]

DEFAULT_KB_PATH = Path("knowledge_base/documents.json")


class KnowledgeBase(KnowledgeDocsMixin, KnowledgeRetrievalMixin):
    def __init__(self, path: str | Path = DEFAULT_KB_PATH):
        self.path = Path(path)
        self.documents: list[dict[str, Any]] = []
        self._loaded = False
        # 本地向量与模型向量分离缓存：provider -> {(doc_id, chunk_index, content_md5): vector}
        self._vec_caches: dict[str, dict[tuple[str, int, str], list[float]]] = {
            "local": {},
            "bge": {},
        }
        # BGE-M3 稀疏向量缓存（与稠密向量同样按 provider 隔离）
        self._sparse_caches: dict[str, dict[tuple[str, int, str], dict[str, float]]] = {
            "local": {},
            "bge": {},
        }
        # 按内容指纹缓存向量：剧本复制/多用户同名文档可复用同一分块的向量，避免重复嵌入
        self._content_vec_cache: dict[str, dict[str, list[float]]] = {"local": {}, "bge": {}}
        self._content_sparse_cache: dict[str, dict[str, dict[str, float]]] = {"local": {}, "bge": {}}
        # P1-5: 检索缓存（候选/分词/IDF/BM25）与文档修订号
        self._revision = 0
        self._retrieval_cache: dict[tuple, dict] = {}
        # 索引构建锁：避免预热与首回合检索重复构建同一份索引
        self._index_lock = threading.Lock()



# 全局单例（懒加载）
_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase().load()
        _kb.seed_builtin_rules()
    return _kb
