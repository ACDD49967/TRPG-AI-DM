"""状态效果（中毒/麻痹等）：记录、展示、递减与过期。"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState


class TestConditions(unittest.IsolatedAsyncioTestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "cond", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": 3, "game_system": "dnd5e",
             "attributes": {"str": 12, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="cond", _storage_dir=tmp.name)
        return state

    async def test_add_and_remove_conditions(self):
        state = self.make_state()
        await dm._exec_update_state(
            {"changes": {"conditions_add": {"name": "中毒", "description": "攻击检定劣势",
                                            "remaining_rounds": 3}}, "reason": "毒针陷阱"}, state)
        conditions = state.character_info["conditions"]
        self.assertEqual(len(conditions), 1)
        self.assertEqual(conditions[0]["name"], "中毒")
        self.assertEqual(conditions[0]["remaining_rounds"], 3)

        # 同名重复施加不叠加成两条，而是刷新时长/描述
        await dm._exec_update_state(
            {"changes": {"conditions_add": {"name": "中毒", "remaining_rounds": 5}},
             "reason": "再次中毒"}, state)
        self.assertEqual(len(state.character_info["conditions"]), 1)
        self.assertEqual(state.character_info["conditions"][0]["remaining_rounds"], 5)

        await dm._exec_update_state(
            {"changes": {"conditions_remove": "中毒"}, "reason": "解毒剂"}, state)
        self.assertEqual(state.character_info["conditions"], [])

    async def test_conditions_are_pushed_and_visible_to_dm(self):
        state = self.make_state()
        await dm._exec_update_state(
            {"changes": {"conditions_add": ["麻痹", {"name": "束缚", "remaining_rounds": 2}]},
             "reason": "法术"}, state)
        updates = [d for _, t, d in state.event_history if t == "state_update"]
        self.assertTrue(any(d.get("conditions_added") == ["麻痹", "束缚"] for d in updates))

        info = dm.build_character_info(state)
        self.assertIn("状态效果", info)
        self.assertIn("麻痹", info)
        self.assertIn("束缚", info)

    async def test_conditions_tick_down_and_expire(self):
        state = self.make_state()
        await dm._exec_update_state(
            {"changes": {"conditions_add": {"name": "目盲", "remaining_rounds": 2}},
             "reason": "闪光"}, state)

        await dm.tick_conditions(state)
        remaining = state.character_info["conditions"][0]["remaining_rounds"]
        self.assertEqual(remaining, 1)
        self.assertFalse(any(d.get("type") == "condition_expired"
                             for _, t, d in state.event_history if t == "game_event"))

        await dm.tick_conditions(state)
        self.assertEqual(state.character_info["conditions"], [])
        self.assertTrue(any(d.get("type") == "condition_expired"
                            for _, t, d in state.event_history if t == "game_event"),
                        "状态过期应推送通知")
        # 过期后推送给前端的列表里不应再包含该状态
        pushed = [d.get("conditions") for _, t, d in state.event_history
                  if t == "state_update" and "conditions" in d]
        self.assertEqual(pushed[-1], [], "过期状态不能被重新推给前端")

    async def test_permanent_condition_is_not_expired(self):
        state = self.make_state()
        await dm._exec_update_state(
            {"changes": {"conditions_add": {"name": "诅咒"}}, "reason": "仪式"}, state)
        for _ in range(3):
            await dm.tick_conditions(state)
        self.assertEqual([c["name"] for c in state.character_info["conditions"]], ["诅咒"])

    async def test_conditions_survive_save_load(self):
        from backend import save_manager as saves
        from pathlib import Path

        state = self.make_state()
        await dm._exec_update_state(
            {"changes": {"conditions_add": {"name": "中毒", "remaining_rounds": 4}},
             "reason": "毒"}, state)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old_root = saves.SAVE_ROOT
        saves.SAVE_ROOT = Path(tmp.name)
        try:
            payload = saves.create_save(state, label="中毒存档")
            raw = saves.load_save(state.username, payload["id"])
            restored, _ = saves.restore_state_from_save(raw)
        finally:
            saves.SAVE_ROOT = old_root
        self.assertEqual(restored.character_info["conditions"][0]["name"], "中毒")
        self.assertEqual(restored.character_info["conditions"][0]["remaining_rounds"], 4)


if __name__ == "__main__":
    unittest.main()
