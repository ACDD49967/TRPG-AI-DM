"""击败经验结算：升级系统此前从不触发的缺口回归。"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestDefeatXp(unittest.IsolatedAsyncioTestCase):
    async def test_combat_round_kill_awards_xp_end_to_end(self):
        """整条链：combat_round 击杀 → 写回 HP → 结算 XP（拆分后仍需成立）。"""
        from types import SimpleNamespace
        from unittest.mock import patch

        from backend.engine import combat

        state = self.make_state()
        state.world_state.npcs = [NpcEntry(name="地精斥候", attitude="敌对",
                                           hp=3, max_hp=7, ac=13, level=1, alive=True)]
        hit = SimpleNamespace(roll=18, total=23, result=SimpleNamespace(value="成功"))
        with patch.object(combat, "combat_attack_roll", return_value=(hit, 9)):
            result = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, state)

        self.assertIn("被击败", result)
        self.assertEqual(state.world_state.npcs[0].hp, 0)
        self.assertFalse(state.world_state.npcs[0].alive)
        self.assertEqual(state.character_info["xp"], 50, "击杀必须结算经验")

    def make_state(self, system: str = "dnd5e") -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "xp_test", "char", "测试",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 1, "xp": 0,
             "game_system": system, "char_class": "战士", "race": "人类",
             "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="xp_test", _storage_dir=tmp.name)
        return state

    async def test_defeating_enemy_awards_xp_once(self):
        state = self.make_state()
        npc = NpcEntry(name="地精斥候", attitude="敌对", hp=4, max_hp=7, level=1, alive=True)
        state.world_state.npcs = [npc]

        gained = await dm._persist_combat_damage(state, npc, 0)
        self.assertEqual(gained, 50)
        self.assertEqual(state.character_info["xp"], 50)
        self.assertTrue(npc.xp_awarded)
        self.assertFalse(npc.alive)

        # 再次写回（例如重复结算）不应重复发奖
        again = await dm._persist_combat_damage(state, npc, 0)
        self.assertEqual(again, 0)
        self.assertEqual(state.character_info["xp"], 50)

    async def test_nonlethal_damage_awards_nothing(self):
        state = self.make_state()
        npc = NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7, alive=True)
        gained = await dm._persist_combat_damage(state, npc, 3)
        self.assertEqual(gained, 0)
        self.assertEqual(state.character_info["xp"], 0)
        self.assertTrue(npc.alive)

    async def test_coc_system_has_no_xp(self):
        state = self.make_state("coc")
        npc = NpcEntry(name="深潜者", attitude="敌对", hp=5, max_hp=5, alive=True)
        gained = await dm._persist_combat_damage(state, npc, 0)
        self.assertEqual(gained, 0)
        self.assertEqual(state.character_info.get("xp", 0), 0)

    async def test_xp_threshold_triggers_level_up(self):
        state = self.make_state()
        npc = NpcEntry(name="地精头目", attitude="敌对", hp=10, max_hp=10, level=3, alive=True)
        state.character_info["xp"] = 250
        gained = await dm._persist_combat_damage(state, npc, 0)
        self.assertEqual(gained, 200)
        self.assertEqual(state.character_info["xp"], 450)
        self.assertEqual(state.character_info["level"], 2, "450 XP 应升到 2 级")
        self.assertGreater(state.character_info["max_hp"], 20, "升级应提高最大生命值")

    def test_xp_table_scales_with_threat(self):
        self.assertEqual(dm._defeat_xp_for(NpcEntry(name="a", level=1)), 50)
        self.assertEqual(dm._defeat_xp_for(NpcEntry(name="b", level=3)), 200)
        self.assertGreater(dm._defeat_xp_for(NpcEntry(name="c", level=12)),
                           dm._defeat_xp_for(NpcEntry(name="d", level=10)))


if __name__ == "__main__":
    unittest.main()
