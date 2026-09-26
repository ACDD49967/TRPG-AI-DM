"""文件资源 ID 边界回归，全部使用临时目录或不触发 lifespan 的 ASGI 请求。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.paths import InvalidResourceId, validate_resource_id


class TestResourceIds(unittest.TestCase):
    def test_reject_path_syntax_on_all_platforms(self):
        for value in ("", ".", "..", "../bob/probe", r"..\bob\probe", "/tmp/probe",
                      r"C:\tmp\probe", "C:probe", "probe.json", "probe:stream", "%2e%2e",
                      "a\x00b", "a\nb", " leading", "trailing ", "CON", "nul", "a" * 129, None):
            with self.subTest(value=value), self.assertRaises(InvalidResourceId):
                validate_resource_id(value)
        for value in ("abc012", "auto_session-123", "classic_01", "a" * 128):
            self.assertEqual(validate_resource_id(value), value)

    def test_managers_reject_traversal_without_touching_other_users(self):
        from backend import save_manager as saves, character_card_manager as cards
        from backend import extension_manager as extensions, scenario_store as scenarios
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bob").mkdir()
            victim = root / "bob" / "probe.json"
            victim.write_text('{"sentinel": true}', encoding="utf-8")
            with (patch.object(saves, "SAVE_ROOT", root), patch.object(cards, "CHAR_ROOT", root),
                  patch.object(extensions, "EXT_ROOT", root), patch.object(scenarios, "SCENARIO_DIR", str(root))):
                operations = [
                    lambda i: saves.load_save("alice", i), lambda i: saves.delete_save("alice", i),
                    lambda i: cards.get_character_card("alice", i), lambda i: cards.delete_character_card("alice", i),
                    lambda i: cards.save_character_card("alice", {}, card_id=i),
                    lambda i: extensions.get_extension("alice", i), lambda i: extensions.delete_extension("alice", i),
                    lambda i: scenarios.Scenario.load(i, "alice"), lambda i: scenarios.delete_scenario(i, "alice"),
                    lambda i: scenarios.Scenario(id=i).save(),
                ]
                for op in operations:
                    for resource_id in ("../bob/probe", r"..\bob\probe"):
                        with self.subTest(op=op, resource_id=resource_id), self.assertRaises(InvalidResourceId):
                            op(resource_id)
                self.assertEqual(victim.read_text(encoding="utf-8"), '{"sentinel": true}')

    def test_valid_card_and_scenario_roundtrip(self):
        from backend import character_card_manager as cards, scenario_store as scenarios
        with tempfile.TemporaryDirectory() as td:
            with patch.object(cards, "CHAR_ROOT", Path(td) / "cards"):
                card = cards.save_character_card("alice", {"name": "test"})
                self.assertEqual(cards.get_character_card("alice", card["id"])["id"], card["id"])
                self.assertTrue(cards.delete_character_card("alice", card["id"]))
            with patch.object(scenarios, "SCENARIO_DIR", str(Path(td) / "scenarios")):
                scenario = scenarios.Scenario(id="scenario-01")
                scenario.meta.username = "alice"
                scenario.save()
                self.assertIsNotNone(scenarios.Scenario.load("scenario-01", "alice"))
                self.assertTrue(scenarios.delete_scenario("scenario-01", "alice"))


class TestResourceIdApi(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_ids_return_400(self):
        from backend.main import app
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/saves/load", json={"username": "alice", "save_id": "../bob/probe"})
            self.assertEqual(response.status_code, 400)
            for method, path in (("GET", "/api/scenarios/..%5Cbob%5Cprobe"),
                                 ("PUT", "/api/characters/..%5Cbob%5Cprobe"),
                                 ("DELETE", "/api/extensions/..%5Cbob%5Cprobe")):
                response = await client.request(method, path, json={"username": "alice", "card": {}})
                self.assertEqual(response.status_code, 400, response.text)
