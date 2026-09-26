"""长期记忆：SQLite 快速检索索引 + Markdown 记忆库（memory_vault）。

结构与职责：
- SQLite（`data/long_term_memory.db`）保存元数据与可检索字段；
- Markdown 记忆库（`memory_vault/<user>/`）是人类可读的正文，由 `memory_vault` 负责；
- 本模块只保留**常量、连接与再导出**：`DB_PATH` / `VAULT_ROOT` / `MEMORY_TYPES` / `_conn`
  会被测试与探针替换（`ltm.VAULT_ROOT = tmp`），所以它们必须留在这里；
  写入、检索、索引分别拆到 memory_store / memory_retrieve / memory_index。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path("data") / "long_term_memory.db"
VAULT_ROOT = Path("memory_vault")

MEMORY_TYPES = {"episodic", "semantic", "procedural", "thread", "reflection"}

# Markdown 记忆库与检索打分各有归属模块，这里只做再导出：
# VAULT_ROOT 由 memory_vault._vault_root() 惰性读取，改本模块的常量仍然生效。
from backend.memory_vault import (  # noqa: E402,F401
    _VAULT_LOCK,
    _append_daily,
    _delete_page,
    _memory_path,
    _now,
    _render_page,
    _slug,
    _vault_user_dir,
    _write_page,
)
from backend.memory_scoring import (  # noqa: E402,F401
    _cosine,
    _embed,
    _json_list,
    _lexical_score,
    _loads,
    _memory_id,
    _recency_score,
    _tokenize,
)

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

# 写入 / 检索 / 索引拆出后在这里再导出，既有调用方（session_tools、saves、game_setup…）不变
from backend.memory_store import (  # noqa: E402,F401
    delete_facts, load_facts, store_fact, store_memory,
)
from backend.memory_manage import (  # noqa: E402,F401
    delete_memory, load_memory, update_memory,
)
from backend.memory_retrieve import (  # noqa: E402,F401
    load_recent_memories, retrieve_memories,
)
from backend.memory_index import (  # noqa: E402,F401
    consolidate_memories, rebuild_index,
)
