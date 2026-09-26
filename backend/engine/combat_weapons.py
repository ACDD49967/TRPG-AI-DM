"""武器辅助：从背包解析武器伤害骰、已装备武器名与玩家攻击加值。

从 `backend/engine/combat.py` 拆出；那边保留四个规则处理器并再导出这些名字。
"""
from __future__ import annotations

from backend.engine.combat_targets import _first_dice
from backend.engine.session import GameSessionState


from typing import Any

def _weapon_dice_from_inventory(state: GameSessionState) -> str:
    items = (state.character_info.get("inventory") or {}).get("items", []) \
        if isinstance(state.character_info.get("inventory"), dict) else []
    dice_map = {"巨斧": "1d12", "长戟": "1d10", "长剑": "1d8", "战斧": "1d8",
                "细剑": "1d8", "短弓": "1d6", "短剑": "1d6", "短棍": "1d6",
                "硬头锤": "1d6", "手斧": "1d6", "轻弩": "1d8", "长弓": "1d8",
                "短弯刀": "1d6", "飞镖": "1d4", "小刀": "1d4"}
    def find(only_equipped: bool):
        for item in items:
            if only_equipped and not (isinstance(item, dict) and item.get("equipped")):
                continue
            name = item.get("name") if isinstance(item, dict) else str(item)
            for key, dice in dice_map.items():
                if key in name:
                    desc = item.get("description") if isinstance(item, dict) else ""
                    return _first_dice(desc) or dice
        return None
    equipped_dice = find(True)
    if equipped_dice:
        return equipped_dice
    return find(False) or "1d8"

def _equipped_weapon_name(state: GameSessionState) -> str:
    """取已装备武器的名字（用于推断物理伤害类型；没有装备标记时取第一件武器名的物品）。"""
    inventory = state.character_info.get("inventory")
    items = inventory.get("items", []) if isinstance(inventory, dict) else []
    weapon_keys = ("巨斧", "长戟", "长剑", "战斧", "细剑", "短弓", "短剑", "短棍",
                   "硬头锤", "手斧", "轻弩", "长弓", "短弯刀", "弯刀", "飞镖", "小刀", "匕首")
    fallback = ""
    for item in items:
        name = item.get("name") if isinstance(item, dict) else str(item)
        if not any(key in str(name) for key in weapon_keys):
            continue
        if isinstance(item, dict) and item.get("equipped"):
            return str(name)
        fallback = fallback or str(name)
    return fallback

def _player_attack_bonus(state: GameSessionState, action: str) -> int:
    info = state.character_info
    attrs = info.get("attributes", {})
    prof = int(info.get("proficiency_bonus") or (2 + (int(info.get("level", 1)) - 1) // 4))
    cc = info.get("char_class", "战士")
    action_lower = (action or "").lower()
    inv_items = (info.get("inventory") or {}).get("items", []) if isinstance(info.get("inventory"), dict) else []
    finesse = any(
        (item.get("name") if isinstance(item, dict) else str(item)) in ("细剑", "短剑", "匕首")
        for item in inv_items
    )
    if any(w in action_lower for w in ("弓", "弩", "投掷", "远程", "射击", "射")):
        attr = "dex"
    elif cc in ("武僧", "游荡者") or finesse:
        attr = "dex"
    else:
        attr = "str"
    return ((attrs.get(attr, 10) or 10) - 10) // 2 + prof
