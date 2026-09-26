"""隐藏状态的读写与出手暴露。

玩家写角色卡状态、NPC 写 NPC 卡状态，两条路都复用既有的状态写入接口
（`character_state._exec_update_state` / `world_npc_tools._exec_adjust_npc`），
所以落盘、事件推送与免疫拦截都不需要在这里重做一遍。
"""
from __future__ import annotations

from typing import Any

from backend.engine.combat_advantage_base import _has, _norm
from backend.engine.session import GameSessionState

HIDDEN = "隐藏"
_HIDDEN_WORDS = ("隐藏", "hidden", "未被看见", "unseen", "躲藏")
# 会让行动者暴露的工具：攻击、施法、范围效果都算"出手"
_EXPOSING_TOOLS = {"combat_round", "enemy_attack", "cast_spell", "save_damage"}


def _conditions_of(state: Any, target: str) -> list | None:
    """取目标的状态列表；目标不存在时返回 None。"""
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, target):
        return (getattr(state, "character_info", {}) or {}).get("conditions") or []
    world = getattr(state, "world_state", None)
    npc = world.get_npc(target) if world is not None else None
    if npc is None:
        return None
    return getattr(npc, "conditions", None) or []


def is_hidden(state: Any, name: Any = "") -> bool:
    """目标当前是否处于隐藏状态（玩家看角色卡状态，NPC 看 NPC 卡状态）。"""
    target = str(name or getattr(state, "character_name", "") or "")
    conditions = _conditions_of(state, target)
    for condition in (conditions or []):
        text = _norm(condition.get("name") if isinstance(condition, dict) else condition)
        if _has(text, *_HIDDEN_WORDS):
            return True
    return False


async def set_hidden(state: GameSessionState, target: str, hidden: bool, *, reason: str) -> None:
    """写「隐藏」状态：玩家走角色卡状态，NPC 走 NPC 卡状态（都自带落盘/事件）。"""
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, target):
        from backend.engine.character_state import _exec_update_state

        changes = ({"conditions_add": {"name": HIDDEN, "description": reason}}
                   if hidden else {"conditions_remove": HIDDEN})
        await _exec_update_state({"changes": changes, "reason": reason}, state)
        return
    from backend.engine.world_npc_tools import _exec_adjust_npc

    await _exec_adjust_npc({
        "name": target, "field": "condition_add" if hidden else "condition_remove",
        "value": HIDDEN, "description": reason, "reason": reason,
    }, state)


async def break_stealth(state: Any, actor: str) -> str:
    """出手后暴露：清掉隐藏状态并返回可叙述的说明（没在隐藏时返回空串）。"""
    actor = str(actor or "").strip()
    if not actor or not is_hidden(state, actor):
        return ""
    await set_hidden(state, actor, False, reason="出手后暴露")
    return f"👀 {actor} 因出手暴露，隐藏状态结束。"


def exposing_actor(tool_name: str, args: dict, state: Any) -> str:
    """这次工具调用会不会暴露行动者；会则返回行动者名，否则空串。"""
    name = str(tool_name or "")
    if name not in _EXPOSING_TOOLS:
        return ""
    if name == "enemy_attack":
        return str((args or {}).get("enemy_name") or "").strip()
    if name == "save_damage":
        return str((args or {}).get("actor") or "").strip()
    return str(getattr(state, "character_name", "") or "").strip()


async def break_stealth_after_tool(tool_name: str, args: dict, state: Any) -> str:
    """工具执行后的暴露收口：出手就现形；不需要暴露或本来没藏着时返回空串。

    调用方（`tool_executor`）不需要知道哪些工具会暴露、状态存在哪张卡上。
    清理失败只记日志，不能让一次攻击因为状态清理出错而整体失败。
    """
    actor = exposing_actor(tool_name, args, state)
    if not actor:
        return ""
    try:
        return await break_stealth(state, actor)
    except Exception as exc:
        from backend.logging_utils import get_logger
        get_logger("stealth").warning("隐藏状态清除失败: %s", exc, exc_info=True)
        return ""
