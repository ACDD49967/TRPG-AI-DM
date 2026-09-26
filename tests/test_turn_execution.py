"""运行完整回合编排，模型与磁盘写入替换为隔离桩，验证实际状态变更。"""
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from backend.engine import dm_agent as dm
from backend.engine import dm_turn
from backend.engine.focused_subagents import ToolAgentResult
from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState


class TestTurnExecution(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = GameSessionState("turn-test", "char", "test", {"hp": 20, "game_system": "dnd5e"})
        self.state.world_state = WorldState(session_id="turn-test")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(dm, "_client", return_value=object()))
        self.stack.enter_context(patch.object(dm, "_model", return_value="mock"))
        self.stack.enter_context(patch.object(dm, "get_knowledge_base", return_value=SimpleNamespace(retrieve=lambda *a, **k: [])))
        self.stack.enter_context(patch("backend.engine.dm_modules.run_dm_dispatch", new=AsyncMock(return_value={"module": "combat"})))
        self.stack.enter_context(patch.object(dm, "build_memory_context", new=AsyncMock(return_value={})))
        self.stack.enter_context(patch.object(dm, "build_character_info", return_value="test"))
        self.stack.enter_context(patch.object(dm, "build_system_prompt", return_value="test"))
        self.tasks = [{"key": "rules"}, {"key": "world"}]
        self.stack.enter_context(patch.object(dm, "build_dm_brief_tasks", return_value=self.tasks))
        self.stack.enter_context(patch.object(dm, "plan_task_keys", new=AsyncMock(return_value=["rules", "world"])))
        self.delegates = self.stack.enter_context(patch.object(dm, "run_tool_subagents", new=AsyncMock(return_value={})))
        self.stream = self.stack.enter_context(patch.object(dm, "_stream_with_tools", new=AsyncMock()))
        # 回合准备阶段已拆到 dm_turn：把同名桩也绑到那个模块（patch 目标要跟着实现走）
        self.stack.enter_context(patch.multiple(
            dm_turn,
            **{name: getattr(dm, name) for name in (
                '_client', '_model', 'get_knowledge_base', 'build_memory_context', 'build_dm_brief_tasks', 'plan_task_keys', 'run_tool_subagents', 'build_character_info', 'build_system_prompt', 'sanitize_user_text', '_refresh_combat_state',
            ) if hasattr(dm, name) and hasattr(dm_turn, name)},
        ))
        self.stack.enter_context(patch.object(dm, "_generate_suggestions_subagent", new=AsyncMock(return_value=[])))
        self.stack.enter_context(patch.object(dm, "advance_background_plot_if_due", new=AsyncMock()))
        self.stack.enter_context(patch.object(dm, "compress_memory_if_needed", new=AsyncMock()))
        self.stack.enter_context(patch.object(WorldState, "save", new=Mock()))
        self.save = self.stack.enter_context(patch.object(dm, "auto_save_if_needed"))
        self.narrative = "The attack strikes the goblin's shield, forcing it backward across the room. Dust rises as the adventurer prepares for the next exchange."

    async def test_identical_actions_settle_twice_despite_legacy_cache(self):
        self.state.response_cache["attack goblin"] = "stale narration"
        tool = {"id": "call-1", "function": {"name": "combat_round", "arguments": '{"target": "goblin"}'}}
        self.stream.side_effect = [("", [tool]), (self.narrative, []), ("", [tool]), (self.narrative, [])]

        async def execute(name, args, state):
            state.character_info["hp"] -= 2
            return "attack settled"

        with patch.object(dm, "execute_tool", new=AsyncMock(side_effect=execute)) as execute_mock:
            for _ in range(2):
                result = await dm.process_player_action(self.state, "attack goblin")
                self.assertEqual(result, self.narrative)
        self.assertEqual(execute_mock.await_count, 2)
        self.assertEqual(self.state.character_info["hp"], 16)
        self.assertEqual(self.state.world_state.turn_count, 2)
        self.assertEqual(self.save.call_count, 2)

    async def test_late_suggestions_do_not_block_turn_and_still_push(self):
        """建议生成慢时不该拖住回合结束，但完成后仍要推送 choices。"""
        import asyncio

        gate = asyncio.Event()
        options = ["观察四周的痕迹", "继续向前推进"]

        async def slow_suggestions(*args, **kwargs):
            await gate.wait()
            return options

        events: list[str] = []

        async def fake_push_event(state, name, payload):
            events.append(name)

        self.stack.enter_context(patch.object(dm, "_generate_suggestions_subagent", new=slow_suggestions))
        self.stack.enter_context(patch.object(dm, "push_event", new=fake_push_event))
        self.stream.return_value = (self.narrative, [])

        await dm.process_player_action(self.state, "look around")
        self.assertIn("end_of_turn", events)
        self.assertNotIn("choices", events, "建议还没生成完，不应阻塞回合返回")

        gate.set()
        for _ in range(100):
            await asyncio.sleep(0.01)
            if "choices" in events:
                break
        self.assertIn("choices", events, "后台建议完成后仍要推送 choices")

    async def test_partial_failure_preserves_tools_and_execution_record(self):
        self.delegates.return_value = {
            "rules": ToolAgentResult(status="timeout", observations=["combat_round: goblin HP 10 -> 8"], successful_tools=["combat_round"]),
            "world": ToolAgentResult(status="completed", content="room unchanged"),
        }
        self.stream.return_value = (self.narrative, [])
        await dm.process_player_action(self.state, "attack goblin")
        call = self.stream.await_args_list[0]
        self.assertTrue(call.args[3], "主 DM 必须仍能调用工具")
        messages = call.args[2]
        self.assertTrue(any("goblin HP 10 -> 8" in str(m.get("content", "")) for m in messages))
        self.assertFalse(any("你不再拥有工具调用权限" in str(m.get("content", "")) for m in messages))

    async def test_completed_settlement_can_use_narration_only(self):
        self.delegates.return_value = {
            "rules": ToolAgentResult(status="completed", content="attack settled", successful_tools=["combat_round"]),
            "world": ToolAgentResult(status="completed", content="room unchanged"),
        }
        self.stream.return_value = (self.narrative, [])
        await dm.process_player_action(self.state, "attack goblin")
        self.assertEqual(self.stream.await_args_list[0].args[3], [])

    def test_old_save_cache_is_ignored(self):
        from backend.save_manager import restore_state_from_save
        state, _ = restore_state_from_save({"session": {"response_cache": {"attack goblin": "stale"}}})
        self.assertEqual(state.response_cache, {})

    async def test_metrics_update_carries_the_finished_turn(self):
        """前端在 end_of_turn 拉 /metrics 时本轮还没结算（新会话 recent_turns 为空）。

        因此回合真正结算后必须再推一次 metrics_update，让前端能拿到含本轮的统计。
        """
        seen: list[tuple[str, dict]] = []

        async def fake_push(state, event_type, payload=None):
            if event_type in ("end_of_turn", "metrics_update"):
                snapshot = state.telemetry.snapshot()
                seen.append((event_type, {
                    "turn_open": state.telemetry.current is not None,
                    "completed_turns": len(snapshot.get("recent_turns") or []),
                }))

        self.stream.return_value = (self.narrative, [])
        with patch.object(dm, "push_event", new=fake_push):
            await dm.process_player_action(self.state, "attack goblin")

        kinds = [kind for kind, _ in seen]
        self.assertEqual(kinds.count("end_of_turn"), 1, "每轮必须推一次 end_of_turn")
        self.assertEqual(kinds.count("metrics_update"), 1,
                         "回合结算后必须补推一次统计刷新事件")
        self.assertLess(kinds.index("end_of_turn"), kinds.index("metrics_update"),
                        "统计刷新必须排在 end_of_turn 之后（那时才结算完）")
        _, update = seen[kinds.index("metrics_update")]
        self.assertFalse(update["turn_open"], "刷新事件发出时回合必须已结算")
        self.assertGreaterEqual(update["completed_turns"], 1,
                                "刷新后的统计必须包含刚结束的这一轮")
