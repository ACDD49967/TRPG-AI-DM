# -*- coding: utf-8 -*-
"""核心修复的零依赖回归测试（unittest）。

运行：
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.engine.knowledge_graph import build_player_graph, graph_to_context
from backend.engine.session import GameSessionState, SessionManager, push_event, sse_event_generator
from backend.engine.tools import DM_TOOLS
from backend.engine.world_state import LocationEntry, NpcEntry, NpcVisibility, WorldState
from backend.paths import safe_username
from backend.task_center import TaskManager


class TestPaths(unittest.TestCase):
    def test_safe_username_blocks_traversal(self):
        self.assertEqual(safe_username(".."), "default")
        self.assertEqual(safe_username("../x"), "x")
        self.assertEqual(safe_username("a/b\\c"), "a_b_c")
        self.assertEqual(safe_username("霍华德"), "霍华德")
        self.assertNotIn("..", safe_username(".."))


class TestPlayerViewAndGraph(unittest.TestCase):
    def _ws(self):
        ws = WorldState(session_id="test", _storage_dir=tempfile.mkdtemp())
        hidden = NpcEntry(name="隐藏者", role="反派", level=10, ac=20, hp=100, max_hp=100,
                          discovered=False, visibility=NpcVisibility.mysterious())
        visible = NpcEntry(name="公开者", role="商人", level=3, ac=12, hp=20, max_hp=20,
                           visibility=NpcVisibility())
        ws.add_npc(hidden)
        ws.add_npc(visible)
        ws.add_location(LocationEntry(name="测试城", type="城镇"))
        return ws

    def test_player_view_hides_sensitive_fields(self):
        npc = NpcEntry(name="神秘人", role="反派", level=10, ac=20, hp=100, max_hp=100,
                       image_path="/media/x.png", related_npcs=["某人"],
                       visibility=NpcVisibility.mysterious())
        view = npc.to_player_view()
        self.assertFalse(view["fully_revealed"])
        for key in ("level", "ac", "hp", "max_hp", "image_path", "related_npcs"):
            self.assertIn(key, view)
        self.assertIsNone(view["level"])
        self.assertIsNone(view["ac"])
        self.assertEqual(view["image_path"], "")
        self.assertEqual(view["related_npcs"], [])

    def test_player_view_reveals_stats_when_fully_revealed(self):
        npc = NpcEntry(name="盟友", level=5, ac=15, hp=30, max_hp=30,
                       visibility=NpcVisibility.full_reveal())
        view = npc.to_player_view()
        self.assertTrue(view["fully_revealed"])
        self.assertEqual(view["level"], 5)
        self.assertEqual(view["ac"], 15)

    def test_player_graph_hidden_topology_not_leaked(self):
        graph = build_player_graph(self._ws())
        labels = {n["label"] for n in graph["nodes"]}
        self.assertIn("公开者", labels)
        self.assertIn("???", labels)  # 聚合提示
        hidden_nodes = [n for n in graph["nodes"] if n["label"] == "???"]
        self.assertEqual(len(hidden_nodes), 1)
        # 公开者 + 测试城 + 一个聚合 ??? 节点
        self.assertEqual(len(graph["nodes"]), 3)
        # 隐藏实体不应出现在任何边中，也不应出现 ???1/???2 这类占位 id
        for edge in graph["edges"]:
            self.assertNotIn("隐藏者", (edge["source"], edge["target"]))
        self.assertFalse(any(str(n["id"]).startswith("???") for n in graph["nodes"]))

    def test_graph_to_context(self):
        text = graph_to_context(self._ws())
        self.assertIn("关系图谱摘要", text)
        self.assertIn("公开者", text)


class TestToolsCoverage(unittest.TestCase):
    def test_all_tools_in_some_module(self):
        from backend.engine.dm_agent import MODULE_TOOL_NAMES
        covered = {name for names in MODULE_TOOL_NAMES.values() for name in names}
        all_names = {t["function"]["name"] for t in DM_TOOLS}
        missing = all_names - covered - {"suggest_choices"}
        self.assertEqual(missing, set(), f"未进入任何模块白名单的工具: {sorted(missing)}")


class TestTaskCenter(unittest.TestCase):
    def test_json_safe_and_prune(self):
        manager = TaskManager()
        task = manager.create("unit", message="x")
        task.result = {"nested": object()}
        json.dumps(task.to_dict(), default=str)  # 不应抛异常
        for _ in range(260):
            manager.create("unit")
        manager.prune(max_age_seconds=9999, max_tasks=200)
        self.assertLessEqual(len(manager.list(limit=999)), 200)


class TestSessionSse(unittest.IsolatedAsyncioTestCase):
    def _state(self):
        return GameSessionState(
            session_id="s1", character_id="c1", character_name="测试",
            character_info={"hp": 10, "max_hp": 10},
        )

    async def test_push_event_broadcasts_to_all_subscribers(self):
        state = self._state()
        q1, q2 = asyncio.Queue(), asyncio.Queue()
        state.subscribers.update({q1, q2})
        await push_event(state, "narrative", {"token": "hi"})
        e1 = await asyncio.wait_for(q1.get(), 1)
        e2 = await asyncio.wait_for(q2.get(), 1)
        self.assertEqual(e1, e2)
        self.assertEqual(e1[0], 1)
        self.assertEqual(state.event_history[-1][0], 1)

    async def test_reconnect_replays_without_opening(self):
        state = self._state()
        for i in range(3):
            await push_event(state, "narrative", {"token": str(i)})
        state.status = "ended"
        gen = sse_event_generator(state, last_event_id=1)
        chunks = []
        async def collect():
            async for c in gen:
                chunks.append(c)
        await asyncio.wait_for(collect(), 2)
        text = "".join(chunks)
        self.assertIn("id: 2", text)
        self.assertIn("id: 3", text)
        self.assertNotIn("id: 1\n", text)
        self.assertNotIn("state_update", text)  # 重连不重放开场/初始状态

    async def test_prune_idle(self):
        manager = SessionManager()
        state = manager.create_session("old", "c", "n", {})
        state.status = "ended"
        state.last_active_at = time.time() - 10000
        removed = manager.prune_idle(max_idle_seconds=3600)
        self.assertIn("old", removed)
        self.assertIsNone(manager.get_session("old"))


class TestSaveManager(unittest.TestCase):
    def test_save_omits_api_key_and_restores_dynamic(self):
        import backend.save_manager as sm
        from backend.engine.rules import DeathSaves
        with tempfile.TemporaryDirectory() as td:
            old_root = sm.SAVE_ROOT
            sm.SAVE_ROOT = Path(td)
            try:
                state = GameSessionState(
                    session_id="s1", character_id="c1", character_name="测试",
                    character_info={"game_system": "dnd5e"},
                    api_key="sk-secret-should-not-be-saved",
                    model_name="m",
                )
                state._death_saves = DeathSaves(successes=1, failures=2)
                state._hit_dice_remaining = 3
                save = sm.create_save(state, label="单测")
                self.assertNotIn("api_key", save["session"])
                path = sm._save_path(state.username, save["id"])
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.assertNotIn("api_key", raw["session"])
                restored, _ = sm.restore_state_from_save(raw)
                self.assertEqual(restored._death_saves.successes, 1)
                self.assertEqual(restored._death_saves.failures, 2)
                self.assertEqual(restored._hit_dice_remaining, 3)
            finally:
                sm.SAVE_ROOT = old_root


class TestMediaAsdict(unittest.TestCase):
    def test_sync_scenario_maps_accepts_dataclass(self):
        import backend.media_manager as mm
        with tempfile.TemporaryDirectory() as td:
            old_root = mm.MEDIA_ROOT
            old_seed = mm.ensure_seeded
            old_imports = (mm._import_kb_monsters, mm._import_dnd4_pdf_monsters, mm._import_kb_locations)
            mm.MEDIA_ROOT = Path(td)
            try:
                mm.ensure_seeded = lambda username: None
                mm._import_kb_monsters = lambda username: None
                mm._import_dnd4_pdf_monsters = lambda username: None
                mm._import_kb_locations = lambda username: None
                mm.sync_scenario_maps("u", "scn", [LocationEntry(name="城", type="城镇")], "custom")
                items = mm.list_maps_exact("u", "scn")
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["scenario_id"], "scn")
            finally:
                mm.MEDIA_ROOT = old_root
                mm.ensure_seeded = old_seed
                mm._import_kb_monsters, mm._import_dnd4_pdf_monsters, mm._import_kb_locations = old_imports


if __name__ == "__main__":
    unittest.main()
