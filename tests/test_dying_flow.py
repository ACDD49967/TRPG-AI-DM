"""濒死流程安全网：HP 0 必须进入濒死、必须有死亡豁免推进。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestDyingFlow(unittest.IsolatedAsyncioTestCase):
    def make_state(self, hp: int = 12, system: str = "dnd5e") -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "dying", "char", "测试",
            {"hp": hp, "max_hp": 12, "ac": 16, "level": 1, "xp": 0,
             "game_system": system, "attributes": {"con": 14}},
        )
        state.world_state = WorldState(session_id="dying", _storage_dir=tmp.name)
        return state

    async def test_damage_to_zero_enters_dying_and_hints_dm(self):
        state = self.make_state(hp=3)
        await dm._exec_update_state({"changes": {"hp": -5}, "reason": "地精攻击"}, state)

        self.assertEqual(state.character_info["hp"], 0)
        self.assertTrue(state.dying)
        self.assertTrue(any(h.startswith("[系统强制-濒死]") for h in state.pending_system_hints))
        events = [(t, d) for _, t, d in state.event_history]
        self.assertTrue(
            any(t == "game_event" and d.get("type") == "dying" for t, d in events),
            "应推送玩家可见的濒死提示事件",
        )

    async def test_healing_clears_dying(self):
        state = self.make_state(hp=2)
        await dm._exec_update_state({"changes": {"hp": -2}, "reason": "受创"}, state)
        self.assertTrue(state.dying)

        await dm._exec_update_state({"changes": {"hp": 4}, "reason": "治疗药水"}, state)
        self.assertFalse(state.dying)
        self.assertEqual(state.character_info["hp"], 4)
        self.assertEqual(state.pending_system_hints, [])

    async def test_coc_has_no_dying_flow(self):
        state = self.make_state(hp=2, system="coc")
        await dm._exec_update_state({"changes": {"hp": -2}, "reason": "深潜者"}, state)
        self.assertFalse(state.dying)

    async def test_auto_death_save_fires_once_per_turn(self):
        state = self.make_state(hp=1)
        await dm._exec_update_state({"changes": {"hp": -1}, "reason": "受创"}, state)

        first = await dm._maybe_auto_death_save(state)
        self.assertIn("死亡豁免", first)
        self.assertEqual(state._death_save_turn, state.world_state.turn_count)

        # 同一回合重复调用不会二次掷骰
        self.assertEqual(await dm._maybe_auto_death_save(state), "")

    async def test_no_auto_save_when_dm_already_rolled(self):
        state = self.make_state(hp=1)
        await dm._exec_update_state({"changes": {"hp": -1}, "reason": "受创"}, state)
        await dm._exec_death_save({}, state)
        turns_before = getattr(state._death_saves, "successes", 0) + getattr(state._death_saves, "failures", 0)

        self.assertEqual(await dm._maybe_auto_death_save(state), "")
        after = getattr(state._death_saves, "successes", 0) + getattr(state._death_saves, "failures", 0)
        self.assertEqual(turns_before, after)

    async def test_stabilising_stops_the_clock(self):
        state = self.make_state(hp=1)
        await dm._exec_update_state({"changes": {"hp": -1}, "reason": "受创"}, state)
        state._death_saves.successes = 3
        state._death_saves.failures = 0

        # 固定 d20=15（成功）才能稳定；否则这条测试会随随机结果时好时坏
        with patch("backend.engine.rules.roll_d20", return_value=15):
            await dm._exec_death_save({}, state)
        self.assertFalse(state.dying, "三次成功后应稳定，不再每回合掷豁免")
        self.assertEqual(await dm._maybe_auto_death_save(state), "")

    async def test_natural_twenty_restores_one_hp_and_clears_dying(self):
        state = self.make_state(hp=1)
        await dm._exec_update_state({"changes": {"hp": -1}, "reason": "受创"}, state)
        with patch("backend.engine.rules.roll_d20", return_value=20):
            await dm._exec_death_save({}, state)
        self.assertEqual(state.character_info["hp"], 1)
        self.assertFalse(state.dying)

    async def test_dying_player_cannot_be_attacked_into_negative_hp(self):
        state = self.make_state(hp=4)
        await dm._exec_update_state({"changes": {"hp": -9}, "reason": "重击"}, state)
        self.assertEqual(state.character_info["hp"], 0, "HP 不应出现负值")
        self.assertTrue(state.dying)

    async def test_dying_and_death_survive_save_load(self):
        """濒死/死亡状态必须进存档，否则读档后死亡锁定和濒死时钟会消失。"""
        import json

        from backend import save_manager as saves

        state = self.make_state(hp=2)
        await dm._exec_update_state({"changes": {"hp": -5}, "reason": "重击"}, state)
        state._death_saves.failures = 2

        with_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(with_tmp.cleanup)
        old_root = saves.SAVE_ROOT
        saves.SAVE_ROOT = Path(with_tmp.name)
        try:
            payload = saves.create_save(state, label="濒死存档")
            raw = json.loads(saves._save_path(state.username, payload["id"]).read_text(encoding="utf-8"))
            self.assertTrue(raw["session"]["dynamic_state"]["dying"])
            restored, _ = saves.restore_state_from_save(raw)
        finally:
            saves.SAVE_ROOT = old_root

        self.assertTrue(restored.dying, "读档后仍应处于濒死")
        self.assertEqual(restored.character_info["hp"], 0)
        self.assertEqual(restored._death_saves.failures, 2)
        self.assertEqual(restored.character_dead, False)

        # 死亡锁定同样要保留
        state.character_dead = True
        state.dying = False
        saves.SAVE_ROOT = Path(with_tmp.name)
        try:
            payload2 = saves.create_save(state, label="死亡存档")
            saved2 = saves.load_save(state.username, payload2["id"])
            restored2, _ = saves.restore_state_from_save(saved2)
        finally:
            saves.SAVE_ROOT = old_root
        self.assertTrue(restored2.character_dead, "死亡状态读档后不能复活")


if __name__ == "__main__":
    unittest.main()
