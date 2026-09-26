"""给玩家的规则/世界摘要（旧接口兼容层）：复用通用 runner 产出短结论。

从 `backend/engine/focused_subagents.py` 拆出。
"""
from __future__ import annotations

from typing import Any


# ── 旧接口兼容 ───────────────────────────────────────────────

async def summarize_rules_for_player(
    client: Any,
    model: str,
    query: str,
    retrieved_text: str,
) -> str:
    """规则/战斗模块子 Agent：把检索到的规则片段整理成简洁可执行的规则结论。"""
    from backend.engine.subagent_runners import run_focused_agent

    return await run_focused_agent(
        client, model,
        role="规则整理者",
        task="根据检索到的规则片段，整理玩家本次行动需要的规则结论。",
        context=retrieved_text,
        max_tokens=800,
        temperature=0.1,
    )


async def summarize_world_for_player(
    client: Any,
    model: str,
    query: str,
    world_context: str,
) -> str:
    """场景/社交模块子 Agent：把冗长世界背景压缩为当前场景可用的信息。"""
    from backend.engine.subagent_runners import run_focused_agent

    return await run_focused_agent(
        client, model,
        role="世界背景整理者",
        task=f"根据当前玩家问题「{query}」，从世界背景中提取当前场景最相关的事实。",
        context=world_context,
        max_tokens=700,
        temperature=0.2,
    )
