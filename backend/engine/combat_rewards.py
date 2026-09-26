"""击败奖励与伤害落库：按等级给 XP，并把 HP 变更写回实体并推送事件。

从 `backend/engine/combat.py` 拆出；那边保留四个规则处理器并再导出这些名字。
"""
from __future__ import annotations

from typing import Any

from backend.engine.character_state import _exec_update_state
from backend.engine.combat_state import _refresh_combat_state
from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system

_NPC_LEVEL_XP = {1: 50, 2: 100, 3: 200, 4: 450, 5: 700,
                 6: 1100, 7: 1800, 8: 2300, 9: 2900, 10: 3900}


def _defeat_xp_for(npc: Any) -> int:
    level = max(1, int(getattr(npc, "level", 1) or 1))
    if level in _NPC_LEVEL_XP:
        return _NPC_LEVEL_XP[level]
    return 5000 + (level - 10) * 1000


async def _award_defeat_xp(state: GameSessionState, npc: Any) -> int:
    """击败结算 XP（dnd 系），并触发既有的自动升级逻辑。"""
    if _game_system(state) not in ("dnd5e", "dnd4e"):
        return 0
    if npc is None or getattr(npc, "xp_awarded", False):
        return 0
    gain = _defeat_xp_for(npc)
    npc.xp_awarded = True
    if gain > 0:
        await _exec_update_state({"changes": {"xp": gain}, "reason": f"击败{npc.name}"}, state)
    return gain

async def _persist_combat_damage(state: GameSessionState, npc: Any, new_hp: int) -> int:
    """把敌人 HP 写回世界状态实体；保持 alive 与 HP 一致，并返回本次结算的经验。"""
    if npc is None:
        return 0
    was_alive = bool(getattr(npc, "alive", True))
    previous_hp = int(getattr(npc, "hp", 0) or 0)
    npc.hp = max(0, new_hp)
    npc.alive = was_alive and npc.hp > 0
    # 怪物施法者：受伤同样要过专注豁免（倒地则直接中断），由后端统一结算
    damage_taken = previous_hp - npc.hp
    if damage_taken > 0:
        from backend.engine.concentration import handle_npc_damage
        await handle_npc_damage(state, npc, damage_taken)
    # 先攻表同步：血量/阵亡状态必须和后端权威一致，否则会提示"该敌人还没行动"
    from backend.engine import initiative
    initiative.sync_hp(state, getattr(npc, "name", ""), npc.hp, int(getattr(npc, "max_hp", 0) or 0))
    if not npc.alive:
        initiative.sync_defeat(state, getattr(npc, "name", ""))
        # 擒抱者倒下 → 它抓着的目标立即挣脱（5e：擒抱者无法行动时擒抱结束）
        from backend.engine.contest_rules import release_grapples_by

        await release_grapples_by(state, getattr(npc, "name", ""))
    xp_gain = 0
    if was_alive and not npc.alive:
        from backend.engine.turn_start_effects import has_regeneration, mark_pending_regeneration
        if has_regeneration(npc):
            # 再生生物被击倒先不发经验：等它真正无法再生时再结算
            mark_pending_regeneration(state, getattr(npc, "name", ""))
        else:
            xp_gain = await _award_defeat_xp(state, npc)
    was_in_combat = bool(getattr(state, "in_combat", False))
    _refresh_combat_state(state)
    # 4e 里程碑：这一击如果让战斗收场，就算一次遭遇结束（每 2 次 +1 行动点）
    from backend.engine.milestones import record_encounter_end
    await record_encounter_end(state, was_in_combat)
    ws = getattr(state, "world_state", None)
    if ws is not None:
        ws.save()
        try:
            await push_event(state, "journal_update", ws.to_player_journal())
        except Exception:
            pass
    return xp_gain
