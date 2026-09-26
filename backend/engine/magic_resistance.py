"""魔法抗性：从特性/装备文本解析“对法术豁免有优势”。"""
from __future__ import annotations

from typing import Any

_MARKERS = (
    "magic resistance", "spell resistance", "魔法抗性", "法术抗性",
    "魔法抵抗", "对法术豁免有优势",
)


def _flatten(value: Any, parts: list[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            parts.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _flatten(item, parts)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _flatten(item, parts)


def has_magic_resistance(*sources: Any) -> bool:
    parts: list[str] = []
    for source in sources:
        _flatten(source, parts)
    text = "\n".join(parts).lower()
    return any(marker.lower() in text for marker in _MARKERS)


def player_magic_resistance(state: Any) -> bool:
    info = getattr(state, "character_info", {}) or {}
    inventory = info.get("inventory")
    items = inventory.get("items") if isinstance(inventory, dict) else inventory
    equipped = [
        item for item in (items or [])
        if isinstance(item, dict) and item.get("equipped")
    ]
    return has_magic_resistance(
        info.get("race_traits"),
        info.get("class_proficiencies"),
        info.get("feats"),
        [item.get("name") for item in equipped],
        [item.get("description") for item in equipped],
    )


def creature_magic_resistance(npc: Any) -> bool:
    return has_magic_resistance(
        getattr(npc, "traits", []) or [],
        getattr(npc, "equipment", []) or [],
        getattr(npc, "notes", "") or "",
    )
