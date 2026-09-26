"""对抗动作的数值：运动 / 杂技加值、体型等级、能否行动。

玩家看角色卡、NPC 看简易卡，两条路的取值口径在 `_sheet` 里统一，
避免"玩家算熟练、NPC 不算"这类只会在实战里暴露的偏差。
"""
from __future__ import annotations

from typing import Any

from backend.engine.condition_apply import has_condition

# 体型等级：目标比行动者大出两级以上就不能擒抱/推撞（5e）
SIZE_ORDER = ("微型", "小型", "中型", "大型", "巨型", "超巨型")
_SIZE_WORDS = {
    0: ("微型", "tiny"),
    1: ("小型", "small"),
    2: ("中型", "medium"),
    3: ("大型", "large"),
    4: ("巨型", "huge"),
    5: ("超巨型", "gargantuan"),
}
_ATHLETICS_WORDS = ("运动", "athletics")
_ACROBATICS_WORDS = ("杂技", "特技", "acrobatics")
# 无法行动（失能/麻痹/震慑/昏迷/石化）：此时对抗检定自动成功
_HELPLESS_WORDS = ("失能", "无力", "incapacitated", "麻痹", "paralyzed", "震慑", "stunned",
                   "昏迷", "unconscious", "石化", "petrified")


def _sheet(state: Any, name: str) -> tuple[dict, list, int]:
    """返回 (属性表, 技能表, 熟练加值)：玩家用角色卡，NPC 用简易卡。"""
    from backend.engine.perception_rules import proficiency_bonus
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, name):
        info = getattr(state, "character_info", {}) or {}
        return (info.get("attributes") or {}, list(info.get("skill_proficiencies") or []),
                proficiency_bonus(state))
    world = getattr(state, "world_state", None)
    npc = world.get_npc(str(name)) if world is not None else None
    if npc is None:
        return {}, [], 0
    from backend.engine.rules_5e import get_dnd5_proficiency_bonus

    try:
        level = int(getattr(npc, "level", 1) or 1)
    except (TypeError, ValueError):
        level = 1
    return (getattr(npc, "attributes", None) or {},
            list(getattr(npc, "skills", None) or []),
            get_dnd5_proficiency_bonus(level))


def _skill_modifier(state: Any, name: str, ability: str, words: tuple[str, ...]) -> int:
    from backend.engine.damage_rules import ability_modifier

    attributes, skills, prof = _sheet(state, name)
    mod = ability_modifier(attributes.get(ability, 10))
    for skill in skills:
        text = str(skill or "").lower()
        if any(word in text for word in words):
            return mod + prof
    return mod


def athletics_modifier(state: Any, name: str) -> int:
    """力量（运动）：擒抱/推撞的进攻方，也是防御方可选的对抗项之一。"""
    return _skill_modifier(state, name, "str", _ATHLETICS_WORDS)


def acrobatics_modifier(state: Any, name: str) -> int:
    """敏捷（杂技）：防御方更擅长翻滚脱身时选它，逃脱擒抱也用它。"""
    return _skill_modifier(state, name, "dex", _ACROBATICS_WORDS)


def defense_modifier(state: Any, name: str, defense: str = "") -> int:
    """防御方加值：明确指定 str/dex 就按指定项；未指定时取更高的那项。"""
    choice = str(defense or "").strip().lower()
    athletics, acrobatics = athletics_modifier(state, name), acrobatics_modifier(state, name)
    if choice in ("str", "力量", "运动", "athletics"):
        return athletics
    if choice in ("dex", "敏捷", "杂技", "acrobatics"):
        return acrobatics
    return max(athletics, acrobatics)


def _size_text(state: Any, name: str) -> str:
    """拼出可用于判体型的文本：NPC 看特性/装备/备注，玩家看种族特性与体型字段。"""
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, name):
        info = getattr(state, "character_info", {}) or {}
        return " ".join(str(x) for x in (
            info.get("size"), info.get("race"), info.get("race_traits"),
            info.get("species_traits"), info.get("feats"),
        ) if x)
    world = getattr(state, "world_state", None)
    npc = world.get_npc(str(name)) if world is not None else None
    if npc is None:
        return ""
    return " ".join(str(x) for x in (
        getattr(npc, "traits", None) or [], getattr(npc, "notes", "") or "",
        getattr(npc, "equipment", None) or [], getattr(npc, "appearance", "") or "",
    ) if x).lower()


def size_index(state: Any, name: str, override: Any = "") -> int:
    """体型等级下标（中型=2）。给了 override 就用它；否则从卡面文本里找。"""
    text = str(override or "").strip().lower()
    if not text:
        text = _size_text(state, name)
    for index in range(len(SIZE_ORDER) - 1, -1, -1):
        if any(word in text for word in _SIZE_WORDS[index]):
            return index
    return 2


def can_action_target(state: Any, actor: str, target: str) -> str:
    """体型限制：目标比行动者大出两级以上时返回拒绝原因，否则空串。"""
    actor_size = size_index(state, actor)
    target_size = size_index(state, target)
    if target_size > actor_size + 1:
        return (f"{target}（{SIZE_ORDER[target_size]}）比 {actor}（{SIZE_ORDER[actor_size]}）"
                f"大出两级以上，擒抱/推撞对这样的目标无效")
    return ""


def is_helpless(state: Any, name: str) -> bool:
    """目标无法行动（失能/麻痹/震慑/昏迷/石化）时为 True——5e 这类对抗自动成功。"""
    return has_condition(state, name, *_HELPLESS_WORDS)
