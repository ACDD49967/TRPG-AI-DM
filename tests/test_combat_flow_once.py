"""战斗流程合理性：一回合内每个敌人只行动一次，且不受名字写法影响。"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def _roll(value: str = "成功", total: int = 18):
    return SimpleNamespace(roll=15, total=total, result=SimpleNamespace(value=value))


class TestCombatFlowOnce(unittest.IsolatedAsyncioTestCase):
    def make_state(self, enemies: list[tuple[str, int]] | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "flow", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 1, "xp": 0,
             "game_system": "dnd5e", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="flow", _storage_dir=tmp.name)
        state.world_state.npcs = [
            NpcEntry(name=name, attitude="敌对", hp=hp, max_hp=hp, ac=13, level=1, alive=True)
            for name, hp in (enemies or [("地精斥候", 7)])
        ]
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state

    def _patch_dice(self, player_damage: int = 3, enemy_damage: int = 4):
        def fake(attacker, ac, mod, dice):
            return _roll(), (player_damage if attacker == "你" else enemy_damage)
        return patch.object(combat, "combat_attack_roll", side_effect=fake)

    async def test_enemy_counters_once_and_variant_name_is_not_a_second_attack(self):
        state = self.make_state()
        with self._patch_dice():
            result = await dm.execute_tool(
                "combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, state)
            hp_after_counter = state.character_info["hp"]
            second = await dm.execute_tool(
                "enemy_attack", {"enemy_name": "地精斥候（受伤）"}, state)

        self.assertIn("战斗结算", result)
        self.assertEqual(hp_after_counter, 16, "敌人应反击一次（20-4）")
        self.assertEqual(state.character_info["hp"], 16, "变体名字不该触发第二次反击")
        self.assertIn("主行动已经结算过", second)
        enemy_attacks = [
            d for _, t, d in state.event_history
            if t == "dice_roll" and "地精斥候" in str(d.get("skill", ""))
        ]
        self.assertEqual(len(enemy_attacks), 1, "一回合内同一敌人只应攻击一次")

    async def test_each_enemy_acts_once_but_distinct_enemies_still_act(self):
        state = self.make_state([("地精斥候", 7), ("野狼", 11)])
        with self._patch_dice():
            first = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
            second = await dm.execute_tool("enemy_attack", {"enemy_name": "野狼"}, state)
            third = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)

        self.assertIn("地精斥候", first)
        self.assertIn("野狼", second)
        # 参数完全相同的重复调用会先被结算缓存拦下，另一种写法则由行动账本拦下；
        # 两者都是"拒绝"，关键是不产生第二次伤害。
        self.assertTrue(
            "主行动已经结算过" in third or "重复调用已跳过" in third,
            f"第三次调用应被拒绝，实际：{third[:80]}",
        )
        self.assertEqual(state.character_info["hp"], 12, "两个不同敌人各攻击一次共 8 点")
        enemy_attacks = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertEqual(len(enemy_attacks), 2, "只应有两名敌人各一次攻击")

    async def test_legendary_action_allows_declared_extra_attack(self):
        state = self.make_state()
        with self._patch_dice():
            await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
            extra = await dm.execute_tool(
                "enemy_attack",
                {"enemy_name": "地精斥候", "action_source": "legendary_action"}, state)
            blocked = await dm.execute_tool(
                "enemy_attack",
                {"enemy_name": "地精斥候", "action_source": "legendary_action",
                 "attacks": 1}, state)

        self.assertIn("地精斥候", extra)
        self.assertEqual(state.character_info["hp"], 12, "主行动 + 1 次传奇动作")
        self.assertIn("已用完", blocked)

    async def test_dead_enemy_does_not_act(self):
        state = self.make_state()
        state.world_state.npcs[0].hp = 0
        state.world_state.npcs[0].alive = False
        result = await dm.execute_tool("enemy_attack", {"enemy_name": "地精斥候"}, state)
        self.assertIn("已阵亡", result)
        self.assertEqual(state.character_info["hp"], 20)


if __name__ == "__main__":
    unittest.main()
