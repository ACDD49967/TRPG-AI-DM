"""长期记忆索引：重建 Markdown 索引、把 SQLite 记录合并去重（consolidate）。

从 `backend/long_term_memory.py` 拆出；连接仍经原模块获取（DB_PATH 常被测试替换）。
"""
from __future__ import annotations

import re
from datetime import datetime

from backend.memory_vault import _VAULT_LOCK, _delete_page, _now, _vault_user_dir


def _conn():
    """经 long_term_memory 取连接：测试/探针会替换 ltm.DB_PATH，直接 from-import 会失效。"""
    from backend.long_term_memory import _conn as _open
    return _open()


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



# ── 写入 ─────────────────────────────────────────────────────


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
