"""陷阱：被动察觉 / 主动搜查 / 解除，以及"失败超过 5 点立即触发"。

此前这三步全靠 DM 记 DC、比数字、再自己决定"失败多少算踩响"。
现在交给 `resolve_trap`，并且触发伤害直接走既有的豁免管线。
"""
import unittest
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine.action_economy import primary_action_available
from backend.engine.trap_rules import (
    TRIGGER_MARGIN, disarm_modifier, passive_perception, perception_modifier,
    proficiency_bonus,
)
from backend.engine.session import GameSessionState


def hero(hp: int = 30, max_hp: int = 30) -> GameSessionState:
    return GameSessionState(
        "trap", "char", "岚",
        {"game_system": "dnd5e", "char_class": "游荡者", "level": 3,
         "hp": hp, "max_hp": max_hp, "ac": 15,
         "attributes": {"str": 10, "dex": 16, "con": 14, "wis": 14},
         "skill_proficiencies": ["察觉", "巧手"]},
        username="trap-user",
    )


class TestTrapMath(unittest.TestCase):
    def test_proficiency_bonus_prefers_card_then_derives_from_level(self):
        state = hero()
        self.assertEqual(proficiency_bonus(state), 2, "3 级角色熟练 +2")
        state.character_info["proficiency_bonus"] = 4
        self.assertEqual(proficiency_bonus(state), 4, "角色卡算好的值优先")

    def test_passive_perception_prefers_card_then_computes(self):
        state = hero()
        # 10 + 感知调整(+2) + 察觉熟练(+2)
        self.assertEqual(passive_perception(state), 14)
        state.character_info["passive_perception"] = 20
        self.assertEqual(passive_perception(state), 20, "角色卡算好的值优先")

    def test_modifiers_include_skill_proficiency(self):
        state = hero()
        self.assertEqual(perception_modifier(state), 4, "感知 +2，察觉熟练 +2")
        self.assertEqual(disarm_modifier(state), 5, "敏捷 +3，巧手熟练 +2")


