"""后台预热：状态机、API 暴露与失败不阻断启动。"""
import unittest
from unittest.mock import patch

import httpx

from backend.engine import warmup
from backend.engine.session import GameSessionState, session_manager


class TestBackgroundWarmup(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        warmup.reset_for_tests()

    def tearDown(self):
        warmup.reset_for_tests()

    async def test_background_warmup_records_stage_timings(self):
        calls = []

        def fake_warmup(on_stage=None):
            calls.append(on_stage)
            if on_stage:
                on_stage("reranker", 12.5)
                on_stage("retrieval_index", 3.5)

        with patch("backend.engine.rag_utils.warmup_rag", side_effect=fake_warmup):
            self.assertEqual(warmup.status()["state"], "pending")
            task = await warmup.start_background_warmup()
            self.assertIsNotNone(task)
            snapshot = await warmup.wait_for_warmup(timeout=10)

        self.assertEqual(snapshot["state"], "ready")
        self.assertTrue(snapshot["ready"])
        self.assertEqual(snapshot["stages_ms"]["reranker"], 12.5)
        self.assertGreater(snapshot["duration_ms"], 0)

    async def test_warmup_failure_is_isolated(self):
        with patch("backend.engine.rag_utils.warmup_rag", side_effect=RuntimeError("boom")):
            await warmup.start_background_warmup()
            snapshot = await warmup.wait_for_warmup(timeout=10)
        self.assertEqual(snapshot["state"], "failed")
        self.assertIn("RuntimeError", snapshot["error"])

    async def test_status_endpoint_and_health_expose_warmup(self):
        from backend.main import app

        warmup._snapshot.state = "running"  # noqa: SLF001 - 直接置位以验证接口输出
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            warm = await client.get("/api/system/warmup")
            health = await client.get("/api/health")

        self.assertEqual(warm.status_code, 200)
        self.assertEqual(warm.json()["state"], "running")
        self.assertIn("warmup", health.json())


class TestTurnToolStateReset(unittest.TestCase):
    def test_session_has_dedupe_store(self):
        state = GameSessionState("s", "c", "n", {})
        self.assertEqual(state.turn_tool_results, {})
        session_manager._sessions.pop("s", None)


if __name__ == "__main__":
    unittest.main()
