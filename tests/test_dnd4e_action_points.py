"""DND4e 行动点：用行动点换额外行动时必须真的扣掉，没有点数要拒绝。

此前 `action_source="action_point"` 只是走行动经济配额（默认 1 次），
没有任何地方扣减 `action_points`——行动点成了面板上只涨不跌的摆设。
"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import combat, dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


def make_state(system: str = "dnd4e", ap: int = 1) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    state = GameSessionState(
        "ap4e", "char", "岚",
        {"game_system": system, "level": 1, "char_class": "战士",
         "hp": 30, "max_hp": 30, "ac": 16, "action_points": ap,
         "attributes": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10}},
        username="ap-user",
    )
    state.world_state = WorldState(session_id="ap4e", _storage_dir=tmp.name)
    state.world_state.npcs = [NpcEntry(name="地精", attitude="敌对", hp=7, max_hp=7,
                                       ac=13, alive=True)]
    state.turn_tool_results = {}
    state.turn_action_ledger = {}
    return state


class TestDnd4eActionPoints(unittest.IsolatedAsyncioTestCase):
    async def test_spending_an_action_point_deducts_it(self):
        state = make_state(ap=1)
        with patch.object(combat, "_roll_damage_simple", return_value=3):
            await dm.execute_tool("combat_round", {
                "enemy_name": "地精", "player_action": "再补一剑",
                "action_source": "action_point"}, state)
        self.assertEqual(state.character_info["action_points"], 0, "行动点要被扣掉")

    async def test_without_action_point_the_extra_action_is_refused(self):
        state = make_state(ap=0)
        with patch.object(combat, "_roll_damage_simple", return_value=3):
            result = await dm.execute_tool("combat_round", {
                "enemy_name": "地精", "player_action": "再补一剑",
                "action_source": "action_point"}, state)
        self.assertIn("行动点", result)
        self.assertEqual(state.character_info["action_points"], 0)
        self.assertEqual(state.world_state.get_npc("地精").hp, 7, "被拒的行动不该造成伤害")

    async def test_normal_action_does_not_touch_action_points(self):
        state = make_state(ap=1)
        with patch.object(combat, "_roll_damage_simple", return_value=3):
            await dm.execute_tool("combat_round", {
                "enemy_name": "地精", "player_action": "砍一剑"}, state)
        self.assertEqual(state.character_info["action_points"], 1, "普通行动不花行动点")

    async def test_other_systems_ignore_action_point_source(self):
        """5e 没有行动点概念：声明这个来源不该被拦，也不该报错。"""
        state = make_state(system="dnd5e", ap=0)
        with patch.object(combat, "_roll_damage_simple", return_value=3):
            result = await dm.execute_tool("combat_round", {
                "enemy_name": "地精", "player_action": "再补一剑",
                "action_source": "action_point"}, state)
        self.assertNotIn("行动点不足", result)


if __name__ == "__main__":
    unittest.main()
