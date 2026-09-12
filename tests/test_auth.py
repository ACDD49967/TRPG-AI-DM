# -*- coding: utf-8 -*-
"""本地账号注册/登录测试（使用临时 SQLite，不污染主库）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.database import Base


class TestAuthManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "auth_test.db"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        import backend.auth_manager as am
        self.am = am
        self._old_session = am.async_session
        am.async_session = self.Session

    async def asyncTearDown(self):
        self.am.async_session = self._old_session
        await self.engine.dispose()
        self.tmp.cleanup()

    async def test_register_login_flow(self):
        created = await self.am.register_account("霍华德", "secret123")
        self.assertEqual(created["username"], "霍华德")

        with self.assertRaises(self.am.UsernameTaken):
            await self.am.register_account("霍华德", "another123")

        with self.assertRaises(self.am.AuthError):
            await self.am.login_account("霍华德", "wrong-password")

        logged = await self.am.login_account("霍华德", "secret123")
        self.assertEqual(logged["username"], "霍华德")
        self.assertTrue(await self.am.account_exists("霍华德"))
        self.assertFalse(await self.am.account_exists("不存在"))

    async def test_invalid_input(self):
        with self.assertRaises(self.am.InvalidAuthInput):
            await self.am.register_account("a", "secret123")
        with self.assertRaises(self.am.InvalidAuthInput):
            await self.am.register_account("用户", "123")


if __name__ == "__main__":
    unittest.main()
