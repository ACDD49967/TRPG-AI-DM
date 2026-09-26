"""自定义规则系统的判定骰：规则写"用 2d10"，后端就得真的掷 2d10。

此前 dice_roll 固定 d20（COC 走 d100），而自定义提示词告诉模型"可用 d20/d100/其他骰子"——
承诺了工具做不到的事，玩家写了 2d10 也只能得到 d20 结果。
"""
import unittest
from unittest.mock import AsyncMock, patch

from backend.engine.rules import parse_dice_expression
from backend.engine.session import GameSessionState
from backend.engine.dice_tools import _exec_dice_roll


def state(system: str = "custom") -> GameSessionState:
    return GameSessionState(
        "dice", "char", "岚",
        {"game_system": system, "level": 1, "hp": 30, "max_hp": 30,
         "attributes": {"str": 12, "dex": 12, "con": 12, "int": 12, "wis": 12, "cha": 12}},
        username="dice-user",
    )


class TestDiceExpression(unittest.TestCase):
    def test_accepts_d_and_ndm(self):
        self.assertEqual(parse_dice_expression("d20"), (1, 20))
        self.assertEqual(parse_dice_expression("2d10"), (2, 10))
        self.assertEqual(parse_dice_expression(" 3D6 "), (3, 6))
        self.assertEqual(parse_dice_expression("1d100"), (1, 100))

    def test_rejects_nonsense_and_out_of_range(self):
        for bad in ("", "d", "2d", "0d6", "11d6", "2d1", "2d1001", "abc", "2d6+3", "d20*2"):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_dice_expression(bad))


class TestCustomDiceRoll(unittest.IsolatedAsyncioTestCase):
    async def test_rules_text_supplies_the_default_dice(self):
        """模型不传 dice 时，规则里写的 2d10 也要生效（不能指望模型自觉）。"""
        rules_state = state()
        rules_state.character_info["custom_rules"] = "所有风险判定用 2d10 取和，目标值 12。"
        with patch("backend.engine.dice_tools.random.randint", return_value=8), \
             patch("backend.engine.dice_tools.push_event", new=AsyncMock()) as event, \
             patch("backend.engine.dice_tools.push_narrative_token", new=AsyncMock()):
            line = await _exec_dice_roll({"skill_name": "攀爬", "dc": 12}, rules_state)
        payload = event.await_args.args[2]
        self.assertEqual(payload["dice"], "2d10")
        self.assertEqual(payload["formula"], "2d10=8+8=16")
        self.assertIn("成功", line)

    async def test_rules_without_dice_expression_stay_on_d20(self):
        plain = state()
        plain.character_info["custom_rules"] = "本世界没有魔法，只有蒸汽与火药。"
        with patch("backend.engine.dice_tools.random.randint", return_value=15), \
             patch("backend.engine.dice_tools.push_event", new=AsyncMock()) as event, \
             patch("backend.engine.dice_tools.push_narrative_token", new=AsyncMock()):
            line = await _exec_dice_roll({"skill_name": "察觉", "dc": 12}, plain)
        self.assertNotIn("dice", event.await_args.args[2])
        self.assertIn("d20=15", line)

    async def test_custom_system_rolls_the_declared_dice(self):
        with patch("backend.engine.dice_tools.random.randint", return_value=7), \
             patch("backend.engine.dice_tools.push_event", new=AsyncMock()) as event, \
             patch("backend.engine.dice_tools.push_narrative_token", new=AsyncMock()):
            line = await _exec_dice_roll(
                {"skill_name": "撬锁", "dc": 15, "modifier": 2, "dice": "2d10"}, state())

        payload = event.await_args.args[2]
        self.assertEqual(payload["dice"], "2d10")
        self.assertEqual(payload["formula"], "2d10=7+7+2=16")
        self.assertEqual(payload["result"], "成功")
        self.assertIn("2d10=", str(payload.get("display")))
        self.assertIn("2d10=7+7+2=16 vs DC15 → 成功", line)
        self.assertNotIn("d20=", line)

    async def test_custom_dice_can_fail(self):
        with patch("backend.engine.dice_tools.random.randint", return_value=3), \
             patch("backend.engine.dice_tools.push_event", new=AsyncMock()) as event, \
             patch("backend.engine.dice_tools.push_narrative_token", new=AsyncMock()):
            line = await _exec_dice_roll(
                {"skill_name": "撬锁", "dc": 20, "dice": "2d10"}, state())
        self.assertEqual(event.await_args.args[2]["formula"], "2d10=3+3=6")
        self.assertIn("失败", line)

    async def test_d20_or_invalid_dice_falls_back_to_normal_check(self):
        for dice in ("d20", "2d", ""):
            with self.subTest(dice=dice):
                with patch("backend.engine.dice_tools.random.randint", return_value=15), \
                     patch("backend.engine.dice_tools.push_event", new=AsyncMock()) as event, \
                     patch("backend.engine.dice_tools.push_narrative_token", new=AsyncMock()):
                    line = await _exec_dice_roll(
                        {"skill_name": "察觉", "dc": 12, "dice": dice}, state())
                payload = event.await_args.args[2]
                self.assertNotIn("dice", payload, "走回普通 d20 路径时不该带自定义骰式")
                self.assertIn("d20=15", line)

    async def test_other_systems_ignore_the_dice_parameter(self):
        """5e/4e 有规范骰，模型就算传了 2d10 也不能改掉。"""
        for system in ("dnd5e", "dnd4e"):
            with self.subTest(system=system):
                with patch("backend.engine.dice_tools.random.randint", return_value=15), \
                     patch("backend.engine.dice_tools.push_event", new=AsyncMock()) as event, \
                     patch("backend.engine.dice_tools.push_narrative_token", new=AsyncMock()):
                    line = await _exec_dice_roll(
                        {"skill_name": "察觉", "dc": 12, "dice": "2d10"}, state(system))
                self.assertNotIn("dice", event.await_args.args[2])
                self.assertIn("d20=15", line)


if __name__ == "__main__":
    unittest.main()
