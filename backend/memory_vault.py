"""Markdown 记忆库：人类可读的记忆页、每日流水与索引文件。

从 backend/long_term_memory 拆出；那边保留 SQLite 索引与公开 API。
"""
from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

_VAULT_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat()


def _vault_root() -> Path:
    """惰性读取 long_term_memory.VAULT_ROOT：避免 re-export 值拷贝导致改动不生效。"""
    from backend.long_term_memory import VAULT_ROOT
    return VAULT_ROOT

# ── Markdown 记忆库 ──────────────────────────────────────────

def _vault_user_dir(username: str) -> Path:
    safe = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]", "_", (username or "default").strip()) or "default"
    return _vault_root() / safe


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
            marker = f"[{record.get('id', '')}]"
            if marker in path.read_text(encoding="utf-8"):
                return
            with path.open("a", encoding="utf-8") as f:
                summary = record.get("summary") or record.get("content", "")[:60]
                f.write(f"- {marker} {summary}\n")
    except Exception as e:
        print(f"[MemoryVault] 追加 daily 失败: {e}")
