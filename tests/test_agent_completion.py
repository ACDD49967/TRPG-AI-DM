"""委派状态、预算耗尽、部分结算与接手判定回归。"""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.engine.focused_subagents import (
    MAX_DELEGATED_TASKS, ToolAgentResult, delegation_is_complete,
    delegation_execution_context, run_tool_subagent, run_tool_subagents,
)
from backend.engine.session import GameSessionState


def response(content="", calls=(), finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=list(calls)), finish_reason=finish)])


def call(name="combat_round", args='{"target": "goblin"}'):
    return SimpleNamespace(id="call-1", function=SimpleNamespace(name=name, arguments=args))


class TestCompletionDecision(unittest.TestCase):
    def test_partial_missing_and_empty_results_keep_main_tools(self):
        tasks = [{"key": "rules"}, {"key": "world"}]
        success = ToolAgentResult(status="completed", content="done", successful_tools=["combat_round"])
        for status in ("incomplete", "timeout", "failed"):
            self.assertFalse(delegation_is_complete(tasks, {"rules": ToolAgentResult(status=status), "world": success}, "combat"))
        self.assertFalse(delegation_is_complete(tasks, {"rules": success}, "combat"))
        self.assertFalse(delegation_is_complete([], {}, "combat"))
        self.assertFalse(delegation_is_complete(tasks, {"rules": ToolAgentResult(status="completed"), "world": success}, "combat"))
        self.assertTrue(delegation_is_complete(tasks, {"rules": success, "world": success}, "combat"))

    def test_advice_and_search_are_not_settlement(self):
        tasks = [{"key": "rules"}]
        result = ToolAgentResult(status="completed", content="attack should hit", successful_tools=["search_npcs"])
        self.assertFalse(delegation_is_complete(tasks, {"rules": result}, "combat"))
        self.assertFalse(delegation_is_complete(tasks, {"rules": result}, "scene"))


