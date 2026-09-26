"""会话身份：SSE 下发的 username 必须与会话归属一致。"""
import tempfile
import unittest

from backend.engine.session import GameSessionState, push_event
from backend.engine.world_state import WorldState


class TestSessionIdentity(unittest.IsolatedAsyncioTestCase):
    async def test_state_update_uses_session_username(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # character_info 里故意不写 username（读档/老存档常见）
        state = GameSessionState("sid", "char", "岚", {"hp": 10, "max_hp": 10}, username="alice")
        state.world_state = WorldState(session_id="sid", _storage_dir=tmp.name)
        # resumed=True 走历史回放分支，避免测试触发真实 LLM 开场白
        state.resumed = True

        from backend.engine.session import sse_event_generator

        generator = sse_event_generator(state, last_event_id=0)
        try:
            payload = ""
            for _ in range(5):
                chunk = await generator.__anext__()
                if "event: state_update" in chunk:
                    payload = chunk
                    break
        finally:
            await generator.aclose()
        self.assertIn("event: state_update", payload, "应能收到状态快照事件")
        self.assertIn('"username": "alice"', payload)
        self.assertNotIn('"username": "default"', payload)


if __name__ == "__main__":
    unittest.main()
