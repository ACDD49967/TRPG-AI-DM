# -*- coding: utf-8 -*-
"""空响应防护回归测试。

覆盖本次排查结论：推理模型的 reasoning_content 与正文 content 共享 max_tokens，
推理吃满预算时正文为空（finish_reason=length），需要在重试时禁用思考并放大预算。

全部使用 mock client，不访问真实 API。
"""
import asyncio
import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

import backend.engine.world_builder as wb
import backend.scenario_importer as si
import backend.scenario_llm_split as si_split


# ── 假流式/非流式响应 ──────────────────────────────────────────
def _delta(content="", reasoning=""):
    return SimpleNamespace(content=content, reasoning_content=reasoning, tool_calls=None)


def _chunk(content="", reasoning="", finish=None, usage=None):
    choice = SimpleNamespace(delta=_delta(content, reasoning), finish_reason=finish)
    return SimpleNamespace(choices=[choice], usage=usage)


class FakeStream:
    def __init__(self, chunks):
        self._it = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def close(self):
        return None


def _usage(prompt=100, completion=100, reasoning=None):
    details = SimpleNamespace(reasoning_tokens=reasoning)
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion,
                           completion_tokens_details=details)


def _resp(content="", reasoning="", finish="stop"):
    msg = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)],
                           usage=_usage())


