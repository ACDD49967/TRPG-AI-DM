"""RAG 工具：本地稠密向量（哈希嵌入）+ 可选 BGE-M3（稠密+稀疏）+ BGE-reranker。

- 默认 local：零依赖、零成本、确定性哈希向量。
- 可选 bge：当用户配置 `EMBEDDING_PROVIDER=bge` 且本地存在 BGE-M3 模型目录时使用。
  BGE-M3 同时产出稠密向量与稀疏（lexical weights）向量，召回阶段做混合检索。
- 可选重排：当配置 `BGE_RERANKER_PATH` 且本地存在 BGE-reranker-base 时使用。
- 所有模型均为可选：不会自动下载；缺少配置时自动回退 local。
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from typing import Any, Callable

from backend.config import settings

_DIM = 512

# 全局惰性模型
_bge_m3 = None
_bge_m3_tried = False
_bge_llm = None
_bge_tried = False
_reranker = None
_reranker_tried = False
_current_provider = settings.EMBEDDING_PROVIDER if settings.EMBEDDING_PROVIDER in ("local", "bge") else "local"


def set_provider(mode: str):
    """运行时切换向量生成模式：local | bge（bge 不可用时自动回退 local）。"""
    global _current_provider
    _current_provider = mode if mode in ("local", "bge") else "local"


def get_provider() -> str:
    return _current_provider


def model_ready() -> bool:
    """BGE-M3 模型是否已就绪（目录或旧版 GGUF 文件存在，不加载）。"""
    dir_path = (settings.BGE_M3_DIR or "").strip()
    if dir_path and os.path.isdir(dir_path):
        return True
    path = (settings.BGE_MODEL_PATH or "").strip()
    return bool(path and os.path.exists(path))


def reranker_ready() -> bool:
    """BGE-reranker 模型目录是否已就绪（仅检查路径存在，不加载）。"""
    path = (settings.BGE_RERANKER_PATH or "").strip()
    return bool(path and os.path.exists(path))


def sparse_ready() -> bool:
    """BGE-M3 是否已加载并支持稀疏向量。"""
    return _load_bge_m3() is not None


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


def _load_bge_m3() -> Any | None:
    """惰性加载 BGE-M3 完整模型（FlagEmbedding，支持稠密+稀疏）。"""
    global _bge_m3, _bge_m3_tried
    if _bge_m3_tried:
        return _bge_m3
    _bge_m3_tried = True
    path = (settings.BGE_M3_DIR or "").strip()
    if _current_provider != "bge" or not path or not os.path.isdir(path):
        return None
    try:
        from FlagEmbedding import BGEM3FlagModel
        _bge_m3 = BGEM3FlagModel(path, use_fp16=False)
    except Exception as e:
        print(f"[RAG] BGE-M3 加载失败，回退本地哈希: {e}")
        _bge_m3 = None
    return _bge_m3


def _load_bge_gguf() -> Any | None:
    """惰性加载 BGE-M3 GGUF（通过 llama-cpp-python），仅作为旧版回退。"""
    global _bge_llm, _bge_tried
    if _bge_tried:
        return _bge_llm
    _bge_tried = True
    path = (settings.BGE_MODEL_PATH or "").strip()
    if _current_provider != "bge" or not path or not os.path.exists(path):
        return None
    try:
        from llama_cpp import Llama
        _bge_llm = Llama(
            model_path=path,
            embedding=True,
            n_ctx=4096,
            n_threads=min(8, os.cpu_count() or 2),
            verbose=False,
        )
    except Exception as e:
        print(f"[RAG] BGE-GGUF 加载失败，回退本地哈希: {e}")
        _bge_llm = None
    return _bge_llm


def embed_text(text: str) -> list[float]:
    """返回归一化稠密向量；优先 BGE-M3 完整模型，其次 GGUF，最后本地哈希。"""
    text = str(text or "")
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


def _load_reranker() -> Callable[[str, list[str]], list[float]] | None:
    """惰性加载 BGE-reranker-base；未配置/失败回退 None。"""
    global _reranker, _reranker_tried
    if _reranker_tried:
        return _reranker
    _reranker_tried = True
    path = (settings.BGE_RERANKER_PATH or "").strip()
    if not path or not os.path.exists(path):
        return None
    try:
        from FlagEmbedding import FlagReranker
        model = FlagReranker(path, use_fp16=False)
        def rerank(query: str, texts: list[str]) -> list[float]:
            pairs = [[query, t] for t in texts]
            scores = model.compute_score(pairs, normalize=True)
            if isinstance(scores, float):
                scores = [scores]
            return [float(s) for s in scores]
        _reranker = rerank
    except Exception as e:
        print(f"[RAG] BGE-reranker 加载失败，跳过重排: {e}")
        _reranker = None
    return _reranker


def rerank(query: str, texts: list[str], top_k: int = 5) -> list[tuple[str, float]]:
    """若配置 BGE-reranker 且可加载，则重排；否则原序返回。"""
    fn = _load_reranker()
    if fn is None or not texts:
        return [(t, 0.0) for t in texts[:top_k]]
    try:
        scores = fn(query, texts)
        pairs = sorted(zip(texts, scores), key=lambda x: x[1], reverse=True)
        return pairs[:top_k]
    except Exception as e:
        print(f"[RAG] rerank 失败，按原序返回: {e}")
        return [(t, 0.0) for t in texts[:top_k]]
