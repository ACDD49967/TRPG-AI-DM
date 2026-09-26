"""流式响应必须被关闭：提前中断/工具上限时也要释放，避免连接泄漏。"""
import tempfile
import unittest
from types import SimpleNamespace

from backend.engine import dm_agent as dm
from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState


def _chunk(content: str = "", tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls, reasoning_content=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None)])


class FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.closed = False
        self._iterated = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        self._iterated += 1
        return self._chunks.pop(0)

    async def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, stream):
        self._stream = stream

    @property
    def chat(self):
        return SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        return self._stream


class TestStreamCleanup(unittest.IsolatedAsyncioTestCase):
    def make_state(self) -> GameSessionState:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = GameSessionState("stream", "c", "n", {"game_system": "dnd5e"})
        state.world_state = WorldState(session_id="stream", _storage_dir=tmp.name)
        return state

    async def test_stream_is_closed_after_normal_completion(self):
        stream = FakeStream([_chunk("你好。"), _chunk("继续。")])
        state = self.make_state()
        content, tools = await dm._stream_with_tools(
            FakeClient(stream), "mock", [], [], state, thinking_mode="low")
        self.assertIn("你好", content)
        self.assertEqual(tools, [])
        self.assertTrue(stream.closed, "正常结束后也应释放流")

    async def test_stream_is_closed_when_aborted_mid_stream(self):
        stream = FakeStream([_chunk("第一句。"), _chunk("第二句。"), _chunk("第三句。")])
        state = self.make_state()
        state.request_abort()
        await dm._stream_with_tools(FakeClient(stream), "mock", [], [], state, thinking_mode="low")
        self.assertTrue(stream.closed, "玩家中断后必须关闭流")
        self.assertLess(stream._iterated, 3, "中断后不应继续消费流")

    async def test_tool_echo_is_filtered_but_narration_survives(self):
        stream = FakeStream([
            _chunk("你握紧长剑。"),
            _chunk("\n🎲 察觉: d20=12 vs DC13 → 失败\n"),
            _chunk("雾里什么也没有。"),
        ])
        state = self.make_state()
        content, _ = await dm._stream_with_tools(
            FakeClient(stream), "mock", [], [], state, thinking_mode="low")
        pushed = "".join(str(d.get("token", "")) for _, t, d in state.event_history if t == "narrative")
        self.assertIn("你握紧长剑", pushed)
        self.assertIn("雾里什么也没有", pushed)
        self.assertNotIn("d20=12", pushed, "DM 复述的工具行不应推给玩家")


if __name__ == "__main__":
    unittest.main()
