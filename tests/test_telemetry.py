import unittest
from types import SimpleNamespace

from backend.telemetry import ModelCallMetric, TelemetryCollector


class TestTelemetryCollector(unittest.IsolatedAsyncioTestCase):
    async def test_event_history_stores_snapshot_not_live_object(self):
        """事件历史会被断线重放；若存可变对象引用，后续修改会追溯改写历史事件。"""
        import tempfile

        from backend.engine.session import GameSessionState, push_event
        from backend.engine.world_state import WorldState

        state = GameSessionState("snapshot", "c", "n", {})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state.world_state = WorldState(session_id="snapshot", _storage_dir=tmp.name)

        conditions = [{"name": "中毒", "remaining_rounds": 2}]
        await push_event(state, "state_update", {"conditions": conditions})
        conditions[0]["remaining_rounds"] = 0  # 后续回合修改原对象
        stored = state.event_history[-1][2]
        self.assertEqual(stored["conditions"][0]["remaining_rounds"], 2,
                         "历史事件必须是发出时的快照")

    async def test_first_visible_output_is_tracked_once(self):
        import tempfile

        from backend.engine.session import GameSessionState, push_event
        from backend.engine.world_state import WorldState

        state = GameSessionState("first_output", "c", "n", {})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state.world_state = WorldState(session_id="first_output", _storage_dir=tmp.name)
        state.telemetry.begin_turn(1)

        await push_event(state, "journal_update", {})   # 玩家不可见，不算
        self.assertIsNone(state.telemetry.current.first_output_ms)

        await push_event(state, "narrative", {"token": "你"})
        first = state.telemetry.current.first_output_ms
        self.assertIsNotNone(first)

        await push_event(state, "narrative", {"token": "好"})
        self.assertEqual(state.telemetry.current.first_output_ms, first)

    async def test_phase_and_turn_snapshot(self):
        telemetry = TelemetryCollector()
        telemetry.begin_turn(3)
        async with telemetry.phase("dispatch"):
            telemetry.record_call(ModelCallMetric(
                phase="dispatcher", model="mock", duration_ms=12,
                prompt_tokens=10, completion_tokens=4, total_tokens=14, success=True,
            ))
        telemetry.record_failure("memory", RuntimeError("temporary"))
        telemetry.end_turn()
        snapshot = telemetry.snapshot()
        self.assertEqual(snapshot["totals"]["model_calls"], 1)
        self.assertEqual(snapshot["totals"]["total_tokens"], 14)
        self.assertEqual(snapshot["totals"]["failures"], 1)
        self.assertEqual(snapshot["recent_turns"][0]["turn"], 3)
        self.assertIn("dispatch", snapshot["recent_turns"][0]["phases_ms"])

    async def test_cache_usage_is_captured_from_deepseek_and_openai_shapes(self):
        from backend.telemetry import _cache_usage

        deepseek = SimpleNamespace(usage=SimpleNamespace(
            prompt_tokens=1000, prompt_cache_hit_tokens=800, prompt_cache_miss_tokens=200))
        openai = SimpleNamespace(usage=SimpleNamespace(
            prompt_tokens=1000, prompt_tokens_details=SimpleNamespace(cached_tokens=640)))
        none = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1000))
        self.assertEqual(_cache_usage(deepseek), (800, 200))
        self.assertEqual(_cache_usage(openai), (640, 360))
        self.assertEqual(_cache_usage(none), (0, 0))

    async def test_totals_include_cache_hits(self):
        telemetry = TelemetryCollector()
        telemetry.begin_turn(1)
        telemetry.record_call(ModelCallMetric(
            phase="dm", model="deepseek-chat", prompt_tokens=5000, completion_tokens=100,
            total_tokens=5100, cache_hit_tokens=4000, cache_miss_tokens=1000, success=True,
        ))
        telemetry.end_turn()
        self.assertEqual(telemetry.snapshot()["totals"]["cache_hit_tokens"], 4000)

    async def test_failed_call_is_counted_without_exposing_error_payload(self):
        telemetry = TelemetryCollector()
        telemetry.begin_turn(1)
        telemetry.record_call(ModelCallMetric(
            phase="dm", model="deepseek-chat", success=False,
            error="RateLimitError: secret prompt should not be here",
        ))
        telemetry.end_turn()
        metric = telemetry.snapshot()["recent_turns"][0]["model_calls"][0]
        self.assertEqual(metric["error"], "RateLimitError: secret prompt should not be here")
        self.assertNotIn("api_key", str(telemetry.snapshot()))


if __name__ == "__main__":
    unittest.main()
