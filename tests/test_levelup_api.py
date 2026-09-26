"""升级选择接口：属性提升 / 专长直连写入，不依赖 DM 工具调用。"""
import tempfile
import unittest

import httpx

from backend.engine.session import GameSessionState, session_manager
from backend.engine.world_state import WorldState


class TestLevelUpApi(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from backend.main import app

        self.app = app
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state = GameSessionState(
            "levelup-api", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 4, "xp": 6500, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14,
                                                  "int": 10, "wis": 12, "cha": 10}},
            username="alice",
        )
        self.state.world_state = WorldState(session_id="levelup-api", _storage_dir=tmp.name)
        session_manager._sessions[self.state.session_id] = self.state

    async def asyncTearDown(self):
        session_manager._sessions.pop("levelup-api", None)

    def client(self):
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test")

    async def test_get_exposes_pending_level_and_feat_catalog(self):
        async with self.client() as client:
            response = await client.get("/api/game/levelup-api/levelup?username=alice")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["pending_level"], 4, "4 级战士应有属性提升待分配")
        self.assertTrue(any(f["id"] == "war_caster" for f in body["feats"]))
        self.assertEqual(len(body["abilities"]), 6)

    async def test_apply_asi_is_persisted_and_not_repeatable(self):
        async with self.client() as client:
            first = await client.post(
                "/api/game/levelup-api/levelup?username=alice",
                json={"kind": "asi", "ability": "str"})
            second = await client.post(
                "/api/game/levelup-api/levelup?username=alice",
                json={"kind": "asi", "ability": "str"})
        self.assertEqual(first.status_code, 200)
        body = first.json()
        self.assertEqual(body["current"]["attributes"]["str"], 18)
        self.assertEqual(body["pending_level"], None)
        self.assertEqual(body["taken_levels"], [4])
        self.assertEqual(second.status_code, 400, "同一等级不能重复分配")

    async def test_apply_split_asi(self):
        async with self.client() as client:
            response = await client.post(
                "/api/game/levelup-api/levelup?username=alice",
                json={"kind": "asi", "ability": "str", "ability2": "con"})
        self.assertEqual(response.status_code, 200)
        attrs = response.json()["current"]["attributes"]
        self.assertEqual((attrs["str"], attrs["con"]), (17, 15))

    async def test_apply_feat_is_persisted(self):
        async with self.client() as client:
            response = await client.post(
                "/api/game/levelup-api/levelup?username=alice",
                json={"kind": "feat", "feat_id": "war_caster"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("战地施法者", response.json()["current"]["feats"])
        # 专长效果应被后端识别（专注豁免优势）
        from backend.engine.dm_agent import _has_feat_effect
        self.assertTrue(_has_feat_effect(self.state, "concentration_advantage"))

    async def test_invalid_requests_are_rejected(self):
        async with self.client() as client:
            bad_feat = await client.post(
                "/api/game/levelup-api/levelup?username=alice",
                json={"kind": "feat", "feat_id": "not_a_feat"})
            bad_ability = await client.post(
                "/api/game/levelup-api/levelup?username=alice",
                json={"kind": "asi", "ability": "luck"})
            same_twice = await client.post(
                "/api/game/levelup-api/levelup?username=alice",
                json={"kind": "asi", "ability": "str", "ability2": "str"})
        self.assertEqual(bad_feat.status_code, 400)
        self.assertEqual(bad_ability.status_code, 400)
        self.assertEqual(same_twice.status_code, 400)

    async def test_non_asi_level_is_rejected(self):
        self.state.character_info["level"] = 3
        async with self.client() as client:
            response = await client.post(
                "/api/game/levelup-api/levelup?username=alice",
                json={"kind": "asi", "ability": "str"})
        self.assertEqual(response.status_code, 400)

    async def test_other_systems_have_no_levelup(self):
        self.state.character_info["game_system"] = "coc"
        async with self.client() as client:
            response = await client.get("/api/game/levelup-api/levelup?username=alice")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["pending_level"])


if __name__ == "__main__":
    unittest.main()
