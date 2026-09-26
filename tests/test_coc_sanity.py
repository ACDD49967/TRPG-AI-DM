"""COC 7e 理智：单次损失 ≥5 要提示智力检定，SAN 归 0 进入永久疯狂。

此前理智规则只写在提示词里（rules_system 的 COC 段），后端对 SAN 变化不做任何反应：
DM 忘了掷检定、玩家 SAN 掉到 0 也没人管。这里按濒死流程的同一做法做代码级兜底。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.character_state import _exec_update_state
from backend.engine.session import GameSessionState


def investigator(san: int = 20, system: str = "coc") -> GameSessionState:
    return GameSessionState(
        "san", "char", "林", 
        {"game_system": system, "char_class": "记者", "hp": 10, "max_hp": 10,
         "san": san, "max_san": 55, "luck": 50,
         "attributes": {"str": 50, "con": 50, "dex": 50, "int": 60, "pow": 55,
                        "cha": 45, "siz": 50, "edu": 70}},
        username="san-user",
    )


def hints(state: GameSessionState) -> list[str]:
    return [h for h in (state.pending_system_hints or []) if h.startswith("[系统强制-理智")]


class TestCocSanity(unittest.IsolatedAsyncioTestCase):
    async def test_losing_five_or_more_asks_for_an_int_check(self):
        state = investigator(san=20)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"san": -6}, "reason": "目击神话生物"}, state)
        self.assertEqual(state.character_info["san"], 14)
        self.assertTrue(hints(state), "掉 6 点应注入强制理智提示")
        self.assertIn("智力", hints(state)[0])
        events = [d for _, t, d in state.event_history if t == "game_event"]
        self.assertEqual(events[-1]["type"], "sanity")
        self.assertEqual(events[-1]["extra"]["san_lost"], 6)
        self.assertFalse(state.character_info.get("permanent_insanity"))

    async def test_small_losses_stay_quiet(self):
        state = investigator(san=20)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"san": -4}, "reason": "听到低语"}, state)
        self.assertEqual(state.character_info["san"], 16)
        self.assertFalse(hints(state), "不足 5 点不该打扰 DM")

    async def test_san_zero_means_permanent_madness(self):
        state = investigator(san=3)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"san": -5}, "reason": "直面旧日支配者"}, state)
        self.assertEqual(state.character_info["san"], 0)
        self.assertTrue(state.character_info.get("permanent_insanity"), "SAN 归 0 要打上永久疯狂标记")
        self.assertIn("永久疯狂", hints(state)[0])
        events = [d for _, t, d in state.event_history if t == "game_event"]
        self.assertEqual(events[-1]["type"], "insanity")
        self.assertTrue(events[-1]["extra"]["permanent"])

    async def test_permanent_madness_does_not_repeat_the_event(self):
        state = investigator(san=2)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"san": -5}, "reason": "又一次冲击"}, state)
            before = len([1 for _, t, _d in state.event_history if t == "game_event"])
            await _exec_update_state({"changes": {"san": -5}, "reason": "再来一次"}, state)
            after = len([1 for _, t, _d in state.event_history if t == "game_event"])
        self.assertEqual(before, after, "永久疯狂只播报一次")

    async def test_non_coc_systems_ignore_san(self):
        state = investigator(san=20, system="dnd5e")
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"san": -10}, "reason": "无关字段"}, state)
        self.assertFalse(hints(state))

    async def test_dm_context_remembers_permanent_madness(self):
        """永久疯狂要一直出现在主 DM 的角色信息里，别下一轮就忘。"""
        from backend.engine.dm_prompts import build_character_info

        state = investigator(san=2)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"san": -5}, "reason": "终局"}, state)
        self.assertIn("永久疯狂", build_character_info(state))


if __name__ == "__main__":
    unittest.main()
