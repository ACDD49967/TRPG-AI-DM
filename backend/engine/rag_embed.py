"""RAG 嵌入：本地哈希稠密/稀疏向量，以及小模型与 BGE-M3 的优先回退链。

从 `rag_utils.py` 拆出；模型加载与 provider 状态在 rag_models。
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from backend.engine.rag_models import (
    _DIM, _load_bge_gguf, _load_bge_m3, _load_small_embedder,
)


def _tokens(text: str) -> list[str]:
    text = str(text or "").lower()
    cleaned = re.sub(r"\s+", "", text)
    out: list[str] = []
    for i in range(max(0, len(cleaned) - 2)):
        out.append(cleaned[i:i + 3])
    try:
        import jieba
        out.extend(w for w in jieba.cut(cleaned) if len(w.strip()) > 1)
    except Exception:
        pass
    return out


def _bucket(token: str) -> int:
    h = hashlib.md5(token.encode("utf-8", errors="ignore")).hexdigest()
    return int(h[:8], 16) % _DIM


def _local_embed(text: str) -> list[float]:
    vec = [0.0] * _DIM
    toks = _tokens(text)
    if not toks:
        return vec
    counts = Counter(toks)
    max_tf = max(counts.values()) or 1
    for tok, tf in counts.items():
        idx = _bucket(tok)
        vec[idx] += (1 + math.log(tf)) / max_tf
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _local_sparse(text: str) -> dict[str, float]:
    """本地回退稀疏向量：基于 jieba/字三元组的词频归一化。"""
    toks = _tokens(text)
    if not toks:
        return {}
    counts = Counter(toks)
    total = sum(counts.values()) or 1.0
    return {tok: cnt / total for tok, cnt in counts.items()}


def embed_text(text: str) -> list[float]:
    """返回归一化稠密向量；按 provider 优先小模型 / BGE-M3 / GGUF，最后本地哈希。"""
    text = str(text or "")

    small = _load_small_embedder()
    if small is not None:
        try:
            emb = small.encode([text], normalize_embeddings=True)[0]
            if emb is not None:
                return [float(v) for v in emb]
        except Exception as e:
            print(f"[RAG] 小模型 dense 失败，尝试 BGE/本地: {e}")

    model = _load_bge_m3()
    if model is not None:
        try:
            out = model.encode([text], return_dense=True, return_sparse=False, return_colbert_vecs=False)
            emb = out["dense_vecs"][0]
            if emb is not None:
                norm = math.sqrt(sum(float(v) * float(v) for v in emb)) or 1.0
                return [float(v) / norm for v in emb]
        except Exception as e:
            print(f"[RAG] BGE-M3 dense 失败，尝试 GGUF/本地: {e}")

    model = _load_bge_gguf()
    if model is not None:
        try:
            emb = model.create_embedding(text)["data"][0]["embedding"]
            if emb:
                norm = math.sqrt(sum(v * v for v in emb)) or 1.0
                return [v / norm for v in emb]
        except Exception as e:
            print(f"[RAG] BGE-GGUF embedding 失败，回退本地: {e}")
    return _local_embed(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    small = _load_small_embedder()
    if small is not None:
        try:
            embs = small.encode(list(texts), normalize_embeddings=True)
            return [list(map(float, v)) for v in embs]
        except Exception as e:
            print(f"[RAG] 小模型 batch dense 失败，逐个回退: {e}")
    model = _load_bge_m3()
    if model is not None:
        try:
            out = model.encode(list(texts), return_dense=True, return_sparse=False, return_colbert_vecs=False)
            return [list(map(float, v)) for v in out["dense_vecs"]]
        except Exception as e:
            print(f"[RAG] BGE-M3 batch dense 失败，逐个回退: {e}")
    return [embed_text(t) for t in texts]


def sparse_embed(text: str) -> dict[str, float]:
    """返回稀疏向量（词->权重）；BGE-M3 不可用时回退本地词频。"""
    text = str(text or "")
    model = _load_bge_m3()
    if model is not None:
        try:
            out = model.encode([text], return_dense=False, return_sparse=True, return_colbert_vecs=False)
            weights = out.get("lexical_weights", [{}])[0] or {}
            return {str(k): float(v) for k, v in weights.items() if float(v) != 0.0}
        except Exception as e:
            print(f"[RAG] BGE-M3 sparse 失败，回退本地稀疏: {e}")
    return _local_sparse(text)
