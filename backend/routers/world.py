"""世界状态与角色状态的增删改查接口。

后端化的一部分：这些改动此前**只能**通过主 DM 的工具调用产生，
前端/脚本没有写入通道。这里的读写复用同一批工具处理器
（`world_tools._exec_update_world_state` / `character_state._exec_update_state`），
所以规则、事件推送、世界状态落盘与 DM 走的是同一条路径，不会出现两套逻辑。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.engine.session import get_session_for_user

router = APIRouter(prefix="/api/game", tags=["world"])


def _state_or_404(session_id: str, username: str):
    return get_session_for_user(session_id, username)


@router.get("/{session_id}/world")
async def get_world_state(session_id: str, username: str = "default"):
    """世界状态快照：场景 / NPC / 地点 / 剧情旗标 + 战场态势与先攻。"""
    from backend.engine import battlefield, initiative

    state = _state_or_404(session_id, username)
    ws = getattr(state, "world_state", None)
    if ws is None:
        raise HTTPException(status_code=404, detail="该会话没有世界状态")
    scene = ws.scene
    return {
        "scene": {
            "location": scene.current_location, "time": scene.current_time,
            "weather": scene.weather, "atmosphere": scene.atmosphere,
            "day_count": scene.day_count,
            "visible_npcs_here": list(scene.visible_npcs_here or []),
            "light": getattr(scene, "light", ""),
            "light_source": getattr(scene, "light_source", ""),
        },
        "npcs": [
            {
                "name": n.name, "role": n.role, "location": n.location, "attitude": n.attitude,
                "alive": n.alive, "hp": n.hp, "max_hp": n.max_hp, "ac": n.ac, "level": n.level,
                "importance": getattr(n, "importance", ""), "discovered": n.discovered,
                "personality": n.personality, "motivation": n.motivation, "secret": n.secret,
                "traits": list(n.traits or []),
            }
            for n in (ws.npcs or [])
        ],
        "locations": [
            {
                "name": loc.name, "description": loc.description, "status": loc.status,
                "type": loc.type, "discovered": loc.discovered,
                "related_npcs": list(loc.related_npcs or []),
            }
            for loc in (ws.locations or [])
        ],
        "plot_flags": [
            {
                "key": f.key, "status": f.status, "description": f.description,
                "consequence": f.consequence, "visible": f.visible,
            }
            for f in (ws.plot_flags or [])
        ],
        "notes": [
            {
                "target": n.target, "target_type": n.target_type,
                "comment": n.character_comment, "clue": n.clue,
                "turn": n.turn_added, "visible": bool(n.visible),
            }
            for n in (ws.character_notes or [])
        ],
        # world_rules 在模型里是纯文本（WorldState.world_rules: str）；
        # 历史数据可能是 dict，这里两种都接受，别让 dict(字符串) 把整个快照打成 500。
        "world_rules": ws.world_rules if isinstance(ws.world_rules, dict) else str(ws.world_rules or ""),
        "battlefield": battlefield.payload(state),
        "initiative": initiative.payload(state),
        "in_combat": bool(getattr(state, "in_combat", False)),
    }


@router.post("/{session_id}/world")
async def update_world_state(session_id: str, payload: dict, username: str = "default"):
    """世界状态增删改：与 DM 的 update_world_state 工具同一处理器。

    body: {"action": "add_npc|update_npc|remove_npc|add_location|update_location|
            remove_location|set_flag|remove_flag|update_scene|set_world_rule|
            add_note|update_note|remove_character_note",
           "target": "名称", "changes": {...}, "reason": "..."}
    """
    from backend.engine.world_tools import _exec_update_world_state

    state = _state_or_404(session_id, username)
    if getattr(state, "world_state", None) is None:
        raise HTTPException(status_code=404, detail="该会话没有世界状态")
    action = str(payload.get("action") or "")
    if not action:
        raise HTTPException(status_code=400, detail="缺少 action")
    result = await _exec_update_world_state(
        {"action": action, "target": payload.get("target") or "",
         "changes": payload.get("changes") or {}, "reason": payload.get("reason") or "接口修改"},
        state)
    return {"result": result, "world": await get_world_state(session_id, username)}


@router.get("/{session_id}/state")
async def get_character_state(session_id: str, username: str = "default"):
    """角色状态快照（角色卡 + 运行期状态），供前端编辑器读取。"""
    state = _state_or_404(session_id, username)
    info = dict(state.character_info or {})
    info.setdefault("hp", 0)
    return {
        "character_name": state.character_name,
        "character_info": info,
        "dying": bool(getattr(state, "dying", False)),
        "character_dead": bool(getattr(state, "character_dead", False)),
        "in_combat": bool(getattr(state, "in_combat", False)),
        "conditions": info.get("conditions") or [],
        "concentration": info.get("concentration"),
        "exhaustion": int(info.get("exhaustion", 0) or 0),
    }


@router.post("/{session_id}/state")
async def update_character_state(session_id: str, payload: dict, username: str = "default"):
    """角色状态增删改：与 DM 的 update_state 工具同一处理器。

    body: {"changes": {"hp": -5, "conditions_add": ["中毒"], "damage_resistances_add": ["火焰"],
                       "class_resource:ki_points": {"current": 2}, "exhaustion": 1, ...},
           "reason": "..."}
    """
    from backend.engine.character_state import _exec_update_state

    state = _state_or_404(session_id, username)
    changes = payload.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise HTTPException(status_code=400, detail="缺少 changes（要修改的字段）")
    result = await _exec_update_state(
        {"changes": changes, "reason": payload.get("reason") or "接口修改"}, state)
    return {"result": result, "state": await get_character_state(session_id, username)}
