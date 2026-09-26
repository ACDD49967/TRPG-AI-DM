"""豁免伤害的玩家侧：掩体加值、魔法抗性/声明的豁免优势、力竭劣势与临时生命值。

从 `combat_save_damage` 拆出；裁定参数见 `combat_save_common.SaveDamageContext`。
"""
from __future__ import annotations

import random

from backend.engine.combat_save_common import _apply_failure_condition
from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system


def _save_roll(advantage: bool, disadvantage: bool) -> tuple[int, str]:
    """按优势/劣势掷豁免；返回 (骰值, 说明)。同源优劣势互相抵消回到单掷。"""
    if advantage and disadvantage:
        return random.randint(1, 20), "cancel"
    if advantage:
        return max(random.randint(1, 20), random.randint(1, 20)), "advantage"
    if disadvantage:
        return min(random.randint(1, 20), random.randint(1, 20)), "disadvantage"
    return random.randint(1, 20), "normal"


async def apply_to_player(state: GameSessionState, name: str, ctx) -> tuple[str, dict]:
    """玩家侧结算：豁免 → 抗性/免疫/易伤 → 临时生命值；返回 (日志行, 命中信息)。"""
    from backend.engine import player_damage

    mod, _ = player_damage.save_modifier(state, ctx.ability)
    from backend.engine import battlefield

    cover_save = battlefield.dex_bonus_from_cover(state, name) if ctx.ability == "dex" else 0
    mod += cover_save
    from backend.engine.magic_resistance import player_magic_resistance

    magic_advantage = bool(ctx.magic and player_magic_resistance(state))
    # 毒素抗性等额外优势与魔法抗性同类：都是"这次豁免掷两次取高"
    save_advantage = magic_advantage or ctx.extra_advantage
    advantage_note = "魔法抗性" if magic_advantage else (ctx.extra_advantage_reason or "豁免优势")
    # 力竭 3 级起：豁免劣势（5e）。与豁免优势互相抵消，都不生效。
    exhaustion_disadvantage = False
    try:
        from backend.engine.time_supplies import exhaustion_level

        exhaustion_disadvantage = (
            _game_system(state) in ("dnd5e", "dnd4e") and exhaustion_level(state) >= 3)
    except Exception:
        exhaustion_disadvantage = False

    roll, mode = _save_roll(save_advantage, exhaustion_disadvantage)
    if mode == "cancel":
        save_note = f"力竭3级与{advantage_note}抵消"
    elif mode == "advantage":
        save_note = advantage_note
    elif mode == "disadvantage":
        save_note = "力竭3级：豁免劣势"
    else:
        save_note = ""
    total = roll + mod
    success = total >= ctx.dc
    if success and not ctx.half_on_success:
        damage = 0
    elif success:
        damage = ctx.base_damage // 2
    else:
        damage = ctx.base_damage
    await push_event(state, "dice_roll", {
        "skill": f"{name} {ctx.ability_label}豁免", "dc": ctx.dc,
        "roll": roll, "modifier": mod, "result": "成功" if success else "失败",
        **({"advantage": "advantage" if mode == "advantage"
            else "disadvantage" if mode == "disadvantage" else "normal",
            "advantage_note": save_note} if save_note else {}),
    })
    outcome = await player_damage.apply(
        state, damage, damage_type=ctx.damage_type, reason=ctx.reason, source=ctx.reason)
    detail = (f"- {name}（玩家）：d20={roll}{'+' if mod >= 0 else ''}{mod}={total} "
              f"vs DC{ctx.dc} → {'成功' if success else '失败'}，扣血 {outcome['hp_damage']}"
              f"（HP {outcome['hp_before']}→{outcome['hp_after']}）")
    if outcome["temp_absorbed"]:
        detail += f"，临时生命值吸收 {outcome['temp_absorbed']}"
    if outcome["note"]:
        detail += f" [{outcome['note']}]"
    if cover_save:
        detail += f"[掩体 +{cover_save} 敏捷豁免]"
    if save_advantage:
        detail += f"[{advantage_note}：豁免优势]"
    if not success and ctx.condition_on_failure:
        applied = await _apply_failure_condition(
            state, name, ctx.condition_on_failure, reason=ctx.reason,
            rounds=ctx.condition_rounds, note=ctx.condition_note)
        if applied:
            detail += f"[{applied}]"
    return detail, {"name": name, "hp": outcome["hp_after"], "roll": roll,
                    "success": success, "damage": outcome["hp_damage"],
                    "note": outcome["note"], "is_player": True}
