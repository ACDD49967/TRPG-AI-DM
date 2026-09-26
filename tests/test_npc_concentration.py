"""NPC（怪物施法者）专注：登记、受伤掷体质豁免、倒地中断、存档往返。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat
from backend.engine import dm_agent as dm
from backend.engine.concentration import npc_concentration
from backend.engine.rules import RollResult
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestNpcConcentration(unittest.IsolatedAsyncioTestCase):
    def make_state(self, hp: int = 40, concentration: str = "火墙术") -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "npc-conc", "char", "岚",
            {"hp": 30, "max_hp": 30, "ac": 16, "level": 5, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 12}},
        )
        state.world_state = WorldState(session_id="npc-conc", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "祭坛"
        state.world_state.npcs = [
            NpcEntry(name="邪术师", attitude="敌对", hp=hp, max_hp=40, ac=14, level=5,
                     alive=True, location="祭坛", attributes={"con": 12},
                     concentration=concentration),
        ]
        state.world_state.scene.visible_npcs_here = ["邪术师"]
        return state

    async def test_adjust_npc_sets_and_clears_concentration(self):
        state = self.make_state(concentration="")
        npc = state.world_state.npcs[0]
        set_out = await dm.execute_tool(
            "adjust_npc",
            {"name": "邪术师", "field": "concentration", "value": "火墙术"}, state)
        self.assertIn("火墙术", set_out)
        self.assertEqual(npc.concentration, "火墙术")

        found = await dm.execute_tool("search_npcs", {"query": "邪术师"}, state)
        self.assertIn("专注:火墙术", found, "DM 查询时能看到专注状态")

        clear_out = await dm.execute_tool(
            "adjust_npc", {"name": "邪术师", "field": "concentration_clear"}, state)
        self.assertIn("已清除", clear_out)
        self.assertEqual(npc.concentration, "")

    async def test_missing_spell_name_is_rejected(self):
        state = self.make_state(concentration="")
        out = await dm.execute_tool(
            "adjust_npc", {"name": "邪术师", "field": "concentration"}, state)
        self.assertIn("⚠", out)
        self.assertEqual(state.world_state.npcs[0].concentration, "")

    async def test_failed_save_breaks_concentration(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch("backend.engine.concentration.random.randint", return_value=1):
            await dm._persist_combat_damage(state, npc, 22)
        self.assertEqual(npc.concentration, "", "豁免失败应中断专注")
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertTrue(any("专注" in str(d.get("skill")) for d in rolls))
        events = [d for _, t, d in state.event_history if t == "game_event"]
        self.assertTrue(any(d.get("type") == "concentration_broken" for d in events))

    async def test_successful_save_keeps_concentration(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch("backend.engine.concentration.random.randint", return_value=15):
            await dm._persist_combat_damage(state, npc, 32)
        self.assertEqual(npc.concentration, "火墙术")
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertEqual(rolls[-1]["result"], "成功")

    async def test_dropping_to_zero_clears_without_rolling(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        with patch("backend.engine.concentration.random.randint", return_value=1) as rnd:
            await dm._persist_combat_damage(state, npc, 0)
        self.assertFalse(rnd.called, "倒地不该再掷专注豁免")
        self.assertEqual(npc.concentration, "")
        self.assertFalse(npc.alive)

    async def test_damage_without_concentration_does_not_roll(self):
        state = self.make_state(concentration="")
        npc = state.world_state.npcs[0]
        with patch("backend.engine.concentration.random.randint", return_value=1) as rnd:
            await dm._persist_combat_damage(state, npc, 30)
        self.assertFalse(rnd.called)

    async def test_player_attack_triggers_the_mage_save(self):
        state = self.make_state()
        npc = state.world_state.npcs[0]
        hit = SimpleNamespace(roll=18, total=23, result=RollResult.SUCCESS)
        with patch.object(combat, "combat_attack_roll", return_value=(hit, 12)), \
                patch("backend.engine.concentration.random.randint", return_value=1):
            out = await dm.execute_tool(
                "combat_round",
                {"enemy_name": "邪术师", "player_action": "挥长剑劈砍",
                 "enemy_can_act": False},
                state,
            )
        self.assertEqual(npc.concentration, "", "玩家打断怪物施法者的专注")
        self.assertIn("28/40", out, "伤害正常结算")

    async def test_concentration_survives_world_state_save_load(self):
        state = self.make_state()
        state.world_state.save()
        restored = WorldState.load("npc-conc", storage_dir=state.world_state._storage_dir)
        self.assertEqual(npc_concentration(restored.npcs[0]), "火墙术")


if __name__ == "__main__":
    unittest.main()
