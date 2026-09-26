"""LLM 调用与回合的观测数据类型（从 telemetry.py 拆出）。

包含响应解析助手（usage / 缓存命中 / finish_reason）与两个 dataclass；
采集器在 telemetry_collector，OpenAI 代理在 telemetry_openai。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _usage(response: Any) -> tuple[int, int, int]:
    usage = _value(response, "usage")
    prompt = int(_value(usage, "prompt_tokens", 0) or 0)
    completion = int(_value(usage, "completion_tokens", 0) or 0)
    total = int(_value(usage, "total_tokens", prompt + completion) or 0)
    return prompt, completion, total


def _cache_usage(response: Any) -> tuple[int, int]:
    """上下文缓存命中/未命中 token。

    DeepSeek 返回 prompt_cache_hit_tokens / prompt_cache_miss_tokens；
    OpenAI 放在 prompt_tokens_details.cached_tokens 里。缓存命中的输入通常只按 10% 计费，
    不采集这一项会把成本高估近一个数量级。
    """
    usage = _value(response, "usage")
    if usage is None:
        return 0, 0
    hit = int(_value(usage, "prompt_cache_hit_tokens", 0) or 0)
    miss = int(_value(usage, "prompt_cache_miss_tokens", 0) or 0)
    if hit == 0:
        details = _value(usage, "prompt_tokens_details")
        hit = int(_value(details, "cached_tokens", 0) or 0)
    if hit == 0 and miss == 0:
        return 0, 0
    prompt = int(_value(usage, "prompt_tokens", 0) or 0)
    if miss == 0 and prompt:
        miss = max(0, prompt - hit)
    return hit, miss


def _finish_reason(response: Any) -> str:
    choices = _value(response, "choices", []) or []
    if not choices:
        return ""
    return str(_value(choices[0], "finish_reason", "") or "")


@dataclass
class ModelCallMetric:
    phase: str
    model: str
    duration_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    success: bool = False
    streamed: bool = False
    finish_reason: str = ""
    error: str = ""


@dataclass
class TurnMetric:
    turn: int
    started_at: float
    duration_ms: float = 0.0
    first_output_ms: float | None = None   # 玩家看到第一段内容的时间（真实等待感）
    phases_ms: dict[str, float] = field(default_factory=dict)
    model_calls: list[ModelCallMetric] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    # prompt 体积归因（字符数）：用于定位 token 花在哪一块
    sizes: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
