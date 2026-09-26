"""追逐的状态：冲刺计数、免费额度与力竭落库。

从 `chase_rules` 拆出（那边只留判定流程）。5e 的追逐是"能跑多久"的记账问题：
免费冲刺 = 3 + 体质调整值，超出后每次都要过体质豁免、失败力竭 +1。
玩家力竭是角色卡数值，NPC 没有这个字段，改用「力竭 N 级」状态承载。
"""
from __future__ import annotations

from typing import Any

from backend.engine.session import GameSessionState

FREE_DASH_BASE = 3      # 5e：免费冲刺次数 = 3 + 体质调整值
DASH_SAVE_DC = 10
EXHAUSTION_CONDITION = "力竭"

_EXHAUSTION_TEXT = {
    1: "属性检定劣势", 2: "移动速度减半", 3: "攻击与豁免劣势",
    4: "生命值上限减半", 5: "移动速度降为 0", 6: "死亡",
}


def _sheet(state: Any, name: str) -> dict:
    """取属性表：玩家用角色卡，NPC 用简易卡。"""
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, name):
        info = getattr(state, "character_info", {}) or {}
        return info.get("attributes") or {}
    world = getattr(state, "world_state", None)
    npc = world.get_npc(str(name)) if world is not None else None
    return (getattr(npc, "attributes", None) or {}) if npc is not None else {}


def con_modifier(state: Any, name: str) -> int:
    from backend.engine.damage_rules import ability_modifier

    return ability_modifier(_sheet(state, name).get("con", 10))


def free_dashes(state: Any, name: str) -> int:
    """免费冲刺次数：3 + 体质调整值（最低 1，体质再差也还能冲一次）。"""
    return max(1, FREE_DASH_BASE + con_modifier(state, name))


def _counters(state: Any) -> dict[str, int]:
    counters = getattr(state, "chase_dashes", None)
    if not isinstance(counters, dict):
        counters = {}
        try:
            state.chase_dashes = counters
        except Exception:
            pass
    return counters


def _key(state: Any, name: str) -> str:
    from backend.engine.action_economy import normalize_actor

    return normalize_actor(state, name)


def dash_count(state: Any, name: str) -> int:
    return int(_counters(state).get(_key(state, name), 0) or 0)


def record_dash(state: Any, name: str) -> int:
    """记一次冲刺并返回累计次数。"""
    counters = _counters(state)
    key = _key(state, name)
    counters[key] = int(counters.get(key, 0) or 0) + 1
    return counters[key]


def reset_chase(state: Any, name: str = "") -> int:
    """结束追逐：清掉某人的计数（name 为空则清空全部）；返回清掉的人数。"""
    counters = _counters(state)
    if not name:
        cleared = len(counters)
        counters.clear()
        return cleared
    return 1 if counters.pop(_key(state, name), None) is not None else 0


def npc_exhaustion(state: Any, name: str) -> int:
    """NPC 的力竭等级：写在「力竭」状态的描述里（形如"力竭 2 级：…"）。"""
    import re

    world = getattr(state, "world_state", None)
    npc = world.get_npc(str(name)) if world is not None else None
    if npc is None:
        return 0
    for condition in (getattr(npc, "conditions", None) or []):
        if not isinstance(condition, dict):
            continue
        if str(condition.get("name") or "") != EXHAUSTION_CONDITION:
            continue
        match = re.search(r"(\d+)", str(condition.get("description") or ""))
        return int(match.group(1)) if match else 1
    return 0


async def add_exhaustion(state: GameSessionState, name: str, reason: str) -> int:
    """力竭 +1；返回新的等级。玩家走角色卡数值，NPC 走「力竭 N 级」状态。"""
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, name):
        from backend.engine.character_state import _exec_update_state

        await _exec_update_state({"changes": {"exhaustion": 1}, "reason": reason}, state)
        return int((getattr(state, "character_info", {}) or {}).get("exhaustion", 0) or 0)
    level = min(6, npc_exhaustion(state, name) + 1)
    from backend.engine.condition_apply import apply_named_condition

    await apply_named_condition(
        state, name, EXHAUSTION_CONDITION, add=True,
        reason=f"力竭 {level} 级：{_EXHAUSTION_TEXT.get(level, '')}")
    return level
