"""工具执行层：同回合重复结算保护与再导出兼容。"""
import unittest
from unittest.mock import patch

from backend.engine import dm_agent, tool_executor
from backend.engine.session import GameSessionState
from backend.engine.tool_executor import execute_tool


class TestToolExecutorDedupe(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = GameSessionState("dedupe", "char", "测试", {})
        self.state.turn_tool_results = {}
        self.calls: list[dict] = []

    async def _fake(self, args, state):
        self.calls.append(args)
        return f"结算 #{len(self.calls)}"

    def _patch(self):
        return patch.object(tool_executor, "_handlers", return_value={"combat_round": self._fake})

    async def test_identical_settlement_call_runs_once_per_turn(self):
        """参数完全相同的结算（含顺序不同）直接复用结果，不再重复扣血/扣资源。"""
        with patch.object(tool_executor, "_handlers", return_value={"update_state": self._fake}):
            first = await execute_tool("update_state", {"changes": {"hp": -3}, "reason": "中毒"}, self.state)
            second = await execute_tool("update_state", {"reason": "中毒", "changes": {"hp": -3}}, self.state)
            other = await execute_tool("update_state", {"changes": {"hp": -1}, "reason": "中毒"}, self.state)

        self.assertEqual(first, "结算 #1")
        self.assertIn("重复调用已跳过", second)
        self.assertIn("结算 #1", second)
        self.assertEqual(other, "结算 #2")
        self.assertEqual(len(self.calls), 2)

    async def test_dedupe_resets_between_turns(self):
        args = {"enemy_name": "地精"}
        with self._patch():
            await execute_tool("combat_round", args, self.state)
            # dm_agent 每轮开始时清空结算缓存与行动账本
            self.state.turn_tool_results = {}
            self.state.turn_action_ledger = {}
            await execute_tool("combat_round", args, self.state)
        self.assertEqual(len(self.calls), 2)

    async def test_non_settlement_tool_is_not_deduped(self):
        with patch.object(tool_executor, "_handlers", return_value={"search_npcs": self._fake}):
            await execute_tool("search_npcs", {"name": "地精"}, self.state)
            await execute_tool("search_npcs", {"name": "地精"}, self.state)
        self.assertEqual(len(self.calls), 2)

    async def test_undeclared_second_attack_is_refused(self):
        """实测 bug：一次行动先掷失败、再重掷成功，玩家白捡一次重掷。"""
        with self._patch():
            first = await execute_tool("combat_round", {"enemy_name": "地精斥候", "player_action": "挥剑"}, self.state)
            second = await execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "player_action": "我追上去继续攻击，务必击倒它"},
                self.state,
            )
        self.assertEqual(first, "结算 #1")
        self.assertIn("主行动已经结算过", second)
        self.assertIn("action_source", second)
        self.assertEqual(len(self.calls), 1, "未声明额外行动时不应二次结算")

    async def test_attacking_a_second_enemy_needs_a_declared_action(self):
        """玩家一回合只有一次主行动：打第二个目标必须声明多段攻击等额外行动。"""
        with self._patch():
            await execute_tool("combat_round", {"enemy_name": "地精斥候"}, self.state)
            blocked = await execute_tool("combat_round", {"enemy_name": "野狼"}, self.state)
            allowed = await execute_tool(
                "combat_round", {"enemy_name": "野狼", "action_source": "multiattack"}, self.state)
        self.assertIn("主行动已经结算过", blocked)
        self.assertEqual(allowed, "结算 #2")
        self.assertEqual(len(self.calls), 2)

    async def test_declared_multiattack_is_allowed_up_to_quota(self):
        with self._patch():
            for _ in range(3):
                await execute_tool(
                    "combat_round",
                    {"enemy_name": "地精斥候", "action_source": "multiattack",
                     "attacks": 3, "player_action": f"第{len(self.calls)+1}次挥砍"},
                    self.state,
                )
            blocked = await execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "action_source": "multiattack",
                 "attacks": 3, "player_action": "第4次挥砍"},
                self.state,
            )
        self.assertEqual(len(self.calls), 3, "声明的 3 段攻击应被允许")
        self.assertIn("已用完", blocked)

    async def test_action_surge_grants_one_extra_action_only(self):
        with self._patch():
            await execute_tool("combat_round", {"enemy_name": "地精斥候"}, self.state)
            second = await execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "action_source": "action_surge", "player_action": "动作如潮再砍"}, self.state)
            third = await execute_tool(
                "combat_round",
                {"enemy_name": "地精斥候", "action_source": "action_surge", "player_action": "再砍第三刀"}, self.state)
        self.assertEqual(second, "结算 #2")
        self.assertIn("已用完", third)
        self.assertEqual(len(self.calls), 2)

    async def test_attack_guard_resets_between_turns(self):
        args = {"enemy_name": "地精斥候"}
        with self._patch():
            await execute_tool("combat_round", args, self.state)
            self.state.turn_tool_results = {}
            self.state.turn_action_ledger = {}
            await execute_tool("combat_round", args, self.state)
        self.assertEqual(len(self.calls), 2)

    async def test_unknown_tool_returns_message(self):
        result = await execute_tool("not_a_tool", {}, self.state)
        self.assertIn("未知", result)

    def test_dm_agent_reexports_executor(self):
        self.assertIs(dm_agent.execute_tool, tool_executor.execute_tool)


if __name__ == "__main__":
    unittest.main()
