"""特长选择闭环：升级提示 → feats_add 写入 → 前端可见。"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState


class TestFeatChoice(unittest.IsolatedAsyncioTestCase):
    def make_state(self, xp: int = 0, level: int = 1) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState(
            "feat", "char", "岚",
            {"hp": 20, "max_hp": 20, "ac": 16, "level": level, "xp": xp,
             "game_system": "dnd5e", "char_class": "战士",
             "attributes": {"str": 16, "dex": 14, "con": 14}},
        )
        state.world_state = WorldState(session_id="feat", _storage_dir=tmp.name)
        return state

    async def test_feats_add_and_remove(self):
        state = self.make_state()
        await dm._exec_update_state(
            {"changes": {"feats_add": {"name": "巨武器大师", "description": "-5命中/+10伤害"}},
             "reason": "2级特长"}, state)
        self.assertEqual([f["name"] for f in state.character_info["feats"]], ["巨武器大师"])

        # 同名不重复添加
        await dm._exec_update_state(
            {"changes": {"feats_add": {"name": "巨武器大师"}}, "reason": "重复"}, state)
        self.assertEqual(len(state.character_info["feats"]), 1)

        await dm._exec_update_state(
            {"changes": {"feats_remove": "巨武器大师"}, "reason": "洗点"}, state)
        self.assertEqual(state.character_info["feats"], [])

    async def test_feats_add_accepts_plain_string_and_list(self):
        state = self.make_state()
        await dm._exec_update_state(
            {"changes": {"feats_add": ["哨兵", {"name": "幸运", "description": "重掷"}]},
             "reason": "多重特长"}, state)
        names = [f["name"] for f in state.character_info["feats"]]
        self.assertEqual(names, ["哨兵", "幸运"])

    async def test_level_up_pushes_feat_available_and_feat_can_be_recorded(self):
        state = self.make_state(xp=2600)
        await dm._exec_update_state({"changes": {"xp": 600}, "reason": "击败头目"}, state)
        self.assertEqual(state.character_info["level"], 4, "6500 XP 应为 4 级")
        events = [(t, d) for _, t, d in state.event_history]
        self.assertTrue(
            any(t == "game_event" and d.get("type") == "feat_available" for t, d in events),
            "升到 4 级应推送属性提升/专长提示",
        )

        await dm._exec_update_state(
            {"changes": {"feats_add": {"name": "巨武器大师", "description": "-5/+10"}},
             "reason": "玩家选择"}, state)
        self.assertEqual(state.character_info["feats"][0]["name"], "巨武器大师")
        # 已写入的角色信息会随状态推送给前端（前端角色卡直接展示 feats）
        state_updates = [d for t, d in events + [(t, d) for _, t, d in state.event_history]
                         if t == "state_update"]
        self.assertTrue(any("feats" in d for d in state_updates))

    async def test_level_two_does_not_grant_a_feat(self):
        """5e 规则：2 级没有属性提升/专长（此前代码写的是"每 2 级送专长"）。"""
        state = self.make_state(xp=290)
        await dm._exec_update_state({"changes": {"xp": 20}, "reason": "击败小怪"}, state)
        self.assertEqual(state.character_info["level"], 2)
        events = [(t, d) for _, t, d in state.event_history]
        self.assertFalse(
            any(t == "game_event" and d.get("type") == "feat_available" for t, d in events),
            "2 级不应推送专长/属性提升",
        )

    def test_asi_levels_per_class(self):
        from backend.engine.game_systems import get_dnd5_asi_levels

        self.assertEqual(get_dnd5_asi_levels("法师"), [4, 8, 12, 16, 19])
        self.assertIn(6, get_dnd5_asi_levels("战士"))
        self.assertIn(14, get_dnd5_asi_levels("战士"))
        self.assertIn(10, get_dnd5_asi_levels("游荡者"))
        self.assertNotIn(2, get_dnd5_asi_levels("战士"))

    async def test_attributes_add_applies_asi_and_recomputes_derived(self):
        state = self.make_state(xp=6500, level=4)
        before_saves = dict(state.character_info.get("saves", {}))
        await dm._exec_update_state(
            {"changes": {"attributes_add": {"str": 2}}, "reason": "4级属性提升"}, state)
        self.assertEqual(state.character_info["attributes"]["str"], 18)
        self.assertIn("attributes", [k for _, t, d in state.event_history if t == "state_update" for k in d])
        self.assertNotEqual(state.character_info.get("saves"), before_saves,
                            "力量提升后应重算豁免")

    async def test_attributes_add_is_capped_at_twenty(self):
        state = self.make_state()
        state.character_info["attributes"]["str"] = 19
        await dm._exec_update_state(
            {"changes": {"attributes_add": {"str": 2}}, "reason": "超上限"}, state)
        self.assertEqual(state.character_info["attributes"]["str"], 20)


if __name__ == "__main__":
    unittest.main()
