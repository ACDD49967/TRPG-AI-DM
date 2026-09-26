"""COC 7e 战斗结算：d100 对抗、技能百分比兜底与敌人反击。

从 `combat._exec_combat_round` 拆出（d20 分支仍留在 combat.py）；
调用方传入已解析好的参战数据，本模块只做 d100 判定、事件推送与反击。

**补丁契约**：`_roll_damage_simple` / `_persist_combat_damage` / `_exec_update_state` /
`_exec_enemy_attack` 统一经 `_combat()` 在调用时取 `combat` 模块属性，
`tests/test_coc_combat.py` 的 `patch.object(combat, "_roll_damage_simple")` 依然生效。
"""
from __future__ import annotations

import random
from typing import Any

from backend.engine.combat_state import _build_combat_snapshot
from backend.engine.session import GameSessionState, push_event, push_narrative_token
from backend.engine.tool_executor import primary_action_available


def _combat():
    """延迟拿 combat 模块：保留测试对 combat.* 的打桩语义，同时避免模块级循环导入。"""
    from backend.engine import combat
    return combat


async def resolve_coc_round(
    args: dict, state: GameSessionState, *,
    enemy: str, p_action: str, p_mod: int, p_dice: str,
    e_mod: int, e_hp: int, npc: Any, enemy_can_act: bool,
) -> str:
    # COC 敌人技能是百分比；NPC 卡没有 str/dex 时不能套 D&D 加值，回退到 40%
    if args.get("enemy_attack_modifier") is None and e_mod <= 10:
        e_mod = 40
    p_skill = max(1, min(99, int(p_mod or 50)))
    e_skill = max(1, min(99, int(e_mod or 40)))
    pr = random.randint(1, 100)
    if pr <= max(1, p_skill // 5) or pr <= 5:
        p_hit, p_result = True, "极限成功"
    elif pr <= p_skill:
        p_hit, p_result = True, "成功"
    else:
        p_hit, p_result = False, "失败"
    pd = _combat()._roll_damage_simple(p_dice) if p_hit else 0
    new_e_hp = max(0, e_hp - pd)
    ed = 0
    await push_event(state, "dice_roll", {
        "skill": p_action or "攻击", "dc": p_skill,
        "roll": pr, "modifier": 0, "result": p_result,
    })
    # 敌人攻击由 enemy_attack 工具在敌人回合/剧情中单独调用
    lines = [
        f"⚔️ 战斗结算（COC d100）",
        f"你的{p_action}: d100={pr} vs {p_skill}% → {p_result}" + (f"，造成 {pd} 点伤害" if pd else ""),
    ]
    xp_gain = await _combat()._persist_combat_damage(state, npc, new_e_hp)
    if new_e_hp <= 0:
        lines.append(f"💀 {enemy}被击败！" + (f"（+{xp_gain} XP）" if xp_gain else ""))
    desc = "\n".join(lines)
    extras = {"enemy_name": enemy, "enemy_hp_remaining": new_e_hp,
              "player_damage_taken": ed, "player_damage_dealt": pd,
              "enemy_dead": new_e_hp <= 0, "system": "coc",
              "enemies": _build_combat_snapshot(state, args.get("enemy_names") or [], enemy, new_e_hp)}
    await push_narrative_token(state, f"\n{desc}\n")
    await push_event(state, "game_event", {"type": "combat", "description": desc, "extra": extras})
    if ed:
        await _combat()._exec_update_state(
            {"changes": {"hp": -ed}, "reason": f"{enemy}造成{ed}伤害"}, state)
    # 目标敌人若仍能行动，立即结算其一次反击；dedup 保证主DM随后不会重复结算
    if enemy_can_act and new_e_hp > 0 and primary_action_available(state, enemy):
        enemy_result = await _combat()._exec_enemy_attack(
            {"enemy_name": enemy, "attacker_condition": str(args.get("enemy_condition") or "")},
            state)
        desc += "\n" + enemy_result
    return desc
