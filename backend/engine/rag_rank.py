"""RAG 相似度与重排：余弦、稀疏余弦、BGE-reranker（不可用时返回 None 由调用方回退）。

从 `rag_utils.py` 拆出；重排模型的加载在 rag_models。
"""
from __future__ import annotations

import math

from backend.engine.rag_models import _load_reranker


def sparse_cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """稀疏向量余弦相似度。"""
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, v in a.items():
        if k in b:
            dot += v * b[k]
    norm_a = math.sqrt(sum(v * v for v in a.values())) or 1.0
    norm_b = math.sqrt(sum(v * v for v in b.values())) or 1.0
    return dot / (norm_a * norm_b)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    for x, y in zip(a, b):
        dot += x * y
    return dot


def rerank_or_none(query: str, texts: list[str], top_k: int = 5) -> list[tuple[str, float]] | None:
    """尝试重排；未配置/加载失败/执行失败时返回 None，由调用方保留原始混合检索分数。"""
    fn = _load_reranker()
    if fn is None or not texts:
        return None
    try:
        scores = fn(query, texts)
        if not scores:
            return None
        pairs = sorted(zip(texts, scores), key=lambda x: x[1], reverse=True)
        return pairs[:top_k]
    except Exception as e:
        print(f"[RAG] rerank 失败，保留混合检索原始分数: {e}")
        return None


def rerank(query: str, texts: list[str], top_k: int = 5) -> list[tuple[str, float]]:
    """兼容旧接口：保留原序返回；新代码请使用 rerank_or_none。"""
    result = rerank_or_none(query, texts, top_k=top_k)
    if result is not None:
        return result
    return [(t, 0.0) for t in texts[:top_k]]
