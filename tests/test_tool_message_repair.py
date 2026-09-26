"""工具调用消息配对：不允许出现「assistant.tool_calls 后面没有紧邻的等量 tool 响应」。

真实模型实测：工具循环里两条 tool 响应中间插了一条 system 提示（combat_round 后的强制
提示），网关只数紧邻 assistant 的连续 tool 消息，于是整回合 400
（insufficient tool messages following tool_calls message）。
_ui_playthrough.py 把它抓成 console error，同一类畸形还包括提前退出留下的半截配对。
"""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.engine.dm_runtime import _stream_with_tools
from backend.engine.dm_tool_loop import ToolLoopHooks, run_tool_loop
from backend.engine.dm_tool_protocol import (
    MISSING_TOOL_RESULT, repair_tool_message_pairs, unpaired_tool_calls,
)


def _call(call_id: str, name: str = "dice_roll"):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": '{"expr": "1d20"}'}}


def _fake_state():
    return SimpleNamespace(character_info={}, thinking_strength="high",
                           aborted=False, in_combat=False, world_state=None)


class TestRepairToolMessagePairs(unittest.TestCase):
    def test_fills_missing_tool_response(self):
        messages = [
            {"role": "user", "content": "我攻击"},
            {"role": "assistant", "content": "看剑", "tool_calls": [_call("a"), _call("b")]},
            {"role": "tool", "tool_call_id": "a", "content": "命中"},
        ]
        self.assertEqual(unpaired_tool_calls(messages), ["b"])
        self.assertEqual(repair_tool_message_pairs(messages), 1)
        self.assertEqual(unpaired_tool_calls(messages), [])
        tool_ids = [m.get("tool_call_id") for m in messages if m.get("role") == "tool"]
        self.assertEqual(tool_ids, ["a", "b"], "补的响应排在已有响应之后")
        filler = [m for m in messages if m.get("tool_call_id") == "b"][0]
        self.assertEqual(filler["content"], MISSING_TOOL_RESULT)
        # 已有响应不能被覆盖
        self.assertEqual([m for m in messages if m.get("tool_call_id") == "a"][0]["content"], "命中")

    def test_moves_system_hint_after_tool_responses(self):
        """提示夹在两条 tool 响应中间会被判成响应不足 —— 必须挪到整批响应之后。"""
        hint = {"role": "system", "content": "[系统] 敌人必须还手"}
        messages = [
            {"role": "assistant", "content": None, "tool_calls": [_call("a"), _call("b")]},
            {"role": "tool", "tool_call_id": "a", "content": "结算完成"},
            hint,
            {"role": "tool", "tool_call_id": "b", "content": "敌人反击"},
        ]
        self.assertEqual(unpaired_tool_calls(messages), ["b"], "修复前应能体检出畸形")
        self.assertEqual(repair_tool_message_pairs(messages), 1)
        self.assertEqual(unpaired_tool_calls(messages), [])
        self.assertEqual([m.get("role") for m in messages], ["assistant", "tool", "tool", "system"])
        self.assertIs(messages[-1], hint)

    def test_noop_on_paired_history(self):
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，旅行者"},
        ]
        before = [dict(m) for m in messages]
        self.assertEqual(repair_tool_message_pairs(messages), 0)
        self.assertEqual(messages, before)


class TestToolLoopKeepsPairing(unittest.IsolatedAsyncioTestCase):
    async def _run(self, messages, side_effect, execute):
        stream = AsyncMock(side_effect=side_effect)
        return await run_tool_loop(
            _fake_state(), client=object(), model="mock", messages=messages,
            module_tools=[], skill=SimpleNamespace(max_tokens=2000, temperature=0.7),
            module="combat", lite=False, settlement_group=None, settled_tools=set(),
            settlement_tools=set(), delegated_tools_executed=False, delegation_used=True,
            telemetry=None,
            hooks=ToolLoopHooks(stream_with_tools=stream, execute_tool=execute,
                                push_event=AsyncMock()),
        )

    async def test_error_streak_break_still_answers_every_tool_call(self):
        """连续错误保护提前退出时，本批每个 tool_call 都必须有响应。"""
        messages = [{"role": "system", "content": "sp"}, {"role": "user", "content": "我攻击"}]
        result = await self._run(messages, [
            ("让我看看。", [_call("a", "search_npcs"), _call("b", "search_bestiary")]),
            ("还是不行。", [_call("c", "combat_round")]),
        ], AsyncMock(side_effect=RuntimeError("工具炸了")))
        self.assertIn("让我看看。", result[0])
        self.assertEqual(unpaired_tool_calls(messages), [], "提前退出后不允许残留半截配对")
        self.assertEqual(sum(1 for m in messages if m.get("role") == "tool"), 3,
                         "两个失败调用加上一个被跳过的调用都要有响应")

    async def test_combat_hint_does_not_split_tool_responses(self):
        """combat_round 的强制提示排在整批响应之后，不能插在中间。"""
        messages = [{"role": "system", "content": "sp"}, {"role": "user", "content": "我攻击"}]
        await self._run(messages, [
            ("剑光落下。", [_call("a", "combat_round"), _call("b", "enemy_attack")]),
            ("它倒下了。", []),
        ], AsyncMock(return_value="造成 7 点伤害"))
        self.assertEqual(unpaired_tool_calls(messages), [])
        start = next(i for i, m in enumerate(messages) if m.get("tool_calls"))
        roles = [m.get("role") for m in messages[start + 1:start + 4]]
        self.assertEqual(roles, ["tool", "tool", "system"], "两条响应必须先紧邻出现")


class TestStreamFunnelRepairs(unittest.IsolatedAsyncioTestCase):
    async def test_stream_with_tools_sends_paired_messages(self):
        """主 DM 的模型调用出口统一体检：带病消息不会发出去。"""
        sent: dict = {}

        class _Completions:
            async def create(self, **kwargs):
                sent.update(kwargs)

                async def _empty():
                    return
                    yield  # pragma: no cover - 空流

                return _empty()

        client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
        messages = [
            {"role": "user", "content": "我攻击"},
            {"role": "assistant", "content": "看剑",
             "tool_calls": [_call("x"), _call("y")]},
            {"role": "tool", "tool_call_id": "x", "content": "命中"},
            {"role": "system", "content": "[系统] 敌人必须还手"},
            {"role": "tool", "tool_call_id": "y", "content": "反击"},
        ]
        await _stream_with_tools(client, "mock", messages, [], _fake_state(), max_tokens=100)
        self.assertEqual(sent["messages"], messages, "发送的就是同一个列表对象")
        self.assertEqual(unpaired_tool_calls(sent["messages"]), [])


if __name__ == "__main__":
    unittest.main()