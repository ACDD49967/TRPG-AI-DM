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
    from backend.paths import safe_username
    return EXT_ROOT / safe_username(username)


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
    from backend.paths import validate_resource_id
    path = _user_dir(username) / f"{validate_resource_id(ext_id, '扩展包 ID')}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_extension(username: str, ext_id: str) -> bool:
    from backend.paths import validate_resource_id
    path = _user_dir(username) / f"{validate_resource_id(ext_id, '扩展包 ID')}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def update_extension(username: str, ext_id: str, name: str | None = None,
                     description: str | None = None, content: str | None = None,
                     system: str | None = None,
                     tags: list[str] | None = None) -> dict | None:
    """就地更新扩展包（改名/改描述/改正文；正文变了会重新切块）。"""
    from backend.paths import validate_resource_id
    path = _user_dir(username) / f"{validate_resource_id(ext_id, '扩展包 ID')}.json"
    data = get_extension(username, ext_id)
    if data is None:
        return None
    if name is not None:
        data["name"] = str(name)[:120] or data.get("name", "")
    if description is not None:
        data["description"] = str(description)[:500]
    if system is not None:
        data["system"] = str(system)
    if tags is not None:
        data["tags"] = [str(t) for t in tags]
    if content is not None and str(content) != str(data.get("content", "")):
        data["content"] = str(content)
        data["chunks"] = split_text(str(content), mode="naive", chunk_size=900)
    data["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


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
