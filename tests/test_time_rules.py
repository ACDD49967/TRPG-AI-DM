"""时间推进与补给：日数/时刻、跨天口粮与饮水、力竭、照明消耗、休息时间成本。"""
import tempfile
import unittest

from backend.engine import dm_agent as dm
from backend.engine import time_rules
from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState


class TimeRulesBase(unittest.IsolatedAsyncioTestCase):
    def make_state(self, items: list[dict] | None = None, info: dict | None = None) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = {
            "hp": 30, "max_hp": 30, "ac": 16, "level": 3, "game_system": "dnd5e",
            "char_class": "战士", "attributes": {"str": 16, "dex": 14, "con": 14},
            "inventory": {"items": items if items is not None else [
                {"name": "口粮（1日）", "type": "gear", "quantity": 3},
                {"name": "水袋", "type": "gear", "quantity": 3},
                {"name": "火把", "type": "gear", "quantity": 3},
            ]},
        }
        base.update(info or {})
        state = GameSessionState("time", "char", "岚", base)
        state.world_state = WorldState(session_id="time", _storage_dir=tmp.name)
        state.world_state.scene.current_location = "旧商道"
        state.world_state.scene.current_time = "清晨"
        state.world_state.scene.day_count = 1
        state.turn_tool_results = {}
        state.turn_action_ledger = {}
        return state


class TestClock(TimeRulesBase):
    async def test_advance_updates_clock_and_scene(self):
        state = self.make_state()
        result = await time_rules.advance(state, 4 * 60, "赶路")
        self.assertEqual(result["day"], 1)
        self.assertIn("10:00", result["clock"], "清晨(6:00) + 4 小时 = 10:00")
        self.assertEqual(state.world_state.scene.day_count, 1)
        self.assertIn("10:00", state.world_state.scene.current_time)

    async def test_advance_crossing_midnight_increments_day(self):
        state = self.make_state()
        state.world_state.scene.current_time = "深夜"
        state.clock_minutes = 22 * 60
        result = await time_rules.advance(state, 5 * 60, "守夜")
        self.assertEqual(result["day"], 2)
        self.assertEqual(result["days_crossed"], 1)
        self.assertIn("第2天", state.world_state.scene.current_time)

    async def test_clock_parses_narrative_time(self):
        state = self.make_state()
        state.world_state.scene.current_time = "黄昏"
        self.assertEqual(time_rules.clock_text(time_rules._parse_clock(state))[:4], "第1天 ")
        self.assertIn("18:00", time_rules.clock_text(time_rules._parse_clock(state)))

    async def test_clock_text_periods(self):
        self.assertIn("清晨", time_rules.clock_text(6 * 60))
        self.assertIn("正午", time_rules.clock_text(12 * 60))
        self.assertIn("深夜", time_rules.clock_text(23 * 60))


class TestSupplies(TimeRulesBase):
    async def test_crossing_day_consumes_ration_and_water(self):
        state = self.make_state()
        await time_rules.advance(state, 24 * 60, "长途旅行")
        items = state.character_info["inventory"]["items"]
        rations = next(i for i in items if i["name"] == "口粮（1日）")
        water = next(i for i in items if i["name"] == "水袋")
        self.assertEqual(rations["quantity"], 2)
        self.assertEqual(water["quantity"], 2)
        self.assertEqual(time_rules.exhaustion_level(state), 0)

    async def test_missing_rations_causes_exhaustion(self):
        state = self.make_state(items=[{"name": "水袋", "quantity": 5}])
        result = await time_rules.advance(state, 24 * 60, "长途旅行")
        self.assertEqual(time_rules.exhaustion_level(state), 1)
        self.assertTrue(any("力竭" in note for note in result["notes"]))
        self.assertIn("属性检定具有劣势", result["summary"])

    async def test_missing_water_also_counts(self):
        state = self.make_state(items=[{"name": "口粮（1日）", "quantity": 5}])
        await time_rules.advance(state, 24 * 60, "长途旅行")
        self.assertEqual(time_rules.exhaustion_level(state), 1)

    async def test_exhaustion_accumulates_and_caps_at_six(self):
        state = self.make_state(items=[])
        for _ in range(8):
            await time_rules.advance(state, 24 * 60, "断粮")
        self.assertEqual(time_rules.exhaustion_level(state), 6)
        self.assertEqual(state.character_info["exhaustion"], 6)

    async def test_last_ration_is_removed_when_consumed(self):
        state = self.make_state(items=[
            {"name": "口粮（1日）", "quantity": 1}, {"name": "水袋", "quantity": 1}])
        await time_rules.advance(state, 24 * 60, "旅行")
        names = [i["name"] for i in state.character_info["inventory"]["items"]]
        self.assertNotIn("口粮（1日）", names, "吃完最后一份应移除条目")

    async def test_light_source_consumes_torches_per_hour(self):
        state = self.make_state(items=[
            {"name": "口粮（1日）", "quantity": 3}, {"name": "水袋", "quantity": 3},
            {"name": "火把", "quantity": 5},
        ])
        result = await time_rules.advance(state, 3 * 60, "夜行", light_source="火把")
        torches = next(i for i in state.character_info["inventory"]["items"] if i["name"] == "火把")
        self.assertEqual(torches["quantity"], 2, "3 小时夜行消耗 3 支火把")
        self.assertTrue(any("火把" in note for note in result["notes"]))

    async def test_missing_light_source_is_reported(self):
        state = self.make_state(items=[{"name": "口粮（1日）", "quantity": 2}])
        result = await time_rules.advance(state, 2 * 60, "夜行", light_source="火把")
        self.assertTrue(any("没有可用的照明" in note for note in result["notes"]))

    async def test_long_rest_recovers_one_exhaustion_with_food(self):
        state = self.make_state(info={"exhaustion": 3})
        text = await time_rules.finish_long_rest(state)
        self.assertEqual(time_rules.exhaustion_level(state), 2)
        self.assertIn("力竭", text)
        self.assertIn("14:00", text, "清晨(6:00) + 8 小时 = 14:00，文案要体现时刻")

    async def test_long_rest_without_food_keeps_exhaustion(self):
        state = self.make_state(items=[], info={"exhaustion": 2})
        await time_rules.finish_long_rest(state)
        self.assertGreaterEqual(time_rules.exhaustion_level(state), 2,
                                "没口粮时长休不应凭空恢复（跨天还会计入缺粮）")


