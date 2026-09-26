"""OpenAI 客户端代理：把 chat.completions 的调用与流式用量接进采集器（从 telemetry.py 拆出）。

只代理 chat.completions.create，其余客户端能力原样透传；流式响应按 chunk 取最大用量，
结束时补一条完整 metric（成功/失败都记）。
"""
from __future__ import annotations

import time
from typing import Any

from backend.telemetry_collector import TelemetryCollector
from backend.telemetry_types import (
    ModelCallMetric, _cache_usage, _finish_reason, _usage, _value,
)


class _CompletionsProxy:
    def __init__(self, completions: Any, telemetry: TelemetryCollector, phase_getter):
        self._completions = completions
        self._telemetry = telemetry
        self._phase_getter = phase_getter

    async def create(self, *args, **kwargs):
        phase = self._phase_getter() or "llm"
        model = str(kwargs.get("model") or "")
        streamed = bool(kwargs.get("stream"))
        started = time.perf_counter()
        try:
            response = await self._completions.create(*args, **kwargs)
            if streamed:
                return _StreamProxy(response, self._telemetry, phase, model, started)
            prompt, completion, total = _usage(response)
            hit, miss = _cache_usage(response)
            self._telemetry.record_call(ModelCallMetric(
                phase=phase, model=model, duration_ms=round((time.perf_counter() - started) * 1000, 2),
                prompt_tokens=prompt, completion_tokens=completion, total_tokens=total,
                cache_hit_tokens=hit, cache_miss_tokens=miss,
                success=True, finish_reason=_finish_reason(response),
            ))
            return response
        except Exception as exc:
            self._telemetry.record_call(ModelCallMetric(
                phase=phase, model=model, duration_ms=round((time.perf_counter() - started) * 1000, 2),
                success=False, error=f"{type(exc).__name__}: {str(exc)[:240]}",
            ))
            raise


class _ChatProxy:
    def __init__(self, chat: Any, telemetry: TelemetryCollector, phase_getter):
        self.completions = _CompletionsProxy(chat.completions, telemetry, phase_getter)


class InstrumentedAsyncOpenAI:
    """只代理 chat.completions.create，其余客户端能力保持原样。"""

    def __init__(self, client: Any, telemetry: TelemetryCollector, phase_getter):
        self._client = client
        self.chat = _ChatProxy(client.chat, telemetry, phase_getter)

    def __getattr__(self, name: str):
        return getattr(self._client, name)


class _StreamProxy:
    def __init__(self, stream: Any, telemetry: TelemetryCollector, phase: str, model: str, started: float):
        self._stream = stream
        self._telemetry = telemetry
        self._phase = phase
        self._model = model
        self._started = started
        self._prompt = self._completion = self._total = 0
        self._finish = ""
        self._done = False

    def __aiter__(self):
        return self

    async def close(self) -> None:
        self._finish_metric(True)
        close = getattr(self._stream, "close", None)
        if close is not None:
            await close()

    def __getattr__(self, name: str):
        return getattr(self._stream, name)

    async def __anext__(self):
        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            self._finish_metric(True)
            raise
        except Exception as exc:
            self._finish_metric(False, exc)
            raise
        prompt, completion, total = _usage(chunk)
        hit, miss = _cache_usage(chunk)
        self._prompt = max(self._prompt, prompt)
        self._completion = max(self._completion, completion)
        self._total = max(self._total, total)
        self._cache_hit = max(getattr(self, "_cache_hit", 0), hit)
        self._cache_miss = max(getattr(self, "_cache_miss", 0), miss)
        choices = _value(chunk, "choices", []) or []
        if choices:
            self._finish = str(_value(choices[-1], "finish_reason", "") or self._finish)
        return chunk

    def _finish_metric(self, success: bool, error: Exception | None = None):
        if self._done:
            return
        self._done = True
        self._telemetry.record_call(ModelCallMetric(
            phase=self._phase, model=self._model,
            duration_ms=round((time.perf_counter() - self._started) * 1000, 2),
            prompt_tokens=self._prompt, completion_tokens=self._completion,
            total_tokens=self._total or self._prompt + self._completion,
            cache_hit_tokens=getattr(self, "_cache_hit", 0),
            cache_miss_tokens=getattr(self, "_cache_miss", 0),
            success=success, streamed=True, finish_reason=self._finish,
            error=(f"{type(error).__name__}: {str(error)[:240]}" if error else ""),
        ))
