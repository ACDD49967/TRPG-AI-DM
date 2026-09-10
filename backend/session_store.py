# -*- coding: utf-8 -*-
"""P1-20/P1-21: 把活动会话快照写回 SQLite，使 DB 成为可审计/可恢复的辅助层。"""
from __future__ import annotations

import uuid
from typing import Any

from backend.logging_utils import get_logger


def _current_state_payload(state: Any) -> dict:
    info = state.character_info or {}
    keep = (
        "hp", "max_hp", "mp", "max_mp", "xp", "gold", "level", "ac", "inventory",
        "attributes", "character_name", "race", "char_class", "gender", "game_system",
        "scenario_id", "san", "max_san", "luck", "healing_surges", "max_healing_surges",
        "surge_value", "action_points", "known_spells", "class_resources",
    )
    payload = {k: info.get(k) for k in keep if k in info}
    ws = getattr(state, "world_state", None)
    if ws is not None:
        payload["turn_count"] = getattr(ws, "turn_count", 0)
        payload["location"] = getattr(getattr(ws, "scene", None), "current_location", "")
    payload["session_status"] = getattr(state, "status", "active")
    return payload


async def persist_session_snapshot(state: Any) -> bool:
    """登记/更新 user、character、game_session，并写入一条回合快照事件。"""
    try:
        from sqlalchemy import select
        from backend.database import async_session
        from backend.models import Character, GameEventLog, GameSession, User

        username = (getattr(state, "username", "") or "default").strip() or "default"
        async with async_session() as db:
            user = await db.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(id=uuid.uuid4().hex[:12], username=username)
                db.add(user)
                await db.flush()

            char = await db.get(Character, state.character_id)
            info = state.character_info or {}
            if char is None:
                char = Character(
                    id=state.character_id,
                    user_id=user.id,
                    name=state.character_name or "冒险者",
                    gender=str(info.get("gender", "未指定") or "未指定"),
                    race=str(info.get("race", "人类") or "人类"),
                    char_class=str(info.get("char_class", "战士") or "战士"),
                    level=int(info.get("level", 1) or 1),
                    hp=int(info.get("hp", 30) or 30),
                    max_hp=int(info.get("max_hp", 30) or 30),
                    mp=int(info.get("mp", 10) or 10),
                    max_mp=int(info.get("max_mp", 10) or 10),
                    xp=int(info.get("xp", 0) or 0),
                    gold=int(info.get("gold", 10) or 10),
                    attributes=dict(info.get("attributes", {}) or {}),
                    inventory={"items": info.get("inventory", []) if isinstance(info.get("inventory"), list) else []},
                )
                db.add(char)
                await db.flush()

            gs = await db.get(GameSession, state.session_id)
            if gs is None:
                gs = GameSession(id=state.session_id, user_id=user.id, character_id=char.id,
                                 status=getattr(state, "status", "active"))
                db.add(gs)
            ws = getattr(state, "world_state", None)
            gs.status = getattr(state, "status", "active")
            gs.current_state = _current_state_payload(state)
            mem = getattr(state, "memory", None)
            gs.summary = (str(getattr(mem, "summary", "") or ""))[:4000]
            gs.world_context = (ws.to_context_compact()[:12000] if ws is not None and hasattr(ws, "to_context_compact") else "")
            db.add(GameEventLog(
                session_id=state.session_id,
                seq=int(getattr(state, "seq", 0) or 0),
                event_type="turn_snapshot",
                data={"location": gs.current_state.get("location", ""),
                      "turn": gs.current_state.get("turn_count", 0)},
            ))
            await db.commit()
        return True
    except Exception as e:
        get_logger("session_store").warning("会话快照写入失败（忽略）: %s", e, exc_info=True)
        return False
