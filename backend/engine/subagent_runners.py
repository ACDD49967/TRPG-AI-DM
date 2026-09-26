"""通用子 Agent runner：单次聚焦调用与并发调用（不涉及工具白名单）。

从 `backend/engine/focused_subagents.py` 拆出；带工具的 runner 仍在那边
（`run_tool_subagent` 是测试的打桩点，必须留在原模块）。
"""
from __future__ import annotations

import asyncio
from typing import Any

from backend.engine.prompt_guard import sanitize_user_text


def _compact_prompt(role: str, task: str, context: str, output_hint: str = "只输出结论，不要解释过程。") -> str:
    return (
        f"你是子Agent，角色：{role}。\n"
        f"任务：{task}\n"
        f"可用上下文：\n{context}\n\n"
        f"输出要求：{output_hint}\n"
        "不要输出 Markdown 代码块，不要输出与任务无关的内容，不要输出隐藏信息给玩家——仅供主DM决策。"
    )


async def run_focused_agent(
    client: Any,
    model: str,
    role: str,
    task: str,
    context: str,
    max_tokens: int = 600,
    temperature: float = 0.2,
    timeout: float = 40,
) -> str:
    """调用一个专注 LLM 子 Agent，返回精简结论。"""
    content = _compact_prompt(role, task, sanitize_user_text(context)[:10000])
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是高效、克制、只输出事实与结论的专业子Agent。不要即兴创作，不要写叙事正文，不要输出隐藏信息给玩家。"},
                    {"role": "user", "content": content},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                extra_body={"thinking": {"type": "disabled"}},
            ),
            timeout=timeout,
        )
        msg = resp.choices[0].message
        return (msg.content or getattr(msg, "reasoning_content", "") or "").strip()
    except Exception as e:
        return f"[子Agent失败] {type(e).__name__}: {e}"


async def run_parallel_subagents(
    client: Any,
    model: str,
    tasks: list[dict],
    timeout: float = 30,
) -> dict[str, str]:
    """并发运行多个专业子 Agent。

    - 单个 Agent 失败/超时只丢弃该 Agent 的结果，不阻塞主流程；
    - 所有 Agent 共享同一超时窗口，总耗时约等于最慢的一个 Agent；
    - 结果按 task["key"] 返回，供 format_dm_brief() 聚合。
    """
    async def _one(task: dict) -> tuple[str, str]:
        key = str(task.get("key", ""))
        try:
            result = await run_focused_agent(
                client,
                model,
                role=str(task.get("role", "专业子Agent")),
                task=str(task.get("task", "")),
                context=str(task.get("context", "")),
                max_tokens=int(task.get("max_tokens", 500)),
                temperature=float(task.get("temperature", 0.2)),
                timeout=float(task.get("timeout", timeout)),
            )
        except Exception as e:  # pragma: no cover - 保险
            return key, f"[子Agent失败] {type(e).__name__}: {e}"
        return key, result

    try:
        raw = await asyncio.gather(*(_one(t) for t in tasks), return_exceptions=True)
    except asyncio.CancelledError:
        return {}
    out: dict[str, str] = {}
    for item in raw:
        if isinstance(item, tuple) and len(item) == 2:
            key, value = item
            out[str(key)] = str(value or "")
        elif isinstance(item, Exception):
            continue
    return out


# ── 可调用工具的子 Agent（DeepSeek harness 风格）────────────────
