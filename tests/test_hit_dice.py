"""生命骰收支：短休按需消耗、长休只回一半（5e 规则），别让它在存档里悄悄变多。

此前 `_hit_dice_remaining` 在长休里被直接写成 `level`（全恢复），
而 `rules.long_rest` 里写明的规则是"至多一半生命骰"；`short_rest` 的注释还说
"AI 可指定数量"，但工具根本没有这个参数。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.session import GameSessionState
from backend.engine.session_tools import _exec_rest


def fighter(level: int = 3, hp: int = 10, max_hp: int = 30,
            hit_dice_left: int = 3) -> GameSessionState:
    state = GameSessionState(
        "hd", "char", "岚",
        {"game_system": "dnd5e", "level": level, "char_class": "战士",
         "hp": hp, "max_hp": max_hp, "ac": 16,
         "attributes": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10}},
        username="hd-user",
    )
    state._hit_dice_remaining = hit_dice_left
    return state


class TestHitDice(unittest.IsolatedAsyncioTestCase):
    async def test_long_rest_restores_only_half_the_hit_dice(self):
        state = fighter(level=3, hit_dice_left=0)
        with patch("backend.engine.rest_tools.push_event", new=AsyncMock()):
            await _exec_rest({"rest_type": "long"}, state)
        self.assertEqual(state._hit_dice_remaining, 1,
                         "3 颗生命骰、长休只回一半（向下取整，至少 1）")

    async def test_long_rest_never_exceeds_the_total(self):
        state = fighter(level=4, hit_dice_left=3)
        with patch("backend.engine.rest_tools.push_event", new=AsyncMock()):
            await _exec_rest({"rest_type": "long"}, state)
        self.assertEqual(state._hit_dice_remaining, 4, "补 2 颗刚好到 4，不能超")

    async def test_short_rest_honours_requested_dice_count(self):
        state = fighter(level=5, hp=10, hit_dice_left=5)
        with patch("backend.engine.rest_tools.push_event", new=AsyncMock()), \
             patch("backend.engine.rules.random.randint", return_value=5):
            await _exec_rest({"rest_type": "short", "hit_dice": 3}, state)
        self.assertEqual(state._hit_dice_remaining, 2, "显式要 3 颗就花 3 颗")

    async def test_short_rest_defaults_to_at_most_two(self):
        state = fighter(level=5, hp=10, hit_dice_left=5)
        with patch("backend.engine.rest_tools.push_event", new=AsyncMock()), \
             patch("backend.engine.rules.random.randint", return_value=5):
            await _exec_rest({"rest_type": "short"}, state)
        self.assertEqual(state._hit_dice_remaining, 3, "不指定时最多花 2 颗")

    async def test_short_rest_cannot_spend_more_than_available(self):
        state = fighter(level=5, hp=10, hit_dice_left=1)
        with patch("backend.engine.rest_tools.push_event", new=AsyncMock()), \
             patch("backend.engine.rules.random.randint", return_value=5):
            await _exec_rest({"rest_type": "short", "hit_dice": 9}, state)
        self.assertEqual(state._hit_dice_remaining, 0, "只剩 1 颗就只花 1 颗")


if __name__ == "__main__":
    unittest.main()