class TestTrapTools(unittest.IsolatedAsyncioTestCase):
    async def test_detect_without_search_uses_passive_and_never_rolls(self):
        state = hero()
        with patch("backend.engine.trap_rules.random.randint") as roll:
            out = await dm.execute_tool(
                "resolve_trap", {"name": "毒针", "stage": "detect", "detect_dc": 13}, state)
        roll.assert_not_called()
        self.assertIn("被动察觉 14", out)
        self.assertIn("注意到可疑的痕迹", out)
        self.assertEqual([e for _, t, e in state.event_history if t == "dice_roll"], [])

    async def test_detect_without_search_reports_nothing_when_dc_is_higher(self):
        state = hero()
        out = await dm.execute_tool(
            "resolve_trap", {"name": "暗门", "stage": "detect", "detect_dc": 18}, state)
        self.assertIn("你没有察觉异常", out)

    async def test_active_search_rolls_perception(self):
        state = hero()
        with patch("backend.engine.trap_rules.random.randint", return_value=18):
            out = await dm.execute_tool(
                "resolve_trap",
                {"name": "毒针", "stage": "detect", "detect_dc": 15, "searching": True},
                state)
        self.assertIn("d20=18+4=22", out)
        self.assertIn("发现陷阱", out)
        rolls = [e for _, t, e in state.event_history if t == "dice_roll"]
        self.assertIn("察觉", rolls[-1]["skill"])

    async def test_active_search_can_fail(self):
        state = hero()
        with patch("backend.engine.trap_rules.random.randint", return_value=3):
            out = await dm.execute_tool(
                "resolve_trap",
                {"name": "毒针", "stage": "detect", "detect_dc": 15, "searching": True},
                state)
        self.assertIn("没有发现", out)

    async def test_disarm_success_opens_the_mechanism(self):
        state = hero()
        with patch("backend.engine.trap_rules.random.randint", return_value=15):
            out = await dm.execute_tool(
                "resolve_trap",
                {"name": "毒针", "stage": "disarm", "disarm_dc": 18}, state)
        self.assertIn("d20=15+5=20", out)
        self.assertIn("机关被拆开", out)
        self.assertEqual(state.character_info["hp"], 30, "成功解除不掉血")

    async def test_close_failure_does_not_trigger(self):
        state = hero()
        with patch("backend.engine.trap_rules.random.randint", return_value=10):
            out = await dm.execute_tool(
                "resolve_trap",
                {"name": "毒针", "stage": "disarm", "disarm_dc": 18, "damage": "3d6"}, state)
        self.assertIn("差 3 点", out)
        self.assertIn("可以再试一次", out)
        self.assertEqual(state.character_info["hp"], 30, "失败 5 点以内不触发")

    async def test_failure_by_five_triggers_damage_through_save_pipeline(self):
        state = hero()
        # 先掷解除(6)，再掷伤害(2d6=3+4)，最后掷敏捷豁免(11)；11+3=14 < DC18 全额 7 点
        with patch("backend.engine.trap_rules.random.randint",
                   side_effect=[6, 3, 4, 11]):
            out = await dm.execute_tool(
                "resolve_trap",
                {"name": "毒针", "stage": "disarm", "disarm_dc": 16, "damage": "2d6",
                 "damage_type": "穿刺", "ability": "dex", "dc": 18}, state)
        self.assertIn("陷阱触发", out)
        self.assertIn("毒针触发", out)
        self.assertEqual(state.character_info["hp"], 23, "2d6=7，豁免失败吃全额")

    async def test_fixed_number_string_still_deals_damage(self):
        state = hero()
        # 模型常把固定伤害写成字符串「5」：不能退化成 0 伤害
        with patch("backend.engine.trap_rules.random.randint", side_effect=[6, 2]):
            out = await dm.execute_tool(
                "resolve_trap",
                {"name": "落石", "stage": "disarm", "disarm_dc": 16, "damage": "5"}, state)
        self.assertEqual(state.character_info["hp"], 25, "固定 5 点伤害照常结算")
        self.assertIn("基础伤害 5", out)

    async def test_natural_one_always_triggers(self):
        state = hero()
        with patch("backend.engine.trap_rules.random.randint", side_effect=[1, 10]):
            out = await dm.execute_tool(
                "resolve_trap",
                {"name": "毒针", "stage": "disarm", "disarm_dc": 12, "damage": 4,
                 "dc": 20}, state)
        self.assertIn("陷阱触发", out)
        self.assertEqual(state.character_info["hp"], 26, "自然 1 直接触发，豁免失败吃全额 4 点")

    async def test_trigger_without_damage_only_reports(self):
        state = hero()
        with patch("backend.engine.trap_rules.random.randint", return_value=1):
            out = await dm.execute_tool(
                "resolve_trap",
                {"name": "毒针", "stage": "disarm", "disarm_dc": 12}, state)
        self.assertIn("未声明 damage", out)
        self.assertEqual(state.character_info["hp"], 30)

    async def test_unknown_stage_lists_options(self):
        state = hero()
        out = await dm.execute_tool("resolve_trap", {"name": "毒针", "stage": "??"}, state)
        self.assertIn("detect", out)
        self.assertIn("disarm", out)

    async def test_same_turn_repeat_disarm_is_not_rerolled(self):
        """解除失败 5 点以内可以再试，但那是下一回合的事——同回合同参数只掷一次。"""
        state = hero()
        args = {"name": "毒针", "stage": "disarm", "disarm_dc": 18}
        with patch("backend.engine.trap_rules.random.randint", return_value=10) as roll:
            first = await dm.execute_tool("resolve_trap", dict(args), state)
            second = await dm.execute_tool("resolve_trap", dict(args), state)
        self.assertEqual(roll.call_count, 1, "第二次调用复用上次结果，不再掷骰")
        self.assertIn("差 3 点", first)
        self.assertIn("重复调用已跳过", second)

    async def test_trigger_margin_constant_is_five(self):
        self.assertEqual(TRIGGER_MARGIN, 5, "5e：失败 5 点以上触发")


class TestTrapToolRegistration(unittest.TestCase):
    def test_tool_is_visible_to_dm(self):
        from backend.engine.tools import DM_TOOLS

        names = {t["function"]["name"] for t in DM_TOOLS}
        self.assertIn("resolve_trap", names)


class TestSaveDamageNumericString(unittest.TestCase):
    def test_numeric_string_is_a_fixed_amount(self):
        from backend.engine.combat_save_damage import _damage_amount

        self.assertEqual(_damage_amount(22), 22)
        self.assertEqual(_damage_amount("22"), 22, "字符串固定值不再退化成 0")
        self.assertEqual(_damage_amount("0"), 0)


class TestTrapActionEconomy(unittest.IsolatedAsyncioTestCase):
    async def test_passive_detect_is_free(self):
        state = hero()
        out = await dm.execute_tool(
            "resolve_trap", {"name": "毒针", "stage": "detect", "detect_dc": 13}, state)
        self.assertIn("被动察觉", out)
        self.assertTrue(primary_action_available(state, "岚"),
                        "不掷骰的被动察觉不该占动作")

    async def test_disarm_and_active_search_cost_the_action(self):
        cases = (
            {"stage": "disarm", "disarm_dc": 18},
            {"stage": "detect", "searching": True, "detect_dc": 15},
        )
        for extra in cases:
            state = hero()
            with patch("backend.engine.trap_rules.random.randint", return_value=10):
                await dm.execute_tool("resolve_trap", {"name": "毒针", **extra}, state)
            self.assertFalse(primary_action_available(state, "岚"), f"{extra} 应当消耗动作")


if __name__ == "__main__":
    unittest.main()
