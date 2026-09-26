"""COC 7e 战斗：d100 命中判定、40% 兜底与敌人反击（此前只有实现、没有测试）。

COC 的战斗不是 d20 vs AC，而是双方各掷 d100 对抗各自的技能百分比；
NPC 卡没有 D&D 属性时要回退到 40%，否则会凭空套上 d20 加值。
"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import combat, dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestCocCombat(unittest.IsolatedAsyncioTestCase):
    def make_state(self, enemy_hp: int = 10) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "coc-combat", "char", "调查员林",
            {"hp": 12, "max_hp": 12, "game_system": "coc",
             "attributes": {"str": 50, "dex": 50, "con": 50}, "skills": {"斗殴": 50}},
            username="coc-user",
        )
        state.world_state = WorldState(session_id="coc-combat", _storage_dir=tmp.name)
        state.world_state.npcs = [NpcEntry(
            name="邪教徒", attitude="敌对", hp=enemy_hp, max_hp=enemy_hp, ac=12, level=1, alive=True,
        )]
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    async def test_player_hit_and_enemy_counter_both_use_d100(self):
        state = self.make_state()
        with patch.object(combat.random, "randint", return_value=20), \
             patch.object(combat, "_roll_damage_simple", return_value=3):
            result = await dm.execute_tool("combat_round", {
                "enemy_name": "邪教徒", "player_action": "用撬棍砸过去",
                "player_attack_modifier": 50}, state)

        self.assertIn("COC d100", result)
        self.assertIn("d100=20 vs 50%", result)
        self.assertEqual(state.world_state.get_npc("邪教徒").hp, 7, "命中 50% 应造成 3 点伤害")
        self.assertEqual(state.character_info["hp"], 9, "敌人 40% 命中后应反击一次（12-3）")
        rolls = [d for _, event, d in state.event_history if event == "dice_roll"]
        self.assertEqual(len(rolls), 2, "玩家一次 + 敌人一次，不该多掷")
        self.assertEqual(rolls[0]["result"], "成功")
        self.assertEqual(rolls[1]["dc"], 40, "NPC 卡没有属性时用 40% 兜底")

    async def test_five_percent_counts_as_extreme_success_and_target_is_clamped(self):
        state = self.make_state(enemy_hp=20)
        with patch.object(combat.random, "randint", return_value=5), \
             patch.object(combat, "_roll_damage_simple", return_value=1):
            result = await dm.execute_tool("combat_round", {
                "enemy_name": "邪教徒", "player_action": "开枪",
                "player_attack_modifier": 150, "enemy_can_act": False}, state)

        self.assertIn("极限成功", result)
        self.assertIn("vs 99%", result, "技能值要夹在 1-99")
        self.assertEqual(state.world_state.get_npc("邪教徒").hp, 19)

    async def test_miss_deals_no_damage(self):
        state = self.make_state()
        with patch.object(combat.random, "randint", return_value=90), \
             patch.object(combat, "_roll_damage_simple", return_value=3):
            result = await dm.execute_tool("combat_round", {
                "enemy_name": "邪教徒", "player_action": "挥拳",
                "player_attack_modifier": 50, "enemy_can_act": False}, state)

        self.assertIn("失败", result)
        self.assertEqual(state.world_state.get_npc("邪教徒").hp, 10, "没命中不能掉血")
        self.assertEqual(state.character_info["hp"], 12, "敌人不行动时玩家也不该掉血")

    async def test_enemy_attack_rolls_d100_with_fallback_skill(self):
        hit_state = self.make_state()
        with patch.object(combat.random, "randint", return_value=39), \
             patch.object(combat, "_roll_damage_simple", return_value=4):
            hit = await dm.execute_tool("enemy_attack", {"enemy_name": "邪教徒"}, hit_state)
        self.assertIn("d100=39 vs 40%", hit)
        self.assertIn("命中", hit)
        self.assertEqual(hit_state.character_info["hp"], 8)

        miss_state = self.make_state()
        with patch.object(combat.random, "randint", return_value=90), \
             patch.object(combat, "_roll_damage_simple", return_value=4):
            miss = await dm.execute_tool("enemy_attack", {"enemy_name": "邪教徒"}, miss_state)
        self.assertIn("未命中", miss)
        self.assertEqual(miss_state.character_info["hp"], 12, "未命中不该扣血")


if __name__ == "__main__":
    unittest.main()
