"""后台剧情的落账：把 LLM 给出的一拍事件写进世界状态（旗标/幕后事件/笔记）。

从 `backend/engine/background_events.py` 拆出。
"""
from __future__ import annotations

import json
from typing import Any

from backend.engine.background_prompt import (
    ALLOWED_FLAG_STATUS, _extract_json_array, _hidden_threads,
)
from backend.engine.world_state import WorldState


def _apply_background_beat(state: Any, ws: WorldState, beat: dict) -> dict | None:
    """把一条幕后进展写入记忆与世界状态。返回规范化后的事件 dict。"""
    thread_key = str(beat.get("thread_key") or beat.get("key") or "").strip()
    event = str(beat.get("event") or "").strip()
    if not thread_key and not event:
        return None
    status = str(beat.get("status") or "进行中").strip()
    if status not in ALLOWED_FLAG_STATUS:
        status = "进行中"
    impact = str(beat.get("impact") or "").strip()
    public_hint = str(beat.get("public_hint") or "").strip()[:120]
    affected_npcs = [str(x).strip() for x in (beat.get("affected_npcs") or []) if str(x).strip()]
    affected_locations = [str(x).strip() for x in (beat.get("affected_locations") or []) if str(x).strip()]

    mem = getattr(state, "memory", None)
    if mem is not None:
        if thread_key:
            mem.update_hidden_thread(
                key=thread_key,
                status=status,
                progress=event,
                turn=ws.turn_count,
            )
            # 若刚创建，补全描述与关联
            existing = next((h for h in mem.hidden_threads if h.get("key") == thread_key), None)
            if existing and not existing.get("description"):
                existing["description"] = event
            if existing:
                for name in affected_npcs:
                    if name not in (existing.get("related_npcs") or []):
                        existing.setdefault("related_npcs", []).append(name)
                for loc in affected_locations:
                    if loc not in (existing.get("related_locations") or []):
                        existing.setdefault("related_locations", []).append(loc)
        if impact:
            for npc_name in affected_npcs:
                mem.add_character_impact(name=npc_name, impact=impact, event=event, turn=ws.turn_count)
            if not affected_npcs:
                mem.add_major_event(
                    title=thread_key or event[:20],
                    description=event,
                    impact=impact,
                    turn=ws.turn_count,
                    npcs=affected_npcs,
                    locations=affected_locations,
                )

    # 同步到世界状态旗标（暗线默认对玩家隐藏）
    if thread_key:
        ws.set_flag(
            key=thread_key,
            status=status,
            description=event,
            consequence=impact,
            visible=False,
        )

    event_entry = {
        "turn": ws.turn_count,
        "thread_key": thread_key,
        "event": event,
        "impact": impact,
        "affected_npcs": affected_npcs,
        "affected_locations": affected_locations,
        "public_hint": public_hint,
        "visible": bool(public_hint),
    }
    ws.add_background_event(event_entry)
    return event_entry


def _fallback_background_plot(state: Any) -> list[dict]:
    """无 LLM/解析失败时的兜底：推进第一条未完成暗线，不产生新内容。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return []
    mem = getattr(state, "memory", None)
    threads = _hidden_threads(state)
    if not threads:
        return []
    target = None
    for t in threads:
        if t.get("status") in ("未触发", "进行中"):
            target = t
            break
    if target is None:
        return []
    key = target.get("key", "")
    status = "进行中" if target.get("status") == "未触发" else "进行中"
    event = f"{key}在暗中继续发展（第{ws.turn_count}轮）"
    beat = {
        "thread_key": key,
        "event": event,
        "impact": "",
        "affected_npcs": target.get("related_npcs", []) or [],
        "affected_locations": target.get("related_locations", []) or [],
        "status": status,
        "public_hint": "",
    }
    entry = _apply_background_beat(state, ws, beat)
    if mem is not None and entry:
        # 兜底只更新进度，不额外添加大事件
        mem.update_hidden_thread(key=key, status=status, progress=event, turn=ws.turn_count)
    return [entry] if entry else []
