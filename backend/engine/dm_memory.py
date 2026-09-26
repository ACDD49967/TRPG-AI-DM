"""会话记忆压缩：超长对话摘要（COMPRESS_SUMMARY_PROMPT）。

从 backend.engine.dm_agent 拆出。
"""
from __future__ import annotations

import asyncio
from typing import Any

from backend.engine.dm_runtime import _client, _model
from backend.engine.session import GameSessionState
from backend.logging_utils import get_logger





COMPRESS_SUMMARY_PROMPT = """你是 TRPG 记忆压缩器。请把以下对话轮次压缩为不超过300字的中文摘要。

要求：
1. 保留：关键事件、NPC、地点、线索、玩家选择及其后果。
2. 使用第三人称客观语气，不添加解释，不编造内容。
3. 如果已有旧摘要，先自然衔接旧摘要，再补充新事件。
4. 只输出摘要正文，不要标题、不要JSON、不要Markdown代码块。

旧摘要：
{old_summary}

待压缩轮次：
{transcript}
"""





async def compress_memory_if_needed(state: GameSessionState):
    """当活跃对话轮数超过阈值时，用 LLM 压缩旧轮次为摘要。"""
    mem = state.memory
    if len(mem.turns) <= mem.summary_trigger:
        return
    overflow = len(mem.turns) - mem.max_active_turns
    if overflow <= 0:
        return

    old_turns = mem.turns[:overflow]
    transcript = "\n".join(
        f"玩家: {t.player_input}\nDM: {t.dm_response[:300]}" for t in old_turns
    )
    try:
        client = _client(state)
        model = _model(state)
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": COMPRESS_SUMMARY_PROMPT.format(old_summary=mem.summary or "无", transcript=transcript[:4000]),
                }],
                max_tokens=800,
                temperature=0.3,
            ),
            timeout=60,
        )
        summary = (resp.choices[0].message.content or "").strip()
        if summary:
            mem.summary = summary[:1200]
            mem.turns = mem.turns[overflow:]
            return
    except Exception as e:
        from backend.logging_utils import get_logger
        get_logger("dm_agent.memory").warning("LLM摘要失败，使用提取式摘要: %s", e)
    mem._maybe_summarise()
