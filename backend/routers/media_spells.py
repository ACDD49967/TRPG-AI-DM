"""法术接口：列表/新增/删除/改名，以及 SRD 法术与媒体描述的机翻。

从 `backend/routers/media.py` 拆出；那边只做装配（`main.py` 仍只 include media 一个路由，
OpenAPI 路径与 `media` 标签都不变）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.engine.session import get_session_for_user as _get_session_for_user

router = APIRouter()


@router.get("/api/spells")
async def list_spells_api(username: str = "default", scenario_id: str | None = None):
    from backend.media_manager import list_spells
    return {"spells": list_spells(username, scenario_id)}



@router.post("/api/spells")
async def add_spell_api(payload: dict):
    from backend.media_manager import add_spell, find_spell_exact, update_spell
    username = str(payload.get("username") or "default")
    name = str(payload.get("name") or "未命名法术")
    scenario_id = str(payload.get("scenario_id") or "")
    existing = find_spell_exact(username, scenario_id or None, name)
    changes = {
        "system": str(payload.get("system") or "custom"),
        "description": str(payload.get("description") or ""),
        "level": str(payload.get("level") or "0"),
        "school": str(payload.get("school") or ""),
        "ritual": bool(payload.get("ritual", False)),
        "casting_time": str(payload.get("casting_time") or ""),
        "range": str(payload.get("range") or ""),
        "components": str(payload.get("components") or ""),
        "duration": str(payload.get("duration") or ""),
        "classes": payload.get("classes") or [],
        "scenario_id": scenario_id,
        "tags": payload.get("tags") or ["自建", "法术"],
    }
    if existing:
        item = update_spell(username, existing["id"], changes)
    else:
        item = add_spell(
            username=username,
            name=name,
            system=str(payload.get("system") or "custom"),
            description=str(payload.get("description") or ""),
            level=str(payload.get("level") or "0"),
            school=str(payload.get("school") or ""),
            ritual=bool(payload.get("ritual", False)),
            casting_time=str(payload.get("casting_time") or ""),
            range_=str(payload.get("range") or ""),
            components=str(payload.get("components") or ""),
            duration=str(payload.get("duration") or ""),
            classes=payload.get("classes") or [],
            scenario_id=scenario_id,
            tags=payload.get("tags") or ["自建", "法术"],
        )
    return {"spell": item}



@router.delete("/api/spells/{spell_id}")
async def delete_spell_api(spell_id: str, username: str = "default"):
    from backend.media_manager import delete_spell
    if not delete_spell(username, spell_id):
        raise HTTPException(status_code=404, detail="法术不存在")
    return {"deleted": True}


@router.put("/api/spells/{spell_id}")
async def update_spell_api(spell_id: str, payload: dict, username: str = "default"):
    """编辑法术条目（等级/学派/描述/施法时间/距离/成分/持续时间/职业等）。"""
    from backend.media_manager import update_spell
    changes = {k: v for k, v in payload.items() if k not in ("username",)}
    result = update_spell(username, spell_id, changes)
    if result is None:
        raise HTTPException(status_code=404, detail="法术不存在")
    return {"spell": result}



from backend.media_translate import translate_media, translate_srd_spells

@router.post("/api/game/{session_id}/translate-srd")
async def translate_srd_spells_api(session_id: str, payload: dict, username: str = "default"):
    """使用当前会话的 LLM 配置，批量机翻 SRD 法术为简体中文（实现见 backend.media_translate）。"""
    state = _get_session_for_user(session_id, username)
    return await translate_srd_spells(state, payload)



@router.post("/api/game/{session_id}/translate-media")
async def translate_media_api(session_id: str, payload: dict, username: str = "default"):
    """使用当前会话 LLM 批量机翻地点/生物描述（实现见 backend.media_translate）。"""
    kind = str(payload.get("kind", ""))
    if kind not in ("locations", "bestiary"):
        raise HTTPException(status_code=400, detail="kind 仅支持 locations 或 bestiary")
    state = _get_session_for_user(session_id, username)
    return await translate_media(state, payload, kind)
