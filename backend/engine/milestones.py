"""D&D 4e 里程碑：每两次遭遇 +1 行动点，长休（延长休息）后清零重算。

4e 的行动点此前只有"花"的路径（`action_economy.spend_action_point`），没有"得"的路径：
提示词与拒绝文案里写着"每达成里程碑 +1"，代码里却只能靠 DM 手写 `update_state`——
于是行动点常年停在初始的 1 点，或者干脆是 0（"有字段没变化"的第七次）。

这里把遭遇计数落到后端：战斗从"有存活敌对单位"变成"没有"时算一次遭遇结束
（`_refresh_combat_state` 的 True→False 跳变，天然覆盖击杀、逃散、撤退三种收场），
每累计 2 次算一个里程碑，给 1 点行动点（沿用 `update_state` 的 0-3 上限）。
计数存在 `character_info` 里，随存档一起持久化。
"""
from __future__ import annotations

from typing import Any

from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system

MILESTONE_ENCOUNTERS = 2
ACTION_POINT_CAP = 3
COUNTER_KEY = "encounters_since_extended_rest"
_HINT_PREFIX = "[系统强制-里程碑]"


def encounter_count(state: Any) -> int:
    """自上次长休以来已完成的遭遇数。"""
    info = getattr(state, "character_info", {}) or {}
    try:
        return max(0, int(info.get(COUNTER_KEY, 0) or 0))
    except (TypeError, ValueError):
        return 0


def reset_encounters(state: Any) -> None:
    """延长休息后重新开始计里程碑。"""
    info = getattr(state, "character_info", None)
    if isinstance(info, dict):
        info[COUNTER_KEY] = 0


def _replace_hint(state: GameSessionState, text: str) -> None:
    existing = [h for h in (state.pending_system_hints or []) if not h.startswith(_HINT_PREFIX)]
    state.pending_system_hints = existing + [text]


async def record_encounter_end(state: GameSessionState, was_in_combat: bool) -> int:
    """遭遇结束时记账；返回本次获得的行动点数（0 = 还没到里程碑）。

    调用方负责"先取旧的 in_combat，再刷新战斗状态"：只有 True→False 才算一次遭遇，
    战斗中反复结算伤害不会重复计数。
    """
    if _game_system(state) != "dnd4e":
        return 0
    if not was_in_combat or bool(getattr(state, "in_combat", False)):
        return 0
    info = state.character_info
    count = encounter_count(state) + 1
    info[COUNTER_KEY] = count
    if count % MILESTONE_ENCOUNTERS:
        return 0

    before = int(info.get("action_points", 1) or 0)
    gained = max(0, min(ACTION_POINT_CAP, before + 1) - before)
    if gained:
        from backend.engine.character_state import _exec_update_state

        await _exec_update_state(
            {"changes": {"action_points": gained},
             "reason": f"里程碑（第 {count} 次遭遇）"}, state)
    after = int(info.get("action_points", before) or 0)
    _replace_hint(
        state,
        f"{_HINT_PREFIX} 这是本次延长休息后的第 {count} 次遭遇，达成里程碑："
        f"行动点 {after}（上限 {ACTION_POINT_CAP}）。玩家可以声明 "
        "action_source=action_point 换一次额外行动（花点由后端结算）。"
        if gained else
        f"{_HINT_PREFIX} 达成里程碑（第 {count} 次遭遇），但行动点已达上限 "
        f"{ACTION_POINT_CAP}，不再累加。",
    )
    await push_event(state, "game_event", {
        "type": "milestone",
        "description": (f"🎖️ 里程碑：第 {count} 次遭遇结束，获得 {gained} 点行动点（当前 {after}）。"
                        if gained else
                        f"🎖️ 里程碑：第 {count} 次遭遇结束（行动点已在上限 {ACTION_POINT_CAP}）。"),
        "extra": {"encounters": count, "action_points": after, "gained": gained},
    })
    return gained


__all__ = [
    "record_encounter_end", "encounter_count", "reset_encounters",
    "MILESTONE_ENCOUNTERS", "ACTION_POINT_CAP", "COUNTER_KEY",
]
