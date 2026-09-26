"""知识库混合检索 mixin：TF-IDF / BM25 / 稠密向量 / 稀疏向量的编排。

由 KnowledgeBase 组合使用（见 backend/knowledge_base.py）。
纯计算（索引/TF-IDF/归一化/动态权重/父块回填）在 `knowledge_rank`，
内置规则种子在 `knowledge_seed`（本 mixin 继承它）。
"""

from __future__ import annotations

import hashlib

from backend.config import settings
from backend.engine.rag_utils import (
    cosine as dense_cosine,
    embed_text,
    get_provider,
    rerank_or_none as rag_rerank_or_none,
    sparse_cosine,
    sparse_embed,
    sparse_ready,
)
from backend.knowledge_text import (
    _classify_query,
    _safe_source,
    _safe_title,
    _tokenize,
)
from backend.knowledge_rank import (
    build_index,
    normalize,
    parent_context,
    query_weights,
    tfidf_scores,
)
from backend.knowledge_seed import KnowledgeSeedMixin
from backend.local_vector_store import load_vectors_by_hashes


class KnowledgeRetrievalMixin(KnowledgeSeedMixin):
    def retrieve(self, query: str, system: str | None = None, top_k: int = 5,
                 username: str | None = None, scenario_id: str | None = None) -> list[dict]:
        """混合检索（按用户名隔离；scenario_id 非空时只看该剧本+全局资料）。"""
        self.load()
        q_terms = _tokenize(query)
        if not q_terms:
            return []

        cache_key = (username or "", system or "", scenario_id or "", self._revision)
        cached = self._retrieval_cache.get(cache_key)
        if cached is None:
            # 建索引很贵（万级分块约十几秒）。预热线程与首回合检索可能同时到达，
            # 用锁 + 双重检查保证只构建一次，后者直接复用结果。
            with self._index_lock:
                cached = self._retrieval_cache.get(cache_key)
                if cached is None:
                    candidates = []
                    for doc in self.documents:
                        if not self._visible_to(doc, username):
                            continue
                        if system and doc.get("system") not in ("custom", system):
                            continue
                        doc_scenario = str(doc.get("scenario_id") or "")
                        if scenario_id:
                            if doc_scenario and doc_scenario != scenario_id:
                                continue
                        else:
                            if doc_scenario:
                                continue
                        for idx, chunk in enumerate(doc.get("chunks", [])):
                            candidates.append((doc, idx, chunk))
                    if not candidates:
                        return []
                    cached = {"candidates": candidates, **build_index(candidates)}
                    if len(self._retrieval_cache) > 8:
                        self._retrieval_cache.pop(next(iter(self._retrieval_cache)))
                    self._retrieval_cache[cache_key] = cached
        candidates = cached["candidates"]
        idf = cached["idf"]

        if not candidates:
            return []

        # TF-IDF 得分
        tfidf_raw = tfidf_scores(candidates, q_terms, idf)

        # BM25 稀疏检索得分（复用缓存 BM25 对象）
        bm25 = cached["bm25"]
        bm25_scores = bm25.get_scores(q_terms)

        tfidf_norm = normalize(tfidf_raw)
        bm25_norm = normalize(bm25_scores)

        # 稠密向量检索：先查内存缓存，再按内容指纹批量取回持久化向量，
        # 只有真正缺失的分块才现场嵌入（10k 分块逐块开库约 12 秒，批量后 <0.5 秒）。
        provider = get_provider()
        cache = self._vec_caches.setdefault(provider, {})
        content_cache = self._content_vec_cache.setdefault(provider, {})
        q_vec = embed_text(query)
        pending_vectors: list[dict] = []
        dense_by_pos: list[list[float] | None] = [None] * len(candidates)
        dense_keys: list[tuple[str, int, str]] = []
        dense_missing: list[tuple[int, str]] = []
        md5_of = lambda text: hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()
        for pos, (doc, idx, chunk) in enumerate(candidates):
            md5 = md5_of(chunk)
            key = (doc["id"], idx, md5)
            dense_keys.append(key)
            vec = cache.get(key) or content_cache.get(md5)
            if vec is None:
                dense_missing.append((pos, md5))
            else:
                dense_by_pos[pos] = vec
        if dense_missing:
            stored_map = load_vectors_by_hashes(provider, [md5 for _, md5 in dense_missing])
            for pos, md5 in dense_missing:
                doc, idx, chunk = candidates[pos]
                stored = stored_map.get(md5)
                vec = stored[0] if stored else None
                if vec is None:
                    vec = embed_text(chunk)
                    pending_vectors.append({
                        "doc_id": doc["id"], "chunk_index": idx, "content_md5": md5,
                        "dense": vec, "sparse": None,
                    })
                content_cache[md5] = vec
                dense_by_pos[pos] = vec
        for pos, key in enumerate(dense_keys):
            if dense_by_pos[pos] is not None:
                cache[key] = dense_by_pos[pos]
        dense_scores = [
            max(0.0, dense_cosine(q_vec, vec)) if vec is not None else 0.0
            for vec in dense_by_pos
        ]
        if pending_vectors:
            try:
                from backend.local_vector_store import save_vectors_batch
                save_vectors_batch(provider, pending_vectors)
            except Exception as e:
                print(f"[KB] 批量写入向量失败（忽略，下次重算）: {e}")
        dense_norm = normalize(dense_scores)

        # BGE-M3 稀疏向量（lexical weights）参与混合检索
        bge_sparse_norm: list[float] = []
        sparse_on = sparse_ready()
        if sparse_on:
            sparse_cache = self._sparse_caches.setdefault(provider, {})
            content_sparse_cache = self._content_sparse_cache.setdefault(provider, {})
            q_sparse = sparse_embed(query)
            sparse_pending: list[dict] = []
            sparse_by_pos: list[dict[str, float] | None] = [None] * len(candidates)
            sparse_keys: list[tuple[str, int, str]] = []
            sparse_missing: list[tuple[int, str]] = []
            for pos, (doc, idx, chunk) in enumerate(candidates):
                md5 = md5_of(chunk)
                key = (doc["id"], idx, md5)
                sparse_keys.append(key)
                svec = sparse_cache.get(key) or content_sparse_cache.get(md5)
                if svec is None:
                    sparse_missing.append((pos, md5))
                else:
                    sparse_by_pos[pos] = svec
            if sparse_missing:
                stored_map = load_vectors_by_hashes(provider, [md5 for _, md5 in sparse_missing])
                for pos, md5 in sparse_missing:
                    doc, idx, chunk = candidates[pos]
                    stored = stored_map.get(md5)
                    svec = stored[1] if stored else None
                    if svec is None:
                        svec = sparse_embed(chunk)
                        sparse_pending.append({
                            "doc_id": doc["id"], "chunk_index": idx, "content_md5": md5,
                            "dense": None, "sparse": svec,
                        })
                    content_sparse_cache[md5] = svec
                    sparse_by_pos[pos] = svec
            for pos, key in enumerate(sparse_keys):
                if sparse_by_pos[pos] is not None:
                    sparse_cache[key] = sparse_by_pos[pos]
            bge_sparse_scores = [
                sparse_cosine(q_sparse, svec) if svec is not None else 0.0
                for svec in sparse_by_pos
            ]
            if sparse_pending:
                try:
                    from backend.local_vector_store import save_vectors_batch
                    save_vectors_batch(provider, sparse_pending)
                except Exception as e:
                    print(f"[KB] 批量写入稀疏向量失败（忽略，下次重算）: {e}")
            bge_sparse_norm = normalize(bge_sparse_scores)

        # 查询分类动态权重：规则查询偏词法，实体查询偏语义
        query_type = _classify_query(query) if settings.RAG_QUERY_CLASSIFY else "general"
        w_dense, w_sparse, w_tfidf, w_bm25 = query_weights(query_type, sparse_on)

        scored = []
        for i, ((doc, idx, chunk), tfidf_v, bm25_v, dense_v) in enumerate(zip(candidates, tfidf_norm, bm25_norm, dense_norm)):
            sparse_v = bge_sparse_norm[i] if sparse_on else 0.0
            final = w_dense * dense_v + w_sparse * sparse_v + w_tfidf * tfidf_v + w_bm25 * bm25_v
            if final > 0:
                # 父子块：检索命中子块时回填父块内容，供前端/DM 获取完整上下文
                parent_id, parent_content = parent_context(doc, chunk)
                scored.append({
                    "doc_id": doc["id"],
                    "title": _safe_title(doc.get("title", "")),
                    "source": _safe_source(doc.get("source", "")),
                    "system": doc.get("system", ""),
                    "chunk_index": idx,
                    "text": chunk,
                    "parent_id": parent_id,
                    "parent_content": parent_content,
                    "images": doc.get("images", []),
                    "tables": doc.get("tables", []),
                    "score": round(final, 4),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)

        # 可选 BGE-reranker 重排（用户本地配置存在时才启用；否则原序）
        pre_top = scored[:max(5, settings.RAG_RERANK_TOP_K)]
        if pre_top:
            reranked = rag_rerank_or_none(query, [s["text"] for s in pre_top], top_k=top_k)
            if reranked:
                rerank_order = {text: score for text, score in reranked}
                scored = [s for s in pre_top if s["text"] in rerank_order]
                scored.sort(key=lambda s: rerank_order.get(s["text"], 0.0), reverse=True)
                for s in scored:
                    s["score"] = round(rerank_order.get(s["text"], s["score"]), 4)

        return scored[:top_k]
