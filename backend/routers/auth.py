"""本地账号注册/登录与健康检查。"""
from __future__ import annotations


from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.engine.session import (
    get_session_for_user,
    session_manager,
)
from backend.schemas import (
    AuthRequest,
    AuthResponse,
)

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["auth"])



@router.post("/api/auth/register", response_model=AuthResponse)
async def auth_register(payload: AuthRequest):
    """注册本地账号：用户名 + 密码。"""
    from backend.auth_manager import InvalidAuthInput, UsernameTaken, register_account
    try:
        data = await register_account(payload.username, payload.password)
    except UsernameTaken as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidAuthInput as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AuthResponse(username=data["username"], message="注册成功")



@router.post("/api/auth/login", response_model=AuthResponse)
async def auth_login(payload: AuthRequest):
    """登录本地账号：用户名 + 密码。"""
    from backend.auth_manager import AuthError, InvalidAuthInput, login_account
    try:
        data = await login_account(payload.username, payload.password)
    except InvalidAuthInput as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return AuthResponse(username=data["username"], message="登录成功")



@router.get("/api/auth/check")
async def auth_check(username: str = ""):
    """检查账号是否存在，用于登录页提示/记住账号校验。"""
    from backend.auth_manager import account_exists
    return {"exists": await account_exists(username)}


@router.delete("/api/auth/user")
async def auth_delete_user(payload: dict):
    """删除账号及其名下全部内容（需要密码确认）。

    顺序是先删账号行、再清内容：宁可留下孤儿目录，也不要清了一半之后
    这个账号还能登录进来、看到被清空一半的世界。
    """
    from backend.account_data import delete_account_data
    from backend.auth_manager import AuthError, delete_account

    username = str(payload.get("username") or "")
    password = str(payload.get("password") or "")
    try:
        name = await delete_account(username, password)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    cleanup = await delete_account_data(name)
    return {"deleted": True, "username": name, "cleanup": cleanup}



@router.get("/api/health")
async def health_check():
    """健康检查端点。"""
    from backend.engine.warmup import status as warmup_status
    return {
        "status": "ok",
        "active_sessions": len(session_manager._sessions),
        "model": settings.MODEL_NAME,
        "warmup": warmup_status(),
    }
