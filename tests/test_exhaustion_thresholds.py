"""力竭 4 级（生命上限减半）与 6 级（死亡）：从"提示词里的表"落成数值。

1/3 级的掷骰后果在 `test_exhaustion_effects` 里；这里补剩下两条改数值的，
并确认降回 4 级以下时上限会恢复（不能连着减半两次）。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.character_state import _exec_update_state
from backend.engine.session import GameSessionState


def hero(hp: int = 30, max_hp: int = 30, exhaustion: int = 0) -> GameSessionState:
    return GameSessionState(
        "exh", "char", "岚",
        {"game_system": "dnd5e", "char_class": "战士", "level": 3,
         "hp": hp, "max_hp": max_hp, "ac": 16, "exhaustion": exhaustion,
         "attributes": {"str": 16, "dex": 14, "con": 14}},
        username="exh-user",
    )


def hints(state: GameSessionState) -> list[str]:
    return [h for h in (state.pending_system_hints or []) if h.startswith("[系统强制-力竭]")]


class TestExhaustionThresholds(unittest.IsolatedAsyncioTestCase):
    async def test_level_four_halves_max_hp(self):
        state = hero(hp=30, max_hp=30)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"exhaustion": 4}, "reason": "断粮四天"}, state)
        self.assertEqual(state.character_info["exhaustion"], 4)
        self.assertEqual(state.character_info["max_hp"], 15, "4 级力竭生命上限减半")
        self.assertEqual(state.character_info["hp"], 15, "当前 HP 也要被上限压住")
        self.assertTrue(hints(state), "要给主 DM 一条力竭提示")

    async def test_recovering_restores_the_original_max_hp(self):
        state = hero(hp=30, max_hp=30)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"exhaustion": 4}, "reason": "断粮"}, state)
            await _exec_update_state({"changes": {"exhaustion": -2}, "reason": "长休两次"}, state)
        self.assertEqual(state.character_info["max_hp"], 30, "降到 4 级以下要恢复原始上限")
        self.assertEqual(state.character_info["exhaustion"], 2)
        self.assertNotIn("_base_max_hp", state.character_info, "恢复后不该留内部字段")

    async def test_level_six_kills_the_character(self):
        state = hero(hp=30, max_hp=30)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"exhaustion": 6}, "reason": "力竭到顶"}, state)
        self.assertEqual(state.character_info["hp"], 0)
        self.assertTrue(state.character_dead, "6 级力竭即死亡")
        self.assertIn("死亡", hints(state)[0])

    async def test_level_two_and_five_do_not_touch_numbers(self):
        """2/5 级只关乎尺数移动，本项目用档位抽象，因此不改任何数值。"""
        state = hero(hp=30, max_hp=30)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"exhaustion": 2}, "reason": "赶路"}, state)
        self.assertEqual(state.character_info["max_hp"], 30)
        self.assertEqual(state.character_info["hp"], 30)
        self.assertFalse(hints(state), "2 级没有数值后果，不该产生强制提示")

    async def test_halving_is_idempotent(self):
        state = hero(hp=30, max_hp=30)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"exhaustion": 4}, "reason": "断粮"}, state)
            state.character_info["hp"] = 15
            await _exec_update_state({"changes": {"exhaustion": 1}, "reason": "继续恶化"}, state)
        self.assertEqual(state.character_info["max_hp"], 15, "已经在 4 级以上不能再次减半")
        self.assertEqual(state.character_info["hp"], 15)


if __name__ == "__main__":
    unittest.main()
