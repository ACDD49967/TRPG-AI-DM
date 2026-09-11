# -*- coding: utf-8 -*-
"""世界状态生命周期维护与删除动作测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.engine.dm_agent import _exec_prune_world_state, _exec_update_world_state
from backend.engine.session import GameSessionState
from backend.engine.world_state import (
    CharacterNote, LocationEntry, NpcEntry, NotableEntry, PlotFlag, WorldState,
)


class TestWorldMaintenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = WorldState(session_id="lifecycle_test", _storage_dir=self.tmp.name)
        self.ws.turn_count = 100
        self.ws.npcs = [
            NpcEntry(name="临时路人", importance="minor", alive=False,
                     turn_added=5, turn_last_seen=10),
            NpcEntry(name="长期盟友", importance="major", alive=True,
                     turn_added=1, turn_last_seen=10),
            NpcEntry(name="当前NPC", importance="minor", alive=True,
                     turn_added=90, turn_last_seen=100),
        ]
        self.ws.scene.visible_npcs_here = ["当前NPC"]
        self.ws.scene.current_location = "当前城"
        self.ws.locations = [
            LocationEntry(name="当前城", discovered=True, turn_added=1, turn_last_visited=100),
            LocationEntry(name="废弃矿洞", status="已废弃", discovered=True,
                          turn_added=5, turn_last_visited=10),
            LocationEntry(name="未来地点", status="可访问", discovered=False,
                          turn_added=5, turn_last_visited=0),
        ]
        self.ws.plot_flags = [
            PlotFlag(key="旧任务", status="已完成", turn_added=1, turn_resolved=10),
            PlotFlag(key="进行中任务", status="进行中", turn_added=20, turn_resolved=0),
            PlotFlag(key="新完成任务", status="已完成", turn_added=90, turn_resolved=95),
        ]
        self.ws.notables = [
            NotableEntry(name="已取走物品", status="已拿走", turn_added=5),
            NotableEntry(name="未解决线索", status="", turn_added=90),
        ]
        self.ws.character_notes = [
            CharacterNote(target="临时路人", target_type="npc", turn_added=10),
            CharacterNote(target="当前NPC", target_type="npc", turn_added=99),
        ]
        self.ws.relations = [
            {"source": "临时路人", "target": "长期盟友", "relation": "旧识",
             "strength": 50, "confidence": 0.5, "turn_updated": 10},
            {"source": "当前NPC", "target": "当前城", "relation": "位于",
             "strength": 80, "confidence": 0.9, "turn_updated": 100},
            {"source": "幽灵实体", "target": "无人知晓", "relation": "悬空",
             "strength": 10, "confidence": 0.1, "turn_updated": 1},
        ]
        self.ws.change_log = [{"description": str(i)} for i in range(400)]
        self.ws.background_events = [{"event": str(i), "turn": i} for i in range(150)]

    def tearDown(self):
        self.tmp.cleanup()

    def test_maintenance_removes_stale(self):
        summary = self.ws.maintenance(scope="all", older_than_turns=20)
        names = {n.name for n in self.ws.npcs}
        self.assertNotIn("临时路人", names)
        self.assertIn("长期盟友", names)
        self.assertIn("当前NPC", names)
        self.assertTrue(summary["npcs"] >= 1)

        loc_names = {l.name for l in self.ws.locations}
        self.assertNotIn("废弃矿洞", loc_names)
        self.assertIn("当前城", loc_names)
        self.assertIn("未来地点", loc_names)

        flag_keys = {f.key for f in self.ws.plot_flags}
        self.assertNotIn("旧任务", flag_keys)
        self.assertIn("进行中任务", flag_keys)
        self.assertIn("新完成任务", flag_keys)

        notable_names = {n.name for n in self.ws.notables}
        self.assertNotIn("已取走物品", notable_names)
        self.assertIn("未解决线索", notable_names)

        note_targets = {n.target for n in self.ws.character_notes}
        self.assertNotIn("临时路人", note_targets)
        self.assertIn("当前NPC", note_targets)

        for rel in self.ws.relations:
            self.assertNotEqual(rel.get("source"), "幽灵实体")
            self.assertNotEqual(rel.get("source"), "临时路人")
        self.assertLessEqual(len(self.ws.change_log), 300)
        self.assertLessEqual(len(self.ws.background_events), 100)

    def test_dry_run_does_not_modify(self):
        before = len(self.ws.npcs)
        summary = self.ws.maintenance(scope="all", older_than_turns=20, dry_run=True)
        self.assertGreater(summary["removed_total"], 0)
        self.assertEqual(len(self.ws.npcs), before)


class TestWorldRemovalActions(unittest.IsolatedAsyncioTestCase):
    def _state(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ws = WorldState(session_id="actions_test", _storage_dir=tmp.name)
        ws.turn_count = 5
        ws.character_notes = [CharacterNote(target="某人", target_type="npc")]
        ws.relations = [{"source": "A", "target": "B", "relation": "盟友",
                         "strength": 50, "confidence": 0.5}]
        state = GameSessionState(session_id="s", character_id="c", character_name="n",
                                 character_info={})
        state.world_state = ws
        return state

    async def test_remove_character_note(self):
        state = self._state()
        msg = await _exec_update_world_state(
            {"action": "remove_character_note", "target": "某人",
             "changes": {"target_type": "npc"}, "reason": "过期"}, state)
        self.assertIn("已移除角色笔记", msg)
        self.assertEqual(state.world_state.character_notes, [])

    async def test_remove_relation(self):
        state = self._state()
        msg = await _exec_update_world_state(
            {"action": "remove_relation", "target": "A",
             "changes": {"target": "B", "relation": "盟友"}, "reason": "关系破裂"}, state)
        self.assertIn("已移除关系", msg)
        self.assertEqual(state.world_state.relations, [])

    async def test_prune_tool_dry_run(self):
        state = self._state()
        state.world_state.npcs = [NpcEntry(name="临时", importance="minor", alive=False,
                                           turn_added=0, turn_last_seen=0)]
        state.world_state.turn_count = 100
        msg = await _exec_prune_world_state({"scope": "all", "dry_run": True}, state)
        self.assertIn("dry_run", msg)
        self.assertEqual(len(state.world_state.npcs), 1)


if __name__ == "__main__":
    unittest.main()
