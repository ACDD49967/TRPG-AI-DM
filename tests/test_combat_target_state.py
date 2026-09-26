"""战斗目标状态：已阵亡单位不得复活或以默认血量继续挨打。"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestCombatTargetState(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = GameSessionState(
            "combat_state", "char", "测试",
            {"hp": 12, "max_hp": 12, "ac": 16, "game_system": "dnd5e",
             "attributes": {"str": 16, "dex": 13, "con": 14}},
        )
        self.state.world_state = WorldState(session_id="combat_state", _storage_dir=self.tmp.name)
        self.ws = self.state.world_state
        self.ws.npcs = [NpcEntry(name="地精斥候", attitude="敌对", hp=8, max_hp=8, ac=13, alive=True)]

    def test_zero_hp_npc_is_not_replaced_by_fallback_hp(self):
        npc = self.ws.npcs[0]
        npc.hp = 0
        stats = dm._resolve_enemy_from_cards(self.state, "地精斥候", {})
        self.assertEqual(stats["e_hp"], 0)

    def test_live_npc_uses_its_own_hp(self):
        stats = dm._resolve_enemy_from_cards(self.state, "地精斥候", {"enemy_hp": 99})
        self.assertEqual(stats["e_hp"], 99)
        stats = dm._resolve_enemy_from_cards(self.state, "地精斥候", {})
        self.assertEqual(stats["e_hp"], 8)

    async def test_attacking_dead_target_is_refused(self):
        npc = self.ws.npcs[0]
        npc.hp = 0
        npc.alive = False
        result = await dm.execute_tool("combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, self.state)
        self.assertIn("已阵亡", result)
        self.assertEqual(npc.hp, 0)
        self.assertFalse(npc.alive)

    async def test_dead_target_cannot_counter_attack(self):
        npc = self.ws.npcs[0]
        npc.hp = 0
        npc.alive = False
        result = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, self.state)
        self.assertIn("无法行动", result)

    async def test_damage_writeback_keeps_alive_consistent(self):
        npc = self.ws.npcs[0]
        await dm._persist_combat_damage(self.state, npc, 0)
        self.assertEqual(npc.hp, 0)
        self.assertFalse(npc.alive)
        npc.hp = 5
        npc.alive = False
        await dm._persist_combat_damage(self.state, npc, 5)
        self.assertFalse(npc.alive, "已阵亡单位不应被写回复活")


if __name__ == "__main__":
    unittest.main()
