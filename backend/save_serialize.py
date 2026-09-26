"""存档序列化：运行期动态属性、分层记忆与世界状态快照。

从 `save_manager.py` 拆出。路径与 CRUD 仍在 save_manager——那里的 `SAVE_ROOT`
会被测试替换，所以路径相关代码不搬；这里只做「会话状态 → 可存 JSON」的纯转换。
"""
from __future__ import annotations

from backend.engine.session import GameSessionState


def _serialize_dynamic(state: GameSessionState) -> dict:
    """序列化死亡豁免/生命骰/奥术回想等运行期动态属性（P1-13）。"""
    ds = getattr(state, "_death_saves", None)
    if ds is not None and hasattr(ds, "__dataclass_fields__"):
        from dataclasses import asdict
        ds = asdict(ds)
    return {
        "death_saves": ds,
        "hit_dice_remaining": getattr(state, "_hit_dice_remaining", None),
        "arcane_recovery_used": getattr(state, "_arcane_recovery_used", None),
        # 濒死/死亡状态必须一起存：否则读档会让"倒地昏迷"和死亡锁定凭空消失
        "dying": bool(getattr(state, "dying", False)),
        "character_dead": bool(getattr(state, "character_dead", False)),
        "death_save_turn": getattr(state, "_death_save_turn", -1),
        # 先攻表：读档后仍要记得"打到第几轮、谁已经行动过"
        "initiative": (state.initiative.to_dict()
                       if hasattr(getattr(state, "initiative", None), "to_dict") else None),
        # 战场态势：读档后仍记得谁在掩体后、谁已经脱离近战
        "battlefield": (state.battlefield.to_dict()
                        if hasattr(getattr(state, "battlefield", None), "to_dict") else None),
        # 游戏内时钟（自第 1 天 0:00 起的分钟数）：读档后时间不会倒流
        "clock_minutes": getattr(state, "clock_minutes", None),
        # 再生生物被击倒后的待复活标记：读档后仍要等它自己的回合结算
        "pending_regeneration": sorted(
            str(x).strip().lower() for x in (getattr(state, "pending_regeneration", set()) or set())
            if str(x).strip()
        ),
    }


def _serialize_memory(state: GameSessionState) -> dict:
    mem = state.memory
    return {
        "turns": [
            {"player_input": t.player_input, "dm_response": t.dm_response, "events": t.events}
            for t in mem.turns
        ],
        "summary": mem.summary,
        "world_facts": mem.world_facts,
        "major_events": mem.major_events,
        "hidden_threads": mem.hidden_threads,
        "character_impacts": mem.character_impacts,
        "max_active_turns": mem.max_active_turns,
        "summary_trigger": mem.summary_trigger,
    }


def _serialize_world_state(state: GameSessionState) -> dict | None:
    ws = getattr(state, "world_state", None)
    if ws is None:
        return None
    # 直接从内存构造快照：以前是"先落盘再读回硬编码的 world_states/<sid>.json"，
    # 会话的 _storage_dir 一旦不是默认目录，存档里的 world_state 就会静默变空。
    try:
        from backend.engine.world_io import world_to_dict
        return world_to_dict(ws)
    except Exception:
        return None
