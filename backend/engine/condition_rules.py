"""条件免疫：从结构化字段与特性文本解析免疫，供玩家/NPC 状态写入拦截。"""
from __future__ import annotations

import random
import re
from typing import Any

_ALIASES: dict[str, tuple[str, ...]] = {
    "blinded": ("blinded", "目盲", "失明"),
    "charmed": ("charmed", "魅惑"),
    "deafened": ("deafened", "耳聋"),
    "exhaustion": ("exhaustion", "力竭"),
    "frightened": ("frightened", "恐惧", "害怕"),
    "grappled": ("grappled", "擒抱"),
    "incapacitated": ("incapacitated", "失能", "无力"),
    "invisible": ("invisible", "隐形"),
    "paralyzed": ("paralyzed", "麻痹"),
    "petrified": ("petrified", "石化"),
    "poisoned": ("poisoned", "中毒"),
    "prone": ("prone", "俯卧", "倒地"),
    "restrained": ("restrained", "束缚"),
    "stunned": ("stunned", "震慑"),
    "unconscious": ("unconscious", "昏迷", "失去意识"),
}
_MARKERS = ("condition immunities", "状态免疫", "免疫", "不受", "不会被", "不惧")


def canonical_condition(name: Any) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    for key, aliases in _ALIASES.items():
        if text in aliases or any(alias in text for alias in aliases):
            return key
    return ""


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


def parse_condition_immunities(*sources: Any) -> set[str]:
    """从文本/结构化来源解析免疫条件；必须出现“免疫/不受/不惧”等标记。"""
    parts: list[str] = []
    for source in sources:
        _flatten(source, parts)
    text = "\n".join(parts).lower()
    if not text or not any(marker in text for marker in _MARKERS):
        return set()
    return {
        key for key, aliases in _ALIASES.items()
        if any(alias.lower() in text for alias in aliases)
    }


def player_condition_immunities(state: Any) -> set[str]:
    info = getattr(state, "character_info", {}) or {}
    items = (info.get("inventory") or {}).get("items", []) if isinstance(info.get("inventory"), dict) else []
    equipped = [
        item for item in items
        if isinstance(item, dict) and item.get("equipped")
    ]
    return parse_condition_immunities(
        info.get("condition_immunities"),
        info.get("race_traits"),
        info.get("class_proficiencies"),
        info.get("damage_traits_notes"),
        info.get("active_effects"),
        info.get("feats"),
        [item.get("name") for item in equipped],
        [item.get("description") for item in equipped],
    )


def creature_condition_immunities(npc: Any) -> set[str]:
    return parse_condition_immunities(
        getattr(npc, "traits", []) or [],
        getattr(npc, "equipment", []) or [],
        getattr(npc, "notes", "") or "",
    )


def condition_block_reason(condition: Any, immunities: set[str]) -> str:
    key = canonical_condition(condition)
    if key and key in immunities:
        return f"免疫「{condition}」"
    return ""


def _roll_effect(spec: Any) -> int:
    """结算每回合伤害/治疗：支持整数、`2d6`、`1d4+1`。"""
    if isinstance(spec, (int, float)):
        return max(0, int(spec))
    text = str(spec or "").strip().lower()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    match = re.fullmatch(r"(\d{0,2})d(\d{1,4})(?:\+(\d+))?", text)
    if not match:
        return 0
    count = int(match.group(1) or 1)
    faces = int(match.group(2))
    bonus = int(match.group(3) or 0)
    return max(0, sum(random.randint(1, faces) for _ in range(count)) + bonus)


