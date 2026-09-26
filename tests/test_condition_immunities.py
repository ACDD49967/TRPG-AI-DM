"""条件免疫：文本解析、玩家状态写入拦截与 NPC 状态写入拦截。"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine.condition_rules import (
    canonical_condition, creature_condition_immunities, parse_condition_immunities,
    player_condition_immunities,
)
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestConditionImmunityRules(unittest.TestCase):
    def test_parse_english_condition_immunities(self):
        immunities = parse_condition_immunities(
            "Condition Immunities: charmed, exhaustion, frightened, paralyzed, petrified, poisoned")
        self.assertIn("charmed", immunities)
        self.assertIn("poisoned", immunities)
        self.assertIn("paralyzed", immunities)

    def test_parse_chinese_markers_and_canonical_names(self):
        self.assertEqual(canonical_condition("中毒"), "poisoned")
        self.assertIn("poisoned", parse_condition_immunities("免疫中毒；不惧恐惧"))
        self.assertEqual(parse_condition_immunities("火焰免疫"), set())


class TestConditionImmunityIntegration(unittest.IsolatedAsyncioTestCase):
    def make_state(self, traits: list[str] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "immune", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14},
             "race_traits": list(traits or [])},
        )
        state.world_state = WorldState(session_id="immune", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "营地"
        state.world_state.npcs = [
            NpcEntry(name="构装体", attitude="敌对", hp=20, max_hp=20, ac=16,
                     alive=True, location="营地",
                     traits=["免疫中毒；不惧恐惧；Condition Immunities: charmed, exhausted"]),
        ]
        state.world_state.scene.visible_npcs_here = ["构装体"]
        return state

    async def test_player_immunity_blocks_condition_add(self):
        state = self.make_state(["免疫中毒"])
        result = await dm.execute_tool(
            "update_state",
            {"changes": {"conditions_add": "中毒"}, "reason": "毒针"},
            state,
        )
        self.assertIn("conditions_blocked", result)
        self.assertEqual(state.character_info["conditions"], [])
        self.assertIn("poisoned", player_condition_immunities(state))

    async def test_player_without_immunity_still_gets_condition(self):
        state = self.make_state()
        await dm.execute_tool(
            "update_state",
            {"changes": {"conditions_add": "中毒"}, "reason": "毒针"},
            state,
        )
        self.assertEqual(state.character_info["conditions"][0]["name"], "中毒")

    async def test_npc_immunity_blocks_condition_add(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        self.assertIn("poisoned", creature_condition_immunities(npc))
        blocked = await dm.execute_tool(
            "adjust_npc",
            {"name": "构装体", "field": "condition_add", "value": "中毒"},
            state,
        )
        self.assertIn("免疫", blocked)
        self.assertEqual(npc.conditions, [])

        allowed = await dm.execute_tool(
            "adjust_npc",
            {"name": "构装体", "field": "condition_add", "value": "俯卧"},
            state,
        )
        self.assertIn("俯卧", allowed)
        self.assertEqual(npc.conditions[0]["name"], "俯卧")


if __name__ == "__main__":
    unittest.main()
