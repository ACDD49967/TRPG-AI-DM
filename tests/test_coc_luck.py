"""幸运兜底：COC 7e 的消耗约束与 5e「幸运」专长的长休重置。

这条线索的第六次：规则写进了提示词/图鉴，但没有任何代码路径负责它。
- CoC：luck 是 0-99 的百分制，消耗要 1:1、不能用于幸运/理智检定；
  此前既可越界累积，也没有任何提示。
- 5e：「幸运」专长的 3 点幸运"每次长休重置"，此前从未被写回。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.character_state import _exec_update_state
from backend.engine.rest_tools import _exec_rest
from backend.engine.session import GameSessionState


def investigator(luck: int = 50, system: str = "coc") -> GameSessionState:
    return GameSessionState(
        "luck", "char", "林",
        {"game_system": system, "char_class": "记者", "level": 1,
         "hp": 10, "max_hp": 10, "san": 55, "max_san": 55, "luck": luck,
         "max_mp": 11, "mp": 11,
         "attributes": {"str": 50, "con": 50, "dex": 50, "int": 60, "pow": 55,
                        "cha": 45, "siz": 50, "edu": 70}},
        username="luck-user",
    )


def hints(state: GameSessionState) -> list[str]:
    return [h for h in (state.pending_system_hints or []) if h.startswith("[系统强制-幸运")]


class TestCocLuck(unittest.IsolatedAsyncioTestCase):
    async def test_spending_luck_warns_about_the_rules(self):
        state = investigator(luck=50)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"luck": -10}, "reason": "让失败变成功"}, state)
        self.assertEqual(state.character_info["luck"], 40)
        self.assertTrue(hints(state), "消耗幸运要注入强制提示")
        text = hints(state)[0]
        self.assertIn("1:1", text)
        self.assertIn("理智检定", text, "COC 7e 的幸运不能用于理智检定")
        events = [d for _, t, d in state.event_history if t == "game_event"]
        self.assertEqual(events[-1]["type"], "luck_spent")
        self.assertEqual(events[-1]["extra"]["luck_spent"], 10)
        self.assertEqual(events[-1]["extra"]["luck"], 40)

    async def test_gaining_luck_stays_quiet(self):
        state = investigator(luck=50)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"luck": 5}, "reason": "成长结算"}, state)
        self.assertEqual(state.character_info["luck"], 55)
        self.assertFalse(hints(state), "增加幸运不该打扰 DM")

    async def test_luck_is_capped_at_99(self):
        state = investigator(luck=95)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"luck": 20}, "reason": "结算"}, state)
        self.assertEqual(state.character_info["luck"], 99, "COC 7e 幸运上限 99")

    async def test_zero_luck_says_it_is_exhausted(self):
        state = investigator(luck=3)
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"luck": -3}, "reason": "孤注一掷"}, state)
        self.assertEqual(state.character_info["luck"], 0)
        self.assertIn("归零", hints(state)[0])

    async def test_non_coc_systems_stay_quiet(self):
        state = investigator(luck=50, system="dnd5e")
        with patch("backend.engine.character_state.push_event", new=AsyncMock()):
            await _exec_update_state({"changes": {"luck": -10}, "reason": "无关字段"}, state)
        self.assertFalse(hints(state))
        self.assertEqual(state.character_info["luck"], 40)

    async def test_5e_lucky_feat_refills_on_long_rest(self):
        state = investigator(luck=0, system="dnd5e")
        state.character_info["feats"] = [{"id": "lucky", "name": "幸运", "description": ""}]
        with patch("backend.engine.character_state.push_event", new=AsyncMock()), \
             patch("backend.engine.time_rules.finish_long_rest", new=AsyncMock(return_value="")), \
             patch("backend.engine.time_rules.advance", new=AsyncMock(return_value={"summary": ""})):
            await _exec_rest({"rest_type": "long"}, state)
        self.assertEqual(state.character_info["luck"], 3, "长休要把幸运专长的点数重置回 3")

    async def test_5e_without_the_feat_is_untouched(self):
        state = investigator(luck=2, system="dnd5e")
        with patch("backend.engine.character_state.push_event", new=AsyncMock()), \
             patch("backend.engine.time_rules.finish_long_rest", new=AsyncMock(return_value="")), \
             patch("backend.engine.time_rules.advance", new=AsyncMock(return_value={"summary": ""})):
            await _exec_rest({"rest_type": "long"}, state)
        self.assertEqual(state.character_info["luck"], 2, "没有幸运专长就不该被重置")


if __name__ == "__main__":
    unittest.main()
