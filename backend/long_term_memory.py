"""SQLite 长期记忆存储——按 username 租户隔离，用于跨存档复用世界事实。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("data") / "long_term_memory.db"


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
    return conn


def store_fact(username: str, fact: str):
    """写入/更新一条长期事实（按用户名隔离）。"""
    username = username or "default"
    fact = fact.strip()
    if not fact:
        return
    from datetime import datetime
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO facts(username, fact, updated_at) VALUES(?, ?, ?) "
            "ON CONFLICT(username, fact) DO UPDATE SET updated_at=excluded.updated_at",
            (username, fact, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def load_facts(username: str, limit: int = 100) -> list[str]:
    """读取该用户的长期事实。"""
    username = username or "default"
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT fact FROM facts WHERE username=? ORDER BY updated_at DESC LIMIT ?",
            (username, limit),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def delete_facts(username: str, facts: list[str]):
    """删除指定事实。"""
    if not facts:
        return
    username = username or "default"
    conn = _conn()
    try:
        conn.executemany(
            "DELETE FROM facts WHERE username=? AND fact=?",
            [(username, f) for f in facts],
        )
        conn.commit()
    finally:
        conn.close()
