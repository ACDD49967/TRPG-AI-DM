"""扩展包管理——租户隔离，支持用户添加或 LLM 生成扩展包。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.scenario_importer import split_text

EXT_ROOT = Path("extensions")


def _user_dir(username: str) -> Path:
    safe = "".join(c for c in (username or "default") if c.isalnum() or c in "._-") or "default"
    return EXT_ROOT / safe


def list_extensions(username: str) -> list[dict]:
    user_dir = _user_dir(username)
    if not user_dir.exists():
        return []
    items = []
    for p in user_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            items.append({
                "id": data.get("id", p.stem),
                "name": data.get("name", "未命名扩展包"),
                "description": data.get("description", ""),
                "system": data.get("system", "custom"),
                "tags": data.get("tags", []),
                "source": data.get("source", "user"),
                "created_at": data.get("created_at", ""),
            })
        except Exception:
            continue
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


def add_extension(username: str, name: str, description: str, content: str,
                  system: str = "custom", tags: list[str] | None = None,
                  source: str = "user") -> dict:
    user_dir = _user_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    ext_id = uuid.uuid4().hex[:16]
    payload = {
        "id": ext_id,
        "name": name or "未命名扩展包",
        "description": description or "",
        "content": content,
        "system": system,
        "tags": tags or [],
        "source": source,
        "created_at": datetime.now().isoformat(),
        "chunks": split_text(content, mode="naive", chunk_size=900),
    }
    path = user_dir / f"{ext_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_extension(username: str, ext_id: str) -> dict | None:
    path = _user_dir(username) / f"{ext_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_extension(username: str, ext_id: str) -> bool:
    path = _user_dir(username) / f"{ext_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def activate_extensions_into_kb(username: str, extension_ids: list[str]):
    """将启用的扩展包内容写入知识库（幂等），供 RAG 检索。"""
    from backend.knowledge_base import get_knowledge_base
    kb = get_knowledge_base()
    for ext_id in extension_ids:
        ext = get_extension(username, ext_id)
        if not ext:
            continue
        source = f"extension:{ext_id}"
        for d in kb.list_documents(username):
            if d.get("source") == source:
                kb.remove_document(d["id"], username)
        kb.add_document(
            title=f"扩展包：{ext.get('name','')}",
            content=ext.get("content", ""),
            source=source,
            system=ext.get("system", "custom"),
            tags=["扩展包"] + ext.get("tags", []),
            username=username,
        )
