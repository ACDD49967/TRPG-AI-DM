"""法术专注（5e）：同时只维持一个、受伤掷体质豁免、昏迷中断、战地施法者优势。"""
import tempfile
import unittest
from unittest.mock import patch

from backend.engine import dm_agent as dm
from backend.engine.concentration import concentration_dc
from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState


class TestConcentrationRules(unittest.TestCase):
    def test_dc_floor_is_ten(self):
        self.assertEqual(concentration_dc(0), 10)
        self.assertEqual(concentration_dc(10), 10)
        self.assertEqual(concentration_dc(21), 10)
        self.assertEqual(concentration_dc(30), 15)
        self.assertEqual(concentration_dc(40), 20)


class TestConcentration(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def next_turn(state: GameSessionState) -> None:
        """模拟进入下一回合：行动经济账本每轮重置（否则同回合二次施法会被拒）。"""
        state.turn_action_ledger = {}
        state.turn_tool_results = {}

    def make_state(self, hp: int = 30, feats: list | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "conc", "char", "岚",
            {"hp": hp, "max_hp": 30, "ac": 15, "level": 5, "game_system": "dnd5e",
             "char_class": "法师", "attributes": {"con": 14, "int": 16},
             "spell_slots": {"spell_slots": [4, 3, 2], "pact_slots": 0},
             "feats": feats or []},
        )
        state.world_state = WorldState(session_id="conc", _storage_dir=tmp.name)
        return state

    async def test_concentration_spell_is_recorded_and_replaced(self):
        state = self.make_state()
        first = await dm.execute_tool(
            "cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        self.assertIn("祝福术", state.character_info["concentration"]["spell"])
        self.assertNotIn("专注中断", first)

        self.next_turn(state)
        second = await dm.execute_tool(
            "cast_spell", {"name": "魅惑人类", "level": 1, "concentration": True}, state)
        self.assertIn("专注中断：祝福术", second, "新专注法术应中断旧的")
        self.assertEqual(state.character_info["concentration"]["spell"], "魅惑人类")

    async def test_non_concentration_spell_keeps_concentration(self):
        state = self.make_state()
        await dm.execute_tool("cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        self.next_turn(state)
        result = await dm.execute_tool("cast_spell", {"name": "魔法飞弹", "level": 1}, state)
        self.assertIn("魔法飞弹", result, "非专注法术应正常施放")
        self.assertEqual(state.character_info["concentration"]["spell"], "祝福术")

    async def test_damage_queues_concentration_save_with_dc(self):
        state = self.make_state(hp=30)
        await dm.execute_tool("cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        with patch("backend.engine.concentration.random.randint", return_value=15):
            await dm._exec_update_state({"changes": {"hp": -21}, "reason": "巨斧"}, state)
        hint = next(h for h in state.pending_system_hints if h.startswith("[系统强制-专注]"))
        self.assertIn("DC 10", hint, "21 点伤害 → DC max(10, 10) = 10")
        self.assertIn("维持专注", hint)

        with patch("backend.engine.concentration.random.randint", return_value=15):
            await dm._exec_update_state({"changes": {"hp": -1}, "reason": "补刀"}, state)
        hints = [h for h in state.pending_system_hints if h.startswith("[系统强制-专注]")]
        self.assertEqual(len(hints), 1, "多次受伤只保留最新一条专注提示")
        self.assertIn("DC 10", hints[0])

    async def test_high_damage_raises_dc(self):
        state = self.make_state(hp=60)
        state.character_info["max_hp"] = 60
        await dm.execute_tool("cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        with patch("backend.engine.concentration.random.randint", return_value=20):
            await dm._exec_update_state({"changes": {"hp": -40}, "reason": "龙息"}, state)
        hint = next(h for h in state.pending_system_hints if h.startswith("[系统强制-专注]"))
        self.assertIn("DC 20", hint, "40 点伤害 → DC 20")

    async def test_war_caster_grants_advantage_hint(self):
        state = self.make_state(feats=[{"id": "war_caster", "name": "战地施法者"}])
        await dm.execute_tool("cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        with patch("backend.engine.concentration.random.randint", side_effect=[3, 18]):
            await dm._exec_update_state({"changes": {"hp": -10}, "reason": "箭矢"}, state)
        hint = next(h for h in state.pending_system_hints if h.startswith("[系统强制-专注]"))
        self.assertIn("优势", hint, "战地施法者应让专注豁免有优势")
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertEqual(rolls[-1]["roll"], 18, "优势取两次中的高值")
        self.assertEqual(rolls[-1]["advantage_note"], "战地施法者")

    async def test_backend_rolls_the_save_and_breaks_concentration_on_failure(self):
        """后端化重点：不再只发提示让 DM 掷骰，失败时直接中断专注。"""
        state = self.make_state(hp=30)
        await dm.execute_tool("cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        with patch("backend.engine.concentration.random.randint", return_value=1):
            await dm._exec_update_state({"changes": {"hp": -21}, "reason": "巨斧"}, state)
        self.assertIsNone(state.character_info.get("concentration"), "豁免失败应直接中断专注")
        events = [d for _, t, d in state.event_history if t == "game_event"]
        self.assertTrue(any(d.get("type") == "concentration_broken" for d in events))
        hint = next(h for h in state.pending_system_hints if h.startswith("[系统强制-专注]"))
        self.assertIn("专注被打断", hint)

    async def test_successful_save_keeps_concentration(self):
        state = self.make_state(hp=30)
        await dm.execute_tool("cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        with patch("backend.engine.concentration.random.randint", return_value=12):
            await dm._exec_update_state({"changes": {"hp": -12}, "reason": "匕首"}, state)
        self.assertEqual(state.character_info["concentration"]["spell"], "祝福术")
        rolls = [d for _, t, d in state.event_history if t == "dice_roll"]
        self.assertIn("专注", str(rolls[-1]["skill"]))
        self.assertEqual(rolls[-1]["result"], "成功")

    async def test_no_save_without_concentration(self):
        state = self.make_state(hp=30)
        with patch("backend.engine.concentration.random.randint", return_value=1) as rnd:
            await dm._exec_update_state({"changes": {"hp": -5}, "reason": "陷阱"}, state)
        self.assertFalse(rnd.called, "没有专注就不该掷专注豁免")
        self.assertFalse(any(t == "dice_roll" for _, t, _ in state.event_history))

    async def test_concentration_clear_and_unconscious_break(self):
        state = self.make_state()
        await dm.execute_tool("cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        await dm._exec_update_state(
            {"changes": {"concentration_clear": True}, "reason": "豁免失败"}, state)
        self.assertIsNone(state.character_info.get("concentration"))
        updates = [d for _, t, d in state.event_history if t == "state_update"]
        self.assertTrue(any(d.get("concentration_cleared") == "祝福术" for d in updates))

        self.next_turn(state)
        again = await dm.execute_tool(
            "cast_spell", {"name": "魅惑人类", "level": 1, "concentration": True}, state)
        self.assertIn("魅惑人类", again, "中断后可以重新施放专注法术")
        self.assertEqual(state.character_info["concentration"]["spell"], "魅惑人类")
        await dm._exec_update_state({"changes": {"hp": -30}, "reason": "被打倒"}, state)
        self.assertIsNone(state.character_info.get("concentration"), "昏迷应中断专注")

    async def test_concentration_survives_save_load(self):
        from pathlib import Path

        from backend import save_manager as saves

        state = self.make_state()
        await dm.execute_tool("cast_spell", {"name": "祝福术", "level": 1, "concentration": True}, state)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old_root = saves.SAVE_ROOT
        saves.SAVE_ROOT = Path(tmp.name)
        try:
            payload = saves.create_save(state, label="专注存档")
            raw = saves.load_save(state.username, payload["id"])
            restored, _ = saves.restore_state_from_save(raw)
        finally:
            saves.SAVE_ROOT = old_root
        self.assertEqual(restored.character_info["concentration"]["spell"], "祝福术")


if __name__ == "__main__":
    unittest.main()
