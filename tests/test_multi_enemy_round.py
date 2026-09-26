"""多敌回合与行动经济：三个敌人各动一次、同回合不能二次行动、下一轮恢复。

玩家最在意的"敌人一动却反击两次"就靠这组不变量守住：
`combat_round` 里目标的反击会消耗它本回合的行动，之后它不能再动；
其它敌人不受牵连。
"""
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.engine import combat, initiative
from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState

ENEMIES = ("地精甲", "地精乙", "地精丙")


class TestMultiEnemyRound(unittest.IsolatedAsyncioTestCase):
    def assertRefused(self, out: str, why: str) -> None:
        """行动经济拒绝的两种措辞：账本路径说"本回合"，先攻表路径说"本轮"。"""
        self.assertTrue("本回合" in out or "本轮" in out, f"{why}；实际输出：{out[:120]}")

    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "multi-enemy", "char", "岚",
            {"hp": 60, "max_hp": 60, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="multi-enemy", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "旧商道"
        state.world_state.scene.visible_npcs_here = list(ENEMIES)
        state.world_state.npcs = [
            NpcEntry(name=name, attitude="敌对", hp=7, max_hp=7, ac=13, level=1,
                     alive=True, location="旧商道")
            for name in ENEMIES
        ]
        state.turn_action_ledger = {}
        state.turn_tool_results = {}
        return state

    async def test_each_enemy_acts_once_per_round(self):
        state = self.make_state()
        initiative.start(state)
        for name in ENEMIES:
            out = await dm.execute_tool("enemy_attack", {"enemy_name": name}, state)
            self.assertNotIn("已结算过", out, f"{name} 的首个行动不该被拒：{out[:80]}")
        denied = await dm.execute_tool("enemy_attack", {"enemy_name": ENEMIES[0]}, state)
        self.assertRefused(denied, "同一敌人同回合不能行动两次")

    async def test_new_round_restores_the_action(self):
        state = self.make_state()
        initiative.start(state)
        await dm.execute_tool("enemy_attack", {"enemy_name": ENEMIES[0]}, state)
        denied = await dm.execute_tool("enemy_attack", {"enemy_name": ENEMIES[0]}, state)
        self.assertRefused(denied, "同回合第二次应被拒")
        tracker = initiative.tracker_for(state)
        self.assertIsNotNone(tracker)
        tracker.begin_round()
        # 新回合也要清掉"同回合重复调用"去重缓存（引擎在每轮开始时重置）
        state.turn_tool_results = {}
        allowed = await dm.execute_tool("enemy_attack", {"enemy_name": ENEMIES[0]}, state)
        self.assertNotIn("已结算过", allowed, "新回合应该重新拥有一次主行动")

    async def test_player_attack_counter_consumes_only_the_target(self):
        """玩家打完目标 → 目标反击一次并耗尽本月行动；其它敌人不受影响。"""
        state = self.make_state()
        initiative.start(state)
        target = ENEMIES[0]
        hit = SimpleNamespace(roll=18, total=23, result=SimpleNamespace(value="成功"))
        with patch.object(combat, "combat_attack_roll", return_value=(hit, 5)):
            first = await dm.execute_tool(
                "combat_round",
                {"enemy_name": target, "player_action": "挥长剑劈砍",
                 "enemy_names": list(ENEMIES)},
                state)
        # 反击由 enemy_attack 结算，文案是"<敌人>攻击玩家"
        self.assertIn(f"{target}攻击玩家", first, "目标仍活着时应有且仅有一次反击")
        again = await dm.execute_tool("enemy_attack", {"enemy_name": target}, state)
        self.assertRefused(again, "反击已经用掉它的行动，不能再动一次")
        for other in ENEMIES[1:]:
            out = await dm.execute_tool("enemy_attack", {"enemy_name": other}, state)
            self.assertNotIn("已结算过", out, f"{other} 不该被牵连")

    async def test_dead_enemy_cannot_act(self):
        state = self.make_state()
        initiative.start(state)
        npc = state.world_state.get_npc(ENEMIES[2])
        npc.hp = 0
        npc.alive = False
        out = await dm.execute_tool("enemy_attack", {"enemy_name": ENEMIES[2]}, state)
        self.assertIn("已阵亡", out)


if __name__ == "__main__":
    unittest.main()
