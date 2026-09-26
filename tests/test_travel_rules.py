"""旅行节奏与强行军：每天超过 8 小时的赶路逐小时掷体质豁免，失败力竭 +1。

5e 的旅行规则此前全靠 DM 记（"今天走了多久""该掷几次"），这里落到后端：
计数按游戏内日期记在角色信息里，跨天自动清零，分多次 advance_time 也不会算漏。
"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.travel_rules import forced_march_dc
from backend.engine.world_state import WorldState

_TEMP_DIRS: list = []


def traveler(hp: int = 30, exhaustion: int = 0, day: int = 1) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)
    state = GameSessionState(
        "travel", "char", "岚",
        {"game_system": "dnd5e", "char_class": "游侠", "level": 3,
         "hp": hp, "max_hp": 30, "ac": 15, "exhaustion": exhaustion,
         # 备好口粮，避免跨天时"缺补给力竭"干扰强行军的断言
         "inventory": {"items": [{"name": "口粮", "quantity": 5},
                                 {"name": "水袋", "quantity": 5}]},
         "attributes": {"str": 14, "dex": 14, "con": 14}},
        username="travel-user",
    )
    state.world_state = WorldState(session_id="travel", _storage_dir=tmp.name)
    state.world_state.scene.day_count = day
    return state


class TestTravelRules(unittest.TestCase):
    def test_forced_march_dc_grows_after_eight_hours(self):
        self.assertEqual(forced_march_dc(9), 10)
        self.assertEqual(forced_march_dc(10), 11)
        self.assertEqual(forced_march_dc(11), 12)


class TestTravelIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_short_day_does_not_force_a_save(self):
        state = traveler()
        out = await dm.execute_tool(
            "advance_time", {"hours": 6, "reason": "赶路", "pace": "normal"}, state)
        self.assertEqual(state.character_info.get("exhaustion", 0), 0)
        self.assertNotIn("强行军", out)

    async def test_two_hours_past_eight_rolls_twice(self):
        state = traveler()
        with patch("backend.engine.travel_rules.random.randint", side_effect=[1, 1]):
            out = await dm.execute_tool(
                "advance_time", {"hours": 10, "reason": "强行军", "pace": "normal"}, state)
        self.assertIn("DC10", out, "第 9 小时 DC10")
        self.assertIn("DC11", out, "第 10 小时 DC11")
        self.assertEqual(state.character_info["exhaustion"], 2)

    async def test_successful_saves_keep_no_exhaustion(self):
        state = traveler()
        with patch("backend.engine.travel_rules.random.randint", side_effect=[20, 20]):
            out = await dm.execute_tool(
                "advance_time", {"hours": 10, "reason": "强行军", "pace": "normal"}, state)
        self.assertEqual(state.character_info.get("exhaustion", 0), 0)
        self.assertIn("成功", out)

    async def test_counter_accumulates_across_calls_in_the_same_day(self):
        state = traveler()
        with patch("backend.engine.travel_rules.random.randint", return_value=1):
            await dm.execute_tool(
                "advance_time", {"hours": 6, "reason": "上午赶路", "pace": "normal"}, state)
            self.assertEqual(state.character_info.get("exhaustion", 0), 0)
            out = await dm.execute_tool(
                "advance_time", {"hours": 4, "reason": "下午继续", "pace": "normal"}, state)
        self.assertIn("强行军", out, "两次相加超过 8 小时也要判")
        self.assertEqual(state.character_info["exhaustion"], 2)

    async def test_new_day_resets_the_counter(self):
        state = traveler()
        with patch("backend.engine.travel_rules.random.randint", return_value=1):
            await dm.execute_tool(
                "advance_time", {"hours": 9, "reason": "第一天", "pace": "normal"}, state)
        self.assertEqual(state.character_info["exhaustion"], 1)
        # 真的跨过午夜（09:00 + 16 小时 = 次日 01:00），再走 6 小时
        await dm.execute_tool("advance_time", {"hours": 16, "reason": "扎营休息"}, state)
        self.assertEqual(state.world_state.scene.day_count, 2, "应当进入第二天")
        out = await dm.execute_tool(
            "advance_time", {"hours": 6, "reason": "第二天", "pace": "normal"}, state)
        self.assertNotIn("强行军", out)
        self.assertEqual(state.character_info["exhaustion"], 1)

    async def test_pace_notes_are_reported(self):
        state = traveler()
        fast = await dm.execute_tool(
            "advance_time", {"hours": 2, "reason": "急行军", "pace": "fast"}, state)
        self.assertIn("被动察觉 −5", fast)
        slow = await dm.execute_tool(
            "advance_time", {"hours": 2, "reason": "慢行", "pace": "slow"}, state)
        self.assertIn("隐蔽", slow)

    async def test_without_pace_nothing_changes(self):
        """不声明 pace 就不是旅行（搜索/守夜/等待），不该触发强行军。"""
        state = traveler()
        out = await dm.execute_tool(
            "advance_time", {"hours": 12, "reason": "守夜"}, state)
        self.assertNotIn("强行军", out)
        self.assertEqual(state.character_info.get("exhaustion", 0), 0)

    async def test_forced_march_chains_into_exhaustion_numbers(self):
        """力竭被顶到 4 级时生命上限减半（与 exhaustion_effects 串联）。"""
        state = traveler(exhaustion=3)
        with patch("backend.engine.travel_rules.random.randint", return_value=1):
            await dm.execute_tool(
                "advance_time", {"hours": 9, "reason": "强行军", "pace": "normal"}, state)
        self.assertEqual(state.character_info["exhaustion"], 4)
        self.assertEqual(state.character_info["max_hp"], 15)


if __name__ == "__main__":
    unittest.main()
