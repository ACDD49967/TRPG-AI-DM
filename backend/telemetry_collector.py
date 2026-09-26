"""单会话观测采集器：回合、阶段耗时、模型调用与 token 归因（从 telemetry.py 拆出）。

只保存时间、阶段、调用次数、token 用量与脱敏错误，不保存 API Key、prompt 或模型正文。
"""
from __future__ import annotations

import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from backend.telemetry_types import ModelCallMetric, TurnMetric


class TelemetryCollector:
    """单会话内存统计；由会话 action_lock 保证同一回合写入顺序。"""

    def __init__(self, max_turns: int = 100):
        self.completed_turns: deque[TurnMetric] = deque(maxlen=max_turns)
        self.current: TurnMetric | None = None
        self._phase_started: dict[str, float] = {}
        self.current_phase = ""
        self.total_model_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.total_cache_hit_tokens = 0
        self.total_failures = 0

    def begin_turn(self, turn: int) -> TurnMetric:
        if self.current is not None:
            self.end_turn()
        self.current = TurnMetric(turn=turn, started_at=time.perf_counter())
        self._phase_started.clear()
        self.current_phase = ""
        return self.current

    def end_turn(self) -> TurnMetric | None:
        current = self.current
        if current is None:
            return None
        current.duration_ms = round((time.perf_counter() - current.started_at) * 1000, 2)
        self.completed_turns.append(current)
        self.current = None
        self._phase_started.clear()
        self.current_phase = ""
        return current

    @asynccontextmanager
    async def phase(self, name: str) -> AsyncIterator[None]:
        started = time.perf_counter()
        previous_phase = self.current_phase
        self.current_phase = name
        self._phase_started[name] = started
        try:
            yield
        except Exception as exc:
            self.record_failure(name, exc)
            raise
        finally:
            if self.current is not None:
                elapsed = (time.perf_counter() - started) * 1000
                self.current.phases_ms[name] = round(
                    self.current.phases_ms.get(name, 0.0) + elapsed, 2
                )
            self._phase_started.pop(name, None)
            self.current_phase = previous_phase

    def record_failure(self, phase: str, error: Any) -> None:
        self.total_failures += 1
        if self.current is not None:
            message = f"{type(error).__name__}: {str(error)[:240]}"
            self.current.failures.append(f"{phase}: {message}")

    def record_sizes(self, **values: int) -> None:
        """记录本轮 prompt 各部分字符数；同名取最大值，避免累计失真。"""
        if self.current is None:
            return
        for key, value in values.items():
            try:
                size = int(value)
            except (TypeError, ValueError):
                continue
            if size > self.current.sizes.get(key, 0):
                self.current.sizes[key] = size

    def mark_first_output(self) -> None:
        """记录本回合第一个玩家可见输出（叙事/骰子/战斗结算）的时间。"""
        if self.current is None or self.current.first_output_ms is not None:
            return
        self.current.first_output_ms = round(
            (time.perf_counter() - self.current.started_at) * 1000, 2)

    def begin_phase(self, name: str) -> None:
        self._phase_started[name] = time.perf_counter()
        self.current_phase = name

    def end_phase(self, name: str) -> None:
        started = self._phase_started.pop(name, None)
        if started is not None and self.current is not None:
            elapsed = (time.perf_counter() - started) * 1000
            self.current.phases_ms[name] = round(
                self.current.phases_ms.get(name, 0.0) + elapsed, 2
            )
        if self.current_phase == name:
            self.current_phase = ""

    def record_call(self, metric: ModelCallMetric) -> None:
        self.total_model_calls += 1
        self.total_prompt_tokens += metric.prompt_tokens
        self.total_completion_tokens += metric.completion_tokens
        self.total_tokens += metric.total_tokens
        self.total_cache_hit_tokens += metric.cache_hit_tokens
        if not metric.success:
            self.total_failures += 1
        if self.current is not None:
            self.current.model_calls.append(metric)
            if not metric.success:
                self.current.failures.append(
                    f"{metric.phase}: {metric.error or metric.finish_reason or 'model call failed'}"
                )

    def snapshot(self) -> dict:
        turns = list(self.completed_turns)
        return {
            "totals": {
                "model_calls": self.total_model_calls,
                "prompt_tokens": self.total_prompt_tokens,
                "completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_tokens,
                "cache_hit_tokens": self.total_cache_hit_tokens,
                "failures": self.total_failures,
            },
            "recent_turns": [turn.to_dict() for turn in turns],
            "active_turn": self.current.to_dict() if self.current is not None else None,
        }
