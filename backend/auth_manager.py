# -*- coding: utf-8 -*-
"""本地账号认证：用户名 + 密码注册/登录。

安全说明：
- 密码只保存 PBKDF2-HMAC-SHA256 派生值 + 随机盐，不保存明文；
- 账号表独立于游戏数据表（user_accounts），由 create_all 自动建表；
- 本项目是本地单机应用，接口未做全站 token 鉴权；登录主要用于前端入口隔离与账号记忆。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import datetime

from sqlalchemy import select

from backend.database import async_session
from backend.models import UserAccount

_USERNAME_RE = re.compile(r"^[0-9A-Za-z_\-\u4e00-\u9fff]{2,32}$")
_PBKDF2_ITERATIONS = 210_000


class AuthError(Exception):
    """认证失败基类。"""


class InvalidAuthInput(AuthError):
    """用户名/密码格式不合法。"""


class UsernameTaken(AuthError):
    """用户名已存在。"""


def _normalize_username(username: str | None) -> str:
    return (username or "").strip()


def validate_username(username: str | None) -> str:
    name = _normalize_username(username)
    if not _USERNAME_RE.match(name):
        raise InvalidAuthInput("用户名需为 2-32 位，仅支持中文、字母、数字、下划线、连字符")
    return name


def validate_password(password: str | None) -> str:
    value = password or ""
    if len(value) < 6 or len(value) > 128:
        raise InvalidAuthInput("密码长度需为 6-128 位")
    return value


def _hash_password(password: str, salt_hex: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        _PBKDF2_ITERATIONS,
    )
    return digest.hex()


async def register_account(username: str, password: str) -> dict:
    name = validate_username(username)
    password = validate_password(password)
    async with async_session() as db:
        existing = await db.scalar(select(UserAccount).where(UserAccount.username == name))
        if existing is not None:
            raise UsernameTaken("用户名已存在")
        salt = os.urandom(16).hex()
        account = UserAccount(
            username=name,
            password_salt=salt,
            password_hash=_hash_password(password, salt),
        )
        db.add(account)
        await db.commit()
        return {"username": name, "created_at": account.created_at.isoformat() if account.created_at else ""}


async def login_account(username: str, password: str) -> dict:
    # 登录失败统一提示，避免泄露“用户名是否存在”。
    name = _normalize_username(username)
    password = password or ""
    async with async_session() as db:
        account = await db.scalar(select(UserAccount).where(UserAccount.username == name))
        if account is None:
            raise AuthError("用户名或密码错误")
        expected = _hash_password(password, account.password_salt)
        if not hmac.compare_digest(expected, account.password_hash):
            raise AuthError("用户名或密码错误")
        account.last_login_at = datetime.now()
        await db.commit()
        return {"username": account.username, "last_login_at": account.last_login_at.isoformat()}


async def account_exists(username: str | None) -> bool:
    name = _normalize_username(username)
    if not name:
        return False
    async with async_session() as db:
        return await db.scalar(select(UserAccount.id).where(UserAccount.username == name)) is not None
