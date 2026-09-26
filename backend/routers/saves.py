"""存档列表、手动存档、读档与新会话恢复。"""
from __future__ import annotations


from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.engine.session import (
    get_session_for_user,
    session_manager,
)

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["saves"])



@router.delete("/api/saves/{save_id}")
async def delete_save_api(save_id: str, username: str = "default"):
    from backend.save_manager import delete_save
    if not delete_save(username, save_id):
        raise HTTPException(status_code=404, detail="存档不存在")
    return {"deleted": True}


@router.put("/api/saves/{save_id}")
async def rename_save_api(save_id: str, payload: dict, username: str = "default"):
    """给存档改标签（存档 id 与文件不变，只改展示名）。"""
    from backend.save_manager import rename_save
    label = str(payload.get("label") or payload.get("title") or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="缺少 label")
    save = rename_save(username, save_id, label)
    if save is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return {"save": save}



@router.get("/api/saves")
async def list_saves_api(username: str = "default"):
    from backend.save_manager import list_saves
    return {"saves": list_saves(username)}



@router.post("/api/game/{session_id}/save")
async def manual_save_api(session_id: str, payload: dict, username: str = "default"):
    """手动存档当前会话。"""
    from backend.save_manager import create_save
    state = _get_session_for_user(session_id, username)
    save = create_save(state, label=str(payload.get("label") or "手动存档"), auto=False)
    return {"save": save}



@router.post("/api/saves/load")
async def load_save_api(payload: dict):
    """载入存档：恢复为新会话并返回 SSE 地址。"""
    from backend.save_manager import load_save, restore_state_from_save
    username = str(payload.get("username") or "default")
    save_id = str(payload.get("save_id") or "")
    save_data = load_save(username, save_id)
    if save_data is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, session_id = restore_state_from_save(save_data)
    state.resumed = True
    # 旧存档兼容：按当前规则系统补全职业资源与行动点
    try:
        _ci = state.character_info or {}
        if _ci.get("game_system") == "dnd5e" and not _ci.get("class_resources"):
            from backend.engine.game_systems import get_dnd5_class_resources
            _ci["class_resources"] = get_dnd5_class_resources(
                _ci.get("char_class", ""), _ci.get("attributes", {}), _ci.get("level", 1))
        elif _ci.get("game_system") == "dnd4e":
            _ci.setdefault("action_points", 1)
            _ci.setdefault("class_resources", [])
        _ci.setdefault("known_spells", [])
    except Exception:
        pass
    # 用前端当前配置覆盖/补全存档中的模型配置，避免旧存档缺模型导致无法读档
    if payload.get("model_name"):
        state.model_name = str(payload["model_name"])
    if payload.get("api_key"):
        state.api_key = str(payload["api_key"])
    if payload.get("base_url"):
        state.base_url = str(payload["base_url"])
    if not (state.model_name or settings.LLM_MODEL_NAME):
        raise HTTPException(status_code=400, detail="存档未包含模型配置，请重新开始并选择模型")
    session_manager._sessions[session_id] = state
    # P1-20：读档生成新 session_id，登记到 DB，避免孤儿会话。
    try:
        from backend.session_store import persist_session_snapshot
        await persist_session_snapshot(state)
    except Exception:
        pass
    # 载入存档后重新激活扩展包，确保 RAG 知识库中有对应内容
    if state.character_info.get("extension_ids"):
        from backend.extension_manager import activate_extensions_into_kb
        activate_extensions_into_kb(username, state.character_info["extension_ids"])
    # 从 SQLite 加载跨存档长期记忆
    try:
        from backend.long_term_memory import load_facts
        for fact in load_facts(username):
            state.memory.add_world_fact(fact)
    except Exception:
        pass
    # 返回可直接用于前端状态恢复的 status（含正确 username 与 camelCase 字段）
    _ci = state.character_info or {}
    _status_keys = [
        "hp", "max_hp", "mp", "max_mp", "xp", "gold", "level", "ac", "inventory", "attributes",
        "character_name", "race", "char_class", "gender", "game_system", "username",
        "character_image", "scenario_id", "backstory", "skill_proficiencies", "skills", "saves",
        "passive_perception", "feats", "custom_classes", "custom_skills", "extra_attributes",
        "race_traits", "class_proficiencies", "hit_die", "san", "max_san", "luck",
        "healing_surges", "max_healing_surges", "surge_value", "speed", "proficiency_bonus",
        "spell_slots", "class_resources", "known_spells", "action_points", "fortitude",
        "reflex", "will", "damage_bonus", "build", "exhaustion",
        "damage_resistances", "damage_immunities", "damage_vulnerabilities",
    ]
    status = {k: _ci.get(k) for k in _status_keys if k in _ci}
    status["username"] = state.username or "default"
    status["character_name"] = state.character_name or status.get("character_name", "")
    # 兼容后端历史格式：inventory 可能是 {"items":[...]}，前端需要数组
    if isinstance(status.get("inventory"), dict):
        status["inventory"] = status["inventory"].get("items") or []
    for snake, camel in (("max_hp", "maxHp"), ("max_mp", "maxMp"), ("max_san", "maxSan")):
        if snake in status:
            status[camel] = status.pop(snake)
    return {
        "session_id": session_id,
        "character_id": state.character_id,
        "username": state.username or "default",
        "status": status,
        "sse_url": f"/api/game/{session_id}/stream",
    }
