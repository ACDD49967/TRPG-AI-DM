"""RAG 工具：本地哈希嵌入 + 可选 BGE-M3（稠密+稀疏）+ BGE-reranker。

- 默认 local：零依赖、零成本、确定性哈希向量。
- 可选 bge：配置 `EMBEDDING_PROVIDER=bge` 且本地有 BGE-M3 目录时启用混合检索。
- 可选重排：配置 `BGE_RERANKER_PATH` 且本地有 BGE-reranker-base 时启用。
- 所有模型均为可选：不会自动下载；缺少配置时自动回退 local。

按职责拆成三段，这里只做再导出，既有 `from backend.engine.rag_utils import ...` 全部照旧：
- `rag_models`：模型惰性加载、预热、provider 状态（全局状态只此一份）
- `rag_embed`：分词、本地稠密/稀疏、embed_text(s)/sparse_embed
- `rag_rank`：cosine / sparse_cosine / rerank(_or_none)
"""
from backend.engine.rag_models import (  # noqa: F401
    _DIM, _load_bge_gguf, _load_bge_m3, _load_reranker, _load_small_embedder,
    get_provider, model_ready, reranker_ready, set_provider, sparse_ready, warmup_rag,
)
from backend.engine.rag_embed import (  # noqa: F401
    _bucket, _local_embed, _local_sparse, _tokens, embed_text, embed_texts, sparse_embed,
)
from backend.engine.rag_rank import (  # noqa: F401
    cosine, rerank, rerank_or_none, sparse_cosine,
)
