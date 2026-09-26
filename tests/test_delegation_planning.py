"""委派任务分配策略：候选不超过并发预算时，不该再花一次串行的分配 LLM 调用。

背景（实测）：一次分配调用约 1.04 秒 / 287 token，占单轮墙钟约 10%；
而候选 ≤ MAX_DELEGATED_TASKS 时它们本来就并发跑满，挑选并不省墙钟时间。
"""
import unittest
from contextlib import ExitStack
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.engine import dm_turn
from backend.engine.dm_brief import build_dm_brief_tasks, combat_roster_text
from backend.engine.dm_prompts import build_system_prompt
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestDelegationPlanningPolicy(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = GameSessionState("plan-policy", "char", "test",
                                      {"hp": 20, "game_system": "dnd5e"})
        self.state.world_state = WorldState(session_id="plan-policy")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(dm_turn, "_client", return_value=object()))
        self.stack.enter_context(patch.object(dm_turn, "_model", return_value="mock"))
        self.stack.enter_context(patch.object(
            dm_turn, "get_knowledge_base",
            return_value=SimpleNamespace(retrieve=lambda *a, **k: [])))
        self.stack.enter_context(patch("backend.engine.dm_modules.run_dm_dispatch",
                                       new=AsyncMock(return_value={"module": "combat"})))
        self.stack.enter_context(patch.object(dm_turn, "build_memory_context",
                                              new=AsyncMock(return_value={})))
        self.stack.enter_context(patch.object(dm_turn, "build_character_info", return_value="test"))
        self.planner = self.stack.enter_context(
            patch.object(dm_turn, "plan_task_keys", new=AsyncMock(return_value=["rules"])))
        self.delegates = self.stack.enter_context(
            patch.object(dm_turn, "run_tool_subagents", new=AsyncMock(return_value={})))

    async def _prepare(self, tasks):
        with patch.object(dm_turn, "build_dm_brief_tasks", return_value=tasks):
            return await dm_turn._prepare_turn(self.state, "我挥剑砍向地精")

    async def test_candidates_within_budget_skip_the_planner_call(self):
        tasks = [{"key": key} for key in ("rules", "combat", "world")]
        await self._prepare(tasks)
        self.planner.assert_not_awaited()
        run_tasks = self.delegates.await_args.args[2]
        self.assertEqual([t["key"] for t in run_tasks], ["rules", "combat", "world"],
                         "跳过分配器时应当跑满候选")

    async def test_candidates_over_budget_still_use_the_planner(self):
        tasks = [{"key": key} for key in ("rules", "combat", "world", "memory", "graph")]
        self.assertGreater(len(tasks), dm_turn.MAX_DELEGATED_TASKS,
                           "该用例的前提就是候选超过并发预算")
        await self._prepare(tasks)
        self.planner.assert_awaited_once()
        run_tasks = self.delegates.await_args.args[2]
        self.assertEqual([t["key"] for t in run_tasks], ["rules"],
                         "分配器的选择必须生效（只跑被选中的任务）")


class TestCombatFactsComeFromBackend(unittest.TestCase):
    """战斗名册是后端事实：主 DM 直接拿到，不再让子 Agent 复述一遍。"""

    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "roster", "char", "岚",
            {"hp": 12, "max_hp": 12, "ac": 16, "level": 1, "game_system": "dnd5e",
             "char_class": "战士", "race": "人类", "play_mode": "deep",
             "attributes": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
             "world_outline": "旧商道上的地精伏击。", "backstory": "为寻找兄长而旅行。"},
        )
        state.world_state = WorldState(session_id="roster", _storage_dir=tmp.name)
        state.world_state.npcs = [NpcEntry(
            name="地精斥候", attitude="敌对", hp=3, max_hp=7, ac=13, alive=True,
            location="旧商道",
        )]
        return state

    def test_roster_text_is_deterministic(self):
        ws = self.make_state().world_state
        text = combat_roster_text(ws)
        self.assertIn("### 战斗单位数值", text)
        self.assertIn("地精斥候", text)
        self.assertIn("HP:3/7", text)
        self.assertIn("AC:13", text)

    def test_plain_world_has_no_roster(self):
        state = self.make_state()
        state.world_state.npcs = [NpcEntry(name="村长", attitude="友好")]
        self.assertEqual(combat_roster_text(state.world_state), "",
                         "没有敌对单位时不该输出名册块")

    def test_combat_module_has_no_roster_agent(self):
        tasks = build_dm_brief_tasks(
            player_input="我挥砍地精斥候", module="combat", lite=False,
            system="dnd5e", char_info="HP 12", retrieved=[],
            memory_text="", recent_text="", world_text="", world_compact="", graph_text="",
        )
        keys = [t["key"] for t in tasks]
        self.assertNotIn("combat", keys, "名册已由后端提供，不该再有复述它的子 Agent")
        self.assertNotIn("memory", keys,
                         "战斗回合的连续性事实在主 DM 提示词里；实测 memory 子 Agent 最慢")
        self.assertEqual(keys, ["rules", "world"], "战斗回合只保留结算与场景两个子 Agent")
        self.assertLessEqual(len(keys), dm_turn.MAX_DELEGATED_TASKS,
                             "候选不超并发预算，dm_turn 应直接跑满而不再调用分配器")

    def test_dm_prompt_contains_the_roster(self):
        state = self.make_state()
        prompt = build_system_prompt(state, dispatch_plan={"module": "combat"})
        self.assertIn("### 战斗单位数值", prompt)
        self.assertIn("地精斥候", prompt)
        self.assertIn("HP:3/7", prompt)


if __name__ == "__main__":
    unittest.main()
