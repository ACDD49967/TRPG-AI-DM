"""账号删除：密码确认、名下内容清理、删后不能登录、别人的内容不受影响。"""
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import httpx


class TestAccountDeletion(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from backend.main import app

        self.app = app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.user = "deltest"
        self.password = "deltest123"

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        from backend import (
            character_card_manager, extension_manager, local_vector_store, media_store, save_manager,
            scenario_store,
        )
        import backend.long_term_memory as ltm

        self.stack.enter_context(patch.object(character_card_manager, "CHAR_ROOT", self.root / "characters"))
        self.stack.enter_context(patch.object(extension_manager, "EXT_ROOT", self.root / "extensions"))
        self.stack.enter_context(patch.object(media_store, "MEDIA_ROOT", self.root / "media"))
        self.stack.enter_context(patch.object(save_manager, "SAVE_ROOT", self.root / "saves"))
        self.stack.enter_context(patch.object(scenario_store, "SCENARIO_DIR", str(self.root / "scenarios")))
        self.stack.enter_context(patch.object(ltm, "VAULT_ROOT", self.root / "memory_vault"))
        self.stack.enter_context(patch.object(local_vector_store, "VECTOR_DB", self.root / "vectors.sqlite3"))

        from backend.knowledge_base import KnowledgeBase
        self.kb = KnowledgeBase(self.root / "kb.json")
        self.stack.enter_context(patch("backend.knowledge_base.get_knowledge_base", return_value=self.kb))

    def client(self):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")

    async def test_delete_requires_password_and_clears_owned_content(self):
        from backend.auth_manager import register_account
        from backend.engine.session import GameSessionState, session_manager
        from backend.engine.world_state import WorldState

        await register_account(self.user, self.password)

        # 造内容：知识库文档（本人 + 别人各一条）、一个用户目录、一个带世界状态文件的内存会话
        self.kb.add_note("删除测试笔记", "内容" * 30, username=self.user)
        other_note = self.kb.add_note("别人的笔记", "内容" * 30, username="someoneelse")
        user_dir = self.root / "characters" / self.user
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "card.json").write_text("{}", encoding="utf-8")

        state = GameSessionState("del-session", "char", "岚", {"hp": 10}, username=self.user)
        state.world_state = WorldState(session_id="del-session", _storage_dir=str(self.root))
        state.world_state.scene.current_location = "测试地点"
        state.world_state.save()
        session_manager._sessions["del-session"] = state
        self.addCleanup(lambda: session_manager._sessions.pop("del-session", None))
        self.assertTrue((self.root / "del-session.json").exists())

        async with self.client() as client:
            wrong = await client.request("DELETE", "/api/auth/user",
                                         json={"username": self.user, "password": "wrong-password"})
            still_exists = await client.get(f"/api/auth/check?username={self.user}")

        self.assertEqual(wrong.status_code, 401, "密码不对不能删号")
        self.assertTrue(still_exists.json()["exists"], "密码错时账号与内容都该原样保留")
        self.assertTrue(user_dir.exists())

        async with self.client() as client:
            deleted = await client.request("DELETE", "/api/auth/user",
                                           json={"username": self.user, "password": self.password})
            gone = await client.get(f"/api/auth/check?username={self.user}")
            relogin = await client.post("/api/auth/login",
                                        json={"username": self.user, "password": self.password})

        self.assertEqual(deleted.status_code, 200)
        body = deleted.json()
        self.assertTrue(body["deleted"])
        self.assertEqual(body["cleanup"]["knowledge_docs"], 1)
        self.assertEqual(body["cleanup"]["sessions"], 1)
        self.assertIn(str(user_dir), body["cleanup"]["dirs"])

        self.assertFalse(gone.json()["exists"])
        self.assertEqual(relogin.status_code, 401, "删号后原密码不能再用")
        self.assertFalse(user_dir.exists(), "用户名下的内容目录要一起删")
        self.assertFalse((self.root / "del-session.json").exists(), "会话的世界状态文件要一起删")
        self.assertNotIn("del-session", session_manager._sessions)
        self.assertIsNotNone(self.kb.get_document(other_note["id"], "someoneelse"),
                             "别人的知识库文档不能被顺手删掉")


if __name__ == "__main__":
    unittest.main()
