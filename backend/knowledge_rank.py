"""混合检索的纯计算部分：索引构建、TF-IDF、归一化、动态权重与父子块回填。

从 `knowledge_retrieval` 拆出——那边只留"取数据 + 拼最终结果"的编排。

**不变量**：父子块回填（`parent_id` / `parent_content`）在这里实现，
搬移时必须保持语义不变（见 SKILL 第 6 条：任何检索改动都要保留父块回填）。
"""
from __future__ import annotations

import math
from collections import Counter

from rank_bm25 import BM25Okapi

from backend.knowledge_text import _tokenize


def build_index(candidates: list) -> dict:
    """为候选分块建 IDF 与 BM25 索引（词频统计与分词一次算完）。"""
    df: Counter[str] = Counter()
    for _, _, chunk in candidates:
        for term in set(_tokenize(chunk)):
            df[term] += 1
    n = max(1, len(candidates))
    idf = {term: math.log((n + 1) / (freq + 1)) + 1 for term, freq in df.items()}
    corpus_tokens = [_tokenize(chunk) for _, _, chunk in candidates]
    return {"idf": idf, "corpus_tokens": corpus_tokens, "bm25": BM25Okapi(corpus_tokens)}


def tfidf_scores(candidates: list, q_terms: list, idf: dict) -> list[float]:
    """查询词与各分块的 TF-IDF 得分（带长度归一）。"""
    scores: list[float] = []
    for _, _, chunk in candidates:
        c_terms = _tokenize(chunk)
        c_tf = Counter(c_terms)
        q_tf = Counter(q_terms)
        score = 0.0
        for term, qf in q_tf.items():
            if term in c_tf:
                score += qf * idf.get(term, 1.0) * (1 + math.log(c_tf[term]))
        score = score / (1 + math.log(len(c_terms) + 1))
        scores.append(score)
    return scores


def normalize(vals) -> list[float]:
    """按最大值归一到 0~1；全 0 或空列表返回 0 序列。"""
    vals = list(vals)
    if not vals:
        return []
    m = max(vals)
    return [v / m if m > 0 else 0.0 for v in vals]


def query_weights(query_type: str, sparse_on: bool) -> tuple[float, float, float, float]:
    """查询分类动态权重：规则查询偏词法，实体查询偏语义。

    返回 `(w_dense, w_sparse, w_tfidf, w_bm25)`；未启用稀疏向量时 `w_sparse` 为 0。
    """
    if sparse_on:
        if query_type == "rule":
            return 0.25, 0.30, 0.20, 0.25
        if query_type == "entity":
            return 0.40, 0.30, 0.15, 0.15
        return 0.35, 0.30, 0.20, 0.15
    if query_type == "rule":
        return 0.30, 0.0, 0.35, 0.35
    if query_type == "entity":
        return 0.50, 0.0, 0.30, 0.20
    return 0.45, 0.0, 0.30, 0.25


def parent_context(doc: dict, chunk: str) -> tuple[str, str]:
    """父子块回填：命中子块时返回其父块 id 与内容，供前端/DM 拿到完整上下文。"""
    parent_id = ""
    parent_content = ""
    child_chunks = doc.get("child_chunks") or []
    if child_chunks and isinstance(child_chunks, list):
        for cc in child_chunks:
            if cc.get("content") == chunk:
                parent_id = str(cc.get("parent_id", ""))
                break
        if parent_id:
            for pc in doc.get("parent_chunks") or []:
                if pc.get("id") == parent_id:
                    parent_content = pc.get("content", "")
                    break
    return parent_id, parent_content
