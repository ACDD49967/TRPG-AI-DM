"""本地知识库——用于 RAG 检索的固定程序实现。

存储：
- 内置规则备注（D&D 5e / D&D 4e / COC / 自定义）
- 玩家上传的剧本/规则/备注（PDF/DOCX/TXT 等）
- 剧本切分后的设定细节

检索：
- 基于字符 n-gram 的 TF-IDF 风格本地检索，不调用 LLM，零 token 消耗。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from backend.engine.game_systems import (
    build_stat_glossary,
    build_system_rule_block,
    get_system,
)
from backend.scenario_importer import split_text
from backend.engine.rag_utils import embed_text, cosine as dense_cosine

DEFAULT_KB_PATH = Path("knowledge_base/documents.json")


def _tokenize(text: str) -> list[str]:
    """字符 bigram + jieba 分词混合，提升中文检索专业性与命中率。"""
    cleaned = re.sub(r"\s+", "", text.lower())
    if len(cleaned) <= 1:
        return [cleaned] if cleaned else []
    terms = [cleaned[i:i + 2] for i in range(len(cleaned) - 1)]
    try:
        import jieba
        words = [w for w in jieba.cut(cleaned) if len(w.strip()) > 1]
        terms.extend(words)
    except Exception:
        pass
    return terms


def _safe_source(source: str) -> str:
    """去除知识库来源中的本地路径/文件名等敏感信息，统一为类别。"""
    source = source or ""
    if source.startswith("local:"):
        return "用户导入资料"
    if source.startswith("srd:"):
        return source
    if source.startswith("scenario:"):
        return "剧本"
    if source.startswith("extension:"):
        return "扩展包"
    if source.startswith("builtin"):
        return source
    if "\\" in source or "/" in source or source.lower().endswith((".pdf", ".docx", ".doc", ".txt", ".md", ".chm")):
        return "用户导入资料"
    return source or "未知来源"


def _safe_title(title: str) -> str:
    """去除标题中的本地文件名前缀，统一为可读名称。"""
    title = title or ""
    if title.startswith("本地资料："):
        return "导入资料"
    return title or "未命名知识"


def _clean_content(text: str) -> str:
    """清理知识库正文中的控制字符/不可打印字符/替换符乱码。"""
    if not text:
        return ""
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
    # 大量 \ufffd 通常是二进制/编码损坏，直接清空
    if cleaned.count("\ufffd") / max(1, len(cleaned)) > 0.3:
        return ""
    return cleaned


def _is_garbled(text: str) -> bool:
    """判断文本是否已严重乱码（替换符+不可打印字符占比过高）。"""
    if not text.strip():
        return True
    repl = text.count("\ufffd")
    nonprint = sum(1 for ch in text if not ch.isprintable() and ch not in "\n\r\t")
    return (repl + nonprint) / max(1, len(text)) > 0.2


class KnowledgeBase:
    def __init__(self, path: str | Path = DEFAULT_KB_PATH):
        self.path = Path(path)
        self.documents: list[dict[str, Any]] = []
        self._loaded = False
        # 稠密向量缓存：{(doc_id, chunk_index, content_md5): vector}
        self._vec_cache: dict[tuple[str, int, str], list[float]] = {}

    def load(self) -> "KnowledgeBase":
        if self._loaded:
            return self
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.documents = data.get("documents", [])
                # 按内容去重 + 清理乱码（统一化处理）
                seen: set[str] = set()
                cleaned_docs = []
                changed = False
                for d in self.documents:
                    h = hashlib.md5((d.get("content", "") or "").encode("utf-8", errors="replace")).hexdigest()
                    if h in seen:
                        changed = True
                        continue
                    seen.add(h)
                    content = _clean_content(d.get("content", "") or "")
                    if _is_garbled(content):
                        changed = True
                        continue
                    if content != (d.get("content", "") or ""):
                        d["content"] = content
                        d["chunks"] = split_text(content, mode="naive", chunk_size=900)
                        changed = True
                    # 历史数据迁移：无 owner 的用户文档归属 default，避免跨用户可见
                    if "owner" not in d:
                        d["owner"] = "default"
                        changed = True
                    cleaned_docs.append(d)
                if changed:
                    self.documents = cleaned_docs
                    self.save()
            except Exception:
                self.documents = []
        else:
            self.documents = []
        self._loaded = True
        return self

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"documents": self.documents}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _visible_to(self, doc: dict, username: str | None) -> bool:
        """文档可见性：内置规则与 SRD 全局可见，其余仅本人可见。"""
        owner = doc.get("owner", "")
        if not username or owner in ("", "builtin") or str(doc.get("source", "")).startswith("srd:"):
            return True
        return owner == username

    def add_document(
        self,
        title: str,
        content: str,
        source: str = "user",
        system: str = "custom",
        tags: list[str] | None = None,
        chunk_size: int = 900,
        username: str | None = None,
    ) -> dict:
        self.load()
        content = _clean_content(content)
        chunks = split_text(content, mode="naive", chunk_size=chunk_size)
        if not chunks:
            chunks = [content.strip()] if content.strip() else []
        doc = {
            "id": uuid.uuid4().hex[:16],
            "title": _safe_title(title),
            "content": content,
            "chunks": chunks,
            "source": _safe_source(source),
            "system": system,
            "tags": tags or [],
            "owner": (username or "").strip(),
            "created_at": datetime.now().isoformat(),
        }
        self.documents.append(doc)
        self.save()
        return doc

    def add_note(self, title: str, content: str, system: str = "custom",
                 tags: list[str] | None = None, username: str | None = None) -> dict:
        return self.add_document(title, content, source="player-note", system=system,
                                 tags=tags or ["备注"], username=username)

    def remove_document(self, doc_id: str, username: str | None = None) -> bool:
        self.load()
        before = len(self.documents)
        self.documents = [
            d for d in self.documents
            if not (d["id"] == doc_id and self._visible_to(d, username))
        ]
        changed = len(self.documents) != before
        if changed:
            self.save()
        return changed

    def list_documents(self, username: str | None = None) -> list[dict]:
        self.load()
        return [
            {
                "id": d["id"],
                "title": _safe_title(d.get("title", "")),
                "source": _safe_source(d.get("source", "")),
                "system": d.get("system", "custom"),
                "tags": d.get("tags", []),
                "chunk_count": len(d.get("chunks", [])),
                "created_at": d.get("created_at", ""),
            }
            for d in self.documents if self._visible_to(d, username)
        ]

    def get_document(self, doc_id: str, username: str | None = None) -> dict | None:
        self.load()
        for d in self.documents:
            if d["id"] == doc_id and self._visible_to(d, username):
                return d
        return None

    def retrieve(self, query: str, system: str | None = None, top_k: int = 5,
                 username: str | None = None) -> list[dict]:
        """基于字符 bigram 的本地 TF-IDF 检索，返回相关片段（按用户名隔离）。"""
        self.load()
        q_terms = _tokenize(query)
        if not q_terms:
            return []

        candidates = []
        for doc in self.documents:
            if not self._visible_to(doc, username):
                continue
            if system and doc.get("system") not in ("custom", system):
                continue
            for idx, chunk in enumerate(doc.get("chunks", [])):
                candidates.append((doc, idx, chunk))

        if not candidates:
            return []

        # 文档频率（用于 IDF）
        df: Counter[str] = Counter()
        for _, _, chunk in candidates:
            for term in set(_tokenize(chunk)):
                df[term] += 1
        n = max(1, len(candidates))
        idf = {term: math.log((n + 1) / (freq + 1)) + 1 for term, freq in df.items()}

        # TF-IDF 得分
        tfidf_scores: list[float] = []
        corpus_tokens = [_tokenize(chunk) for _, _, chunk in candidates]
        for _, _, chunk in candidates:
            c_terms = _tokenize(chunk)
            c_tf = Counter(c_terms)
            q_tf = Counter(q_terms)
            score = 0.0
            for term, qf in q_tf.items():
                if term in c_tf:
                    score += qf * idf.get(term, 1.0) * (1 + math.log(c_tf[term]))
            score = score / (1 + math.log(len(c_terms) + 1))
            tfidf_scores.append(score)

        # BM25 稀疏检索得分
        bm25 = BM25Okapi(corpus_tokens)
        bm25_scores = bm25.get_scores(q_terms)

        def _norm(vals) -> list[float]:
            vals = list(vals)
            if not vals:
                return []
            m = max(vals)
            return [v / m if m > 0 else 0.0 for v in vals]

        tfidf_norm = _norm(tfidf_scores)
        bm25_norm = _norm(bm25_scores)

        # 稠密向量检索（本地哈希嵌入，缓存加速）
        dense_scores: list[float] = []
        q_vec = embed_text(query)
        for doc, idx, chunk in candidates:
            key = (doc["id"], idx, hashlib.md5(chunk.encode("utf-8", errors="replace")).hexdigest())
            vec = self._vec_cache.get(key)
            if vec is None:
                vec = embed_text(chunk)
                self._vec_cache[key] = vec
            dense_scores.append(max(0.0, dense_cosine(q_vec, vec)))
        dense_norm = _norm(dense_scores)

        scored = []
        for (doc, idx, chunk), tfidf_v, bm25_v, dense_v in zip(candidates, tfidf_norm, bm25_norm, dense_norm):
            # 0.45 稠密向量 + 0.3 TF-IDF + 0.25 BM25 三路融合
            final = 0.45 * dense_v + 0.3 * tfidf_v + 0.25 * bm25_v
            if final > 0:
                scored.append({
                    "doc_id": doc["id"],
                    "title": _safe_title(doc.get("title", "")),
                    "source": _safe_source(doc.get("source", "")),
                    "system": doc.get("system", ""),
                    "chunk_index": idx,
                    "text": chunk,
                    "score": round(final, 4),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def seed_builtin_rules(self):
        """将内置规则备注写入知识库（幂等，按 doc id 去重）。"""
        self.load()
        existing_ids = {d["id"] for d in self.documents}
        seeds = [
            {
                "id": "builtin-rules-dnd5e",
                "title": "D&D 5e 规则备注",
                "content": build_system_rule_block("dnd5e") + "\n\n" + build_stat_glossary("dnd5e"),
                "source": "builtin",
                "system": "dnd5e",
                "tags": ["规则书", "DND5e"],
            },
            {
                "id": "builtin-rules-dnd4e",
                "title": "D&D 4e 规则备注",
                "content": build_system_rule_block("dnd4e") + "\n\n" + build_stat_glossary("dnd4e"),
                "source": "builtin",
                "system": "dnd4e",
                "tags": ["规则书", "DND4e"],
            },
            {
                "id": "builtin-rules-coc",
                "title": "COC 7e 规则备注",
                "content": build_system_rule_block("coc") + "\n\n" + build_stat_glossary("coc"),
                "source": "builtin",
                "system": "coc",
                "tags": ["规则书", "COC7e"],
            },
            {
                "id": "builtin-rules-custom",
                "title": "自定义规则通用备注",
                "content": build_system_rule_block("custom"),
                "source": "builtin",
                "system": "custom",
                "tags": ["规则书", "自定义"],
            },
        ]
        for seed in seeds:
            doc = {
                "id": seed["id"],
                "title": seed["title"],
                "content": seed["content"],
                "chunks": split_text(seed["content"], mode="naive", chunk_size=900),
                "source": seed["source"],
                "system": seed["system"],
                "tags": seed["tags"],
                "owner": "builtin",
                "created_at": datetime.now().isoformat(),
            }
            if seed["id"] in existing_ids:
                # 内置规则随版本更新，覆盖旧内容（例如修正 COC 衍生公式）
                for i, d in enumerate(self.documents):
                    if d["id"] == seed["id"]:
                        self.documents[i] = doc
                        break
            else:
                self.documents.append(doc)
                existing_ids.add(seed["id"])
        self.save()


# 全局单例（懒加载）
_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase().load()
        _kb.seed_builtin_rules()
    return _kb