class TestToolAgentExecution(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = GameSessionState("test", "char", "test", {})
        self.pack = SimpleNamespace(name="rules", description="test", content="test", metadata={"allowed-tools": ["combat_round"]})
        self.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())))
        self.task = {"key": "rules", "skill": "combat-rules-advisor", "context": "test"}

    async def run_agent(self, responses, **kwargs):
        self.client.chat.completions.create.side_effect = responses
        with patch("backend.engine.focused_subagents.get_agent_skill", return_value=self.pack):
            return await run_tool_subagent(self.client, "mock", self.task, self.state, **kwargs)

    async def test_empty_sentinel_and_truncated_outputs_are_incomplete(self):
        for content, finish in (("", "stop"), ("[子Agent未返回结论]", "stop"), ("partial", "length")):
            outcome = await self.run_agent([response(content, finish=finish)])
            self.assertFalse(outcome.completed)

    async def test_tool_then_final_is_completed(self):
        with patch("backend.engine.dm_agent.execute_tool", new=AsyncMock(return_value="HP 10 -> 8")) as execute:
            outcome = await self.run_agent([response(calls=[call()], finish="tool_calls"), response("HP is now 8")])
        self.assertTrue(outcome.completed)
        self.assertEqual(outcome.successful_tools, ["combat_round"])
        execute.assert_awaited_once()

    async def test_iteration_exhaustion_keeps_executed_record(self):
        with patch("backend.engine.dm_agent.execute_tool", new=AsyncMock(return_value="HP 10 -> 8")):
            outcome = await self.run_agent([response(calls=[call()], finish="tool_calls")], max_iterations=1)
        self.assertFalse(outcome.completed)
        context = delegation_execution_context({"rules": outcome})
        self.assertIn("HP 10 -> 8", context)
        self.assertIn("goblin", context)

    async def test_timeout_after_tool_keeps_record(self):
        with patch("backend.engine.dm_agent.execute_tool", new=AsyncMock(return_value="HP 10 -> 8")):
            outcome = await self.run_agent([response(calls=[call()], finish="tool_calls"), asyncio.TimeoutError()])
        self.assertEqual(outcome.status, "timeout")
        self.assertIn("HP 10 -> 8", delegation_execution_context({"rules": outcome}))

    async def test_tool_failure_cannot_be_overridden_by_final_text(self):
        with patch("backend.engine.dm_agent.execute_tool", new=AsyncMock(side_effect=ValueError("bad target"))):
            outcome = await self.run_agent([response(calls=[call()], finish="tool_calls"), response("done")])
        self.assertFalse(outcome.completed)

    async def test_unauthorized_or_invalid_tool_is_not_executed(self):
        for tc in (call("take_rest"), call(args="not json"), call(args="[]")):
            with patch("backend.engine.dm_agent.execute_tool", new=AsyncMock()) as execute:
                outcome = await self.run_agent([response(calls=[tc]), response("done")])
            execute.assert_not_awaited()
            self.assertFalse(outcome.completed)

    async def test_fast_settle_write_tools_skip_the_summary_round_trip(self):
        """结算型任务：写型工具跑完直接用真实结果当结论，不再多一次 LLM 往返。"""
        self.task["fast_settle"] = True
        with patch("backend.engine.dm_agent.execute_tool",
                   new=AsyncMock(return_value="HP 10 -> 8")) as execute:
            outcome = await self.run_agent([response(calls=[call()], finish="tool_calls")])
        self.assertTrue(outcome.completed)
        self.assertIn("HP 10 -> 8", outcome.content)
        self.assertEqual(self.client.chat.completions.create.await_count, 1,
                         "fast_settle 生效时不该再发起第二次调用")
        execute.assert_awaited_once()

    async def test_fast_settle_requires_the_task_flag(self):
        with patch("backend.engine.dm_agent.execute_tool",
                   new=AsyncMock(return_value="HP 10 -> 8")):
            outcome = await self.run_agent([
                response(calls=[call()], finish="tool_calls"),
                response("HP is now 8"),
            ])
        self.assertTrue(outcome.completed)
        self.assertEqual(self.client.chat.completions.create.await_count, 2,
                         "没有 fast_settle 标记的任务保持原来的总结轮")

    async def test_fast_settle_skipped_for_read_only_tools(self):
        """只查询（search_*）不算结算完成，仍然要走总结轮。"""
        self.task["fast_settle"] = True
        self.pack = SimpleNamespace(
            name="rules", description="test", content="test",
            metadata={"allowed-tools": ["search_npcs", "combat_round"]})
        with patch("backend.engine.dm_agent.execute_tool",
                   new=AsyncMock(return_value="找到 1 个 NPC")):
            outcome = await self.run_agent([
                response(calls=[call("search_npcs", '{"name": "柯尔"}')], finish="tool_calls"),
                response("柯尔在村里"),
            ])
        self.assertTrue(outcome.completed)
        self.assertEqual(self.client.chat.completions.create.await_count, 2)

    async def test_write_tool_agent_is_not_serialized_by_session_lock(self):
        """写型子 Agent 不应被整段会话锁串行化（实测会让墙钟时间逐个叠加）。"""
        await self.state.agent_write_lock.acquire()
        try:
            outcome = await self.run_agent([response("done")], timeout=5)
        finally:
            self.state.agent_write_lock.release()
        self.assertTrue(outcome.completed)
        self.client.chat.completions.create.assert_awaited()

    async def test_tasks_over_budget_are_explicitly_incomplete(self):
        # 候选要超过 MAX_DELEGATED_TASKS 才谈得上"超出预算"
        tasks = [{"key": key} for key in ("rules", "combat", "world", "memory", "graph")]
        self.assertLess(MAX_DELEGATED_TASKS, len(tasks), "该用例的前提是候选超过并发预算")
        done = ToolAgentResult(status="completed", content="done", successful_tools=["combat_round"])
        with patch("backend.engine.focused_subagents.run_tool_subagent", new=AsyncMock(return_value=done)):
            results = await run_tool_subagents(self.client, "mock", tasks, self.state)
        self.assertEqual(results["world"].status, "completed",
                         "预算内的任务必须真的跑，不能因为后面有超额任务就被吞掉")
        self.assertEqual(results["memory"].status, "incomplete")
        self.assertEqual(results["graph"].status, "incomplete")
        self.assertFalse(delegation_is_complete(tasks, results, "combat"))
