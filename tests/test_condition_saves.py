"""条件回合豁免：成功自动移除，失败保留并递减。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import condition_rules, initiative
from backend.engine.character_conditions import tick_conditions
from backend.engine.session import GameSessionState
from backend.engine.turn_start_effects import apply_turn_start_effects
from backend.engine.world_state import NpcEntry, WorldState


class TestConditionSaves(unittest.IsolatedAsyncioTestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "saves", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="saves", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "营地"
        state.world_state.npcs = [
            NpcEntry(name="地精斥候", attitude="敌对", hp=10, max_hp=10, ac=13,
                     alive=True, location="营地", attributes={"con": 14}),
        ]
        state.world_state.scene.visible_npcs_here = ["地精斥候"]
        return state

    async def test_player_condition_save_success_removes_condition(self):
        state = self.make_state()
        state.character_info["conditions"] = [{
            "name": "中毒", "description": "", "remaining_rounds": 2,
            "save_dc": 10, "save_ability": "con",
        }]
        with patch.object(condition_rules.random, "randint", return_value=15):
            await tick_conditions(state)
        self.assertEqual(state.character_info["conditions"], [])
        events = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertTrue(any("中毒" in str(d.get("skill")) for d in events))

    async def test_player_condition_save_failure_keeps_condition(self):
        state = self.make_state()
        state.character_info["conditions"] = [{
            "name": "束缚", "description": "", "remaining_rounds": 2,
            "save_dc": 20, "save_ability": "str",
        }]
        with patch.object(condition_rules.random, "randint", return_value=2):
            await tick_conditions(state)
        condition = state.character_info["conditions"][0]
        self.assertEqual(condition["name"], "束缚")
        self.assertEqual(condition["remaining_rounds"], 1)

    async def test_npc_condition_save_success_removes_condition(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{
            "name": "麻痹", "description": "", "remaining_rounds": 2,
            "save_dc": 10, "save_ability": "con",
        }]
        initiative.start(state)
        with patch.object(condition_rules.random, "randint", return_value=15):
            await apply_turn_start_effects(state, "地精斥候", npc)
        self.assertEqual(npc.conditions, [])

    async def test_npc_condition_save_failure_keeps_condition(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{
            "name": "麻痹", "description": "", "remaining_rounds": 2,
            "save_dc": 20, "save_ability": "con",
        }]
        initiative.start(state)
        with patch.object(condition_rules.random, "randint", return_value=2):
            await apply_turn_start_effects(state, "地精斥候", npc)
        self.assertEqual(npc.conditions[0]["name"], "麻痹")
        self.assertEqual(npc.conditions[0]["remaining_rounds"], 1)


if __name__ == "__main__":
    unittest.main()
