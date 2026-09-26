"""玩家可见叙事去重：工具结算行与幕后台词不应被 DM 复述进来。"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState


class TestNarrativeDedupe(unittest.IsolatedAsyncioTestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState("dedupe-text", "c", "n", {"game_system": "dnd5e"})
        state.world_state = WorldState(session_id="dedupe-text", _storage_dir=tmp.name)
        return state

    def test_tool_echo_lines_are_dropped(self):
        for line in (
            "🎲 死亡豁免: d20=11 vs DC10 → 成功（1/3）",
            "🚨 魅力（说服）检定: d20=17+0=17 vs DC15 → 成功",
            " 攻击: d20=4+5=9 vs AC13→失败",
            "⚔️ 战斗结算（D&D5e d20）",
            "💀 地精斥候被击败！（+50 XP）",
            "🛌 短休: +8HP，短休资源已恢复",
            "\n☠️ 呼吸停止了。",
            "造成 1 点伤害 (敌人HP: 6/7)",
        ):
            self.assertFalse(dm._is_player_visible_segment(line), line)

    def test_normal_narration_and_meta_leak_rules_unchanged(self):
        self.assertTrue(dm._is_player_visible_segment("剑锋擦过它的肩甲，裂开一道口子。"))
        self.assertTrue(dm._is_player_visible_segment(""))
        self.assertFalse(dm._is_player_visible_segment("我来结算这次攻击。"))
        self.assertFalse(dm._is_player_visible_segment("（关于你的角色回想——没有这回事）"))

    def test_mid_sentence_emoji_is_not_treated_as_tool_echo(self):
        self.assertTrue(dm._is_player_visible_segment("你注意到地上有一枚 🎲 形状的骰石，是旅人留下的。"))

    async def test_dice_roll_refuses_rest_checks(self):
        state = self.make_state()
        result = await dm.execute_tool(
            "dice_roll", {"skill_name": "短休恢复(生命骰d10+2体质)", "dc": 5}, state)
        self.assertIn("take_rest", result)
        self.assertFalse(any(t == "dice_roll" for _, t, _ in state.event_history))

    async def test_dice_roll_still_works_for_skill_checks(self):
        state = self.make_state()
        result = await dm.execute_tool("dice_roll", {"skill_name": "察觉", "dc": 12}, state)
        self.assertIn("察觉", result)
        self.assertTrue(any(t == "dice_roll" for _, t, _ in state.event_history))


if __name__ == "__main__":
    unittest.main()
