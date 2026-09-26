"""魔法抗性：法术豁免优势由后端自动套用。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import combat_damage
from backend.engine import dm_agent as dm
from backend.engine.magic_resistance import creature_magic_resistance, has_magic_resistance
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestMagicResistanceRules(unittest.TestCase):
    def test_detects_english_and_chinese_traits(self):
        self.assertTrue(has_magic_resistance("Magic Resistance: advantage on saves against spells"))
        self.assertTrue(has_magic_resistance("魔法抗性：对法术豁免有优势"))
        self.assertFalse(has_magic_resistance("Keen Smell"))


class TestMagicResistanceIntegration(unittest.IsolatedAsyncioTestCase):
    def make_state(self, player_traits: list[str] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "magic-res", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 10},
             "race_traits": list(player_traits or [])},
        )
        state.world_state = WorldState(session_id="magic-res", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "营地"
        state.world_state.npcs = [
            NpcEntry(name="魔像", attitude="敌对", hp=30, max_hp=30, ac=16,
                     alive=True, location="营地", attributes={"con": 10},
                     traits=["Magic Resistance: advantage on saving throws against spells"]),
        ]
        state.world_state.scene.visible_npcs_here = ["魔像"]
        return state

    async def test_magic_save_gets_advantage_for_resistant_npc(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        self.assertTrue(creature_magic_resistance(npc))
        with patch.object(combat_damage.random, "randint", side_effect=[2, 20]):
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["魔像"], "dc": 15, "damage": 10, "damage_type": "火焰",
                 "ability": "con", "magic": True, "reason": "火球术"},
                state,
            )
        self.assertIn("成功", out)
        self.assertIn("魔法抗性", out)
        self.assertEqual(npc.hp, 25, "优势取 20，豁免成功减半")
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertEqual(rolls[-1]["roll"], 20)
        self.assertEqual(rolls[-1]["advantage_note"], "魔法抗性")

    async def test_non_magic_save_does_not_gain_advantage(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch.object(combat_damage.random, "randint", return_value=2):
            await dm.execute_tool(
                "save_damage",
                {"targets": ["魔像"], "dc": 15, "damage": 10, "damage_type": "火焰",
                 "ability": "con", "magic": False, "reason": "陷阱"},
                state,
            )
        self.assertEqual(npc.hp, 20, "非魔法效果不吃魔法抗性")

    async def test_player_magic_resistance_grants_save_advantage(self):
        state = self.make_state(["魔法抗性"])
        with patch.object(combat_damage.random, "randint", side_effect=[2, 20]):
            out = await dm.execute_tool(
                "save_damage",
                {"targets": ["岚"], "dc": 15, "damage": 10, "damage_type": "火焰",
                 "ability": "dex", "magic": True, "reason": "火球术"},
                state,
            )
        self.assertIn("魔法抗性", out)
        self.assertEqual(state.character_info["hp"], 25, "玩家优势成功也应减半")

    def test_magic_argument_is_visible_in_model_tool_schema(self):
        from backend.engine.tools import SAVE_DAMAGE_TOOL

        props = SAVE_DAMAGE_TOOL["function"]["parameters"]["properties"]
        self.assertIn("magic", props)


if __name__ == "__main__":
    unittest.main()
