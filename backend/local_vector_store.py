# -*- coding: utf-8 -*-
"""内置本地向量存储（SQLite）。

选型说明：
- 本应用定位：单机/局域网跑团工具，SQLite + JSON 已足够；
- 本地向量存储无需额外服务、无需 Docker/PostgreSQL，部署成本最低；
- 对 512 维本地向量 / 1024 维 BGE 向量均可持久化，避免每次重启后重新 embedding；
- 如果未来需要多人并发、海量知识库、向量检索大规模扩展，再切换到 pgvector。

存储位置：
    knowledge_base/vectors.sqlite3
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

VECTOR_DB = Path("knowledge_base/vectors.sqlite3")
_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    VECTOR_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(VECTOR_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_vectors (
            provider TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content_md5 TEXT NOT NULL,
            block_type TEXT NOT NULL DEFAULT 'text',
            dense TEXT,
            sparse TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (provider, doc_id, chunk_index, content_md5)
        )
    """)
    return conn


def save_vector(
    provider: str,
    doc_id: str,
    chunk_index: int,
    content_md5: str,
    dense: list[float] | None,
    sparse: dict[str, float] | None,
    block_type: str = "text",
) -> None:
    with _LOCK:
        conn = _conn()
        try:
            conn.execute(
                """
                INSERT INTO document_vectors
                    (provider, doc_id, chunk_index, content_md5, block_type, dense, sparse, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(provider, doc_id, chunk_index, content_md5) DO UPDATE SET
                    block_type = excluded.block_type,
                    dense = COALESCE(excluded.dense, document_vectors.dense),
                    sparse = COALESCE(excluded.sparse, document_vectors.sparse),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    provider, doc_id, chunk_index, content_md5, block_type,
                    json.dumps(dense, ensure_ascii=False) if dense is not None else None,
                    json.dumps(sparse, ensure_ascii=False) if sparse is not None else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def save_vectors_batch(
    provider: str,
    items: list[dict[str, Any]],
    block_type: str = "text",
) -> int:
    """批量写入向量，单连接单事务提交；items 元素：
    {doc_id, chunk_index, content_md5, dense, sparse}
    """
    if not items:
        return 0
    with _LOCK:
        conn = _conn()
        try:
            for it in items:
                conn.execute(
                    """
                    INSERT INTO document_vectors
                        (provider, doc_id, chunk_index, content_md5, block_type, dense, sparse, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(provider, doc_id, chunk_index, content_md5) DO UPDATE SET
                        block_type = excluded.block_type,
                        dense = COALESCE(excluded.dense, document_vectors.dense),
                        sparse = COALESCE(excluded.sparse, document_vectors.sparse),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        provider,
                        str(it.get("doc_id", "")),
                        int(it.get("chunk_index", 0) or 0),
                        str(it.get("content_md5", "")),
                        str(it.get("block_type") or block_type),
                        json.dumps(it.get("dense"), ensure_ascii=False) if it.get("dense") is not None else None,
                        json.dumps(it.get("sparse"), ensure_ascii=False) if it.get("sparse") is not None else None,
                    ),
                )
            conn.commit()
            return len(items)
        finally:
            conn.close()


def load_vector(
    provider: str,
    doc_id: str,
    chunk_index: int,
    content_md5: str,
) -> tuple[list[float] | None, dict[str, float] | None] | None:
    with _LOCK:
        conn = _conn()
        try:
            row = conn.execute(
                """
                SELECT dense, sparse FROM document_vectors
                WHERE provider=? AND doc_id=? AND chunk_index=? AND content_md5=?
                """,
                (provider, doc_id, chunk_index, content_md5),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    dense = json.loads(row[0]) if row[0] else None
    sparse = json.loads(row[1]) if row[1] else None
    return dense, sparse


def delete_doc_vectors(doc_id: str) -> int:
    with _LOCK:
        conn = _conn()
        try:
            cur = conn.execute("DELETE FROM document_vectors WHERE doc_id=?", (doc_id,))
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()


def vector_stats() -> dict[str, Any]:
    with _LOCK:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(dense,''))+LENGTH(COALESCE(sparse,''))),0) FROM document_vectors"
            ).fetchone()
        finally:
            conn.close()
    return {"count": int(row[0] or 0), "approx_bytes": int(row[1] or 0)}
