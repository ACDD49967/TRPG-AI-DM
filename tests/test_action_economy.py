"""行动经济：默认一单位一主行动，额外行动需声明来源且受限。"""
import tempfile
import unittest

from backend.engine import tool_executor as te
from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry, WorldState


class TestActionEconomy(unittest.TestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState("economy", "c", "岚", {"game_system": "dnd5e"})
        state.world_state = WorldState(session_id="economy", _storage_dir=tmp.name)
        state.world_state.npcs = [NpcEntry(name="地精斥候", attitude="敌对", hp=7, max_hp=7, alive=True)]
        state.turn_action_ledger = {}
        return state

    def test_primary_action_then_declared_extra(self):
        state = self.make_state()
        self.assertTrue(te.consume_action(state, "岚")[0])
        blocked, reason = te.consume_action(state, "岚")
        self.assertFalse(blocked)
        self.assertIn("action_source", reason)
        self.assertTrue(te.consume_action(state, "岚", "multiattack", 2)[0])

    def test_multiattack_quota_and_override(self):
        state = self.make_state()
        # 声明 3 段就是 3 次；未声明时按该来源默认上限（multiattack=4）
        for _ in range(3):
            self.assertTrue(te.consume_action(state, "岚", "multiattack", 3)[0])
        blocked, reason = te.consume_action(state, "岚", "multiattack", 3)
        self.assertFalse(blocked)
        self.assertIn("3", reason)

    def test_multiattack_default_quota_is_four(self):
        state = self.make_state()
        for _ in range(4):
            self.assertTrue(te.consume_action(state, "岚", "multiattack")[0])
        self.assertFalse(te.consume_action(state, "岚", "multiattack")[0])

    def test_declared_count_can_raise_quota(self):
        state = self.make_state()
        for _ in range(5):
            self.assertTrue(te.consume_action(state, "岚", "homebrew_flurry", 5)[0])
        self.assertFalse(te.consume_action(state, "岚", "homebrew_flurry", 5)[0])

    def test_absurd_declared_count_is_capped(self):
        state = self.make_state()
        for _ in range(8):
            self.assertTrue(te.consume_action(state, "岚", "homebrew_flurry", 99)[0])
        self.assertFalse(te.consume_action(state, "岚", "homebrew_flurry", 99)[0])

    def test_unknown_source_is_bounded(self):
        state = self.make_state()
        self.assertTrue(te.consume_action(state, "岚", "some_homebrew_feature")[0])
        self.assertFalse(te.consume_action(state, "岚", "some_homebrew_feature")[0])

    def test_legendary_action_allows_three(self):
        state = self.make_state()
        for _ in range(3):
            self.assertTrue(te.consume_action(state, "巨龙", "legendary_action")[0])
        self.assertFalse(te.consume_action(state, "巨龙", "legendary_action")[0])

    def test_actor_names_are_canonicalised(self):
        state = self.make_state()
        self.assertTrue(te.consume_action(state, "地精斥候（受伤）")[0])
        blocked, _ = te.consume_action(state, "地精斥候")
        self.assertFalse(blocked, "带注解的名字应归一到同一个敌人")

    def test_primary_action_available_reports_state(self):
        state = self.make_state()
        self.assertTrue(te.primary_action_available(state, "地精斥候"))
        te.consume_action(state, "地精斥候")
        self.assertFalse(te.primary_action_available(state, "地精斥候"))


if __name__ == "__main__":
    unittest.main()
