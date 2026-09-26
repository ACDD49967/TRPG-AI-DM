"""读档恢复：把存档 JSON 还原成一个内存会话（不写数据库）。

从 `save_manager.py` 拆出；旧存档兼容（api_key/model_name 只在内存恢复）也在这里。
世界状态先写到 `world_states/<新 session_id>.json`，再交给 WorldState.load。
"""
from __future__ import annotations

import uuid
from pathlib import Path

from backend.engine.session import GameSessionState
from backend.logging_utils import get_logger


def restore_state_from_save(save_data: dict) -> tuple[GameSessionState, dict]:
    """从存档数据恢复一个内存会话（不写数据库）。"""
    session = save_data.get("session", {})
    session_id = uuid.uuid4().hex[:16]
    character_id = session.get("character_id", uuid.uuid4().hex[:12])
    character_name = session.get("character_name", "冒险者")
    character_info = dict(session.get("character_info", {}))
    character_info["play_mode"] = session.get("play_mode", "deep")
    character_info["game_system"] = session.get("game_system", "dnd5e")
    character_info["scenario_id"] = session.get("scenario_id", "")
    character_info["custom_rules"] = session.get("custom_rules", "")
    character_info["extension_ids"] = session.get("extension_ids", [])

    from backend.engine.session import GameSessionState
    from backend.engine.memory import MemorySystem, DialogueTurn

    state = GameSessionState(
        session_id=session_id,
        character_id=character_id,
        character_name=character_name,
        character_info=character_info,
        username=save_data.get("username", "default"),
    )
    state.response_cache = {}
    state.opening_text = session.get("opening_text", "")
    # 旧存档兼容：仅在内存中恢复历史 api_key；新存档不再包含该字段。
    state.api_key = session.get("api_key")
    state.model_name = session.get("model_name")
    state.base_url = session.get("base_url")

    dyn = session.get("dynamic_state") or {}
    try:
        if dyn.get("death_saves") is not None:
            from backend.engine.rules import DeathSaves
            state._death_saves = DeathSaves(**dyn["death_saves"])
        if dyn.get("hit_dice_remaining") is not None:
            state._hit_dice_remaining = int(dyn["hit_dice_remaining"])
        if dyn.get("arcane_recovery_used") is not None:
            state._arcane_recovery_used = bool(dyn["arcane_recovery_used"])
        state.dying = bool(dyn.get("dying", False))
        state.character_dead = bool(dyn.get("character_dead", False))
        if dyn.get("death_save_turn") is not None:
            state._death_save_turn = int(dyn["death_save_turn"])
        if dyn.get("initiative"):
            from backend.engine.initiative import InitiativeTracker
            state.initiative = InitiativeTracker.from_dict(dyn["initiative"])
        if dyn.get("battlefield"):
            from backend.engine.battlefield import Battlefield
            state.battlefield = Battlefield.from_dict(dyn["battlefield"])
        if dyn.get("clock_minutes") is not None:
            state.clock_minutes = int(dyn["clock_minutes"])
        pending = dyn.get("pending_regeneration")
        if isinstance(pending, list):
            state.pending_regeneration = {
                str(x).strip().lower() for x in pending if str(x).strip()
            }
    except Exception as e:
        get_logger("save_manager").warning("动态属性恢复失败: %s", e, exc_info=True)

    mem = MemorySystem()
    mem_data = session.get("memory", {})
    from dataclasses import fields as _dc_fields
    _turn_fields = {f.name for f in _dc_fields(DialogueTurn)}
    mem.turns = [
        DialogueTurn(**{k: v for k, v in t.items() if k in _turn_fields})
        for t in mem_data.get("turns", []) if isinstance(t, dict)
    ]
    mem.summary = mem_data.get("summary", "")
    mem.world_facts = list(mem_data.get("world_facts", []))
    mem.major_events = list(mem_data.get("major_events", []))
    mem.hidden_threads = list(mem_data.get("hidden_threads", []))
    mem.character_impacts = list(mem_data.get("character_impacts", []))
    mem.max_active_turns = mem_data.get("max_active_turns", 10)
    mem.summary_trigger = mem_data.get("summary_trigger", mem.max_active_turns + 1)
    state.memory = mem

    ws_data = session.get("world_state")
    if ws_data:
        # 写入新 session 的 world_state 文件
        from backend.engine.world_state import WorldState
        from backend.save_manager import _atomic_write_json
        ws_dir = Path("world_states")
        ws_dir.mkdir(exist_ok=True)
        _atomic_write_json(ws_dir / f"{session_id}.json", ws_data)
        state.world_state = WorldState.load(session_id)

    return state, session_id
