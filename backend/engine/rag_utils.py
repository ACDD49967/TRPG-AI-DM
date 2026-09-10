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
_small_embedder = None
_small_embedder_tried = False
_reranker = None
_reranker_tried = False
_current_provider = settings.EMBEDDING_PROVIDER if settings.EMBEDDING_PROVIDER in ("local", "small", "bge") else "local"


def warmup_rag():
    """启动时预热：初始化 jieba 与重排模型，避免每次对话首次调用时重复加载日志。"""
    try:
        import jieba
        # 初始化分词器；若缓存缺失会构建一次，后续不再重复
        jieba.initialize()
    except Exception:
        pass
    try:
        # 重排模型若本地存在则预热，避免对话中首次加载 201/201 权重
        _load_reranker()
    except Exception:
        pass


def set_provider(mode: str):
    """运行时切换向量生成模式：local | small | bge（模型不可用时自动回退 local）。"""
    global _current_provider, _bge_m3, _bge_llm, _small_embedder, _reranker
    global _bge_m3_tried, _bge_tried, _small_embedder_tried, _reranker_tried
    _current_provider = mode if mode in ("local", "small", "bge") else "local"
    # 重置惰性加载闩锁，使运行期切换 provider 能立即重新尝试加载
    _bge_m3_tried = False
    _bge_tried = False
    _small_embedder_tried = False
    _reranker_tried = False
    _bge_m3 = None
    _bge_llm = None
    _small_embedder = None
    _reranker = None


def get_provider() -> str:
    return _current_provider


def model_ready() -> bool:
    """任一向量模型是否已就绪（小模型 / BGE-M3 / 旧版 GGUF，仅检查路径）。"""
    small_dir = (settings.SMALL_EMBEDDING_DIR or "").strip()
    if small_dir and os.path.isdir(small_dir):
        return True
    dir_path = (settings.BGE_M3_DIR or "").strip()
    if dir_path and os.path.isdir(dir_path):
        return True
    path = (settings.BGE_MODEL_PATH or "").strip()
    return bool(path and os.path.exists(path))


def reranker_ready() -> bool:
    """重排模型是否已就绪（小模型重排 / BGE-reranker，仅检查路径）。"""
    small_path = (settings.SMALL_RERANKER_DIR or "").strip()
    if small_path and os.path.exists(small_path):
        return True
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
    path = (settings.BGE_M3_DIR or "").strip()
    if _current_provider != "bge" or not path or not os.path.isdir(path):
        return None
    if _bge_m3_tried:
        return _bge_m3
    _bge_m3_tried = True
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
    path = (settings.BGE_MODEL_PATH or "").strip()
    if _current_provider != "bge" or not path or not os.path.exists(path):
        return None
    if _bge_tried:
        return _bge_llm
    _bge_tried = True
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


def _load_small_embedder() -> Any | None:
    """惰性加载小中文向量模型（sentence-transformers，如 m3e-small）。"""
    global _small_embedder, _small_embedder_tried
    path = (settings.SMALL_EMBEDDING_DIR or "").strip()
    if _current_provider != "small" or not path or not os.path.isdir(path):
        return None
    if _small_embedder_tried:
        return _small_embedder
    _small_embedder_tried = True
    try:
        from sentence_transformers import SentenceTransformer
        _small_embedder = SentenceTransformer(path)
    except Exception as e:
        print(f"[RAG] 小模型加载失败，回退本地哈希: {e}")
        _small_embedder = None
    return _small_embedder


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
    path = (settings.SMALL_RERANKER_DIR or "").strip() if _current_provider == "small" else ""
    if not path or not os.path.exists(path):
        path = (settings.BGE_RERANKER_PATH or "").strip()
    if not path or not os.path.exists(path):
        return None
    if _reranker_tried:
        return _reranker
    _reranker_tried = True
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
