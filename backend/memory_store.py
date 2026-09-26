"""长期记忆写入：store_memory / store_fact / load_facts / delete_facts。

从 `backend/long_term_memory.py` 拆出；写完会调用 memory_index.rebuild_index 刷新索引。
"""
from __future__ import annotations

import json

from backend.memory_index import rebuild_index
from backend.memory_scoring import _embed, _json_list, _memory_id
from backend.memory_vault import _append_daily, _delete_page, _now, _write_page


def _memory_types() -> set:
    """惰性读取 long_term_memory.MEMORY_TYPES，避免 import 环与值拷贝。"""
    from backend.long_term_memory import MEMORY_TYPES
    return MEMORY_TYPES


def _conn():
    """经 long_term_memory 取连接：测试/探针会替换 ltm.DB_PATH，直接 from-import 会失效。"""
    from backend.long_term_memory import _conn as _open
    return _open()


def store_memory(
    username: str,
    content: str,
    *,
    memory_type: str = "semantic",
    summary: str = "",
    entities: list[str] | None = None,
    tags: list[str] | None = None,
    importance: float = 0.5,
    confidence: float = 0.7,
    session_id: str = "",
    turn: int = 0,
    source: str = "",
    metadata: dict | None = None,
) -> str:
    """写入/强化一条长期记忆，并同步 Markdown 记忆页。"""
    username = (username or "default").strip()
    content = (content or "").strip()
    if not content:
        return ""
    memory_type = memory_type if memory_type in _memory_types() else "semantic"
    mem_id = _memory_id(username, memory_type, content)
    now = _now()
    record = {
        "id": mem_id,
        "username": username,
        "memory_type": memory_type,
        "content": content,
        "summary": (summary or "").strip(),
        "entities": list(dict.fromkeys([str(x).strip() for x in (entities or []) if str(x).strip()])),
        "tags": list(dict.fromkeys([str(x).strip() for x in (tags or []) if str(x).strip()])),
        "importance": max(0.0, min(1.0, float(importance))),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "access_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    vault_path = _write_page(username, record)
    _append_daily(username, record)

    conn = _conn()
    try:
        conn.execute(
            """
            INSERT INTO memories
                (id, username, memory_type, content, summary, entities, tags,
                 importance, confidence, access_count, last_access, created_at,
                 updated_at, session_id, turn, source, metadata, embedding, vault_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                summary = CASE WHEN excluded.summary != '' THEN excluded.summary ELSE memories.summary END,
                entities = CASE WHEN excluded.entities != '[]' THEN excluded.entities ELSE memories.entities END,
                tags = CASE WHEN excluded.tags != '[]' THEN excluded.tags ELSE memories.tags END,
                importance = MAX(memories.importance, excluded.importance),
                confidence = MAX(memories.confidence, excluded.confidence),
                updated_at = excluded.updated_at,
                session_id = CASE WHEN excluded.session_id != '' THEN excluded.session_id ELSE memories.session_id END,
                turn = CASE WHEN excluded.turn != 0 THEN excluded.turn ELSE memories.turn END,
                source = CASE WHEN excluded.source != '' THEN excluded.source ELSE memories.source END,
                metadata = CASE WHEN excluded.metadata != '{}' THEN excluded.metadata ELSE memories.metadata END,
                embedding = CASE WHEN excluded.embedding != '[]' THEN excluded.embedding ELSE memories.embedding END,
                vault_path = CASE WHEN excluded.vault_path != '' THEN excluded.vault_path ELSE memories.vault_path END
            """,
            (
                mem_id, username, memory_type, content, record["summary"],
                _json_list(record["entities"]), _json_list(record["tags"]),
                record["importance"], record["confidence"], now, now,
                session_id, int(turn or 0), source,
                json.dumps(metadata or {}, ensure_ascii=False),
                json.dumps(_embed(content), ensure_ascii=False),
                vault_path,
            ),
        )
        if memory_type == "semantic":
            conn.execute(
                "INSERT INTO facts(username, fact, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(username, fact) DO UPDATE SET updated_at=excluded.updated_at",
                (username, content, now),
            )
        conn.commit()
    finally:
        conn.close()
    rebuild_index(username)
    return mem_id


# ── 检索 ─────────────────────────────────────────────────────


def store_fact(username: str, fact: str):
    """写入/更新一条长期事实（按用户名隔离）。"""
    store_memory(username, fact, memory_type="semantic", importance=0.6,
                 confidence=0.8, source="legacy_fact")


def load_facts(username: str, limit: int = 100) -> list[str]:
    """读取该用户的长期语义事实（兼容旧接口）。"""
    username = (username or "default").strip()
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT content FROM memories WHERE username=? AND memory_type='semantic' "
            "ORDER BY updated_at DESC LIMIT ?",
            (username, max(1, int(limit))),
        ).fetchall()
        facts = [r[0] for r in rows]
        if len(facts) < limit:
            legacy = conn.execute(
                "SELECT fact FROM facts WHERE username=? ORDER BY updated_at DESC LIMIT ?",
                (username, max(1, int(limit) - len(facts))),
            ).fetchall()
            facts.extend(r[0] for r in legacy)
    finally:
        conn.close()
    return list(dict.fromkeys(facts))[:limit]


def delete_facts(username: str, facts: list[str]):
    """删除指定事实（同时清理 memories 与 Markdown 页面）。"""
    if not facts:
        return
    username = (username or "default").strip()
    conn = _conn()
    paths: list[str] = []
    try:
        for f in facts:
            rows = conn.execute(
                "SELECT vault_path FROM memories WHERE username=? AND memory_type='semantic' AND content=?",
                (username, f),
            ).fetchall()
            paths.extend([r[0] for r in rows if r[0]])
        conn.executemany(
            "DELETE FROM facts WHERE username=? AND fact=?",
            [(username, f) for f in facts],
        )
        conn.executemany(
            "DELETE FROM memories WHERE username=? AND memory_type='semantic' AND content=?",
            [(username, f) for f in facts],
        )
        conn.commit()
    finally:
        conn.close()
    for p in paths:
        _delete_page(p)
    rebuild_index(username)
