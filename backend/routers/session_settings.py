"""会话设置的读写接口（模型 / API 地址 / 游玩模式 / 思考档位 / API Key）。

从 `backend/routers/world.py` 拆出：会话设置属于"本局运行参数"，
与世界状态/角色状态的增删改查不是同一个域，混在一个模块里会让两边都继续膨胀。
路径与拆分前完全一致（`/api/game/{session_id}/settings`），前端无需改动。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.engine.session import get_session_for_user

router = APIRouter(prefix="/api/game", tags=["settings"])


@router.get("/{session_id}/settings")
async def get_session_settings(session_id: str, username: str = "default"):
    """当前会话设置（不含 API Key）。"""
    state = get_session_for_user(session_id, username)
    return {
        "model_name": state.model_name,
        "base_url": state.base_url,
        "play_mode": (state.character_info or {}).get("play_mode", "deep"),
        "thinking_strength": state.thinking_strength,
    }


@router.patch("/{session_id}/settings")
async def update_session_settings(session_id: str, payload: dict, username: str = "default"):
    """会话设置（模型 / API 地址 / 游玩模式 / 思考档位）。

    只回显非敏感字段：api_key 会被写入会话但**不会**在响应里返回。
    """
    state = get_session_for_user(session_id, username)
    info = state.character_info
    changed: dict = {}

    if payload.get("model_name"):
        state.model_name = str(payload["model_name"])
        changed["model_name"] = state.model_name
    if payload.get("base_url"):
        state.base_url = str(payload["base_url"])
        changed["base_url"] = state.base_url
    if payload.get("api_key"):
        state.api_key = str(payload["api_key"])
        changed["api_key"] = "已更新（不回显）"
    play_mode = str(payload.get("play_mode") or "")
    if play_mode:
        if play_mode not in ("lite", "deep"):
            raise HTTPException(status_code=400, detail="play_mode 仅支持 lite / deep")
        info["play_mode"] = play_mode
        changed["play_mode"] = play_mode
    thinking = str(payload.get("thinking_strength") or "")
    if thinking:
        if thinking not in ("low", "medium", "high"):
            raise HTTPException(status_code=400, detail="thinking_strength 仅支持 low / medium / high")
        state.thinking_strength = thinking
        changed["thinking_strength"] = thinking
    if not changed:
        raise HTTPException(status_code=400, detail="没有可更新的字段")
    return {
        "settings": {
            "model_name": state.model_name,
            "base_url": state.base_url,
            "play_mode": info.get("play_mode", "deep"),
            "thinking_strength": state.thinking_strength,
        },
        "changed": changed,
    }
