"""SSE 事件总线：广播、环形历史、断线重放与打字机推送（从 session.py 拆出）。

每个连接持有独立有界队列；`push_event` 负责广播与历史快照，
`sse_event_generator` 负责首连开场白、重连补发与心跳。
"""
import asyncio
import copy
import json
import time
from collections.abc import AsyncGenerator

from backend.engine.session_state import GameSessionState


# ── SSE 事件格式化工具 ────────────────────────────────────

def _format_sse(event_type: str, data: dict | None = None, seq: int = 0) -> str:
    """将事件格式化为 SSE (Server-Sent Events) 协议格式。

    格式: event: <type>\ndata: <json>\n\n
    """
    payload = json.dumps(data or {}, ensure_ascii=False, default=str)
    if seq:
        return f"id: {seq}\nevent: {event_type}\ndata: {payload}\n\n"
    return f"event: {event_type}\ndata: {payload}\n\n"


async def sse_event_generator(
    state: GameSessionState,
    last_event_id: int = 0,
) -> AsyncGenerator[str, None]:
    """SSE 生成器：广播订阅、断线重放、心跳保活。

    - 每个连接持有独立有界队列，push_event 广播给所有订阅者；
    - 连接建立时按 Last-Event-ID / last_event_seq 从环形历史补发；
    - last_event_id > 0 表示重连：不重新生成开场白，只补事件。
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    state.subscribers.add(queue)
    last_sent = int(last_event_id or 0)

    try:
        if last_event_id <= 0:
            # 首次连接：生成开场白或恢复历史
            if getattr(state, "resumed", False):
                turns = [
                    {"player_input": t.player_input, "dm_response": t.dm_response}
                    for t in state.memory.turns
                ]
                if getattr(state, "opening_text", "").strip():
                    turns.insert(0, {"player_input": "", "dm_response": state.opening_text})
                await push_event(state, "history", {"turns": turns})
                state.resumed = False
            else:
                from backend.engine.dm_agent import generate_opening_scene
                try:
                    await asyncio.wait_for(generate_opening_scene(state), timeout=90)
                except Exception:
                    await push_narrative_token(state, f"欢迎，{state.character_name}。冒险开始了…")

            info = state.character_info
            await push_event(state, "state_update", {
                "hp": info.get("hp", 30),
                "max_hp": info.get("max_hp", 30),
                "mp": info.get("mp", 10),
                "max_mp": info.get("max_mp", 10),
                "xp": info.get("xp", 0),
                "gold": info.get("gold", 10),
                "level": info.get("level", 1),
                "inventory": info.get("inventory", {}).get("items", []) if isinstance(info.get("inventory"), dict) else [],
                "attributes": info.get("attributes", {}),
                "ac": info.get("ac", 12),
                "character_name": state.character_name,
                "race": info.get("race", ""),
                "char_class": info.get("char_class", ""),
                "gender": info.get("gender", ""),
                "game_system": info.get("game_system", "dnd5e"),
                # 账号归属以会话为准：character_info 里可能没有 username，
                # 之前回退成 "default" 会把非 default 玩家的前端状态污染成 default，
                # 导致后续按用户名归属的接口全部 404。
                "username": state.username or info.get("username") or "default",
                "character_image": info.get("character_image", ""),
                "scenario_id": info.get("scenario_id", ""),
                "backstory": info.get("backstory", ""),
                "skill_proficiencies": info.get("skill_proficiencies", []),
                "skills": info.get("skills", {}),
                "saves": info.get("saves", {}),
                "passive_perception": info.get("passive_perception", 10),
                "feats": info.get("feats", []),
                "custom_classes": info.get("custom_classes", []),
                "custom_skills": info.get("custom_skills", []),
                "extra_attributes": info.get("extra_attributes", {}),
                "race_traits": info.get("race_traits", []),
                "class_proficiencies": info.get("class_proficiencies", []),
                "hit_die": info.get("hit_die", ""),
                "san": info.get("san", info.get("max_san", 0)),
                "maxSan": info.get("max_san", info.get("san", 0)),
                "luck": info.get("luck", 0),
                "healing_surges": info.get("healing_surges", 0),
                "max_healing_surges": info.get("max_healing_surges", 0),
                "surge_value": info.get("surge_value", 0),
                "proficiency_bonus": info.get("proficiency_bonus", 2),
                "spell_slots": info.get("spell_slots", []),
                "class_resources": info.get("class_resources", []),
                "known_spells": info.get("known_spells", []),
                "action_points": info.get("action_points", 1),
                "fortitude": info.get("fortitude", 10),
                "reflex": info.get("reflex", 10),
                "will": info.get("will", 10),
                "damage_bonus": info.get("damage_bonus", "0"),
                "build": info.get("build", 0),
            })
            await push_event(state, "end_of_turn", {})
        else:
            # 重连：从环形历史补发缺失事件；订阅之后新产生的事件会在 live queue 中
            replay = [e for e in list(state.event_history) if e[0] > last_event_id]
            for seq, event_type, data in replay:
                if seq <= last_sent:
                    continue
                last_sent = seq
                yield _format_sse(event_type, data, seq)

        while True:
            if state.status != "active" and queue.empty():
                break
            try:
                seq, event_type, data = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                continue
            if seq <= last_sent:
                continue
            last_sent = seq
            yield _format_sse(event_type, data, seq)
    finally:
        state.subscribers.discard(queue)


async def push_event(
    state: GameSessionState,
    event_type: str,
    data: dict | None = None,
):
    """广播一个事件给所有订阅者，并写入环形历史供断线重放。"""
    # 玩家可见事件 = 等待结束；记录到回合指标用于衡量真实等待感
    if event_type in ("narrative", "narrative_flush", "dice_roll", "game_event", "intro"):
        telemetry = getattr(state, "telemetry", None)
        if telemetry is not None:
            try:
                telemetry.mark_first_output()
            except Exception:
                pass
    state.seq += 1
    # 事件历史用于断线重放：必须存快照，否则后续回合修改同一个 dict/list 时，
    # 会把"当时发出的事件"追溯性改写（实测状态效果递减就踩过这个坑）。
    payload = copy.deepcopy(data) if data else {}
    entry = (state.seq, event_type, payload)
    state.last_active_at = time.time()
    state.event_history.append(entry)
    dead: list[asyncio.Queue] = []
    for queue in list(state.subscribers):
        try:
            queue.put_nowait(entry)
        except asyncio.QueueFull:
            # 慢客户端：丢最旧事件，保证队列有界
            try:
                queue.get_nowait()
                queue.put_nowait(entry)
            except Exception:
                dead.append(queue)
    for queue in dead:
        state.subscribers.discard(queue)


async def push_narrative_token(state: GameSessionState, token: str):
    """推送单个叙事 token，用于打字机效果。"""
    await push_event(state, "narrative", {"token": token})


async def push_narrative_flush(state: GameSessionState, full_text: str):
    """推送完整叙事文本，跳过打字机直接显示。"""
    await push_event(state, "narrative_flush", {"full_text": full_text})
