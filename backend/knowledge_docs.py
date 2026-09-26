"""知识库文档 CRUD mixin：加载/保存、增删改查与向量模式开关。

由 KnowledgeBase 组合使用（见 backend/knowledge_base.py）。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from backend.engine.rag_utils import (
    get_provider,
    model_ready,
    reranker_ready,
    set_provider,
)
from backend.knowledge_text import (
    _clean_content,
    _is_garbled,
    _safe_source,
    _safe_title,
)
from backend.scenario_importer import split_text


if TYPE_CHECKING:
    from backend.knowledge_base import KnowledgeBase


class KnowledgeDocsMixin:
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
        # 文档内容变化后使检索缓存失效
        self._revision += 1
        self._retrieval_cache.clear()
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
        splitter: str = "semantic",
        parent_chunks: list | None = None,
        child_chunks: list | None = None,
        images: list | None = None,
        tables: list | None = None,
        doc_id: str | None = None,
        scenario_id: str = "",
    ) -> dict:
        self.load()
        content = _clean_content(content)
        if splitter == "semantic":
            mode = "semantic"
        elif splitter == "recursive":
            mode = "recursive"
        else:
            mode = "semantic" if splitter == "llm" else "naive"
        chunks = split_text(content, mode=mode, chunk_size=chunk_size)
        if child_chunks:
            # 父子块优先：检索索引使用子块，父块/图片/表格一并保存
            chunks = [c.content for c in child_chunks if getattr(c, "content", "")]
        if not chunks:
            chunks = [content.strip()] if content.strip() else []
        final_doc_id = doc_id or uuid.uuid4().hex[:16]
        if child_chunks is None and parent_chunks is None and chunks:
            # 纯文本备注也统一生成父子块，保证所有入库文档都有父块回填能力
            parent_id = uuid.uuid4().hex[:16]
            parent_chunks = [{
                "id": parent_id, "doc_id": final_doc_id, "role": "parent",
                "content": content, "type": "text", "page_no": 1, "metadata": {},
            }]
            child_chunks = [{
                "id": uuid.uuid4().hex[:16], "doc_id": final_doc_id,
                "parent_id": parent_id, "role": "child", "content": c,
                "context": c, "type": "text", "page_no": 1, "metadata": {},
            } for c in chunks]
        doc = {
            "id": final_doc_id,
            "title": _safe_title(title),
            "content": content,
            "chunks": chunks,
            "source": _safe_source(source),
            "system": system,
            "tags": tags or [],
            "owner": (username or "").strip(),
            "scenario_id": scenario_id or "",
            "created_at": datetime.now().isoformat(),
        }
        if parent_chunks is not None:
            doc["parent_chunks"] = [vars(c) if hasattr(c, "__dict__") else c for c in parent_chunks]
        if child_chunks is not None:
            doc["child_chunks"] = [vars(c) if hasattr(c, "__dict__") else c for c in child_chunks]
        if images is not None:
            doc["images"] = [vars(i) if hasattr(i, "__dict__") else i for i in images]
        if tables is not None:
            doc["tables"] = [vars(t) if hasattr(t, "__dict__") else t for t in tables]
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
            from backend.local_vector_store import delete_doc_vectors
            try:
                delete_doc_vectors(doc_id)
            except Exception:
                pass
            self.save()
        return changed

    def update_document(self, doc_id: str, title: str | None = None, content: str | None = None,
                        tags: list[str] | None = None, system: str | None = None,
                        username: str | None = None) -> dict | None:
        """就地更新知识文档（标题/正文/标签/规则系统）；正文变了会重新切块。

        实现上沿用"取出旧文档 → 用同一 doc_id 重新入库"的既有路径，
        这样切块、父子块与向量索引都不用另写一套。
        """
        old = self.get_document(doc_id, username)
        if old is None:
            return None
        self.remove_document(doc_id, username)
        return self.add_document(
            title=str(title) if title is not None else str(old.get("title", "")),
            content=str(content) if content is not None else str(old.get("content", "")),
            source=str(old.get("source", "user")),
            system=str(system) if system is not None else str(old.get("system", "custom")),
            tags=list(tags) if tags is not None else list(old.get("tags") or []),
            username=str(username or old.get("owner") or ""),
            scenario_id=str(old.get("scenario_id") or ""),
            doc_id=doc_id,
        )

    def list_documents(self, username: str | None = None, include_scenario: bool = False) -> list[dict]:
        self.load()
        out = []
        for d in self.documents:
            if not self._visible_to(d, username):
                continue
            if not include_scenario and d.get("scenario_id"):
                continue
            out.append({
                "id": d["id"],
                "title": _safe_title(d.get("title", "")),
                "source": _safe_source(d.get("source", "")),
                "system": d.get("system", "custom"),
                "tags": d.get("tags", []),
                "chunk_count": len(d.get("chunks", [])),
                "created_at": d.get("created_at", ""),
                "scenario_id": d.get("scenario_id", ""),
            })
        return out

    def get_document(self, doc_id: str, username: str | None = None) -> dict | None:
        self.load()
        for d in self.documents:
            if d["id"] == doc_id and self._visible_to(d, username):
                return d
        return None

    def set_vector_mode(self, mode: str):
        """切换本地/模型向量模式；bge 不可用时可切换但实际回退 local。"""
        set_provider(mode)
        self._vec_caches.setdefault(mode, {})
        self._sparse_caches.setdefault(mode, {})

    def get_vector_mode(self) -> str:
        return get_provider()

    def model_ready(self) -> bool:
        return model_ready()

    def reranker_ready(self) -> bool:
        return reranker_ready()

