"""传奇抗性：次数解析、消耗一次把失败豁免改为成功、存档往返。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import combat_damage
from backend.engine import dm_agent as dm
from backend.engine.legendary_resistance import (
    legendary_resistance_remaining,
    parse_legendary_resistance,
    spend_legendary_resistance,
)
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestLegendaryResistanceRules(unittest.TestCase):
    def make_npc(self, *traits: str) -> NpcEntry:
        return NpcEntry(name="远古红龙", attitude="敌对", hp=200, max_hp=200,
                        ac=22, alive=True, location="洞窟", traits=list(traits))

    def test_parses_english_and_chinese_day_counts(self):
        self.assertEqual(parse_legendary_resistance(
            self.make_npc("Legendary Resistance (3/Day)")), 3)
        self.assertEqual(parse_legendary_resistance(
            self.make_npc("传奇抗性(3次)")), 3)
        self.assertEqual(parse_legendary_resistance(
            self.make_npc("Legendary Resistance (5/day)")), 5)

    def test_defaults_to_three_without_explicit_count(self):
        self.assertEqual(parse_legendary_resistance(self.make_npc("Legendary Resistance")), 3)
        self.assertEqual(parse_legendary_resistance(self.make_npc("传奇抗性")), 3)

    def test_returns_zero_without_the_trait(self):
        self.assertEqual(parse_legendary_resistance(self.make_npc("Keen Smell")), 0)
        self.assertEqual(legendary_resistance_remaining(self.make_npc("Keen Smell")), 0)

    def test_first_query_initializes_remaining_charges(self):
        npc = self.make_npc("Legendary Resistance (3/Day)")
        self.assertEqual(legendary_resistance_remaining(npc), 3)
        self.assertEqual(npc.legendary_resistance, 3)
        self.assertEqual(npc.legendary_resistance_max, 3)

    def test_spend_decrements_and_stops_at_zero(self):
        npc = self.make_npc("Legendary Resistance (2/Day)")
        self.assertTrue(spend_legendary_resistance(npc))
        self.assertEqual(npc.legendary_resistance, 1)
        self.assertTrue(spend_legendary_resistance(npc))
        self.assertEqual(npc.legendary_resistance, 0)
        self.assertFalse(spend_legendary_resistance(npc))
        self.assertEqual(npc.legendary_resistance, 0)


class TestLegendaryResistanceIntegration(unittest.IsolatedAsyncioTestCase):
    def make_state(self, *traits: str) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "legendary-res", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 10}},
        )
        state.world_state = WorldState(session_id="legendary-res", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "洞窟"
        state.world_state.npcs = [
            NpcEntry(name="远古红龙", attitude="敌对", hp=200, max_hp=200, ac=22,
                     alive=True, location="洞窟", attributes={"con": 10},
                     traits=list(traits or ["Legendary Resistance (3/Day)"])),
        ]
        state.world_state.scene.visible_npcs_here = ["远古红龙"]
        return state

    async def test_failed_save_becomes_success_and_spends_a_charge(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch.object(combat_damage.random, "randint", return_value=2):
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["远古红龙"], "dc": 18, "damage": 20, "damage_type": "火焰",
                 "ability": "con", "legendary_resistance": True, "reason": "火球术"},
                state,
            )
        self.assertIn("成功", out)
        self.assertIn("传奇抗性", out)
        self.assertEqual(npc.legendary_resistance, 2, "消耗一次传奇抗性")
        self.assertEqual(npc.hp, 190, "改为成功后伤害减半")
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertIs(rolls[-1]["legendary_resistance"], True)
        self.assertEqual(rolls[-1]["result"], "成功")

    async def test_exhausted_resistance_does_not_change_the_result(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.legendary_resistance_max = 1
        npc.legendary_resistance = 0
        with patch.object(combat_damage.random, "randint", return_value=2):
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["远古红龙"], "dc": 18, "damage": 20, "damage_type": "火焰",
                 "ability": "con", "legendary_resistance": True, "reason": "火球术"},
                state,
            )
        self.assertIn("传奇抗性已用尽", out)
        self.assertEqual(npc.hp, 180, "次数耗尽仍全额受伤")
        self.assertEqual(npc.legendary_resistance, 0)
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertNotIn("legendary_resistance", rolls[-1])

    async def test_resistance_is_not_spent_when_not_declared(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch.object(combat_damage.random, "randint", return_value=2):
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["远古红龙"], "dc": 18, "damage": 20, "damage_type": "火焰",
                 "ability": "con", "reason": "火球术"},
                state,
            )
        self.assertNotIn("传奇抗性", out)
        self.assertEqual(npc.hp, 180)
        self.assertEqual(npc.legendary_resistance, 0, "未声明则不初始化也不消耗")

    async def test_resistance_survives_world_state_save_load(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.legendary_resistance = 2
        npc.legendary_resistance_max = 3
        state.world_state.save()
        restored = WorldState.load("legendary-res", storage_dir=state.world_state._storage_dir)
        self.assertEqual(restored.npcs[0].legendary_resistance, 2)
        self.assertEqual(restored.npcs[0].legendary_resistance_max, 3)

    def test_legendary_argument_is_visible_in_model_tool_schema(self):
        from backend.engine.tools import SAVE_DAMAGE_TOOL

        props = SAVE_DAMAGE_TOOL["function"]["parameters"]["properties"]
        self.assertIn("legendary_resistance", props)


if __name__ == "__main__":
    unittest.main()
