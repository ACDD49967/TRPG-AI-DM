"""角色与 NPC 图片接口（含把图片写回会话状态）。

从 `backend/routers/media.py` 拆出；那边只做装配（`main.py` 仍只 include media 一个路由，
OpenAPI 路径与 `media` 标签都不变）。
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.engine.session import (
    get_session_for_user as _get_session_for_user,
    push_event,
)

router = APIRouter()


@router.post("/api/media/character")
async def upload_character_image_pre(username: str = Form("default"), file: UploadFile = File(...)):
    """创建角色前上传角色图片，返回可用的图片路径。"""
    from backend.media_manager import save_image
    image_path = save_image(username, await file.read(), file.filename or "character.png")
    return {"image_path": image_path}



@router.post("/api/game/{session_id}/image")
async def upload_character_image(session_id: str, file: UploadFile = File(...), username: str = Form("default")):
    """上传当前角色图片。"""
    from backend.media_manager import save_image
    state = _get_session_for_user(session_id, username)
    data = await file.read()
    image_path = save_image(state.username, data, file.filename or "character.png")
    state.character_info["character_image"] = image_path
    await push_event(state, "state_update", {"character_image": image_path})
    return {"image_path": image_path}



@router.post("/api/game/{session_id}/npc")
async def add_npc_api(session_id: str, payload: dict, username: str = "default"):
    """DM 手动为当前剧本新增一个 NPC/角色。"""
    state = _get_session_for_user(session_id, username)
    from backend.engine.world_state import NpcEntry, WorldState
    ws = getattr(state, "world_state", None) or WorldState(session_id=session_id)
    npc = NpcEntry(
        name=str(payload.get("name") or "未命名NPC"),
        race=str(payload.get("race") or ""),
        role=str(payload.get("role") or "未知身份"),
        location=str(payload.get("location") or ws.scene.current_location),
        attitude=str(payload.get("attitude") or "中立"),
        hp=int(payload.get("hp") or 10),
        max_hp=int(payload.get("hp") or 10),
        ac=int(payload.get("ac") or 10),
        level=int(payload.get("level") or 1),
        attributes=payload.get("attributes") or {},
        skills=payload.get("skills") or [],
        traits=payload.get("traits") or [],
    )
    ws.add_npc(npc)
    state.world_state = ws
    await push_event(state, "journal_update", ws.to_player_journal())
    return {"npc": {"name": npc.name, "role": npc.role}}



@router.post("/api/game/{session_id}/npc/image")
async def upload_npc_image(session_id: str, npc_name: str = Form(...), file: UploadFile = File(...), username: str = Form("default")):
    """为当前剧本中的 NPC 上传自定义图片。"""
    state = _get_session_for_user(session_id, username)
    from backend.media_manager import save_image
    from backend.engine.world_state import WorldState
    ws = getattr(state, "world_state", None) or WorldState(session_id=session_id)
    npc = ws.get_npc(npc_name)
    if npc is None:
        raise HTTPException(status_code=404, detail="NPC 不存在")
    image_path = save_image(state.username, await file.read(), file.filename or "npc.png")
    npc.image_path = image_path
    ws.save()
    state.world_state = ws
    await push_event(state, "journal_update", ws.to_player_journal())
    return {"image_path": image_path}
