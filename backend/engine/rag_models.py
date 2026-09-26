"""RAG 模型与全局状态：本地哈希/小模型/BGE-M3/BGE-reranker 的惰性加载、预热与切换。

从 `rag_utils.py` 拆出。**全局模型状态只存在于本模块**（provider、已加载的模型、加载闩锁），
嵌入与相似度计算分别在 rag_embed / rag_rank，`rag_utils.py` 只做再导出。
"""
from __future__ import annotations

import os
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


def warmup_rag(on_stage: Any | None = None):
    """启动时预热：分词、稠密嵌入、重排模型与一次真实检索。

    实测（dist/_probe_live_turn.py）首个回合的检索阶段需要 26.7 秒，第二次只要 0.6 秒：
    成本来自模型首次加载与检索索引/向量首次构建。把这段工作提前到启动阶段，
    玩家第一次行动就不必等模型冷启动。

    on_stage(name, ms) 用于把各阶段耗时上报给后台预热状态。
    """
    def _stage(name: str, fn) -> None:
        import time
        started = time.perf_counter()
        try:
            fn()
        except Exception:
            pass
        finally:
            if on_stage is not None:
                try:
                    on_stage(name, round((time.perf_counter() - started) * 1000, 2))
                except Exception:
                    pass

    def _jieba() -> None:
        import jieba
        jieba.initialize()

    def _dense() -> None:
        from backend.engine.rag_embed import embed_text
        embed_text("预热")

    def _sparse() -> None:
        from backend.engine.rag_embed import sparse_embed
        if sparse_ready():
            sparse_embed("预热")

    def _rerank() -> None:
        _load_reranker()

    def _retrieve() -> None:
        from backend.knowledge_base import get_knowledge_base
        get_knowledge_base().retrieve("预热检索", top_k=1)

    _stage("jieba", _jieba)
    _stage("dense_embedding", _dense)
    _stage("sparse_embedding", _sparse)
    _stage("reranker", _rerank)
    _stage("retrieval_index", _retrieve)


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
