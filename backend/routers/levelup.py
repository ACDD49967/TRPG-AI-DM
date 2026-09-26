"""升级选择（属性提升 / 专长）接口。

升级后的选择此前只能靠 DM 调工具写入：玩家要等一整轮 LLM 回复，还可能被忘掉。
这里提供确定性接口，前端角色面板可直接选择。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.engine import character_state
from backend.engine.feats import FEATS_LIST
from backend.engine.game_systems import get_dnd5_asi_levels
from backend.engine.session import get_session_for_user

router = APIRouter(prefix="/api/game", tags=["levelup"])

_ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
_ABILITY_NAMES = {"str": "力量", "dex": "敏捷", "con": "体质",
                  "int": "智力", "wis": "感知", "cha": "魅力"}


class LevelUpRequest(BaseModel):
    kind: str = Field(pattern="^(asi|feat)$")
    ability: str | None = None
    ability2: str | None = None
    feat_id: str | None = None


def _taken_levels(state) -> set[int]:
    raw = (state.character_info or {}).get("asi_taken_levels") or []
    levels: set[int] = set()
    for item in raw:
        try:
            levels.add(int(item))
        except (TypeError, ValueError):
            continue
    return levels


def pending_asi_level(state) -> int | None:
    """当前是否有待选择的属性提升/专长等级（仅 5e）。"""
    info = state.character_info or {}
    if str(info.get("game_system") or "") != "dnd5e":
        return None
    try:
        level = int(info.get("level", 1) or 1)
    except (TypeError, ValueError):
        return None
    if level in get_dnd5_asi_levels(info.get("char_class", "")) and level not in _taken_levels(state):
        return level
    return None


def levelup_state(state) -> dict:
    info = state.character_info or {}
    return {
        "pending_level": pending_asi_level(state),
        "taken_levels": sorted(_taken_levels(state)),
        "feats": [{"id": f.get("id"), "name": f.get("name"), "desc": f.get("desc", "")}
                  for f in FEATS_LIST],
        "abilities": [{"key": k, "name": _ABILITY_NAMES[k]} for k in _ABILITIES],
        "current": {
            "feats": [f.get("name") if isinstance(f, dict) else str(f)
                      for f in (info.get("feats") or [])],
            "attributes": dict(info.get("attributes") or {}),
        },
    }


@router.get("/{session_id}/levelup")
async def get_levelup_state(session_id: str, username: str = "default"):
    """返回待选择的升级、可选专长目录与当前属性。"""
    state = get_session_for_user(session_id, username)
    return levelup_state(state)


@router.post("/{session_id}/levelup")
async def apply_levelup(session_id: str, payload: LevelUpRequest, username: str = "default"):
    """应用一次属性提升或专长选择。"""
    state = get_session_for_user(session_id, username)
    level = pending_asi_level(state)
    if level is None:
        raise HTTPException(status_code=400, detail="当前等级没有待分配的属性提升或专长")

    info = state.character_info
    if payload.kind == "feat":
        feat = next((f for f in FEATS_LIST if str(f.get("id")) == str(payload.feat_id)), None)
        if feat is None:
            raise HTTPException(status_code=400, detail="未找到该专长")
        result = await character_state._exec_update_state({
            "changes": {"feats_add": {"id": feat["id"], "name": feat["name"],
                                      "description": feat.get("desc", "")}},
            "reason": f"{level}级专长：{feat['name']}",
        }, state)
    else:
        ability = str(payload.ability or "")
        ability2 = str(payload.ability2 or "")
        if ability not in _ABILITIES:
            raise HTTPException(status_code=400, detail="请选择要提升的属性")
        if ability2 and ability2 not in _ABILITIES:
            raise HTTPException(status_code=400, detail="第二项属性不合法")
        if ability2 and ability2 == ability:
            raise HTTPException(status_code=400, detail="两项属性不能相同")
        deltas = {ability: 1, ability2: 1} if ability2 else {ability: 2}
        result = await character_state._exec_update_state({
            "changes": {"attributes_add": deltas},
            "reason": f"{level}级属性提升",
        }, state)

    info["asi_taken_levels"] = sorted(_taken_levels(state) | {level})
    applied = {
        "level": level,
        "feats": [f.get("name") if isinstance(f, dict) else str(f) for f in (info.get("feats") or [])],
        "attributes": dict(info.get("attributes") or {}),
        "asi_taken_levels": info["asi_taken_levels"],
        "message": result,
    }
    from backend.engine.session import push_event
    await push_event(state, "state_update", applied)
    return {"applied": applied, **levelup_state(state)}