async def apply_condition_tick_effects(
    state: Any, conditions: list[Any], actor: str, *, is_player: bool = False,
) -> list[str]:
    """执行条件上的每回合伤害/治疗；返回给玩家可见的说明行。"""
    from backend.engine.session import push_event, push_narrative_token

    lines: list[str] = []
    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        damage = _roll_effect(condition.get("damage_per_turn"))
        heal = _roll_effect(condition.get("heal_per_turn"))
        if not damage and not heal:
            continue
        name = str(condition.get("name") or "持续效果")
        damage_type = str(condition.get("damage_type") or "")
        if is_player:
            from backend.engine import player_damage
            if damage:
                outcome = await player_damage.apply(
                    state, damage, damage_type=damage_type, reason=name, source=name)
                lines.append(
                    f"🩸 {name}：受到 {outcome['hp_damage']} 点伤害"
                    f"（HP {outcome['hp_before']}→{outcome['hp_after']}）")
            if heal:
                from backend.engine.character_state import _exec_update_state
                await _exec_update_state({"changes": {"hp": heal}, "reason": f"{name}治疗"}, state)
                lines.append(f"💚 {name}：恢复 {heal} 点生命。")
        else:
            from backend.engine import combat
            world = getattr(state, "world_state", None)
            npc = world.get_npc(actor) if world is not None else None
            if npc is None:
                continue
            current = int(getattr(npc, "hp", 0) or 0)
            if damage:
                new_hp = max(0, current - damage)
                fortitude_note = ""
                if new_hp <= 0:
                    from backend.engine.undead_fortitude import resolve_undead_fortitude
                    fort = await resolve_undead_fortitude(
                        state, npc, actor, damage=damage, damage_type=damage_type)
                    fortitude_note = str(fort.get("note") or "")
                    if fort.get("applied"):
                        new_hp = int(fort.get("hp") or 1)
                await combat._persist_combat_damage(state, npc, new_hp)
                lines.append(f"🩸 {actor} 的{name}：受到 {damage} 点伤害（HP {current}→{new_hp}）")
                if fortitude_note:
                    lines.append(f"  [{fortitude_note}]")
                current = new_hp
            if heal and current > 0:
                max_hp = int(getattr(npc, "max_hp", 0) or current)
                new_hp = min(max_hp or current + heal, current + heal)
                await combat._persist_combat_damage(state, npc, new_hp)
                lines.append(f"💚 {actor} 的{name}：恢复 {new_hp - current} 点生命。")
        if damage:
            await push_event(state, "game_event", {
                "type": "ongoing_effect",
                "description": lines[-1],
                "extra": {"actor": actor, "effect": name, "damage": damage,
                          "damage_type": damage_type},
            })
    if lines:
        await push_narrative_token(state, "\n" + "\n".join(lines) + "\n")
    return lines


async def apply_condition_end_saves(
    state: Any, conditions: list[Any], actor: str, *, is_player: bool = False,
) -> tuple[list[Any], list[str]]:
    """回合末/回合开始的条件豁免：成功移除，失败保留。返回 (保留条件, 说明行)。"""
    from backend.engine.session import push_event

    kept: list[Any] = []
    lines: list[str] = []
    for condition in conditions:
        if not isinstance(condition, dict):
            kept.append(condition)
            continue
        dc = int(condition.get("save_dc") or 0)
        ability = str(condition.get("save_ability") or "").lower()
        if dc <= 0 or ability not in ("str", "dex", "con", "int", "wis", "cha"):
            kept.append(condition)
            continue
        name = str(condition.get("name") or "状态")
        if is_player:
            from backend.engine import player_damage
            modifier, source = player_damage.save_modifier(state, ability)
        else:
            from backend.engine import damage_rules
            world = getattr(state, "world_state", None)
            npc = world.get_npc(actor) if world is not None else None
            if npc is None:
                kept.append(condition)
                continue
            modifier, source = damage_rules.creature_save_modifier(npc, {}, ability)
        roll = random.randint(1, 20)
        total = roll + modifier
        success = roll == 20 or (roll != 1 and total >= dc)
        result = "成功" if success else "失败"
        await push_event(state, "dice_roll", {
            "skill": f"{actor} {ability.upper()} 豁免（{name}）",
            "dc": dc, "roll": roll, "modifier": modifier, "result": result,
        })
        if success:
            lines.append(f"✅ {actor} 的{name}：豁免成功（d20={roll}+{modifier}={total} vs DC{dc}），状态结束。")
        else:
            kept.append(condition)
            lines.append(f"⏳ {actor} 的{name}：豁免失败（d20={roll}+{modifier}={total} vs DC{dc}），状态继续。")
    if lines:
        from backend.engine.session import push_narrative_token
        await push_narrative_token(state, "\n" + "\n".join(lines) + "\n")
    return kept, lines