class TestToolIntegration(TimeRulesBase):
    async def test_update_scene_advances_clock_from_narrative(self):
        """DM 用 update_scene(current_time="入夜") 也必须让权威时钟前进。"""
        state = self.make_state()
        state.world_state.scene.current_time = "清晨"
        out = await dm.execute_tool("update_scene", {"current_time": "入夜（天黑前抵达）"}, state)
        self.assertIn("时间推进", out, "叙述时间应被换算成时钟推进")
        self.assertEqual(state.world_state.scene.day_count, 1, "清晨 6:00 → 入夜 20:00，同日")
        self.assertEqual(state.clock_minutes, 20 * 60, "权威时钟应推进到 20:00")
        self.assertIn("入夜", state.world_state.scene.current_time, "DM 的叙述措辞要保留")
        self.assertEqual(time_rules._item_qty_left(state, "口粮（1日）"), 3, "同日不扣口粮")

    async def test_update_scene_crossing_midnight_consumes_supplies(self):
        state = self.make_state()
        state.clock_minutes = 22 * 60
        state.world_state.scene.current_time = "深夜"
        out = await dm.execute_tool("update_scene", {"current_time": "清晨"}, state)
        self.assertIn("第2天", out)
        self.assertEqual(state.world_state.scene.day_count, 2)
        self.assertEqual(time_rules._item_qty_left(state, "口粮（1日）"), 2, "跨天扣 1 份口粮")

    async def test_update_scene_ignores_vague_time_words(self):
        state = self.make_state()
        out = await dm.execute_tool("update_scene", {"current_time": "不久之后"}, state)
        self.assertNotIn("时间推进", out)
        self.assertEqual(state.clock_minutes, 6 * 60, "只固化旧时钟，不推进")

    async def test_advance_time_tool(self):
        state = self.make_state()
        out = await dm.execute_tool("advance_time", {"hours": 6, "reason": "沿商道赶路"}, state)
        self.assertIn("时间推进", out)
        self.assertIn("第1天", out)
        events = [d for _, t, d in state.event_history if t == "game_event" and d.get("type") == "time"]
        self.assertEqual(len(events), 1)

    async def test_advance_time_tool_requires_an_amount(self):
        state = self.make_state()
        out = await dm.execute_tool("advance_time", {}, state)
        self.assertIn("需要", out)

    async def test_short_rest_advances_one_hour(self):
        state = self.make_state()
        state.clock_minutes = 9 * 60
        out = await dm.execute_tool("take_rest", {"rest_type": "short"}, state)
        self.assertIn("短休", out)
        self.assertIn("10:00", out, "短休应把时钟推进 1 小时")

    async def test_long_rest_advances_eight_hours(self):
        state = self.make_state()
        state.clock_minutes = 20 * 60
        out = await dm.execute_tool("take_rest", {"rest_type": "long"}, state)
        self.assertIn("长休", out)
        self.assertIn("第2天", out, "20:00 + 8h 跨天到第 2 天 04:00")

    async def test_update_state_can_adjust_exhaustion(self):
        state = self.make_state()
        await dm.execute_tool("update_state", {"changes": {"exhaustion": 2}, "reason": "疲惫"}, state)
        self.assertEqual(time_rules.exhaustion_level(state), 2)
        await dm.execute_tool("update_state", {"changes": {"exhaustion": 9}, "reason": "过度"}, state)
        self.assertEqual(time_rules.exhaustion_level(state), 6, "力竭上限 6")
        await dm.execute_tool("update_state", {"changes": {"exhaustion": -10}, "reason": "恢复"}, state)
        self.assertEqual(time_rules.exhaustion_level(state), 0, "下限 0")

    async def test_clock_survives_save_serialization(self):
        from backend.save_manager import _serialize_dynamic
        state = self.make_state()
        await time_rules.advance(state, 90, "搜索")
        dyn = _serialize_dynamic(state)
        self.assertEqual(dyn["clock_minutes"], state.clock_minutes)


if __name__ == "__main__":
    unittest.main()
