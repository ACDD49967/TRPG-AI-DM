"""DND4e 的休息：短休必须消耗回复力，长休重置回复力与行动点。

此前 `healing_surges` / `action_points` 在所有测试里一次都没出现：
长休会补满它们，但**短休走的是 5e 的生命骰公式**，回复力从不消耗——
4e 的核心资源成了只涨不跌的摆设，短休恢复也用了错的规则。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.session import GameSessionState
from backend.engine.session_tools import _exec_rest


def fighter4e(hp: int = 10, max_hp: int = 30, surges: int = 5,
              surge_value: int = 7, ap: int = 0) -> GameSessionState:
    return GameSessionState(
        "rest4e", "char", "岚",
        {"game_system": "dnd4e", "level": 1, "char_class": "战士",
         "hp": hp, "max_hp": max_hp, "ac": 16, "action_points": ap,
         "healing_surges": surges, "max_healing_surges": 9, "surge_value": surge_value,
         "attributes": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10}},
        username="d4-user",
    )


class TestDnd4eRest(unittest.IsolatedAsyncioTestCase):
    async def test_short_rest_spends_surges_to_heal(self):
        state = fighter4e(hp=10, max_hp=30, surges=5, surge_value=7)
        with patch("backend.engine.session_tools.push_event", new=AsyncMock()):
            line = await _exec_rest({"rest_type": "short"}, state)
        info = state.character_info
        self.assertEqual(info["hp"], 30, "20 点缺口、每次 7 点，应花 3 点回复力补满")
        self.assertEqual(info["healing_surges"], 2, "回复力要被真的扣掉")
        self.assertIn("回复力", line)

    async def test_short_rest_at_full_hp_spends_nothing(self):
        state = fighter4e(hp=30, max_hp=30, surges=5)
        with patch("backend.engine.session_tools.push_event", new=AsyncMock()):
            await _exec_rest({"rest_type": "short"}, state)
        self.assertEqual(state.character_info["healing_surges"], 5, "满血短休不该浪费回复力")

    async def test_short_rest_without_surges_heals_nothing(self):
        state = fighter4e(hp=10, max_hp=30, surges=0)
        with patch("backend.engine.session_tools.push_event", new=AsyncMock()):
            line = await _exec_rest({"rest_type": "short"}, state)
        self.assertEqual(state.character_info["hp"], 10, "没有回复力就回不了血")
        self.assertIn("回复力", line)

    async def test_long_rest_resets_surges_and_action_point(self):
        state = fighter4e(hp=7, max_hp=30, surges=1, ap=0)
        with patch("backend.engine.session_tools.push_event", new=AsyncMock()):
            await _exec_rest({"rest_type": "long"}, state)
        info = state.character_info
        self.assertEqual(info["hp"], 30, "长休回满 HP")
        self.assertEqual(info["healing_surges"], info["max_healing_surges"], "长休补满回复力")
        self.assertEqual(info["action_points"], 1, "长休把行动点重置为 1")


if __name__ == "__main__":
    unittest.main()
