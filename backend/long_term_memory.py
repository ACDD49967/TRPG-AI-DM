"""EverOS 风格长期记忆：Markdown 记忆库 + SQLite 检索索引。

Markdown 记忆库（人类可读、可手工编辑、可版本管理）：
    memory_vault/<username>/
        index.md                    # 记忆总览与链接索引
        daily/YYYY-MM-DD.md         # 事件记忆时间线
        episodic/<slug>.md          # 大事件、战斗、重要抉择
        semantic/<slug>.md          # 世界事实、设定、人物关系
        procedural/<slug>.md        # 玩家偏好、桌面约定、推进策略
        thread/<slug>.md            # 跨会话剧情线索/暗线
        reflection/<slug>.md        # AI 对局势的总结与推论

SQLite（data/long_term_memory.db）作为快速检索索引，保存同样的元数据与
向量，用于多因子检索；Markdown 文件始终是长期记忆的权威可读载体。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path("data") / "long_term_memory.db"
VAULT_ROOT = Path("memory_vault")

MEMORY_TYPES = {"episodic", "semantic", "procedural", "thread", "reflection"}
_VAULT_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facts (
            username TEXT NOT NULL,
            fact TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (username, fact)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            memory_type TEXT NOT NULL DEFAULT 'semantic',
            content TEXT NOT NULL,
            summary TEXT DEFAULT '',
            entities TEXT DEFAULT '[]',
            tags TEXT DEFAULT '[]',
            importance REAL DEFAULT 0.5,
            confidence REAL DEFAULT 0.7,
            access_count INTEGER DEFAULT 0,
            last_access TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            session_id TEXT DEFAULT '',
            turn INTEGER DEFAULT 0,
            source TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            embedding TEXT DEFAULT '[]',
            vault_path TEXT DEFAULT ''
        )
        """
    )
    # 旧库迁移：补 vault_path 列
    try:
        conn.execute("ALTER TABLE memories ADD COLUMN vault_path TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_user_type ON memories(username, memory_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_user_updated ON memories(username, updated_at)")
    return conn


# ── Markdown 记忆库 ──────────────────────────────────────────

def _vault_user_dir(username: str) -> Path:
    safe = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]", "_", (username or "default").strip()) or "default"
    return VAULT_ROOT / safe


def _slug(text: str, limit: int = 48) -> str:
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(text or "").strip())
    s = re.sub(r"\s+", "_", s)
    return (s[:limit].strip("_") or "memory")


def _memory_path(username: str, memory_type: str, mem_id: str, content: str) -> Path:
    return _vault_user_dir(username) / memory_type / f"{_slug(content)}_{mem_id}.md"


def _render_page(record: dict[str, Any]) -> str:
    entities = "、".join(record.get("entities") or [])
    tags = "、".join(record.get("tags") or [])
    lines = [
        "---",
        f"id: {record.get('id', '')}",
        f"type: {record.get('memory_type', 'semantic')}",
        f"importance: {record.get('importance', 0.5)}",
        f"confidence: {record.get('confidence', 0.7)}",
        f"entities: [{entities}]",
        f"tags: [{tags}]",
        f"created_at: {record.get('created_at', '')}",
        f"updated_at: {record.get('updated_at', '')}",
        f"access_count: {record.get('access_count', 0)}",
        "---",
        "",
    ]
    summary = str(record.get("summary") or "").strip()
    if summary:
        lines.append(f"# {summary}")
        lines.append("")
    lines.append(str(record.get("content") or "").strip())
    lines.append("")
    return "\n".join(lines)


def _write_page(username: str, record: dict[str, Any]) -> str:
    """把一条记忆写入 Markdown 文件，返回相对路径。"""
    try:
        path = _memory_path(username, record["memory_type"], record["id"], record["content"])
        with _VAULT_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render_page(record), encoding="utf-8")
        return str(path)
    except Exception as e:
        print(f"[MemoryVault] 写入 Markdown 失败: {e}")
        return ""


def _delete_page(vault_path: str) -> None:
    if not vault_path:
        return
    try:
        with _VAULT_LOCK:
            p = Path(vault_path)
            if p.exists():
                p.unlink()
    except Exception:
        pass


def _append_daily(username: str, record: dict[str, Any]) -> None:
    """episodic 记忆追加到 daily/YYYY-MM-DD.md。"""
    if record.get("memory_type") != "episodic":
        return
    try:
        day = datetime.fromisoformat(record.get("created_at") or _now()).strftime("%Y-%m-%d")
        path = _vault_user_dir(username) / "daily" / f"{day}.md"
        with _VAULT_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(f"# {day} 事件时间线\n\n", encoding="utf-8")
            with path.open("a", encoding="utf-8") as f:
                summary = record.get("summary") or record.get("content", "")[:60]
                f.write(f"- [{record.get('id', '')}] {summary}\n")
    except Exception as e:
        print(f"[MemoryVault] 追加 daily 失败: {e}")


