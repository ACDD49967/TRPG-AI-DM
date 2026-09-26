"""长期记忆检索：retrieve_memories（混合打分）与 load_recent_memories。

从 `backend/long_term_memory.py` 拆出。
"""
from __future__ import annotations

from typing import Any

from backend.memory_scoring import (
    _cosine, _embed, _lexical_score, _loads, _recency_score, _tokenize,
)
from backend.memory_vault import _now


def _memory_types() -> set:
    """惰性读取 long_term_memory.MEMORY_TYPES，避免 import 环与值拷贝。"""
    from backend.long_term_memory import MEMORY_TYPES
    return MEMORY_TYPES


def _conn():
    """经 long_term_memory 取连接：测试/探针会替换 ltm.DB_PATH，直接 from-import 会失效。"""
    from backend.long_term_memory import _conn as _open
    return _open()


def retrieve_memories(
    username: str,
    query: str,
    *,
    entities: list[str] | None = None,
    memory_types: list[str] | None = None,
    top_k: int = 5,
    touch: bool = True,
) -> list[dict[str, Any]]:
    """多因子检索长期记忆。"""
    username = (username or "default").strip()
    query = (query or "").strip()
    if not query:
        return []

    types = [t for t in (memory_types or []) if t in _memory_types()]
    where = "username=?"
    params: list[Any] = [username]
    if types:
        where += " AND memory_type IN (" + ",".join("?" for _ in types) + ")"
        params.extend(types)

    conn = _conn()
    try:
        rows = conn.execute(
            f"SELECT id, memory_type, content, summary, entities, tags, importance, "
            f"confidence, access_count, updated_at, embedding, vault_path FROM memories "
            f"WHERE {where} ORDER BY updated_at DESC LIMIT 500",
            params,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    q_tokens = _tokenize(query)
    q_vec = _embed(query)
    q_entities = [str(e).strip().lower() for e in (entities or []) if str(e).strip()]
    scored: list[dict[str, Any]] = []
    for (mem_id, mtype, content, summary, ent_json, tag_json, importance,
         confidence, access_count, updated_at, embedding_json, vault_path) in rows:
        dense = _cosine(q_vec, _loads(embedding_json, []))
        text = f"{content} {summary}"
        lexical = _lexical_score(q_tokens, text)
        entity_hit = 0.0
        if q_entities:
            low = text.lower()
            entity_hit = sum(1 for e in q_entities if e in low) / len(q_entities)
        score = (
            0.30 * dense
            + 0.28 * lexical
            + 0.20 * entity_hit
            + 0.08 * _recency_score(updated_at)
            + 0.09 * float(importance or 0.5)
            + 0.05 * float(confidence or 0.7)
        )
        scored.append({
            "id": mem_id,
            "memory_type": mtype,
            "content": content,
            "summary": summary,
            "entities": _loads(ent_json, []),
            "tags": _loads(tag_json, []),
            "importance": float(importance or 0.5),
            "confidence": float(confidence or 0.7),
            "access_count": int(access_count or 0),
            "updated_at": updated_at,
            "vault_path": vault_path,
            "score": round(score, 4),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: max(1, int(top_k))]
    if touch and top:
        now = _now()
        conn = _conn()
        try:
            conn.executemany(
                "UPDATE memories SET access_count=access_count+1, last_access=? WHERE id=?",
                [(now, m["id"]) for m in top],
            )
            conn.commit()
        finally:
            conn.close()
    return top


def load_recent_memories(username: str, limit: int = 20, memory_types: list[str] | None = None) -> list[dict]:
    """按更新时间读取最近长期记忆，供短期记忆图装配。"""
    username = (username or "default").strip()
    types = [t for t in (memory_types or []) if t in _memory_types()]
    where = "username=?"
    params: list[Any] = [username]
    if types:
        where += " AND memory_type IN (" + ",".join("?" for _ in types) + ")"
        params.extend(types)
    conn = _conn()
    try:
        rows = conn.execute(
            f"SELECT id, memory_type, content, summary, entities, tags, importance, "
            f"confidence, access_count, updated_at, vault_path FROM memories WHERE {where} "
            f"ORDER BY updated_at DESC LIMIT ?",
            params + [max(1, int(limit))],
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0], "memory_type": r[1], "content": r[2], "summary": r[3],
            "entities": _loads(r[4], []), "tags": _loads(r[5], []),
            "importance": float(r[6] or 0.5), "confidence": float(r[7] or 0.7),
            "access_count": int(r[8] or 0), "updated_at": r[9],
            "vault_path": r[10],
        }
        for r in rows
    ]
