"""NPC 状态：写入、优势结算、回合递减与存档。"""
import tempfile
import unittest

from backend.engine import initiative
from backend.engine import dm_agent as dm
from backend.engine.combat_advantage import player_attack_advantage
from backend.engine.rules import AdvantageMode
from backend.engine.session import GameSessionState
from backend.engine.turn_start_effects import apply_turn_start_effects
from backend.engine.world_state import NpcEntry, WorldState


class TestNpcConditions(unittest.IsolatedAsyncioTestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "npc-cond", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="npc-cond", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "碎石坡"
        state.world_state.npcs = [
            NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7, ac=13,
                     alive=True, location="碎石坡", attributes={"dex": 12}),
        ]
        state.world_state.scene.visible_npcs_here = ["地精斥候"]
        return state

    async def test_adjust_npc_adds_and_removes_condition(self):
        state = self.make_state()
        added = await dm.execute_tool(
            "adjust_npc",
            {"name": "地精斥候", "field": "condition_add", "value": "俯卧",
             "description": "被击倒", "remaining_rounds": 2, "reason": "绊摔"},
            state,
        )
        npc = state.world_state.npcs[0]
        self.assertEqual(npc.conditions[0]["name"], "俯卧")
        self.assertEqual(npc.conditions[0]["remaining_rounds"], 2)
        self.assertIn("俯卧", added)
        self.assertEqual(npc.to_player_view()["conditions"][0]["name"], "俯卧")

        removed = await dm.execute_tool(
            "adjust_npc",
            {"name": "地精斥候", "field": "condition_remove", "value": "俯卧"},
            state,
        )
        self.assertEqual(npc.conditions, [])
        self.assertIn("状态", removed)

    async def test_persisted_condition_drives_attack_advantage(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{"name": "俯卧", "description": "", "remaining_rounds": 2}]
        decision = player_attack_advantage(
            state, {}, action="挥剑劈下", weapon="长剑",
            enemy_npc=npc, system="dnd5e", player_name="岚",
        )
        self.assertEqual(decision.mode, AdvantageMode.ADVANTAGE)
        self.assertIn("俯卧", decision.summary())

    async def test_turn_start_ticks_condition_and_expires(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{"name": "束缚", "description": "", "remaining_rounds": 1}]
        initiative.start(state)
        text = await apply_turn_start_effects(state, "地精斥候", npc)
        self.assertIn("状态结束", text)
        self.assertIn("束缚", text)
        self.assertEqual(npc.conditions, [])

    async def test_condition_survives_world_state_save_load(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        npc.conditions = [{"name": "中毒", "description": "攻击劣势", "remaining_rounds": 3}]
        state.world_state.save()
        restored = WorldState.load("npc-cond", storage_dir=state.world_state._storage_dir)
        self.assertEqual(restored.npcs[0].conditions[0]["name"], "中毒")
        self.assertEqual(restored.npcs[0].conditions[0]["remaining_rounds"], 3)


if __name__ == "__main__":
    unittest.main()
