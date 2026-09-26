"""装备加成：护甲/盾牌 AC 加值与装备变更后的重算。

从 `backend/engine/character_state.py` 拆出；那边只保留 `_exec_update_state` 主处理器并再导出这些名字。
"""
from __future__ import annotations

from backend.engine.session import GameSessionState
from backend.engine.tool_shims import _game_system

_ARMOR_AC_BONUS = {"皮甲": 1, "链甲衫": 3, "鳞甲": 4, "半身板甲": 5, "板甲": 8, "盾牌": 2}

def _equipped_armor_bonus(info: dict, state: GameSessionState | None = None) -> int:
    """计算已装备护甲/盾牌带来的 AC 加值（state 传入时附带特长加值，如双持客 +1）。"""
    inventory = info.get("inventory") or {}
    items = inventory.get("items", []) if isinstance(inventory, dict) else []
    bonus = 0
    for it in items:
        if not isinstance(it, dict) or not it.get("equipped"):
            continue
        props = it.get("properties") or {}
        try:
            bonus += int(props.get("ac_bonus") or 0)
        except (TypeError, ValueError):
            pass
        name = str(it.get("name") or "")
        best = 0
        for key, val in _ARMOR_AC_BONUS.items():
            if key in name and val > best:
                best = val
        bonus += best
    if state is not None and _game_system(state) == "dnd5e":
        from backend.engine.feat_effects import dual_wield_ac_bonus
        bonus += dual_wield_ac_bonus(info)
    return bonus

def _recalc_equipment_effects(state: GameSessionState, applied: dict):
    """根据已装备物品实时重算 AC（D&D 系）。"""
    info = state.character_info
    if _game_system(state) not in ("dnd5e", "dnd4e"):
        return
    current_bonus = _equipped_armor_bonus(info, state)
    if "base_ac" not in info:
        info["base_ac"] = int(info.get("ac") or 10) - current_bonus
    new_ac = int(info.get("base_ac") or 10) + current_bonus
    if new_ac != info.get("ac"):
        info["ac"] = new_ac
        applied["ac"] = new_ac
