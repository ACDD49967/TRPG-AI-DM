"""生物豁免加值推导：卡面直接给的值 → 4e 四类防御 → 属性 + 熟练。

从 `damage_rules` 拆出（那边再导出，`concentration` / `undead_fortitude` /
`condition_rules` 等既有 import 不变）。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.damage_types import _collect_text

_ABILITY_KEYS = {
    "str": ("力量", "str", "strength"),
    "dex": ("敏捷", "dex", "dexterity"),
    "con": ("体质", "con", "constitution"),
    "int": ("智力", "int", "intelligence"),
    "wis": ("感知", "wis", "wisdom"),
    "cha": ("魅力", "cha", "charisma"),
}

# 4e 的防御类型（没有逐属性豁免时的回退）
_FOUR_E_DEFENSE = {"dex": "反射", "con": "强韧", "wis": "意志"}


def ability_modifier(score: int) -> int:
    return (int(score or 10) - 10) // 2


def creature_save_modifier(entity: Any, stats: dict | None, ability: str) -> tuple[int, str]:
    """返回生物的豁免加值 (modifier, 来源说明)。"""
    stats = stats or {}
    ability = str(ability or "dex").lower()
    names = _ABILITY_KEYS.get(ability, (ability,))
    text = _collect_text(entity)

    # 1) 卡面直接给的豁免加值（"敏捷豁免 +4" / "Dex Save +4"）
    for name in names:
        pattern = rf"{re.escape(name)}\s*(?:豁免|save)\s*[:：]?\s*([+-]?\d+)"
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1)), "卡面豁免"

    # 2) 4e 的四类防御
    four_e_key = _FOUR_E_DEFENSE.get(ability)
    if four_e_key and four_e_key in stats:
        try:
            return int(str(stats[four_e_key]).split()[0]), f"4e {four_e_key}"
        except (ValueError, IndexError):
            pass

    # 3) 属性推导：属性调整值 + 熟练加值（等级越高加值越大）
    score = None
    for name in names:
        if name in stats:
            try:
                score = int(str(stats[name]).split()[0])
                break
            except (ValueError, IndexError):
                continue
    if score is None:
        attrs = getattr(entity, "attributes", None) or {}
        if isinstance(attrs, dict):
            score = attrs.get(ability)
    if score is None:
        score = 10
    try:
        level = int(getattr(entity, "level", 0) or stats.get("等级") or stats.get("挑战等级") or 1)
    except (TypeError, ValueError):
        level = 1
    prof = 2 + max(0, level - 1) // 4
    return ability_modifier(score) + prof, "属性推导"
