"""角色卡管理——租户隔离，支持保存多张角色卡供新游戏复用。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

CHAR_ROOT = Path("characters")


def _user_dir(username: str) -> Path:
    safe = "".join(c for c in (username or "default") if c.isalnum() or c in "._-") or "default"
    return CHAR_ROOT / safe


def _card_path(username: str, card_id: str) -> Path:
    return _user_dir(username) / f"{card_id}.json"


def save_character_card(username: str, card: dict, card_id: str = "") -> dict:
    """保存角色卡；card_id 为空时新建。"""
    user_dir = _user_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat()
    if card_id:
        path = _card_path(username, card_id)
        old = {}
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                old = {}
        card_id = card_id
        created_at = old.get("created_at", now)
    else:
        card_id = uuid.uuid4().hex[:16]
        created_at = now
    payload = {
        "id": card_id,
        "username": username,
        "name": str(card.get("name") or "未命名角色卡"),
        "data": card,
        "created_at": created_at,
        "updated_at": now,
    }
    _card_path(username, card_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def list_character_cards(username: str) -> list[dict]:
    user_dir = _user_dir(username)
    if not user_dir.exists():
        return []
    cards = []
    for p in user_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            cards.append({
                "id": data.get("id", p.stem),
                "name": data.get("name", "未命名角色卡"),
                "character_name": data.get("data", {}).get("character_name", ""),
                "game_system": data.get("data", {}).get("game_system", "dnd5e"),
                "race": data.get("data", {}).get("race", ""),
                "char_class": data.get("data", {}).get("char_class", ""),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            })
        except Exception:
            continue
    cards.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return cards


def get_character_card(username: str, card_id: str) -> dict | None:
    path = _card_path(username, card_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_character_card(username: str, card_id: str) -> bool:
    path = _card_path(username, card_id)
    if path.exists():
        path.unlink()
        return True
    return False
