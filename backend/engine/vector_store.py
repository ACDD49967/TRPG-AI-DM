"""可选 PostgreSQL + pgvector 向量存储适配器。

仅当用户配置 `ENABLE_PGVECTOR=true` 且 `DATABASE_URL` 指向 PostgreSQL 时才会尝试使用；
未配置或缺少依赖时所有函数安全返回 None/空结果，不影响本地 SQLite 模式。
"""
from __future__ import annotations

from backend.config import settings

_available = False
_engine = None
_vec_type = None

if settings.ENABLE_PGVECTOR and settings.DATABASE_URL.startswith(("postgresql", "postgres")):
    try:
        from pgvector.sqlalchemy import Vector
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        _engine = create_async_engine(settings.DATABASE_URL, echo=False)
        _vec_type = Vector
        _available = True
    except Exception as e:
        print(f"[VectorStore] pgvector 不可用（忽略）: {e}")


async def init_vector_store():
    """可选：创建 pgvector 扩展与基础表（仅在可用时执行）。"""
    if not _available or _engine is None:
        return False
    try:
        async with _engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS rag_embeddings ("
                " id TEXT PRIMARY KEY,"
                " embedding vector(1024),"
                " meta JSONB"
                ")"
            ))
        return True
    except Exception as e:
        print(f"[VectorStore] pgvector 初始化失败: {e}")
        return False


async def store_embedding(doc_id: str, embedding: list[float], meta: dict):
    """写入一条向量（可选）。"""
    if not _available or _engine is None:
        return False
    try:
        from sqlalchemy import text
        async with _engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO rag_embeddings(id, embedding, meta) VALUES (:id, :emb, :meta) "
                     "ON CONFLICT(id) DO UPDATE SET embedding=excluded.embedding, meta=excluded.meta"),
                {"id": doc_id, "emb": embedding, "meta": meta},
            )
        return True
    except Exception as e:
        print(f"[VectorStore] 写入失败: {e}")
        return False


async def query_embeddings(embedding: list[float], top_k: int = 5):
    """按余弦相似度查询（可选）。"""
    if not _available or _engine is None:
        return []
    try:
        from sqlalchemy import text
        async with _engine.begin() as conn:
            rows = await conn.execute(
                text("SELECT id, meta, 1 - (embedding <=> :emb) AS score "
                     "FROM rag_embeddings ORDER BY embedding <=> :emb LIMIT :top"),
                {"emb": embedding, "top": top_k},
            )
            return [dict(r._mapping) for r in rows.fetchall()]
    except Exception as e:
        print(f"[VectorStore] 查询失败: {e}")
        return []
