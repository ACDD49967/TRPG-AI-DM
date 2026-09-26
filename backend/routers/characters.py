"""角色卡增删改查。"""
from __future__ import annotations


from fastapi import APIRouter, HTTPException

from backend.engine.session import (
    get_session_for_user,
)

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["characters"])



# ── 角色卡管理 ──

@router.get("/api/characters")
async def list_character_cards_api(username: str = "default"):
    from backend.character_card_manager import list_character_cards
    return {"cards": list_character_cards(username)}



@router.post("/api/characters")
async def save_character_card_api(payload: dict):
    from backend.character_card_manager import save_character_card
    username = str(payload.get("username") or "default")
    card = save_character_card(username, payload.get("card") or {})
    return {"card": card}



@router.get("/api/characters/{card_id}")
async def get_character_card_api(card_id: str, username: str = "default"):
    from backend.character_card_manager import get_character_card
    card = get_character_card(username, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="角色卡不存在")
    return {"card": card}



@router.put("/api/characters/{card_id}")
async def update_character_card_api(card_id: str, payload: dict):
    from backend.character_card_manager import save_character_card
    username = str(payload.get("username") or "default")
    card = save_character_card(username, payload.get("card") or {}, card_id=card_id)
    return {"card": card}



@router.delete("/api/characters/{card_id}")
async def delete_character_card_api(card_id: str, username: str = "default"):
    from backend.character_card_manager import delete_character_card
    if not delete_character_card(username, card_id):
        raise HTTPException(status_code=404, detail="角色卡不存在")
    return {"deleted": True}
