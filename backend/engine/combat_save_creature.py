"""豁免伤害的生物侧：抗性/免疫/易伤、传奇抗性、亡灵坚韧与落库。

从 `combat_save_damage` 拆出；裁定参数见 `combat_save_common.SaveDamageContext`。
"""
from __future__ import annotations

import random

from backend.engine.combat_save_common import _apply_failure_condition, _combat
from backend.engine.combat_targets import _find_bestiary_card, _resolve_enemy_from_cards
from backend.engine.session import GameSessionState, push_event


async def apply_to_creature(state: GameSessionState, name: str, ctx) -> tuple[str, dict | None]:
    """生物侧结算；找不到实体/已阵亡时返回只带说明的行（命中信息为 None）。"""
    from backend.engine.damage_rules import creature_save_modifier, damage_multiplier

    stats = _resolve_enemy_from_cards(state, name, {})
    npc = stats.get("npc")
    if npc is None:
        return (f"- {name}：未找到对应实体，跳过"
                f"（先用 add_scenario_bestiary/update_world_state 建卡）"), None
    if not bool(getattr(npc, "alive", True)) or int(getattr(npc, "hp", 0) or 0) <= 0:
        return f"- {name}：已阵亡，跳过", None
    card = _find_bestiary_card(state, name) or {}
    card_stats = (card.get("stats") if isinstance(card, dict) else {}) or {}
    mod, _mod_source = creature_save_modifier(npc, card_stats, ctx.ability)
    from backend.engine import battlefield

    cover_save = battlefield.dex_bonus_from_cover(state, name) if ctx.ability == "dex" else 0
    mod += cover_save
    from backend.engine.magic_resistance import creature_magic_resistance

    magic_advantage = bool(ctx.magic and creature_magic_resistance(npc))
    advantage_note = ("魔法抗性" if magic_advantage
                      else (ctx.extra_advantage_reason or "豁免优势") if ctx.extra_advantage else "")
    rolls = [random.randint(1, 20)]
    if advantage_note:
        rolls.append(random.randint(1, 20))
    roll = max(rolls)
    total = roll + mod
    success = total >= ctx.dc
    legendary_note = ""
    if not success and ctx.legendary_resistance:
        from backend.engine.legendary_resistance import spend_legendary_resistance

        if spend_legendary_resistance(npc):
            success = True
            legendary_note = "传奇抗性：将失败改为成功"
        else:
            legendary_note = "传奇抗性已用尽"
    if success and not ctx.half_on_success:
        damage = 0
    elif success:
        damage = ctx.base_damage // 2
    else:
        damage = ctx.base_damage
    multiplier, note = damage_multiplier(
        card or npc, ctx.damage_type, extra_text=" ".join(getattr(npc, "traits", []) or []))
    applied = max(0, int(damage * multiplier))
    if applied > 0 and ctx.damage_type:
        from backend.engine.turn_start_effects import record_damage_type

        record_damage_type(state, name, ctx.damage_type)
    current_hp = int(getattr(npc, "hp", 0) or 0)
    new_hp = max(0, current_hp - applied)
    fortitude_note = ""
    if new_hp <= 0 and applied > 0:
        from backend.engine.undead_fortitude import resolve_undead_fortitude

        fort = await resolve_undead_fortitude(
            state, npc, name, damage=applied, damage_type=ctx.damage_type)
        fortitude_note = str(fort.get("note") or "")
        if fort.get("applied"):
            new_hp = int(fort.get("hp") or 1)
    await _combat()._persist_combat_damage(state, npc, new_hp)
    await push_event(state, "dice_roll", {
        "skill": f"{name} {ctx.ability_label}豁免", "dc": ctx.dc,
        "roll": roll, "modifier": mod, "result": "成功" if success else "失败",
        **({"advantage": "advantage", "advantage_note": advantage_note}
           if advantage_note else {}),
        **({"legendary_resistance": True} if legendary_note.startswith("传奇抗性：") else {}),
    })
    detail = (f"- {name}：d20={roll}{'+' if mod >= 0 else ''}{mod}={total} vs DC{ctx.dc} → "
              f"{'成功' if success else '失败'}，受 {applied} 点伤害（HP {current_hp}→{new_hp}）")
    if note:
        detail += f" [{note}]"
    if cover_save:
        detail += f"[掩体 +{cover_save} 敏捷豁免]"
    if advantage_note:
        detail += f"[{advantage_note}：豁免优势]"
    if legendary_note:
        detail += f"[{legendary_note}]"
    if fortitude_note:
        detail += f"[{fortitude_note}]"
    if not success and ctx.condition_on_failure:
        applied_condition = await _apply_failure_condition(
            state, name, ctx.condition_on_failure, reason=ctx.reason,
            rounds=ctx.condition_rounds, note=ctx.condition_note)
        if applied_condition:
            detail += f"[{applied_condition}]"
    if new_hp <= 0:
        detail += " ☠ 已阵亡"
    return detail, {"name": name, "hp": new_hp, "roll": roll,
                    "success": success, "damage": applied, "note": note,
                    "legendary_resistance": legendary_note,
                    "undead_fortitude": fortitude_note}