class FakeCompletions:
    """按预设脚本依次返回响应；每个脚本项可以是 FakeStream / 响应对象 / 异常。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("超出预设的调用次数")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, script):
        self.chat = SimpleNamespace(completions=FakeCompletions(script))

    @property
    def calls(self):
        return self.chat.completions.calls


# ── world_builder._llm ────────────────────────────────────────
class TestWorldBuilderEmptyResponseGuard(unittest.TestCase):
    def _run(self, client, **kw):
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = asyncio.run(wb._llm(client, "m", "sys", "user", **kw))
        return out, buf.getvalue()

    def test_empty_then_retry_with_thinking_disabled(self):
        """第 1 次 reasoning 吃满预算（finish=length、正文空）→ 第 2 次禁思考并放大预算成功。"""
        script = [
            FakeStream([_chunk(reasoning="想" * 50),
                        _chunk(finish="length", usage=_usage(completion=3000, reasoning=3000))]),
            _resp(content="合并后的大纲正文"),
        ]
        client = FakeClient(script)
        out, log = self._run(client, max_tokens=5000, temp=0.4)

        self.assertEqual(out, "合并后的大纲正文")
        self.assertEqual(len(client.calls), 2)
        first, second = client.calls
        self.assertTrue(first["stream"])
        self.assertNotIn("extra_body", first)
        # 第 2 次：非流式 + 禁思考 + 预算放大
        self.assertFalse(second.get("stream", False))
        self.assertEqual(second["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(second["max_tokens"], 16000)
        self.assertIn("空响应", log)
        self.assertIn("length", log)

    def test_reasoning_accumulated_from_stream(self):
        """流式路径必须逐 chunk 累计 reasoning，日志才能区分“被推理挤空”与“真没输出”。"""
        script = [
            FakeStream([_chunk(reasoning="推理A"), _chunk(reasoning="推理B"),
                        _chunk(finish="length")]),
            _resp(content="正文"),
        ]
        client = FakeClient(script)
        _, log = self._run(client, max_tokens=3000)
        self.assertNotIn("reasoning≈0字", log)
        self.assertIn("reasoning≈6字", log)

    def test_gateway_without_thinking_param_falls_back(self):
        """网关不支持 thinking 参数（400）→ 去掉该参数保底重试一次。"""
        err = Exception("Error code: 400 - invalid parameter: thinking")
        script = [
            FakeStream([_chunk(finish="length")]),
            err,
            _resp(content="保底正文"),
        ]
        client = FakeClient(script)
        out, _ = self._run(client, max_tokens=3000)

        self.assertEqual(out, "保底正文")
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(client.calls[1]["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertNotIn("extra_body", client.calls[2])

    def test_long_prompt_raises_budget_floor(self):
        """长 prompt（如导入 3 万字剧本）自动抬高正文预算下限，避免正文被推理挤掉。"""
        script = [FakeStream([_chunk(content="正文", finish="stop")])]
        client = FakeClient(script)
        long_user = "剧" * 30000
        asyncio.run(wb._llm(client, "m", "sys", long_user, max_tokens=3000))
        # 8000 + min(8000, 30003//8) = 11750
        self.assertEqual(client.calls[0]["max_tokens"], 11750)

    def test_budget_never_exceeds_cap(self):
        """预算由 settings.LLM_MAX_OUTPUT_TOKENS 封顶，避免请求被服务端拒绝。"""
        script = [FakeStream([_chunk(content="正文", finish="stop")])]
        client = FakeClient(script)
        asyncio.run(wb._llm(client, "m", "s", "u", max_tokens=100000))
        self.assertEqual(client.calls[0]["max_tokens"], wb._current_output_cap())
        self.assertEqual(wb._current_output_cap(), wb._DEFAULT_OUTPUT_CAP)

    def test_deterministic_task_disables_thinking_on_first_call(self):
        """合并/评分/JSON 抽取等确定性任务首次调用即禁用思考，避免白跑一次失败重试。"""
        script = [FakeStream([_chunk(content='{"total_score": 80}', finish="stop")])]
        client = FakeClient(script)
        out, _ = self._run(client, max_tokens=5000, temp=0.4, disable_thinking=True)
        self.assertEqual(out, '{"total_score": 80}')
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["extra_body"], {"thinking": {"type": "disabled"}})

    def test_low_thinking_strength_also_disables_thinking(self):
        """玩家选择 low 思维强度时同样首次禁用思考。"""
        script = [FakeStream([_chunk(content="正文", finish="stop")])]
        client = FakeClient(script)
        self._run(client, max_tokens=3000, thinking_strength="low")
        self.assertEqual(client.calls[0]["extra_body"], {"thinking": {"type": "disabled"}})

    def test_all_attempts_fail_calls_error_callback(self):
        """三次都失败时仍走降级路径并回报错误原因。"""
        errs = []
        script = [FakeStream([_chunk(finish="length")]), Exception("boom"), Exception("boom")]
        client = FakeClient(script)
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = asyncio.run(wb._llm(client, "m", "s", "u", max_tokens=1000,
                                      error_callback=errs.append))
        self.assertEqual(out, "")
        self.assertTrue(errs)


# ── scenario_importer 切分 ────────────────────────────────────
class TestScenarioSplit(unittest.TestCase):
    def test_split_prompt_format_does_not_raise(self):
        """回归：模板中 {"chunks":...} 未转义会让 .format() 抛 KeyError，LLM 切分永久静默回退。"""
        prompt = si.LLM_SPLIT_PROMPT.format(text="第一章 正文")
        self.assertIn("第一章 正文", prompt)
        self.assertIn('{"chunks"', prompt)
        self.assertNotIn("{text}", prompt)

    def test_split_for_llm_respects_limit_and_keeps_order(self):
        text = "\n\n".join(f"第{i}段内容" + "字" * 500 for i in range(30))
        segs = si._split_for_llm(text, limit=6000)
        self.assertGreater(len(segs), 1)
        for s in segs:
            self.assertLessEqual(len(s), 12000)
        self.assertIn("第0段内容", segs[0])
        self.assertIn("第29段内容", segs[-1])

    def test_parse_split_payload_variants(self):
        self.assertEqual(si._parse_split_payload('{"chunks": ["a", "b"]}'), ["a", "b"])
        self.assertEqual(si._parse_split_payload('```json\n{"chunks": ["a"]}\n```'), ["a"])
        self.assertEqual(si._parse_split_payload('["a", "b"]'), ["a", "b"])
        self.assertEqual(si._parse_split_payload('{"chunks": [{"content": "a"}, "b"]}'), ["a", "b"])
        self.assertEqual(si._parse_split_payload("完全不是 JSON"), [])

    def test_llm_split_segment_disables_thinking(self):
        stream = FakeStream([_chunk(content='{"chunk'),
                             _chunk(content='s": ["片段一", "片段二"]}', finish="stop")])
        client = FakeClient([stream])
        chunks = asyncio.run(si._llm_split_segment(client, "m", "文本", 1, 1))
        self.assertEqual(chunks, ["片段一", "片段二"])
        call = client.calls[0]
        self.assertEqual(call["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(call["max_tokens"], si.LLM_SPLIT_MAX_TOKENS)
        self.assertEqual(call["response_format"], {"type": "json_object"})

    def test_llm_split_segment_returns_none_on_empty_output(self):
        stream = FakeStream([_chunk(reasoning="想" * 10, finish="length")])
        client = FakeClient([stream, stream, stream])
        buf = io.StringIO()
        with redirect_stdout(buf):
            chunks = asyncio.run(si._llm_split_segment(client, "m", "文本", 1, 1))
        self.assertIsNone(chunks)
        self.assertIn("空响应", buf.getvalue())

    def test_llm_split_text_segments_and_falls_back(self):
        """逐段切分：成功段用 LLM 结果，失败段回退本地切分，整体不失败。"""
        ok = FakeStream([_chunk(content='{"chunks": ["来自LLM的片段"]}', finish="stop")])
        bad = FakeStream([_chunk(finish="length")])
        client = FakeClient([ok, bad, bad, bad])
        text = "甲" * 5000 + "\n\n" + "乙" * 5000

        with patch.object(si_split, "AsyncOpenAI", return_value=client):
            progress = []
            chunks = asyncio.run(si.llm_split_text(
                text, api_key="sk-unit-test-key", model_name="fake-model",
                progress_callback=lambda label, pct, detail="": progress.append((label, detail))))
        self.assertTrue(any("来自LLM的片段" == c for c in chunks))
        self.assertTrue(any("乙" in c for c in chunks))  # 失败段回退本地切分后仍保留原文
        self.assertTrue(progress)

    def test_llm_split_text_caps_calls_and_locally_splits_tail(self):
        """超出调用上限的尾部用本地切分，避免超长剧本产生海量请求。"""
        script = [FakeStream([_chunk(content='{"chunks": ["p"]}', finish="stop")])
                  for _ in range(si.LLM_SPLIT_MAX_CALLS)]
        client = FakeClient(script)
        # 9 万字 → 分段数超过 LLM_SPLIT_MAX_CALLS，必然产生尾部
        text = "\n\n".join("段" * 3000 for _ in range(30))

        with patch.object(si_split, "AsyncOpenAI", return_value=client):
            chunks = asyncio.run(si.llm_split_text(
                text, api_key="sk-unit-test-key", model_name="fake-model"))
        self.assertEqual(len(client.calls), si.LLM_SPLIT_MAX_CALLS)
        self.assertGreater(len(chunks), si.LLM_SPLIT_MAX_CALLS)


# ── generate_summary ─────────────────────────────────────────
class TestSummaryRetry(unittest.TestCase):
    def test_second_attempt_disables_thinking(self):
        client = FakeClient([FakeStream([_chunk(finish="length")]),
                             _resp(content="这是一个完整的剧本总结。")])
        buf = io.StringIO()
        with redirect_stdout(buf):
            summary = asyncio.run(si.generate_summary(client, "m", "大纲", "来源"))
        self.assertEqual(summary, "这是一个完整的剧本总结。")
        self.assertFalse(client.calls[1].get("stream", False))
        self.assertEqual(client.calls[1]["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(client.calls[1]["max_tokens"], 10000)

    def test_fallback_summary_when_all_fail(self):
        client = FakeClient([FakeStream([_chunk(finish="length")]),
                             FakeStream([_chunk(finish="length")])])
        outline = "# 第一章 村庄\n冒险者抵达村庄。\n\n# 第二章 地城\n深入地城。"
        buf = io.StringIO()
        with redirect_stdout(buf):
            summary = asyncio.run(si.generate_summary(client, "m", outline, "来源"))
        self.assertTrue(summary)
        self.assertIn("村庄", summary)


# ── 输出预算上限自适应 ────────────────────────────────────────
class TestOutputCapAdaptive(unittest.TestCase):
    """网关 max_tokens 上限低于配置时，自动降级并记住，避免每次都撞 400。"""

    def setUp(self):
        self._orig = wb._output_cap

    def tearDown(self):
        wb._output_cap = self._orig

    def test_gateway_rejects_large_budget_then_cap_drops(self):
        err = Exception("Error code: 400 - max_tokens is too large: 32768, maximum is 8192")
        # 降级后用同一套策略（仍是流式）重试
        client = FakeClient([err, FakeStream([_chunk(content="正文", finish="stop")])])
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = asyncio.run(wb._llm(client, "m", "s", "u", max_tokens=16000))
        self.assertEqual(out, "正文")
        self.assertIn("已将输出上限降至", buf.getvalue())
        self.assertEqual(wb._current_output_cap(), wb._OUTPUT_CAP_FALLBACK)
        self.assertLessEqual(client.calls[1]["max_tokens"], wb._OUTPUT_CAP_FALLBACK)

    def test_unrelated_error_keeps_cap(self):
        client = FakeClient([Exception("Connection error"), _resp(content="正文")])
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = asyncio.run(wb._llm(client, "m", "s", "u", max_tokens=16000))
        self.assertEqual(out, "正文")
        self.assertEqual(wb._current_output_cap(), self._orig)


# ── 结构化提取：截断兜底 ─────────────────────────────────────
class TestExtractPlotFlagBackfill(unittest.TestCase):
    def test_backfill_signal_when_flags_missing_but_entities_present(self):
        """有 NPC/地点却没有任何旗标 → 疑似 JSON 被截断，需要补提取。"""
        self.assertTrue(wb._needs_plot_flag_backfill({"npcs": [{"name": "A"}], "plot_flags": []}))
        self.assertTrue(wb._needs_plot_flag_backfill({"locations": [{"name": "B"}], "plot_flags": []}))
        self.assertFalse(wb._needs_plot_flag_backfill({"npcs": [{"name": "A"}],
                                                       "plot_flags": [{"key": "k"}]}))
        self.assertFalse(wb._needs_plot_flag_backfill({"npcs": [], "locations": [], "plot_flags": []}))
        self.assertFalse(wb._needs_plot_flag_backfill({}))

    def test_plot_flag_only_extraction_parses_result(self):
        stream = FakeStream([_chunk(content='{"plot_flags": [{"key": "找到矿坑", '
                                            '"status": "未触发", "description": "进入矿坑后触发"}]}',
                                    finish="stop")])
        client = FakeClient([stream])
        flags = asyncio.run(wb._extract_plot_flags(client, "m", "大纲文本"))
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["key"], "找到矿坑")
        call = client.calls[0]
        self.assertEqual(call["extra_body"], {"thinking": {"type": "disabled"}})

    def test_plot_flag_only_extraction_returns_empty_on_empty_response(self):
        client = FakeClient([FakeStream([_chunk(finish="length")])] * 3)
        buf = io.StringIO()
        with redirect_stdout(buf):
            flags = asyncio.run(wb._extract_plot_flags(client, "m", "大纲文本"))
        self.assertEqual(flags, [])


if __name__ == "__main__":
    unittest.main()
