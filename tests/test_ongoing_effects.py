"""持续效果：条件的每回合伤害/治疗与回合末/回合开始结算。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import initiative
from backend.engine import condition_rules
from backend.engine.character_conditions import tick_conditions
from backend.engine.session import GameSessionState
from backend.engine.turn_start_effects import apply_turn_start_effects
from backend.engine.world_state import NpcEntry, WorldState


class TestOngoingEffects(unittest.IsolatedAsyncioTestCase):
    def make_state(self, hp: int = 20) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "ongoing", "char", "岚",
            {"hp": hp, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="ongoing", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "营地"
        state.world_state.npcs = [
            NpcEntry(name="地精斥候", attitude="敌对", hp=10, max_hp=10, ac=13,
                     alive=True, location="营地", attributes={"dex": 12}),
        ]
        state.world_state.scene.visible_npcs_here = ["地精斥候"]
        return state

    async def test_player_damage_over_time_and_expiry(self):
        state = self.make_state(hp=20)
        state.character_info["conditions"] = [{
            "name": "燃烧", "description": "每回合灼烧", "remaining_rounds": 2,
            "damage_per_turn": "1d4", "damage_type": "火焰",
        }]
        with patch.object(condition_rules.random, "randint", return_value=3):
            await tick_conditions(state)
        self.assertEqual(state.character_info["hp"], 17)
        self.assertEqual(state.character_info["conditions"][0]["remaining_rounds"], 1)

        with patch.object(condition_rules.random, "randint", return_value=3):
            await tick_conditions(state)
        self.assertEqual(state.character_info["hp"], 14)
        self.assertEqual(state.character_info["conditions"], [])
        events = [d for _, t, d in state.event_history if t == "game_event"]
        self.assertTrue(any(d.get("type") == "ongoing_effect" for d in events))

    async def test_player_heal_over_time(self):
        state = self.make_state(hp=10)
        state.character_info["conditions"] = [{
            "name": "再生祝福", "remaining_rounds": 1, "heal_per_turn": 2,
        }]
        await tick_conditions(state)
        self.assertEqual(state.character_info["hp"], 12)

    async def test_npc_damage_over_time_at_turn_start(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{
            "name": "中毒", "remaining_rounds": 1,
            "damage_per_turn": 2, "damage_type": "毒素",
        }]
        initiative.start(state)
        text = await apply_turn_start_effects(state, "地精斥候", npc)
        self.assertIn("中毒", text)
        self.assertEqual(npc.hp, 8)
        self.assertEqual(npc.conditions, [])


if __name__ == "__main__":
    unittest.main()
