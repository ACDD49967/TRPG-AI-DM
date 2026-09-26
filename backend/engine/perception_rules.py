"""察觉类通用计算：熟练加值与被动察觉（玩家 / NPC 共用一份实现）。

陷阱（`trap_rules`）与潜行（`stealth_rules`）都要做"对抗被动察觉"的判定，
算法此前只写在陷阱模块里。抽到中立模块后两处共用，避免两份公式各自漂移；
`trap_rules` 仍然再导出这两个名字，外部 import 面不变。
"""
from __future__ import annotations

from typing import Any


def proficiency_bonus(state: Any) -> int:
    """玩家熟练加值：优先角色卡算好的值，缺了按等级推导。"""
    from backend.engine.rules_5e import get_dnd5_proficiency_bonus

    info = getattr(state, "character_info", {}) or {}
    try:
        bonus = int(info.get("proficiency_bonus") or 0)
    except (TypeError, ValueError):
        bonus = 0
    if bonus:
        return bonus
    try:
        level = int(info.get("level") or 1)
    except (TypeError, ValueError):
        level = 1
    return get_dnd5_proficiency_bonus(level)


def passive_perception(state: Any) -> int:
    """玩家被动察觉：优先角色卡算好的值，缺了按属性 + 察觉熟练补算。"""
    from backend.engine.rules_5e import get_passive_perception

    info = getattr(state, "character_info", {}) or {}
    try:
        cached = int(info.get("passive_perception") or 0)
    except (TypeError, ValueError):
        cached = 0
    if cached > 0:
        return cached
    return int(get_passive_perception(
        info.get("attributes") or {}, proficiency_bonus(state),
        info.get("skill_proficiencies") or []))


def creature_passive_perception(npc: Any) -> int:
    """NPC 被动察觉：感知调整 + 察觉熟练（生物卡缺属性时退回 10）。"""
    from backend.engine.rules_5e import get_dnd5_proficiency_bonus, get_passive_perception

    if npc is None:
        return 10
    try:
        level = int(getattr(npc, "level", 1) or 1)
    except (TypeError, ValueError):
        level = 1
    return int(get_passive_perception(
        getattr(npc, "attributes", None) or {},
        get_dnd5_proficiency_bonus(level),
        list(getattr(npc, "skills", None) or []),
    ))
