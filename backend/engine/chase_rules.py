"""追逐：冲刺判定 + "跑出视线"的摆脱判定。

5e 的追逐是一条"能跑多久"的确定性规则：每个参与者能**免费冲刺**的次数 =
3 + 体质调整值；再加冲刺就要掷 DC 10 体质豁免，失败力竭 +1
（力竭的机械后果由 `exhaustion_effects` 负责，这里不重算）。
被追的人想脱身，靠"跑出视线"——这一步用隐匿对抗追兵的被动察觉。

此前这全靠 DM 自己记"你还能冲几次"、自己决定"跑没跑掉"，于是要么漏算力竭、
要么一路追到天荒地老。冲刺计数与力竭落库在 `chase_state`，这里只留判定流程并再导出。
"""
from __future__ import annotations

import random
from typing import Any

from backend.engine.chase_state import (  # noqa: F401  再导出
    DASH_SAVE_DC, EXHAUSTION_CONDITION, FREE_DASH_BASE, add_exhaustion, con_modifier,
    dash_count, free_dashes, npc_exhaustion, record_dash, reset_chase,
)
from backend.engine.session import GameSessionState, push_event

_DASH_ACTIONS = ("dash", "冲刺", "奔跑", "追", "追捕")
_ESCAPE_ACTIONS = ("escape", "甩掉", "脱身", "摆脱", "逃掉")
_END_ACTIONS = ("end", "reset", "结束", "放弃追击", "追丢了")


def _int_arg(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _first_str(args: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = (args or {}).get(key)
        if isinstance(value, (list, tuple)) and value:
            value = value[0]
        text = str(value or "").strip()
        if text:
            return text
    return ""


async def _escape(state: GameSessionState, quarry: str, pursuers: list[str]) -> str:
    """被追的人尝试跑出视线：隐匿对抗追兵的被动察觉（复用潜行模块）。"""
    from backend.engine import stealth_rules
    from backend.engine.player_damage import is_player_name
    from backend.engine.stealth_modifiers import observer_passive_perception

    if is_player_name(state, quarry):
        mod = stealth_rules.stealth_modifier(state)
    else:
        world = getattr(state, "world_state", None)
        mod = stealth_rules.creature_stealth_modifier(
            world.get_npc(quarry) if world is not None else None)
    best_name, best_dc = "", 0
    world = getattr(state, "world_state", None)
    for name in pursuers:
        npc = world.get_npc(name) if world is not None else None
        value = observer_passive_perception(npc)
        if value > best_dc:
            best_name, best_dc = name, value
    roll = random.randint(1, 20)
    total = roll + mod
    success = roll == 20 or (roll != 1 and total >= best_dc)
    await push_event(state, "dice_roll", {
        "skill": f"{quarry} 甩掉追兵（隐匿）", "dc": best_dc,
        "roll": roll, "modifier": mod, "result": "成功" if success else "失败",
    })
    line = (f"🏃 {quarry} 想跑出视线：d20={roll}{'+' if mod >= 0 else ''}{mod}={total} "
            f"vs {best_name or '追兵'}的被动察觉 {best_dc} → {'成功' if success else '失败'}")
    if success:
        reset_chase(state)
        return line + f"\n{quarry} 甩掉了追兵，追逐结束（冲刺计数已清零）。"
    return line + f"\n{quarry} 还在追兵的视线里，追逐继续。"


async def _exec_resolve_chase(args: dict, state: GameSessionState) -> str:
    from backend.engine.player_damage import is_player_name

    args = args or {}
    action = _first_str(args, ("action", "kind", "行动")) or "dash"
    action = action.lower()
    actor = _first_str(args, ("actor", "attacker", "name", "谁")) 
    if not actor or is_player_name(state, actor):
        actor = str(getattr(state, "character_name", "") or "玩家")

    if action in _END_ACTIONS:
        cleared = reset_chase(state)
        return f"🏁 追逐结束（清理了 {cleared} 个单位的冲刺计数）。"

    if action in _ESCAPE_ACTIONS:
        pursuers = args.get("pursuers") or args.get("targets")
        if isinstance(pursuers, str):
            pursuers = [pursuers]
        names = [str(p).strip() for p in (pursuers or []) if str(p).strip()]
        if not names:
            world = getattr(state, "world_state", None)
            scene = getattr(world, "scene", None)
            here = [str(x) for x in (getattr(scene, "visible_npcs_here", None) or [])]
            names = here or [str(getattr(n, "name", "") or "")
                             for n in (getattr(world, "npcs", None) or [])
                             if bool(getattr(n, "alive", True))]
        return await _escape(state, actor, names)

    if action not in _DASH_ACTIONS:
        return "⚠ resolve_chase 需要 action：dash（冲刺）/ escape（甩掉追兵）/ end（结束追逐）"

    count = record_dash(state, actor)
    free = free_dashes(state, actor)
    if count <= free:
        return (f"🏃 {actor} 冲刺（第 {count} 次）：体质调整值 {con_modifier(state, actor):+d}，"
                f"还能免费冲刺 {free - count} 次。")

    dc = _int_arg(args.get("dc"), DASH_SAVE_DC) or DASH_SAVE_DC
    mod = con_modifier(state, actor)
    roll = random.randint(1, 20)
    total = roll + mod
    success = roll == 20 or (roll != 1 and total >= dc)
    await push_event(state, "dice_roll", {
        "skill": f"{actor} 强行军冲刺（体质豁免）", "dc": dc,
        "roll": roll, "modifier": mod, "result": "成功" if success else "失败",
    })
    line = (f"🏃 {actor} 冲刺（第 {count} 次，超出免费额度 {free} 次）："
            f"体质豁免 d20={roll}{'+' if mod >= 0 else ''}{mod}={total} vs DC{dc} → "
            f"{'成功' if success else '失败'}")
    if success:
        return line + "，硬撑着继续跑（未力竭）。"
    level = await add_exhaustion(state, actor, f"追逐中第 {count} 次冲刺未能坚持")
    return line + f"，力竭 +1 → 力竭 {level} 级。"
