"""COC 7e 的 d100 百分比检定：成功等级与事件推送（此前只有实现、没有测试）。

COC 的判定阈值与 5e 完全不同（极限/困难成功、96+ 大失败），而且这块逻辑由后端
独立实现，属于"规则必须由后端说了算"的关键分支，必须逐档钉住。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.session import GameSessionState
from backend.engine.dice_tools import _exec_dice_roll


def coc_state(**info) -> GameSessionState:
    base = {"game_system": "coc", "attributes": {"pow": 55}, "skills": {}}
    base.update(info)
    return GameSessionState("coc-dice", "char", "调查员林", base, username="coc-user")


class TestCocPercentileRoll(unittest.IsolatedAsyncioTestCase):
    async def roll(self, roll: int, dc: int = 50, skill: str = "聆听", modifier: int = 0):
        state = coc_state()
        with patch("backend.engine.dice_tools.random.randint", return_value=roll), \
             patch("backend.engine.dice_tools.push_event", new=AsyncMock()) as event, \
             patch("backend.engine.dice_tools.push_narrative_token", new=AsyncMock()):
            line = await _exec_dice_roll(
                {"skill_name": skill, "dc": dc, "modifier": modifier}, state)
        return line, event

    async def test_success_levels_follow_coc_thresholds(self):
        """目标 50：≤5 或 ≤目标/5 极限成功，≤目标/2 困难成功，≤目标 成功，96+ 大失败。"""
        cases = {
            5: "极限成功",
            25: "困难成功",
            50: "成功",
            51: "失败",
            95: "失败",
            96: "大失败",
        }
        for roll, expected in cases.items():
            with self.subTest(roll=roll):
                line, event = await self.roll(roll)
                self.assertIn(expected, line)
                self.assertIn(f"d100={roll}", line, "COC 必须掷 d100，不能是 d20")
                payload = event.await_args.args[2]
                self.assertEqual(payload["roll"], roll)
                self.assertEqual(payload["dc"], 50)
                self.assertEqual(payload["result"], expected)
                self.assertEqual(payload["skill"], "聆听")
                self.assertIn("d100=", str(payload.get("display")), "事件要带可显示文本，别让前端拼成 d20")

    async def test_high_target_uses_one_fifth_for_extreme_success(self):
        """目标 90 时 ≤18 都算极限成功（不只是 ≤5）。"""
        line, _ = await self.roll(18, dc=90)
        self.assertIn("极限成功", line)
        line, _ = await self.roll(19, dc=90)
        self.assertIn("困难成功", line)

    async def test_fumble_requires_roll_above_target(self):
        """96+ 只有超过目标值才算大失败：目标 99 时 96 仍是成功。"""
        line, _ = await self.roll(96, dc=99)
        self.assertIn("成功", line)
        self.assertNotIn("大失败", line)
        line, _ = await self.roll(96, dc=50)
        self.assertIn("大失败", line)

    async def test_target_is_clamped_and_modifier_applies(self):
        """目标值夹在 1-99，属性调整值加在目标上。"""
        line, event = await self.roll(150, dc=150)
        self.assertIn("vs 99%", line)
        self.assertEqual(event.await_args.args[2]["dc"], 99)
        line, _ = await self.roll(60, dc=50, modifier=20)
        self.assertIn("vs 70%", line)
        self.assertIn("成功", line)

    async def test_dnd_session_still_rolls_d20(self):
        """同一入口在 5e 局仍走 d20，避免 COC 分支串味。"""
        state = GameSessionState(
            "d20-dice", "char", "岚",
            {"game_system": "dnd5e", "level": 1, "attributes": {"wis": 12},
             "skill_proficiencies": []},
            username="dnd-user",
        )
        with patch("backend.engine.dice_tools.random.randint", return_value=12), \
             patch("backend.engine.dice_tools.push_event", new=AsyncMock()), \
             patch("backend.engine.dice_tools.push_narrative_token", new=AsyncMock()):
            line = await _exec_dice_roll({"skill_name": "察觉", "dc": 15}, state)
        self.assertIn("d20=", line)
        self.assertNotIn("d100=", line)

    async def test_rest_skill_is_redirected_to_take_rest(self):
        line, _ = await self.roll(30, dc=50, skill="短休恢复量")
        self.assertIn("take_rest", line)


if __name__ == "__main__":
    unittest.main()