def rebuild_index(username: str) -> str:
    """重建 memory_vault/<username>/index.md。"""
    user_dir = _vault_user_dir(username)
    rows: list[tuple[str, str, str, float, str]] = []
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT memory_type, id, COALESCE(summary, ''), importance, vault_path "
            "FROM memories WHERE username=? ORDER BY updated_at DESC LIMIT 1000",
            ((username or "default").strip(),),
        ).fetchall()
    finally:
        conn.close()

    by_type: dict[str, list[tuple]] = {}
    for r in rows:
        by_type.setdefault(r[0], []).append(r)
    lines = [f"# {username or 'default'} 的记忆库", "", f"更新时间：{_now()}", ""]
    for mtype in ("episodic", "semantic", "procedural", "thread", "reflection"):
        items = by_type.get(mtype) or []
        if not items:
            continue
        lines.append(f"## {mtype}（{len(items)}）")
        for _t, mem_id, summary, imp, vpath in items[:200]:
            title = summary or mem_id
            lines.append(f"- [{title}]({vpath or '#'})  `{mem_id}`  重要性 {imp}")
        lines.append("")
    try:
        with _VAULT_LOCK:
            user_dir.mkdir(parents=True, exist_ok=True)
            (user_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
        return str(user_dir / "index.md")
    except Exception as e:
        print(f"[MemoryVault] 重建索引失败: {e}")
        return ""


# ── 基础工具 ─────────────────────────────────────────────────

def _json_list(value: Any) -> str:
    if isinstance(value, str):
        items = [x.strip() for x in re.split(r"[,，、;；]", value) if x.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = [str(x).strip() for x in value if str(x).strip()]
    else:
        items = []
    return json.dumps(list(dict.fromkeys(items)), ensure_ascii=False)


def _loads(value: str | None, default: Any) -> Any:
    try:
        data = json.loads(value or "")
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", "", str(text or "").lower())
    if not cleaned:
        return []
    terms = [cleaned[i:i + 2] for i in range(len(cleaned) - 1)]
    try:
        import jieba
        terms.extend(w for w in jieba.cut(cleaned) if len(w.strip()) > 1)
    except Exception:
        pass
    return terms


def _lexical_score(query_tokens: list[str], content: str) -> float:
    if not query_tokens:
        return 0.0
    c = Counter(_tokenize(content))
    if not c:
        return 0.0
    hit = sum(min(q, c.get(t, 0)) for t, q in Counter(query_tokens).items())
    return hit / (sum(c.values()) ** 0.5 + 1e-6)


def _recency_score(updated_at: str) -> float:
    try:
        dt = datetime.fromisoformat(updated_at)
        days = max(0.0, (datetime.now() - dt).total_seconds() / 86400.0)
    except Exception:
        return 0.5
    return 1.0 / (1.0 + days / 30.0)


def _embed(text: str) -> list[float]:
    try:
        from backend.engine.rag_utils import embed_text
        return embed_text(text)
    except Exception:
        return []


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        from backend.engine.rag_utils import cosine
        return max(0.0, float(cosine(a, b)))
    except Exception:
        return 0.0


def _memory_id(username: str, memory_type: str, content: str) -> str:
    raw = f"{username}|{memory_type}|{content.strip()}"
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


# ── 写入 ─────────────────────────────────────────────────────

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
    memory_type = memory_type if memory_type in MEMORY_TYPES else "semantic"
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

    types = [t for t in (memory_types or []) if t in MEMORY_TYPES]
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
    types = [t for t in (memory_types or []) if t in MEMORY_TYPES]
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


def consolidate_memories(username: str, max_items: int = 500) -> dict[str, int]:
    """合并重复语义记忆，衰减低价值旧记忆，并同步删除 Markdown 页面。"""
    username = (username or "default").strip()
    conn = _conn()
    merged = 0
    forgotten = 0
    removed_paths: list[str] = []
    try:
        rows = conn.execute(
            "SELECT id, memory_type, content, importance, access_count, updated_at, vault_path "
            "FROM memories WHERE username=?",
            (username,),
        ).fetchall()
        groups: dict[tuple[str, str], list] = {}
        for row in rows:
            key = (row[1], re.sub(r"\s+", "", str(row[2] or "").lower()))
            groups.setdefault(key, []).append(row)
        for items in groups.values():
            if len(items) <= 1:
                continue
            items.sort(key=lambda r: (float(r[3] or 0), int(r[4] or 0)), reverse=True)
            keep = items[0]
            remove_ids = [r[0] for r in items[1:]]
            removed_paths.extend([r[6] for r in items[1:] if r[6]])
            conn.executemany("DELETE FROM memories WHERE id=?", [(i,) for i in remove_ids])
            merged += len(remove_ids)
            total_access = sum(int(r[4] or 0) for r in items)
            conn.execute("UPDATE memories SET access_count=? WHERE id=?", (total_access, keep[0]))
        now = datetime.now()
        for row in conn.execute(
            "SELECT id, importance, access_count, updated_at, vault_path FROM memories WHERE username=?",
            (username,),
        ).fetchall():
            try:
                days = (now - datetime.fromisoformat(row[3])).total_seconds() / 86400.0
            except Exception:
                days = 0.0
            imp = float(row[1] or 0.5)
            if days > 30 and int(row[2] or 0) == 0:
                imp *= 0.98
                if imp < 0.05:
                    conn.execute("DELETE FROM memories WHERE id=?", (row[0],))
                    if row[4]:
                        removed_paths.append(row[4])
                    forgotten += 1
                else:
                    conn.execute("UPDATE memories SET importance=? WHERE id=?", (imp, row[0]))
        count = conn.execute("SELECT COUNT(*) FROM memories WHERE username=?", (username,)).fetchone()[0]
        if count > max_items:
            overflow = count - max_items
            old = conn.execute(
                "SELECT id, vault_path FROM memories WHERE username=? "
                "ORDER BY importance ASC, updated_at ASC LIMIT ?",
                (username, overflow),
            ).fetchall()
            conn.executemany("DELETE FROM memories WHERE id=?", [(r[0],) for r in old])
            removed_paths.extend([r[1] for r in old if r[1]])
            forgotten += len(old)
        conn.commit()
    finally:
        conn.close()
    for p in removed_paths:
        _delete_page(p)
    rebuild_index(username)
    return {"merged": merged, "forgotten": forgotten}


# ── 旧版兼容接口 ─────────────────────────────────────────────

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
