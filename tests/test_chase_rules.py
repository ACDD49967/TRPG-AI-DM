"""追逐：冲刺配额、超出后的体质豁免与力竭、跑出视线的摆脱判定。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine.action_economy import primary_action_available
from backend.engine.chase_rules import (
    DASH_SAVE_DC, con_modifier, dash_count, free_dashes, reset_chase,
)
from backend.engine.condition_apply import condition_names
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState

_TEMP_DIRS: list[tempfile.TemporaryDirectory] = []


def make_state(*, con: int = 14) -> GameSessionState:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)   # 由 tearDownModule 统一清理
    state = GameSessionState(
        "chase", "char", "岚",
        {"game_system": "dnd5e", "char_class": "游荡者", "level": 3, "hp": 24, "max_hp": 24,
         "ac": 15, "xp": 0,
         "attributes": {"str": 10, "dex": 16, "con": con, "wis": 12},
         "skill_proficiencies": ["隐匿", "察觉"]},
    )
    state.world_state = WorldState(session_id="chase", _storage_dir=tmp.name)
    state.world_state.scene.current_location = "旧商道"
    state.world_state.scene.visible_npcs_here = ["地精追兵"]
    state.world_state.npcs = [
        NpcEntry(name="地精追兵", attitude="敌对", hp=9, max_hp=9, ac=13, level=3, alive=True,
                 location="旧商道", attributes={"str": 12, "dex": 14, "con": 12, "wis": 12}),
    ]
    state.turn_tool_results = {}
    state.turn_action_ledger = {}
    return state


def tearDownModule():
    while _TEMP_DIRS:
        _TEMP_DIRS.pop().cleanup()


class TestChaseMath(unittest.TestCase):
    def test_free_dashes_come_from_constitution(self):
        self.assertEqual(con_modifier(make_state(con=14), "岚"), 2)
        self.assertEqual(free_dashes(make_state(con=14), "岚"), 5, "3 + 体质调整值")
        self.assertEqual(free_dashes(make_state(con=20), "岚"), 8)
        self.assertEqual(free_dashes(make_state(con=6), "岚"), 1, "体质再差也至少能冲一次")

    def test_npc_free_dashes_read_the_card(self):
        state = make_state()
        self.assertEqual(free_dashes(state, "地精追兵"), 4, "地精体质 12 → +1")

    def test_reset_clears_counters(self):
        state = make_state()
        state.chase_dashes = {"岚": 3, "地精追兵": 2}
        self.assertEqual(reset_chase(state, "岚"), 1)
        self.assertEqual(dash_count(state, "岚"), 0)
        self.assertEqual(reset_chase(state), 1, "还剩一个单位")
        self.assertEqual(state.chase_dashes, {})


class TestChaseTool(unittest.IsolatedAsyncioTestCase):
    async def test_dash_within_the_free_quota_needs_no_save(self):
        state = make_state()
        with patch("backend.engine.chase_rules.random.randint") as roll:
            out = await dm.execute_tool("resolve_chase", {"action": "dash"}, state)
        roll.assert_not_called()
        self.assertIn("还能免费冲刺 4 次", out)
        self.assertEqual(dash_count(state, "岚"), 1)
        self.assertEqual(int(state.character_info.get("exhaustion", 0) or 0), 0)

    async def test_dash_beyond_the_quota_forces_a_con_save(self):
        state = make_state()
        state.chase_dashes = {"岚": 5}      # 免费额度 5 已用完
        with patch("backend.engine.chase_rules.random.randint", return_value=3) as roll:
            out = await dm.execute_tool("resolve_chase", {"action": "dash"}, state)
        self.assertEqual(roll.call_count, 1, "超出额度才掷豁免")
        self.assertIn(f"DC{DASH_SAVE_DC}", out)
        self.assertEqual(int(state.character_info["exhaustion"]), 1, "失败力竭 +1")
        self.assertIn("力竭 1 级", out)

    async def test_successful_save_keeps_no_exhaustion(self):
        state = make_state()
        state.chase_dashes = {"岚": 5}
        with patch("backend.engine.chase_rules.random.randint", return_value=18):
            out = await dm.execute_tool("resolve_chase", {"action": "dash"}, state)
        self.assertEqual(int(state.character_info.get("exhaustion", 0) or 0), 0)
        self.assertIn("未力竭", out)

    async def test_repeated_failures_stack_and_chain_into_max_hp(self):
        state = make_state()
        state.chase_dashes = {"岚": 5}
        with patch("backend.engine.chase_rules.random.randint", return_value=1):
            for _ in range(4):
                # 每次冲刺是不同回合：清掉同回合去重表与行动账本
                state.turn_tool_results = {}
                state.turn_action_ledger = {}
                await dm.execute_tool("resolve_chase", {"action": "dash"}, state)
        self.assertEqual(int(state.character_info["exhaustion"]), 4)
        self.assertEqual(state.character_info["max_hp"], 12, "力竭 4 级生命上限减半（24→12）")

    async def test_npc_exhaustion_is_written_on_its_card(self):
        state = make_state()
        state.chase_dashes = {"地精追兵": 4}    # 地精免费额度 4
        with patch("backend.engine.chase_rules.random.randint", return_value=2):
            out = await dm.execute_tool(
                "resolve_chase", {"action": "dash", "actor": "地精追兵"}, state)
        self.assertIn("力竭 1 级", out)
        self.assertIn("力竭", condition_names(state, "地精追兵"))

    async def test_escape_uses_stealth_against_passive_perception(self):
        state = make_state()
        # 隐匿加值：敏捷 +3 + 熟练 2 = 5；地精被动察觉 11
        with patch("backend.engine.chase_rules.random.randint", return_value=15) as roll:
            out = await dm.execute_tool("resolve_chase", {"action": "escape"}, state)
        self.assertEqual(roll.call_count, 1)
        self.assertIn("甩掉了追兵", out)
        self.assertIn("被动察觉 11", out)
        self.assertEqual(state.chase_dashes, {}, "摆脱成功后清零")

    async def test_escape_failure_keeps_the_chase_going(self):
        state = make_state()
        state.chase_dashes = {"岚": 2}
        with patch("backend.engine.chase_rules.random.randint", return_value=3):
            out = await dm.execute_tool("resolve_chase", {"action": "escape"}, state)
        self.assertIn("追逐继续", out)
        self.assertEqual(state.chase_dashes, {"岚": 2}, "没跑掉就不清计数")

    async def test_end_action_clears_everything(self):
        state = make_state()
        state.chase_dashes = {"岚": 3, "地精追兵": 1}
        out = await dm.execute_tool("resolve_chase", {"action": "end"}, state)
        self.assertIn("清理了 2 个单位", out)
        self.assertEqual(state.chase_dashes, {})

    async def test_unknown_action_lists_options(self):
        state = make_state()
        out = await dm.execute_tool("resolve_chase", {"action": "??"}, state)
        self.assertIn("dash", out)
        self.assertIn("escape", out)
        self.assertIn("end", out)

    async def test_same_turn_repeat_dash_is_not_free(self):
        state = make_state()
        await dm.execute_tool("resolve_chase", {"action": "dash"}, state)
        second = await dm.execute_tool("resolve_chase", {"action": "dash"}, state)
        self.assertIn("重复调用已跳过", second)
        self.assertEqual(dash_count(state, "岚"), 1, "同回合同参数不重复计次")

    async def test_player_dash_costs_the_action_but_npc_dash_does_not(self):
        state = make_state()
        await dm.execute_tool("resolve_chase", {"action": "dash"}, state)
        self.assertFalse(primary_action_available(state, "岚"), "冲刺是玩家的动作")

        other = make_state()
        await dm.execute_tool(
            "resolve_chase", {"action": "dash", "actor": "地精追兵"}, other)
        self.assertTrue(primary_action_available(other, "岚"),
                        "追兵是 NPC，不该扣玩家的动作")


class TestChaseRegistration(unittest.TestCase):
    def test_tool_is_visible_to_dm(self):
        from backend.engine.tools import DM_TOOLS

        names = {t["function"]["name"] for t in DM_TOOLS}
        self.assertIn("resolve_chase", names)

    def test_active_chase_adds_a_state_driven_prompt_section(self):
        """追逐进行中时，系统提示要出现专门段落；没有追逐时不出现（避免噪声）。"""
        from backend.engine.dm_prompts import build_system_prompt

        idle = make_state()
        idle.chase_dashes = {}
        self.assertNotIn("进行中的追逐", build_system_prompt(idle, dispatch_plan={"module": "rules"}))

        chasing = make_state()
        chasing.chase_dashes = {"岚": 2, "地精追兵": 1}
        prompt = build_system_prompt(chasing, dispatch_plan={"module": "rules"})
        self.assertIn("进行中的追逐", prompt)
        self.assertIn("resolve_chase", prompt)
        self.assertIn("地精追兵", prompt)


if __name__ == "__main__":
    unittest.main()
