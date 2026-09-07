# -*- coding: utf-8 -*-
"""可选 pgvector 向量存储层。

仅当同时满足以下条件时激活：
- settings.ENABLE_PGVECTOR=True
- settings.DATABASE_URL 为 postgresql:// 地址
- 已安装 pgvector Python 包

未激活时所有函数自动 no-op，不影响原有本地 SQLite + 哈希向量检索。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from backend.config import settings
from backend.database import engine


def pgvector_enabled() -> bool:
    try:
        import pgvector  # noqa: F401
    except Exception:
        return False
    url = (settings.DATABASE_URL or "").lower()
    return bool(settings.ENABLE_PGVECTOR and url.startswith("postgresql"))


async def ensure_pgvector_schema() -> None:
    if not pgvector_enabled():
        return
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_vectors (
                id VARCHAR(64) PRIMARY KEY,
                doc_id VARCHAR(64) NOT NULL,
                chunk_id VARCHAR(64) NOT NULL,
                block_type VARCHAR(32) NOT NULL DEFAULT 'text',
                content TEXT NOT NULL,
                vector VECTOR(1024)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_document_vectors_doc "
            "ON document_vectors (doc_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_document_vectors_vec "
            "ON document_vectors USING hnsw (vector vector_cosine_ops)"
        ))


async def add_document_vectors(
    doc_id: str,
    chunks: list[dict],
) -> int:
    """写入 pgvector 文档块向量；未启用时返回 0。"""
    if not pgvector_enabled() or not chunks:
        return 0
    from backend.engine.rag_utils import embed_text
    await ensure_pgvector_schema()
    count = 0
    async with engine.begin() as conn:
        for c in chunks:
            chunk_id = str(c.get("chunk_id") or c.get("id") or "")
            content = str(c.get("content") or "")
            if not chunk_id or not content:
                continue
            vec = embed_text(content)
            vec_str = "[" + ",".join(f"{float(v):.6f}" for v in vec) + "]"
            await conn.execute(text("""
                INSERT INTO document_vectors
                    (id, doc_id, chunk_id, block_type, content, vector)
                VALUES (:id, :doc_id, :chunk_id, :block_type, :content, CAST(:vec AS vector))
                ON CONFLICT (id) DO UPDATE SET
                    block_type = EXCLUDED.block_type,
                    content = EXCLUDED.content,
                    vector = EXCLUDED.vector
            """), {
                "id": f"{doc_id}:{chunk_id}",
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "block_type": str(c.get("block_type") or "text"),
                "content": content,
                "vec": vec_str,
            })
            count += 1
    return count


async def delete_document_vectors(doc_id: str) -> int:
    if not pgvector_enabled():
        return 0
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM document_vectors WHERE doc_id = :doc_id"),
            {"doc_id": doc_id},
        )
        return int(result.rowcount or 0)


async def search_document_vectors(query: str, top_k: int = 10) -> list[dict]:
    """使用 pgvector cosine 距离检索；未启用返回空列表。"""
    if not pgvector_enabled():
        return []
    from backend.engine.rag_utils import embed_text
    await ensure_pgvector_schema()
    vec = embed_text(query)
    vec_str = "[" + ",".join(f"{float(v):.6f}" for v in vec) + "]"
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("""
                SELECT chunk_id, block_type, content,
                       1 - (vector <=> CAST(:vec AS vector)) AS score
                FROM document_vectors
                ORDER BY vector <=> CAST(:vec AS vector)
                LIMIT :top_k
            """),
            {"vec": vec_str, "top_k": int(top_k)},
        )
        return [
            {
                "chunk_id": row.chunk_id,
                "block_type": row.block_type,
                "content": row.content,
                "score": round(float(row.score), 4),
            }
            for row in rows
        ]
