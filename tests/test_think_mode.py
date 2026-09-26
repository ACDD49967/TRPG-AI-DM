"""思考档位映射：界面选“中”必须真的走中间档，而不是偷偷跑“高”。"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState


class TestThinkMode(unittest.TestCase):
    def make_state(self, strength: str) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState("think", "c", "n", {"game_system": "dnd5e"})
        state.world_state = WorldState(session_id="think", _storage_dir=tmp.name)
        state.thinking_strength = strength
        return state

    def test_player_choice_is_respected_for_narrative(self):
        self.assertEqual(dm.dm_think_mode(self.make_state("low"), "narrative"), "low")
        self.assertEqual(dm.dm_think_mode(self.make_state("medium"), "narrative"), "auto")
        self.assertEqual(dm.dm_think_mode(self.make_state("high"), "narrative"), "high")

    def test_settlement_modules_stay_fast(self):
        for module in ("rules", "combat", "memory", "graph"):
            for strength in ("low", "medium", "high"):
                self.assertEqual(dm.dm_think_mode(self.make_state(strength), module), "fixed")

    def test_thinking_params_match_each_gear(self):
        medium = self.make_state("medium")
        self.assertEqual(dm._call_thinking_params(medium, "auto"), dm._thinking_params(medium))
        self.assertEqual(dm._thinking_extra_body(medium, "auto"), {})
        high = self.make_state("high")
        self.assertEqual(dm._thinking_extra_body(high, "high"), {"thinking": {"type": "enabled"}})
        self.assertGreater(dm._call_thinking_params(high, "high")[0],
                           dm._call_thinking_params(medium, "auto")[0])
        low = self.make_state("low")
        self.assertEqual(dm._thinking_extra_body(low, "low"), {"thinking": {"type": "disabled"}})


if __name__ == "__main__":
    unittest.main()
