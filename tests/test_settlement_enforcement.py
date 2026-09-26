"""强制结算：玩家声明了动作时，主 DM 必须调用对应结算工具，不能只调别的工具糊过去。"""
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from backend.engine import dm_agent as dm
from backend.engine import dm_turn
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestSettlementEnforcement(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = __import__("contextlib").ExitStack()
        self.addCleanup(self.stack.close)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        self.state = GameSessionState(
            "enforce", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        self.state.world_state = WorldState(session_id="enforce", _storage_dir=tmp.name)
        self.state.world_state.scene.current_location = "碎石坡"
        self.state.world_state.scene.visible_npcs_here = ["地精斥候"]
        self.state.world_state.npcs = [NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7,
                                                ac=13, alive=True, location="碎石坡")]

        self.stack.enter_context(patch.object(dm, "_client", return_value=object()))
        self.stack.enter_context(patch.object(dm, "_model", return_value="mock"))
        self.stack.enter_context(patch.object(dm, "get_knowledge_base",
                                              return_value=Mock(retrieve=lambda *a, **k: [])))
        self.stack.enter_context(patch("backend.engine.dm_modules.run_dm_dispatch",
                                       new=AsyncMock(return_value={"module": "combat"})))
        self.stack.enter_context(patch.object(dm, "build_memory_context", new=AsyncMock(return_value={})))
        self.stack.enter_context(patch.object(dm, "build_dm_brief_tasks", return_value=[{"key": "world"}]))
        self.stack.enter_context(patch.object(dm, "plan_task_keys", new=AsyncMock(return_value=["world"])))
        self.stack.enter_context(patch.object(dm, "run_tool_subagents", new=AsyncMock(return_value={})))
        self.stack.enter_context(patch.object(dm, "_generate_suggestions_subagent", new=AsyncMock(return_value=[])))
        self.stack.enter_context(patch.object(dm, "advance_background_plot_if_due", new=AsyncMock()))
        self.stack.enter_context(patch.object(dm, "compress_memory_if_needed", new=AsyncMock()))
        self.stack.enter_context(patch.object(WorldState, "save", new=Mock()))
        self.stack.enter_context(patch.object(dm, "auto_save_if_needed"))
        self.stream = self.stack.enter_context(patch.object(dm, "_stream_with_tools", new=AsyncMock()))
        # 回合准备阶段已拆到 dm_turn：把同名桩也绑到那个模块（patch 目标要跟着实现走）
        self.stack.enter_context(patch.multiple(
            dm_turn,
            **{name: getattr(dm, name) for name in (
                '_client', '_model', 'get_knowledge_base', 'build_memory_context', 'build_dm_brief_tasks', 'plan_task_keys', 'run_tool_subagents', 'build_character_info', 'build_system_prompt', 'sanitize_user_text', '_refresh_combat_state',
            ) if hasattr(dm, name) and hasattr(dm_turn, name)},
        ))

    def tool_call(self, name: str):
        return {"id": "call-1", "function": {"name": name, "arguments": '{"query": "地精"}'}}

    async def test_other_tool_call_does_not_count_as_settlement(self):
        """模型查了 search_npcs 就叙述战斗 —— 必须被强制重试要求 combat_round。"""
        self.stream.side_effect = [
            ("让我先看看它在哪里。", [self.tool_call("search_npcs")]),
            ("我冲上去劈砍，它倒下了。", []),
            ("剑光落下。", []),
        ]
        with patch.object(dm, "execute_tool", new=AsyncMock(return_value="地精斥候 在碎石坡")):
            await dm.process_player_action(self.state, "我挥剑攻击地精斥候。")

        # 只统计"重试型"强制提示（战斗前置提示不算）
        forced = [
            m for call in self.stream.await_args_list for m in call.args[2]
            if m.get("role") == "system" and "你刚才没有调用任何工具" in str(m.get("content", ""))
        ]
        self.assertTrue(forced, "调了非结算工具后仍应强制要求 combat_round")
        self.assertIn("combat_round", str(forced[0]["content"]))

    async def test_real_settlement_stops_the_retry(self):
        self.stream.side_effect = [
            ("剑锋劈下。", [self.tool_call("combat_round")]),
            ("它闷哼倒地。", []),
        ]
        with patch.object(dm, "execute_tool", new=AsyncMock(return_value="造成 7 点伤害")):
            await dm.process_player_action(self.state, "我挥剑攻击地精斥候。")

        forced = [
            m for call in self.stream.await_args_list for m in call.args[2]
            if m.get("role") == "system" and "你刚才没有调用任何工具" in str(m.get("content", ""))
        ]
        self.assertFalse(forced, "真正调用了 combat_round 时不应再强制重试")


if __name__ == "__main__":
    unittest.main()
