"""长期记忆的增删改查：接口 + 存储层（索引 / Markdown 页面 / 语义事实三者一致）。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from backend import long_term_memory as ltm
from backend.memory_manage import delete_memory, load_memory, update_memory
from backend.memory_store import store_memory


class MemoryCrudBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.stack = __import__("contextlib").ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(ltm, "VAULT_ROOT", root / "memory_vault"))
        self.stack.enter_context(patch.object(ltm, "DB_PATH", root / "ltm.db"))
        from backend.long_term_memory import _conn

        _conn().close()  # 建表（首次连接会初始化 schema）；立刻关掉，否则 Windows 上占住临时目录
        self.user = "memcrud"


class TestMemoryStore(MemoryCrudBase):
    def test_create_read_update_delete(self):
        mem_id = store_memory(self.user, "队伍旗帜是折断的鹿角", memory_type="semantic")
        self.assertTrue(mem_id)
        loaded = load_memory(self.user, mem_id)
        self.assertEqual(loaded["content"], "队伍旗帜是折断的鹿角")
        self.assertTrue(loaded["vault_path"])
        self.assertTrue(Path(loaded["vault_path"]).exists(), "Markdown 记忆页应落盘")

        updated = update_memory(self.user, mem_id, content="队伍旗帜换成了灰狼头")
        self.assertIsNotNone(updated)
        self.assertEqual(updated["content"], "队伍旗帜换成了灰狼头")
        self.assertNotEqual(updated["id"], mem_id, "id 是内容哈希，改正文即换 id")
        self.assertIsNone(load_memory(self.user, mem_id), "旧记忆应被删掉")
        self.assertFalse(Path(loaded["vault_path"]).exists(), "旧 Markdown 页应清理")

        self.assertTrue(delete_memory(self.user, updated["id"]))
        self.assertIsNone(load_memory(self.user, updated["id"]))
        self.assertFalse(delete_memory(self.user, updated["id"]), "重复删除返回 False")

    def test_semantic_fact_is_removed_with_the_memory(self):
        mem_id = store_memory(self.user, "镇长承诺给一百金币", memory_type="semantic")
        self.assertIn("镇长承诺给一百金币", ltm.load_facts(self.user))
        delete_memory(self.user, mem_id)
        self.assertNotIn("镇长承诺给一百金币", ltm.load_facts(self.user),
                         "删记忆要连语义事实一起清（否则检索还能召回）")

    def test_update_without_changes_keeps_the_same_id(self):
        mem_id = store_memory(self.user, "北门夜里换岗", memory_type="episodic")
        same = update_memory(self.user, mem_id)
        self.assertEqual(same["id"], mem_id)


class TestMemoryRoutes(MemoryCrudBase, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        super().setUp()
        from backend.main import app

        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                        base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_routes_cover_crud(self):
        created = await self.client.post("/api/memories", json={
            "username": self.user, "content": "桥下的伏兵已经撤离",
            "memory_type": "episodic", "importance": 0.8})
        self.assertEqual(created.status_code, 200, created.text)
        mem_id = created.json()["id"]

        listed = await self.client.get(f"/api/memories?username={self.user}")
        self.assertEqual(listed.status_code, 200)
        contents = [m["content"] for m in listed.json()["memories"]]
        self.assertIn("桥下的伏兵已经撤离", contents)
        self.assertNotIn("vault_path", listed.json()["memories"][0], "本地路径不外泄")

        updated = await self.client.put(f"/api/memories/{mem_id}", json={
            "username": self.user, "content": "桥下的伏兵又回来了"})
        self.assertEqual(updated.status_code, 200, updated.text)
        new_id = updated.json()["memory"]["id"]
        self.assertEqual(updated.json()["memory"]["content"], "桥下的伏兵又回来了")

        deleted = await self.client.delete(f"/api/memories/{new_id}?username={self.user}")
        self.assertEqual(deleted.status_code, 200)
        gone = await self.client.delete(f"/api/memories/{new_id}?username={self.user}")
        self.assertEqual(gone.status_code, 404, "删过的记忆再删应 404")
        after = await self.client.get(f"/api/memories?username={self.user}")
        self.assertNotIn("桥下的伏兵又回来了",
                         [m["content"] for m in after.json()["memories"]])

    async def test_missing_content_is_rejected(self):
        r = await self.client.post("/api/memories", json={"username": self.user, "content": ""})
        self.assertEqual(r.status_code, 400)
        u = await self.client.put("/api/memories/nope",
                                  json={"username": self.user, "content": "x"})
        self.assertEqual(u.status_code, 404)


class TestForgetMemoryTool(MemoryCrudBase, unittest.IsolatedAsyncioTestCase):
    """DM 侧：记错的事实要能删掉（此前只有创建与检索）。"""

    async def asyncSetUp(self):
        super().setUp()
        from backend.engine.session import GameSessionState

        self.state = GameSessionState("mem-tool", "char", "岚", {"hp": 10, "max_hp": 10},
                                      username=self.user)
        self.state.turn_tool_results = {}

    async def test_tool_deletes_by_content_snippet(self):
        from backend.engine import dm_agent as dm
        from backend.engine.tools import DM_TOOLS

        self.assertIn("forget_memory", {t["function"]["name"] for t in DM_TOOLS})
        mem_id = store_memory(self.user, "镇长承诺给一百金币", memory_type="semantic")
        out = await dm.execute_tool("forget_memory", {"content": "一百金币"}, self.state)
        self.assertIn("已删除记忆", out)
        self.assertIsNone(load_memory(self.user, mem_id))

    async def test_tool_reports_missing_and_deletes_by_id(self):
        from backend.engine import dm_agent as dm

        missing = await dm.execute_tool("forget_memory", {"content": "根本没有的事"}, self.state)
        self.assertIn("没有找到", missing)
        blank = await dm.execute_tool("forget_memory", {}, self.state)
        self.assertIn("需要 memory_id 或 content", blank)

        mem_id = store_memory(self.user, "北门夜里换岗", memory_type="episodic")
        out = await dm.execute_tool("forget_memory", {"memory_id": mem_id}, self.state)
        self.assertIn("已删除记忆", out)
        again = await dm.execute_tool("forget_memory", {"memory_id": mem_id}, self.state)
        self.assertIn("不存在", again)


if __name__ == "__main__":
    unittest.main()
