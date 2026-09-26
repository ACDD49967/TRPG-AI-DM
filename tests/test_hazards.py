"""环境危害：坠落伤害、严寒酷暑豁免、窒息。

这三样此前全靠 DM 估：摔多高扣多少血、冷到什么时候力竭、憋气多久倒下。
现在由 `apply_hazard` 后端结算，并与既有的力竭机械后果串起来。
"""
import unittest
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine.exhaustion_effects import apply_exhaustion_effects
from backend.engine.hazards import environment_save_dc, falling_damage_dice
from backend.engine.session import GameSessionState


def hero(hp: int = 30, max_hp: int = 30, exhaustion: int = 0) -> GameSessionState:
    return GameSessionState(
        "hazard", "char", "岚",
        {"game_system": "dnd5e", "char_class": "战士", "level": 3,
         "hp": hp, "max_hp": max_hp, "ac": 16, "exhaustion": exhaustion,
         "attributes": {"str": 16, "dex": 14, "con": 14}},
        username="hazard-user",
    )


class TestHazardRules(unittest.TestCase):
    def test_falling_dice_per_ten_feet_with_cap(self):
        self.assertEqual(falling_damage_dice(10), 1)
        self.assertEqual(falling_damage_dice(5), 1, "不足 10 尺也按 1d6")
        self.assertEqual(falling_damage_dice(30), 3)
        self.assertEqual(falling_damage_dice(200), 20, "上限 20d6")
        self.assertEqual(falling_damage_dice(None), 1)

    def test_environment_dc_grows_with_hours(self):
        self.assertEqual(environment_save_dc(1), 5)
        self.assertEqual(environment_save_dc(3), 7)
        self.assertEqual(environment_save_dc(0), 5, "至少按第 1 小时算")


class TestHazardTools(unittest.IsolatedAsyncioTestCase):
    async def test_falling_damage_is_rolled_and_applied(self):
        state = hero(hp=30, max_hp=30)
        with patch("backend.engine.hazards.random.randint", return_value=4):
            out = await dm.execute_tool(
                "apply_hazard", {"kind": "falling", "distance_ft": 30}, state)
        self.assertIn("3d6=12", out)
        self.assertEqual(state.character_info["hp"], 18, "30 尺 = 3d6，全 4 点 = 12")
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertIn("坠落", rolls[-1]["skill"])

    async def test_extreme_cold_failure_adds_exhaustion(self):
        state = hero(hp=30, max_hp=30)
        with patch("backend.engine.hazards.random.randint", return_value=1):
            out = await dm.execute_tool(
                "apply_hazard", {"kind": "extreme_cold", "hours": 3}, state)
        self.assertEqual(state.character_info["exhaustion"], 1)
        self.assertIn("力竭 +1", out)
        self.assertIn("DC7", out, "第 3 小时 DC = 5 + 2")

    async def test_extreme_heat_success_keeps_no_exhaustion(self):
        state = hero(hp=30, max_hp=30)
        with patch("backend.engine.hazards.random.randint", return_value=20):
            out = await dm.execute_tool(
                "apply_hazard", {"kind": "extreme_heat", "hours": 1}, state)
        self.assertEqual(state.character_info["exhaustion"], 0)
        self.assertIn("成功", out)

    async def test_heat_failure_chains_into_exhaustion_numbers(self):
        """力竭被顶到 4 级时，生命上限减半应当同时生效（两条规则串起来）。"""
        state = hero(hp=30, max_hp=30, exhaustion=3)
        with patch("backend.engine.hazards.random.randint", return_value=1):
            await dm.execute_tool(
                "apply_hazard", {"kind": "extreme_heat", "hours": 1}, state)
        self.assertEqual(state.character_info["exhaustion"], 4)
        self.assertEqual(state.character_info["max_hp"], 15, "力竭 4 级生命上限减半")
        self.assertEqual(state.character_info["hp"], 15)

    async def test_suffocation_drops_to_dying(self):
        state = hero(hp=20, max_hp=30)
        out = await dm.execute_tool("apply_hazard", {"kind": "suffocation"}, state)
        self.assertEqual(state.character_info["hp"], 0)
        self.assertTrue(state.dying)
        self.assertIn("濒死", out)

    async def test_suffocation_on_unconscious_target_is_refused(self):
        state = hero(hp=0, max_hp=30)
        out = await dm.execute_tool("apply_hazard", {"kind": "suffocation"}, state)
        self.assertIn("无需再结算", out)

    async def test_unknown_kind_is_rejected(self):
        state = hero()
        out = await dm.execute_tool("apply_hazard", {"kind": "被雷劈"}, state)
        self.assertIn("需要 kind", out)

    async def test_apply_hazard_is_visible_to_the_dm(self):
        from backend.engine.tools import DM_TOOLS
        names = {t["function"]["name"] for t in DM_TOOLS}
        self.assertIn("apply_hazard", names)


class TestExhaustionEffectsUnit(unittest.IsolatedAsyncioTestCase):
    async def test_apply_effects_is_idempotent_on_repeated_calls(self):
        state = hero(hp=30, max_hp=30, exhaustion=4)
        first = apply_exhaustion_effects(state, state.character_info)
        second = apply_exhaustion_effects(state, state.character_info)
        self.assertEqual(state.character_info["max_hp"], 15)
        self.assertEqual(second.get("max_hp"), None, "第二次不该再改上限")
        self.assertEqual(first.get("max_hp"), 15)


if __name__ == "__main__":
    unittest.main()
