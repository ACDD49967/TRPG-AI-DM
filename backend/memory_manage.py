"""长期记忆的读一条 / 改 / 删（写入与检索分别在 memory_store / memory_retrieve）。

`id` 是内容哈希，所以"改正文"等于删旧写新——调用方拿到新 id 后要按它刷新。
删除要同时清 SQLite 行、Markdown 记忆页与语义事实，否则检索还能召回已删内容。
"""
from __future__ import annotations

from backend.memory_index import rebuild_index
from backend.memory_scoring import _loads
from backend.memory_store import _conn, store_memory
from backend.memory_vault import _delete_page

_COLUMNS = ("id, memory_type, content, summary, entities, tags, importance, "
            "confidence, access_count, created_at, updated_at, session_id, turn, "
            "source, vault_path")


def _row_to_dict(row) -> dict:
    return {
        "id": row[0], "memory_type": row[1], "content": row[2], "summary": row[3],
        "entities": _loads(row[4], []) if isinstance(row[4], str) else (row[4] or []),
        "tags": _loads(row[5], []) if isinstance(row[5], str) else (row[5] or []),
        "importance": row[6], "confidence": row[7], "access_count": row[8],
        "created_at": row[9], "updated_at": row[10], "session_id": row[11],
        "turn": row[12], "source": row[13], "vault_path": row[14],
    }


def load_memory(username: str, mem_id: str) -> dict | None:
    """按 id 读一条长期记忆（含 Markdown 页面路径）；不存在返回 None。"""
    username = (username or "default").strip()
    mem_id = str(mem_id or "").strip()
    if not mem_id:
        return None
    conn = _conn()
    try:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM memories WHERE username=? AND id=?",
            (username, mem_id)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(row) if row is not None else None


def delete_memory(username: str, mem_id: str) -> bool:
    """按 id 删一条记忆：SQLite 行 + Markdown 页面 + 语义 fact，最后重建索引。

    这是"删错记忆"的唯一收口：以前只有按正文匹配的 `delete_facts`，
    且没有任何工具或接口调用它——玩家和 DM 都删不掉一条记错的记忆。
    """
    username = (username or "default").strip()
    mem_id = str(mem_id or "").strip()
    if not mem_id:
        return False
    conn = _conn()
    vault_path = ""
    try:
        row = conn.execute(
            "SELECT vault_path, content, memory_type FROM memories WHERE username=? AND id=?",
            (username, mem_id)).fetchone()
        if row is None:
            return False
        vault_path = str(row[0] or "")
        content = str(row[1] or "")
        memory_type = str(row[2] or "")
        conn.execute("DELETE FROM memories WHERE username=? AND id=?", (username, mem_id))
        if memory_type == "semantic" and content:
            conn.execute("DELETE FROM facts WHERE username=? AND fact=?", (username, content))
        conn.commit()
    finally:
        conn.close()
    if vault_path:
        _delete_page(vault_path)
    rebuild_index(username)
    return True


def update_memory(username: str, mem_id: str, *, content: str | None = None,
                  summary: str | None = None, memory_type: str | None = None,
                  importance: float | None = None, confidence: float | None = None,
                  tags: list[str] | None = None, entities: list[str] | None = None) -> dict | None:
    """改一条记忆；返回**新**记忆（id 随正文变化）。找不到或新正文为空时返回 None。"""
    username = (username or "default").strip()
    old = load_memory(username, mem_id)
    if old is None:
        return None
    new_content = str(content if content is not None else old.get("content") or "").strip()
    if not new_content:
        return None
    unchanged = (new_content == (old.get("content") or "")
                 and all(x is None for x in (summary, memory_type, importance, confidence,
                                             tags, entities)))
    if unchanged:
        return old
    if not delete_memory(username, mem_id):
        return None
    new_id = store_memory(
        username, new_content,
        memory_type=memory_type or old.get("memory_type") or "semantic",
        summary=summary if summary is not None else (old.get("summary") or ""),
        entities=entities if entities is not None else list(old.get("entities") or []),
        tags=tags if tags is not None else list(old.get("tags") or []),
        importance=importance if importance is not None else float(old.get("importance") or 0.5),
        confidence=confidence if confidence is not None else float(old.get("confidence") or 0.7),
        session_id=str(old.get("session_id") or ""),
        turn=int(old.get("turn") or 0),
        source=str(old.get("source") or ""),
    )
    return load_memory(username, new_id) if new_id else None
