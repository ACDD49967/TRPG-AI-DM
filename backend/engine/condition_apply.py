"""给玩家或 NPC 增删一个具名状态（两条卡路都复用既有写入接口）。

玩家写角色卡状态（`character_state._exec_update_state`）、NPC 写 NPC 卡状态
（`world_npc_tools._exec_adjust_npc`）——两条路都自带落盘、事件推送与免疫拦截，
所以规则模块（潜行、对抗动作……）不需要各自重写一遍。
"""
from __future__ import annotations

from typing import Any

from backend.engine.session import GameSessionState


async def apply_named_condition(state: GameSessionState, target: str, name: str, *,
                                add: bool = True, reason: str = "",
                                rounds: int = 0, extra: dict | None = None) -> bool:
    """增/删状态；返回是否作用在玩家卡上（方便调用方拼日志）。

    `extra` 用来带结构化附加字段（例如擒抱的 `grappled_by`），两条卡路都会透传。
    """
    target = str(target or "").strip()
    name = str(name or "").strip()
    if not target or not name:
        return False
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, target):
        from backend.engine.character_state import _exec_update_state

        payload = {"name": name, "description": reason, **(extra or {})}
        if int(rounds or 0) > 0:
            payload["remaining_rounds"] = int(rounds)
        changes = ({"conditions_add": payload}
                   if add else {"conditions_remove": name})
        await _exec_update_state({"changes": changes, "reason": reason or name}, state)
        return True
    from backend.engine.world_npc_tools import _exec_adjust_npc

    await _exec_adjust_npc({
        "name": target, "field": "condition_add" if add else "condition_remove",
        "value": name, "description": reason, "remaining_rounds": int(rounds or 0),
        "reason": reason or name, **(extra or {}),
    }, state)
    return False


def condition_names(state: Any, target: str) -> list[str]:
    """目标当前的状态名列表（目标不存在时返回空表）。"""
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, target):
        conditions = (getattr(state, "character_info", {}) or {}).get("conditions") or []
    else:
        world = getattr(state, "world_state", None)
        npc = world.get_npc(str(target)) if world is not None else None
        if npc is None:
            return []
        conditions = getattr(npc, "conditions", None) or []
    return [str(c.get("name") if isinstance(c, dict) else c) for c in conditions]


def has_condition(state: Any, target: str, *words: str) -> bool:
    """目标是否带有匹配这些关键词的状态（中文/英文别名都用子串匹配）。"""
    wanted = tuple(w.lower() for w in words if w)
    if not wanted:
        return False
    for name in condition_names(state, target):
        text = name.lower()
        if any(word in text for word in wanted):
            return True
    return False
