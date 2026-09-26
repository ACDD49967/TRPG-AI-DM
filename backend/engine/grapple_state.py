"""擒抱状态的维护：谁抓着谁、擒抱者倒下时怎么自动解除。

从 `contest_rules` 拆出（那边只留对抗检定流程）。5e 规定"擒抱者无法行动时擒抱结束"，
所以状态里要记下**谁在抓**（`grappled_by`），后端才能在擒抱者倒地/失能时自动收口，
而不是指望 DM 记得手动清状态。
"""
from __future__ import annotations

from typing import Any

from backend.engine.condition_apply import apply_named_condition, condition_names
from backend.engine.session import GameSessionState, push_event, push_narrative_token

GRAPPLE = "擒抱"


def same_name(a: Any, b: Any) -> bool:
    """名字比较：忽略空白与大小写（DM 常写「地精」/「地精 」这类变体）。"""
    return "".join(str(a or "").split()).lower() == "".join(str(b or "").split()).lower()


def cannot_act(state: Any, name: str) -> bool:
    """目标是否已经无法行动：0 HP/阵亡，或失能/麻痹/昏迷等状态。"""
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, name):
        info = getattr(state, "character_info", {}) or {}
        try:
            hp = int(info.get("hp", 1) or 0)
        except (TypeError, ValueError):
            hp = 1
        if hp <= 0 or getattr(state, "character_dead", False):
            return True
    else:
        world = getattr(state, "world_state", None)
        npc = world.get_npc(str(name)) if world is not None else None
        if npc is not None and (not bool(getattr(npc, "alive", True))
                                or int(getattr(npc, "hp", 0) or 0) <= 0):
            return True
    from backend.engine.contest_modifiers import is_helpless

    return is_helpless(state, name)


def grappling_targets(state: Any, grappler: str) -> list[str]:
    """列出正被 `grappler` 擒抱着的目标（读两张卡上「擒抱」状态的 grappled_by）。"""
    if not str(grappler or "").strip():
        return []
    found: list[str] = []
    world = getattr(state, "world_state", None)
    info = getattr(state, "character_info", {}) or {}
    holders: list[tuple[str, list]] = [
        (str(getattr(state, "character_name", "") or "玩家"), info.get("conditions") or []),
    ]
    for npc in (getattr(world, "npcs", None) or []):
        holders.append((str(getattr(npc, "name", "") or ""), getattr(npc, "conditions", None) or []))
    for holder, conditions in holders:
        if not holder or holder in found:
            continue
        for condition in conditions:
            if not isinstance(condition, dict):
                continue
            if not same_name(condition.get("name"), GRAPPLE):
                continue
            if same_name(condition.get("grappled_by"), grappler):
                found.append(holder)
                break
    return found


async def release_grapples_by(state: GameSessionState, grappler: str) -> str:
    """擒抱者失能/倒地时解除它施加的擒抱；返回可叙述的说明（没有则空串）。"""
    targets = grappling_targets(state, grappler)
    if not targets:
        return ""
    for target in targets:
        await apply_named_condition(
            state, target, GRAPPLE, add=False, reason=f"{grappler} 已无法继续擒抱")
    note = f"👐 {grappler} 已无法行动，{'、'.join(targets)} 挣脱了擒抱。"
    try:
        await push_event(state, "game_event", {
            "type": "combat", "description": note,
            "extra": {"grappler": grappler, "released": targets},
        })
        await push_narrative_token(state, f"\n{note}\n")
    except Exception:
        pass
    return note


def holds_grapple(state: Any, target: str) -> bool:
    """目标当前是否被擒抱着（判定用）。"""
    return GRAPPLE in condition_names(state, target)
