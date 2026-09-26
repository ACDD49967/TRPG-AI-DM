"""观测接口与用量统计端到端（不调用真实模型）。"""
import unittest

import httpx

from backend.engine.session import GameSessionState, session_manager
from backend.telemetry import ModelCallMetric


class TestMetricsApi(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from backend.main import app

        self.app = app
        self.state = GameSessionState(
            session_id="metrics-session", character_id="c1", character_name="测试",
            character_info={"game_system": "dnd5e"}, username="alice",
        )
        session_manager._sessions[self.state.session_id] = self.state

    async def asyncTearDown(self):
        session_manager._sessions.pop("metrics-session", None)

    async def test_metrics_requires_session_owner(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/game/metrics-session/metrics?username=bob")
            self.assertEqual(response.status_code, 404)

    async def test_metrics_reports_tokens_calls_and_failures(self):
        self.state.telemetry.begin_turn(1)
        self.state.telemetry.record_call(ModelCallMetric(
            phase="dm_generation", model="deepseek-chat", duration_ms=1200,
            prompt_tokens=800, completion_tokens=200, total_tokens=1000, success=True,
        ))
        self.state.telemetry.record_call(ModelCallMetric(
            phase="delegation", model="deepseek-chat", success=False, error="TimeoutError: 子任务超时",
        ))
        self.state.telemetry.end_turn()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/game/metrics-session/metrics?username=alice")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["totals"]["total_tokens"], 1000)
        self.assertEqual(body["totals"]["model_calls"], 2)
        self.assertEqual(body["totals"]["failures"], 1)
        self.assertEqual(body["recent_turns"][0]["model_calls"][1]["error"], "TimeoutError: 子任务超时")
        self.assertNotIn("api_key", str(body))


if __name__ == "__main__":
    unittest.main()
